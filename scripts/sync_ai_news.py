#!/usr/bin/env python3
"""Sync the latest AI news digest into the personal website.

Reads the newest ai-news-YYYY-MM-DD.md from the digest folder produced by the
Goose recipe `daily_ai_news_digest`, converts the top stories into
news/latest.json (the format index.html expects), and commits + pushes to
GitHub Pages.
"""
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DIGEST_DIR = Path("/Users/alishahed/Documents/ai-news-digests")
REPO = Path("/Users/alishahed/Projects/alishahed.github.io")
OUT = REPO / "news" / "latest.json"
MAX_SUMMARY = 300
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
    latest = files[-1]
    text = latest.read_text(encoding="utf-8")
    m = re.search(r"(\d{4}-\d{2}-\d{2})", latest.name)
    date = m.group(1) if m else datetime.now().strftime("%Y-%m-%d")

    items = parse_top_stories(text)
    if not items:
        sys.exit(f"could not parse top stories from {latest}")
    for it in items:
        it["date"] = date
    payload = {"updated": date, "items": items}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    new_json = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    changed = not OUT.exists() or OUT.read_text(encoding="utf-8") != new_json
    OUT.write_text(new_json, encoding="utf-8")
    print(f"Synced {len(items)} stories from {latest.name} -> {OUT.relative_to(REPO)} (changed={changed})")
    if not changed:
        return

    def git(*args):
        subprocess.run(["git", *args], cwd=REPO, check=True,
                       capture_output=True, text=True)

    git("add", "news/latest.json")
    git("commit", "-m", f"Update Daily AI News ({date})")
    git("push")
    print("Committed and pushed to GitHub.")


if __name__ == "__main__":
    main()
