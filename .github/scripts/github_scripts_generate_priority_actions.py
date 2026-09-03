#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate a small markdown file with prioritized actions based on yesterday's diary
and the DailySchedule template.
Writes diary/YYYY-MM-DD-actions.md
"""
import os
import glob
import datetime
import re
from zoneinfo import ZoneInfo

DIARY_DIR = "diary"
OUTPUT_SUFFIX = "-actions.md"
TZ = ZoneInfo("Asia/Tokyo")
DAILYSCHEDULE_PATH = "DailySchedule"
PRIORITY_COUNT = 3

KEYWORDS_HIGH = [
    "振込", "振込先", "育休", "育児", "義母", "重要", "締切", "期限", "TODO", "やる", "やります", "対応", "必須"
]

TIME_BLOCK_KEYWORDS = ["授乳", "授乳対応", "寝かしつけ", "夜泣"]

def jst_today():
    return datetime.datetime.now(TZ).date()

def find_yesterday_file():
    yesterday = jst_today() - datetime.timedelta(days=1)
    patterns = [
        yesterday.isoformat(),            # YYYY-MM-DD
        yesterday.strftime("%Y%m%d"),     # YYYYMMDD
    ]
    exts = ["", ".md", ".mdx", ".txt"]
    for pfx in patterns:
        for ext in exts:
            p = os.path.join(DIARY_DIR, f"{pfx}{ext}")
            if os.path.exists(p):
                return p
    # fallback: any most recently modified file in diary/
    all_files = [c for c in glob.glob(os.path.join(DIARY_DIR, "*")) if os.path.isfile(c)]
    if not all_files:
        return None
    return max(all_files, key=os.path.getmtime)

def read_daily_schedule():
    if not os.path.exists(DAILYSCHEDULE_PATH):
        return ""
    with open(DAILYSCHEDULE_PATH, "r", encoding="utf-8") as f:
        return f.read()

def detect_time_block_conflicts(schedule_text):
    # Count occurrences of child-care related blocks (授乳 etc.)
    counts = 0
    lines = schedule_text.splitlines()
    for ln in lines:
        for kw in TIME_BLOCK_KEYWORDS:
            if kw in ln:
                counts += 1
    return counts

def extract_candidates(text):
    lines = text.splitlines()
    candidates = []
    # try section-based extraction first
    sec_headers = ["【明日の予定", "【明日の予定・申し送り事項", "【行動", "【子供対応", "【明日やめること", "【明日の予定・申し送り事項】"]
    in_section = None
    for i, ln in enumerate(lines):
        s = ln.strip()
        # detect headers
        for h in sec_headers:
            if s.startswith(h):
                in_section = h
                continue
        # extract checklist/TODO/bullets
        if re.match(r"^- \[.\]", s) or "TODO" in s or s.startswith("- ") or s.startswith("・"):
            candidates.append(("bullet", s, i))
            continue
        # extract time-action lines like "8:30-9:00\tAI ..."
        if re.match(r"^\d{1,2}:\d{2}", s) or re.match(r"^\d{6,8}", s) or "\t" in ln:
            # take the action portion
            parts = re.split(r"\t|　", ln)
            if len(parts) >= 2:
                action = parts[-1].strip()
                if action:
                    candidates.append(("timed", action, i))
                    continue
        # if inside certain section, take non-empty lines as candidates
        if in_section and s and not s.startswith("【") and not s.startswith("相違理由"):
            candidates.append((f"section:{in_section}", s, i))
    # fallback: take first paragraphs
    if not candidates:
        paras = [p.strip() for p in text.split("\n\n") if p.strip()]
        for idx, p in enumerate(paras[:5]):
            first = p.splitlines()[0].strip()
            candidates.append(("para", first, idx))
    # dedupe preserving order
    seen = set()
    dedup = []
    for typ, val, idx in candidates:
        key = val.strip()
        if key and key not in seen:
            dedup.append((typ, key, idx))
            seen.add(key)
    return dedup

def score_candidate(text):
    score = 0
    t = text.lower()
    # keyword boosting
    for kw in KEYWORDS_HIGH:
        if kw.lower() in t:
            score += 5
    # shorter actionable lines slightly higher
    if len(text) < 80:
        score += 1
    # presence of numbers / times may indicate scheduleable tasks
    if re.search(r"\d{1,2}[:時]\d{0,2}", text):
        score += 1
    return score

def generate_priority_list(candidates, schedule_text, n=PRIORITY_COUNT):
    scored = []
    for typ, val, idx in candidates:
        s = score_candidate(val) + max(0, 100 - idx) * 0.0  # keep original order if tie
        scored.append((s, idx, val))
    # sort by score desc, index asc
    scored.sort(key=lambda x: (-x[0], x[1]))
    top = scored[:n]
    # format as list of dicts
    return [{"action": v, "score": int(s)} for s, i, v in top]

def write_md(out_path, source_path, priority_items, schedule_text):
    today = jst_today().isoformat()
    lines = []
    lines.append(f"# Priority actions for {today}")
    lines.append("")
    lines.append(f"_Generated from {os.path.basename(source_path)}_")
    lines.append("")
    if not priority_items:
        lines.append("No action items detected in yesterday's diary.")
        lines.append("")
    else:
        lines.append("優先アクション（上位 {} 件）:\n".format(len(priority_items)))
        for i, it in enumerate(priority_items, 1):
            lines.append(f"{i}. {it['action']}")
            lines.append(f"   - 理由スコア: {it['score']}")
        lines.append("")
    # schedule note: if many授乳 blocks, add short guidance
    care_count = detect_time_block_conflicts(schedule_text)
    if care_count >= 2:
        lines.append("注意: テンプレに授乳等の中断時間が複数含まれています。短時間で完了できる作業を優先してください。")
    lines.append("")
    lines.append("運用メモ:")
    lines.append("- 今日の優先項目は 2〜3 個に絞ると達成しやすいです。")
    lines.append("- 必要なら GitHub Actions の generate script を改良して LLM 要約を組み込むことを検討してください。")
    lines.append("")
    content = "\n".join(lines)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
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
    candidates = extract_candidates(diary_text)
    priorities = generate_priority_list(candidates, schedule_text, PRIORITY_COUNT)
    today = jst_today().isoformat()
    out_path = os.path.join(DIARY_DIR, f"{today}{OUTPUT_SUFFIX}")
    write_md(out_path, y_path, priorities, schedule_text)

if __name__ == "__main__":
    main()