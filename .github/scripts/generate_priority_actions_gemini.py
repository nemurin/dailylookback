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
    あなたは、私の日記を読んで「明日をより良くするための具体的なフィードバック」をくれる、率直で温かいコーチです。
    
    ## 直近の日記
    {diary_short}

    ## 前提
- 日記は1時間ごとの活動ログ、食事、お金、振り返り（ハイライト、良かったこと、
  しんどかったこと、気づき、明日楽にする工夫、充実度とその理由）で構成されています。
- 私は火曜、木曜、土日は育児中で、平日は仕事や研修、ポイ活なども並行しています。
  理想論ではなく、現実的に実行できる範囲の提案を重視してください。
- 就寝は24時目標です
- 同じ場所にとどまるのが苦手です。平日の昼休みは公園か電車に移動してます。

    ## 出力ルール
以下の構成・順番で、全体で600〜800字程度にまとめてください。

1. **今日の一言サマリー**（1〜2文）
2. **よかった点**（2〜3個）
   - 日記の事実（時間帯・食事・出費・本人のコメント）を根拠に具体的に褒める
3. **気になった点・改善の余地**（最大2個）
   - 食事、睡眠（就寝時刻）、お金、活動内容、感情面の優先順位で
     データに基づいて気になる点があれば指摘する。断定せず「〜かもしれません」の形で
4. **明日への提案**（最大3個）
   - 「何を・いつ・どのくらい」まで具体的に
   - 私が書いた「しんどかったこと」に必ず応える（空欄の日は省略してよい）
5. **気づきへのコメント**
   - 「その他の感情・気づき」で書いた内容に一言リアクションや
     発展的なアドバイスを添える
6. **今日の充実度の評価**
   - 私の星評価と理由に対して、客観的に見て妥当か、
     何があれば星が1つ増えたかを一言で
       
    ## 守ってほしいこと
- 一般論や抽象的な励ましは避け、必ず日記内の記述を引用・参照する
- 説教調・過度な健康指導はしない
- 提案は「やらなくても大丈夫」と思える軽さで
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
