#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate a small markdown file with prioritized actions using OpenAI.
Writes diary/YYYY-MM-DD-actions.md
Requires OPENAI_API_KEY in env.
"""
import os
import glob
import datetime
import re
from openai import OpenAI
from zoneinfo import ZoneInfo

DIARY_DIR = "diary"
OUTPUT_SUFFIX = "-actions.md"
TZ = ZoneInfo("Asia/Tokyo")
DAILYSCHEDULE_PATH = "DailySchedule"
PRIORITY_COUNT = int(os.getenv("PRIORITY_COUNT", "3"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # 置き換え可

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
    if not os.path.exists(DAILYSCHEDULE_PATH):
        return ""
    with open(DAILYSCHEDULE_PATH, "r", encoding="utf-8") as f:
        return f.read()

def shrink_for_tokens(text, max_chars=3000):
    # トークン節約のため、長文は末尾に近い重要箇所を優先して切り詰め
    if len(text) <= max_chars:
        return text
    # 最後の max_chars を返す
    return text[-max_chars:]

def build_prompt(diary_text, schedule_text, n):
    diary_short = shrink_for_tokens(diary_text, max_chars=2500)
    schedule_short = shrink_for_tokens(schedule_text, max_chars=1000)
    system = (
        "あなたは役に立つアシスタントです。出力は必ず日本語のMarkdown箇条書き形式で返してください。"
        "各行は「- アクション：理由（所要時間）』の形式にしてください。余計な説明は入れないでください。"
    )
    user = f"""以下を読み、今日（日本時間）の優先アクション上位 {n} 件を短く箇条書きで出してください。
昨日の日記（要約または重要点）:
{diary_short}

DailySchedule:
{schedule_short}

出力ルール:
- 箇条書きのみ（- から始まる行）。各行は「アクション：理由（所要時間）」の形式。
- 句読点や余計な説明を付けず、短く分かりやすい文にすること。
- もし重要度が同程度なら、実行しやすさ（所要時間が短い）を優先して上位にする。
"""
    return system, user

def call_openai(system_prompt, user_prompt, model, max_tokens=400, temperature=0.2):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set in environment")
    
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    text = response.choices[0].message.content.strip()
    return text

def sanitize_and_ensure_md(text):
    # 必要なら先頭に # ヘッダを付与し、箇条書きでなければ整形する
    lines = text.splitlines()
    if not lines:
        return "- (No actions returned)"
    # If it doesn't start with '-', try to extract lines starting with '-' or split by newline
    if not any(l.strip().startswith("-") for l in lines):
        # fallback: split by line and prefix
        lines = ["- " + l.strip() for l in lines if l.strip()]
    return "\n".join(lines)

def write_output(out_path, source_path, llm_text):
    today = jst_today().isoformat()
    lines = []
    lines.append(f"# Priority actions for {today}")
    lines.append("")
    lines.append(f"_Generated from {os.path.basename(source_path)} (via OpenAI {OPENAI_MODEL})_")
    lines.append("")
    lines.append(llm_text)
    lines.append("")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("Wrote priority actions to", out_path)

def main():
    if not os.path.isdir(DIARY_DIR):
        print("No diary directory found. Exiting.")
        return
    y_path = find_yesterday_file()
    if not y_path:
        print("No yesterday diary file found. Exiting.")
        return
    with open(y_path, "r", encoding="utf-8") as f:
        diary_text = f.read()
    schedule_text = read_daily_schedule()
    system_prompt, user_prompt = build_prompt(diary_text, schedule_text, PRIORITY_COUNT)
    try:
        llm_out = call_openai(system_prompt, user_prompt, OPENAI_MODEL)
    except Exception as e:
        print("OpenAI call failed:", e)
        return
    llm_out = sanitize_and_ensure_md(llm_out)
    today = jst_today().isoformat()
    out_path = os.path.join(DIARY_DIR, f"{today}{OUTPUT_SUFFIX}")
    write_output(out_path, y_path, llm_out)

if __name__ == "__main__":
    main()
