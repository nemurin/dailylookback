#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate priority actions using Google Generative AI (Gemini).
Writes diary/YYYY-MM-DD-actions.md

Required env vars (set in Actions):
- GEMINI_API_KEY: your Google AI API key (from secrets)
- GEMINI_MODEL: model name (e.g. "gemini-1.5-flash"), optional
- TZ: timezone (e.g. "Asia/Tokyo")
"""
import os
import glob
import datetime
from zoneinfo import ZoneInfo
import textwrap

# Google Generative AI client
import google.generativeai as genai

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
    # トークン節約のため長文は短縮する（末尾優先）
    def shrink(s, max_chars):
        return s if len(s) <= max_chars else s[-max_chars:]
    diary_short = shrink(diary_text, 2500)
    schedule_short = shrink(schedule_text, 1000)
    prompt = textwrap.dedent(f"""
    あなたは役に立つアシスタントです。以下を読み、今日（日本時間）の優先アクション上位 {n} 件を短い日本語のMarkdown箇条書きで出してください。
    各行は「- アクション：理由（所要時間）」の形式にしてください。余計な説明は不要です。

    昨日の日記:
    {diary_short}

    DailySchedule:
    {schedule_short}

    出力ルール:
    - 箇条書きのみ（各行は - で始める）
    - 各項目は「アクション：理由（所要時間）」の形式
    - 実行しやすさ（短時間で終わる）を優先する
    """).strip()
    return prompt


def call_gemini(prompt, model_name, api_key, temperature=0.2, max_output_tokens=400):
    # Google Generative AI の API を初期化
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
    )
    return response.text if hasattr(response, "text") else str(response)


def sanitize_and_ensure_md(text):
    lines = [l for l in text.splitlines() if l.strip()]
    if not any(l.strip().startswith("-") for l in lines):
        # 箇条書きでないなら分割して付与
        lines = ["- " + l.strip() for l in lines if l.strip()]
    return "\n".join(lines)


def write_output(out_path, source_path, llm_text):
    today = jst_today().isoformat()
    lines = []
    lines.append(f"# Priority actions for {today}")
    lines.append("")
    lines.append(f"_Generated from {os.path.basename(source_path)} (via Gemini)_")
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
    md = sanitize_and_ensure_md(out)
    today = jst_today().isoformat()
    out_path = os.path.join(DIARY_DIR, f"{today}{OUTPUT_SUFFIX}")
    write_output(out_path, y_path, md)


if __name__ == "__main__":
    main()
