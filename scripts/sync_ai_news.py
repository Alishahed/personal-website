#!/usr/bin/env python3
"""Publish the weekly 'Last Week in AI' digest to the personal website.

Run manually on Sundays (e.g.: python3 scripts/sync_ai_news.py).

Reads the daily ai-news-YYYY-MM-DD.md files produced by the Goose recipe
`daily_ai_news_digest`, takes all digests from the 7-day window ending at the
newest available file, merges their Top Stories (deduped by title, newest
occurrence wins, newest first), converts them to news/latest.json (the format
index.html expects), and commits + pushes to GitHub Pages.
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

DIGEST_DIR = Path("/Users/alishahed/Documents/ai-news-digests")
REPO = Path("/Users/alishahed/Projects/alishahed.github.io")
OUT = REPO / "news" / "latest.json"
MAX_SUMMARY = 300
MAX_STORIES = 6
WINDOW_DAYS = 7  # 7-day window ending at the newest digest
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def parse_top_stories(text):
    """Extract stories from the 'Top Stories of the Day' section."""
    items = []
    m = re.search(r"^## Top Stories of the Day\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return items
    block = m.group(1)
    # split into per-story chunks
    chunks = re.split(r"^### \d+\.\s*", block, flags=re.M)[1:]
    for chunk in chunks:
        lines = [l.strip() for l in chunk.splitlines() if l.strip()]
        if not lines:
            continue
        title = re.sub(r"\s+", " ", lines[0])
        body_lines, link_line = [], None
        for l in lines[1:]:
            if link_line is None and l.startswith("-"):
                link_line = l
            elif not l.startswith("-"):
                body_lines.append(l)
        links = LINK_RE.findall(link_line or "")
        summary = " ".join(body_lines)
        summary = re.sub(r"[*_`]", "", summary)
        summary = re.sub(r"\s+", " ", summary).strip()
        if len(summary) > MAX_SUMMARY:
            summary = summary[:MAX_SUMMARY].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
        items.append({
            "title": title,
            "summary": summary,
            "source": links[0][0] if links else "",
            "url": links[0][1] if links else "",
        })
    return items


def main():
    if not DIGEST_DIR.is_dir():
        sys.exit(f"digest dir not found: {DIGEST_DIR}")
    files = sorted(DIGEST_DIR.glob("ai-news-*.md"))
    if not files:
        sys.exit("no digest files found")

    def file_date(f):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", f.name)
        return datetime.strptime(m.group(1), "%Y-%m-%d").date() if m else None

    latest = files[-1]
    latest_date = file_date(latest) or datetime.now().date()
    cutoff = latest_date - timedelta(days=WINDOW_DAYS - 1)

    # collect digests in the window, oldest first
    window = []
    for f in files:
        d = file_date(f)
        if d is not None and cutoff <= d <= latest_date:
            window.append((d, f))

    # merge top stories, dedupe by normalized title (newest occurrence wins)
    seen = {}
    for d, f in window:
        for it in parse_top_stories(f.read_text(encoding="utf-8")):
            key = re.sub(r"[^a-z0-9]+", "", it["title"].lower())
            it["date"] = d.isoformat()
            if key not in seen:
                seen[key] = it

    items = sorted(seen.values(), key=lambda x: x["date"], reverse=True)
    items = items[:MAX_STORIES]
    if not items:
        sys.exit(f"could not parse top stories from digests in {cutoff}..{latest_date}")

    payload = {"updated": latest_date.isoformat(), "items": items}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    new_json = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    changed = not OUT.exists() or OUT.read_text(encoding="utf-8") != new_json
    OUT.write_text(new_json, encoding="utf-8")
    src = ", ".join(f.name for _, f in window)
    print(f"Week ending {latest_date}: {len(items)} stories from {src} -> {OUT.relative_to(REPO)} (changed={changed})")
    if not changed:
        return

    def git(*args):
        subprocess.run(["git", *args], cwd=REPO, check=True,
                       capture_output=True, text=True)

    git("add", "news/latest.json")
    git("commit", "-m", f"Update Last Week in AI (week ending {latest_date.isoformat()})")
    git("push")
    print("Committed and pushed to GitHub.")


if __name__ == "__main__":
    main()
