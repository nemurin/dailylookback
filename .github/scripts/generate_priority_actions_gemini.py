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
    diary_short = shrink(diary_text, 2500)
    schedule_short = shrink(schedule_text, 1000)

    prompt = textwrap.dedent(f"""
    あなたは優秀で伴走型のパーソナルコーチです。
    提供された「直近の日記」と「基本スケジュール」の内容を分析し、今日（日本時間）取り組むべき優先アクション上位 {n} 件を提案してください。

    ### 直近の日記
    {diary_short}

    ### DailySchedule (基本スケジュール)
    {schedule_short}

    ### 出力要件
    1. **本日のワンポイントメッセージ**: 昨日の振り返りから見えた課題やポジティブな側面に触れる一言（2〜3文）。
    2. **優先アクション（上位 {n} 件）**: 各アクションについて、以下の要素を含めた読みやすいフォーマットで記述してください。
       - タイトル（絵文字 + 明確な行動）
       - 理由（なぜ今やるべきか・日記のどの課題に対応しているか）
       - 具体的な手順 / 実行のコツ（すぐ着手できるレベルまで分解）
       - 見込み時間（例: 5分, 15分）
    3. 全体的に前向きで、すぐ行動に移したくなるトーンにしてください。
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
