#!/usr/bin/env python3
# Generates a "today plan" file from yesterday's diary.
# Writes diary/YYYY-MM-DD-plan.md
import os
import glob
import datetime
from zoneinfo import ZoneInfo
import re

DIARY_DIR = "diary"
PLAN_SUFFIX = "-plan.md"
TZ = ZoneInfo("Asia/Tokyo")

def jst_today():
    return datetime.datetime.now(TZ).date()

def find_yesterday_file():
    yesterday = jst_today() - datetime.timedelta(days=1)
    candidates = []
    # try a few common filename patterns (with and without dashes) and with extensions
    patterns = [
        yesterday.isoformat(),                # 'YYYY-MM-DD'
        yesterday.strftime('%Y%m%d'),         # 'YYYYMMDD'
    ]
    exts = ["", ".md", ".mdx", ".txt"]
    for pfx in patterns:
        for ext in exts:
            p = os.path.join(DIARY_DIR, f"{pfx}{ext}")
            if os.path.exists(p):
                return p
    # fallback: most recently modified diary file (any file)
    all_files = [c for c in glob.glob(os.path.join(DIARY_DIR, "*")) if os.path.isfile(c)]
    if not all_files:
        return None
    return max(all_files, key=os.path.getmtime)

def extract_action_items(text):
    lines = text.splitlines()
    items = []
    for ln in lines:
        s = ln.strip()
        # check markdown checklist or TODO markers or lines starting with verbs/verbs-like markers
        if s.startswith("- [ ]") or s.startswith("- [x]") or "TODO" in s or "やる" in s or "やります" in s or s.startswith("- "):
            items.append(s)
        # Japanese common bullet
        if s.startswith("・"):
            items.append(s)
    # de-duplicate and clean
    cleaned = []
    for it in items:
        it = re.sub(r"^- \[.\]\s*", "- ", it)
        it = it.strip()
        if it and it not in cleaned:
            cleaned.append(it)
    return cleaned

def create_plan(yesterday_path, plan_path):
    with open(yesterday_path, "r", encoding="utf-8") as f:
        text = f.read()
    items = extract_action_items(text)
    today = jst_today().isoformat()
    header = f"# Plan for {today}\n\n"
    meta = f"_Generated from {os.path.basename(yesterday_path)}_\n\n"
    if items:
        body = "Based on yesterday's diary, suggested action items:\n\n"
        for it in items[:20]:
            body += f"- {it.lstrip('- ').strip()}\n"
    else:
        # fallback: take first non-empty paragraphs as ideas
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if paragraphs:
            body = "Ideas and notes from yesterday:\n\n"
            for p in paragraphs[:5]:
                # shorten paragraph to first line or 200 chars
                first_line = p.splitlines()[0]
                body += f"- {first_line.strip()[:200]}\n"
        else:
            body = "No content found in yesterday's diary to generate a plan.\n\n"
            body += "- Add your plan here.\n"
    content = header + meta + body + "\n"
    os.makedirs(os.path.dirname(plan_path), exist_ok=True)
    with open(plan_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Wrote plan to {plan_path}")

def main():
    if not os.path.isdir(DIARY_DIR):
        print(f"No diary directory found at {DIARY_DIR}. Exiting.")
        return
    y_path = find_yesterday_file()
    if not y_path:
        print("No diary file found to base plan on. Exiting.")
        return
    today = jst_today().isoformat()
    plan_filename = today + PLAN_SUFFIX
    plan_path = os.path.join(DIARY_DIR, plan_filename)
    create_plan(y_path, plan_path)

if __name__ == "__main__":
    main()
