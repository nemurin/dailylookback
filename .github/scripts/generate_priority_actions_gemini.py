#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate priority actions using Google Generative AI (Gemini).
Writes diary/YYYY-MM-DD-actions.md
"""
import os
import glob
import datetime
import time
from zoneinfo import ZoneInfo
import textwrap

from google import genai

DIARY_DIR = "diary"
OUTPUT_SUFFIX = "-actions.md"
TZ = ZoneInfo(os.getenv("TZ", "Asia/Tokyo"))
PRIORITY_COUNT = int(os.getenv("PRIORITY_COUNT", "3"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")


def jst_today():
    return datetime.datetime.now(TZ).date()


def find_yesterday_file():
    yesterday = jst_today() - datetime.timedelta(days=1)
    patterns = [yesterday.isoformat(), yesterday.strftime("%Y%m%d")]
    exts = ["", ".md", ".mdx", ".txt"]
    for pfx in patterns:
        for ext in exts:
            p = os.path.join(DIARY_DIR, f"{pfx}{ext}")
            if os.path.exists(p):
                return p
    all_files = [c for c in glob.glob(os.path.join(DIARY_DIR, "*")) if os.path.isfile(c)]
    if not all_files:
        return None
    return max(all_files, key=os.path.getmtime)


def read_daily_schedule():
    p = "DailySchedule"
    if not os.path.exists(p):
        return ""
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def build_prompt(diary_text, schedule_text, n):
    def shrink(s, max_chars):
        return s if len(s) <= max_chars else s[-max_chars:]
    diary_short = shrink(diary_text, 2000)
    schedule_short = shrink(schedule_text, 1000)

    prompt = textwrap.dedent(f"""
    あなたは私の人生戦略コーチです。ポーカー的な思考（結果ではなく判断の質を評価する、期待値で考える）で、日々の振り返りを手伝ってください。
    
    ### 直近の日記
    {diary_short}

    ### DailySchedule (基本スケジュール)
    {schedule_short}

    ###  長期的な指針（これらに沿っているかを確認して):
    働かずに暮らせる状態（FIRE）を実現すること。ただし、以下の5項目のバランスを保ちながら進める。
1. 心の健康：ゲーム、読書、フロー状態（回復の時間として確保。効率化の対象外）
2. 体の健康：散歩、エアロバイク
3. お金：投資の自動化、支出削減（桐谷さん的視点）
4. 人との関わり：育児、家族（効率化の対象外）
5. 時間：エンジニアリングによる自動化・効率化（ひろゆき的視点。時間を切り売りしない）
  
    ### 出力要件
    1. **現在地の確認**（2〜3文）
   - 昨日の内容と長期目標を照らし合わせる
   - 停滞を感じていたなら、その理由を「疲れ」「やり方」「目的のズレ」のどれに近いか一言で推測する
   - 結果の良し悪しではなく、判断の質を評価する
2. **優先アクション（上位{n}件）**
   - タイトル（絵文字＋明確な行動）
   - 理由（5項目のどれに効くか／日記のどの課題を解消するか）
   - 手順（5分以内で着手できる最初の一歩まで分解）
   - 見込み時間と、実行に適した時間帯（上記の自由枠から選ぶ）
3. **今日の問い**
   - 一日の終わりに自分に投げかける、深い内省の質問を一つだけ
       
    ### トーン
    前向きで、すぐ動きたくなる言葉で。ただし、改善すべき点は遠慮せず率直に指摘してください。
    """).strip()
    return prompt


def call_gemini(prompt, model_name, api_key, temperature=0.5, max_output_tokens=5000):
    client = genai.Client(api_key=api_key)
    
    # リトライ処理
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={
                    "temperature": temperature,
                    "max_output_tokens": max_output_tokens,
                },
            )
            return response.text
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            print(f"Attempt {attempt + 1} failed ({e}). Retrying in 5 seconds...")
            time.sleep(5)


def write_output(out_path, source_path, llm_text):
    today = jst_today().isoformat()
    lines = []
    lines.append(f"# 🎯 Priority Actions for {today}")
    lines.append("")
    lines.append(f"> _Generated from `{os.path.basename(source_path)}` via Gemini_")
    lines.append("")
    lines.append(llm_text)
    lines.append("")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("Wrote priority actions to", out_path)


def main():
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY not set. Set this env var in workflow secrets.")
        return
    if not os.path.isdir(DIARY_DIR):
        print("No diary directory. Exiting.")
        return
    y_path = find_yesterday_file()
    if not y_path:
        print("No yesterday diary file found. Exiting.")
        return
    with open(y_path, "r", encoding="utf-8") as f:
        diary_text = f.read()
    schedule_text = read_daily_schedule()
    prompt = build_prompt(diary_text, schedule_text, PRIORITY_COUNT)
    try:
        out = call_gemini(prompt, GEMINI_MODEL, GEMINI_API_KEY)
    except Exception as e:
        print("Gemini call failed:", e)
        return
    
    today = jst_today().isoformat()
    out_path = os.path.join(DIARY_DIR, f"{today}{OUTPUT_SUFFIX}")
    write_output(out_path, y_path, out)


if __name__ == "__main__":
    main()
