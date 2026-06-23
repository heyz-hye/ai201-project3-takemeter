#!/usr/bin/env python3
"""
collect_data.py — Fetch r/leagueoflegends posts via RSS and pre-label with Claude.

No Reddit API credentials needed — uses public RSS feeds.

Usage:
    pip install requests anthropic pandas
    export ANTHROPIC_API_KEY=your_key_here
    python3 collect_data.py

Output:
    dataset_prelabeled.csv  — review and correct every label before training
"""

import os, re, sys, time
import xml.etree.ElementTree as ET
import requests
import pandas as pd
import anthropic

SUBREDDIT = "leagueoflegends"
TARGET = 270
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"}
NS = {"atom": "http://www.w3.org/2005/Atom"}

SYSTEM_PROMPT = """You are classifying posts from r/leagueoflegends into exactly one of three categories.

analysis — The post makes a structured argument about mechanics, balance, meta, or match outcomes, supported by specific verifiable evidence (stats, patch notes, replay observations, or systematic reasoning). Evidence forms a reasoning chain, not just a single stat dropped into a rant.

opinion — The post expresses a personal preference, judgment, or stance. It may reference specific facts or examples, but the core purpose is to assert a viewpoint rather than build a systematic argument. Complaints supported by a few claims still count as opinion.

hype — The post is an immediate emotional reaction (excitement, frustration, celebration, shock) tied to a specific in-game or esports event, with little to no argumentative content. Personal milestone posts (hitting a rank, first win) also count as hype.

Decision rules:
- If removing emotional framing still leaves a complete argument → analysis
- If tied to a specific live moment and the emotion IS the content → hype
- General preferences or frustrations not anchored to a specific event → opinion

Respond with ONLY one word: analysis, opinion, or hype. No explanation."""


def strip_html(html: str) -> str:
    """Remove HTML tags and decode common entities."""
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def extract_post_id(entry_id: str) -> str:
    """Return the Reddit post ID from an Atom entry id field.
    Reddit now stores the ID directly as 't3_xxxxx' in the id element."""
    entry_id = (entry_id or "").strip()
    # Direct format: t3_abc123
    if re.match(r"^t3_[a-z0-9]+$", entry_id):
        return entry_id
    # Fallback: extract from URL path
    m = re.search(r"/comments/([a-z0-9]+)/", entry_id)
    return f"t3_{m.group(1)}" if m else ""


def fetch_rss(sort: str = "", after: str = "") -> list[dict]:
    base = f"https://www.reddit.com/r/{SUBREDDIT}"
    url = f"{base}/{sort}.rss" if sort else f"{base}/.rss"
    params: dict = {"limit": 25}
    if after:
        params["after"] = after

    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=15)
            if r.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"  Rate limited — waiting {wait}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            break
        except requests.HTTPError as e:
            if attempt == 2:
                print(f"  Failed after 3 attempts: {e}")
                return []
    else:
        return []

    root = ET.fromstring(r.content)
    entries = root.findall("atom:entry", NS)
    rows = []
    for entry in entries:
        title_el = entry.find("atom:title", NS)
        content_el = entry.find("atom:content", NS)
        id_el = entry.find("atom:id", NS)
        link_el = entry.find("atom:link", NS)

        title = (title_el.text or "").strip() if title_el is not None else ""
        raw_content = (content_el.text or "") if content_el is not None else ""
        body = strip_html(raw_content)
        entry_id = (id_el.text or "") if id_el is not None else ""
        link = link_el.get("href", "") if link_el is not None else ""
        post_id = extract_post_id(entry_id)

        # Build combined text; prefer body when it adds info beyond the title
        if body and len(body) > len(title) + 20:
            text = f"{title}\n\n{body}"
        else:
            text = title

        text = text.strip()
        if len(text) < 25 or title.lower().startswith(("monday megathread", "weekly", "daily", "patch")):
            continue  # skip megathreads and too-short posts

        rows.append({
            "post_id": post_id,
            "text": text[:1200],
            "permalink": link,
            "sort": sort or "hot",
        })
    return rows


def collect_posts(target: int = TARGET) -> list[dict]:
    seen: set[str] = set()
    all_posts: list[dict] = []

    # Sort types to pull from for variety; each gives different post types
    sorts = [
        ("", 3),          # default hot — 3 pages
        ("top", 3),       # top (month) — 3 pages
        ("new", 4),       # new — 4 pages
        ("rising", 2),    # rising — 2 pages
    ]

    for sort, pages in sorts:
        after = ""
        label = sort or "hot"
        print(f"  [{label}] fetching up to {pages} pages...")
        for page in range(pages):
            rows = fetch_rss(sort, after)
            if not rows:
                break
            new = 0
            for row in rows:
                pid = row["post_id"]
                if pid and pid in seen:
                    continue
                if pid:
                    seen.add(pid)
                all_posts.append(row)
                new += 1
            print(f"    page {page+1}: +{new} posts (total {len(all_posts)})")
            if len(rows) < 25:
                break  # last page
            after = rows[-1]["post_id"]
            time.sleep(2)  # be polite between pages

        if len(all_posts) >= target:
            break
        time.sleep(3)  # pause between sort types

    print(f"\nTotal unique posts collected: {len(all_posts)}")
    return all_posts


def prelabel(text: str, client: anthropic.Anthropic) -> str:
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        raw = msg.content[0].text.strip().lower()
        for label in ("analysis", "opinion", "hype"):
            if label in raw:
                return label
        return "REVIEW"
    except Exception as e:
        print(f"  API error: {e}")
        return "REVIEW"


def main() -> None:
    print(f"Collecting posts from r/{SUBREDDIT} via RSS (no credentials needed)...\n")
    posts = collect_posts()

    if not posts:
        print("No posts collected. Check your internet connection and try again.")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        client = anthropic.Anthropic(api_key=api_key)
        print(f"\nPre-labeling {len(posts)} posts with Claude (claude-haiku-4-5-20251001)...")
        for i, post in enumerate(posts):
            post["label"] = prelabel(post["text"], client)
            post["ai_labeled"] = True
            if (i + 1) % 25 == 0:
                print(f"  {i+1}/{len(posts)} labeled...")
            time.sleep(0.05)
    else:
        print("\nANTHROPIC_API_KEY not set — saving posts without pre-labels.")
        for post in posts:
            post["label"] = ""
            post["ai_labeled"] = False

    cols = ["text", "label", "ai_labeled", "permalink", "sort"]
    df = pd.DataFrame(posts)[[c for c in cols if c in pd.DataFrame(posts).columns]]

    if api_key:
        print("\nPre-label distribution:")
        counts = df["label"].value_counts()
        for lbl, n in counts.items():
            pct = n / len(df) * 100
            flag = "  ⚠️  >70%" if pct > 70 else ""
            print(f"  {lbl:<12} {n:>4}  ({pct:.0f}%){flag}")

    out = "dataset_prelabeled.csv"
    df.to_csv(out, index=False)
    print(f"\n✅ Saved {len(df)} rows → {out}")
    print("""
Next steps:
  1. Open dataset_prelabeled.csv in a spreadsheet editor (Excel, Google Sheets, Numbers)
  2. Read EVERY post and correct any wrong labels — do not skim
  3. Note at least 3 cases that gave you genuine pause (add to planning.md)
  4. Ensure no single label exceeds 70% of the dataset
  5. Once done, export a clean file with only 'text' and 'label' columns as dataset.csv
  6. Upload dataset.csv to Colab when running the notebook
""")


if __name__ == "__main__":
    main()
