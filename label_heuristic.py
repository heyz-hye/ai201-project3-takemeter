#!/usr/bin/env python3
"""
label_heuristic.py — Apply rule-based pre-labels to collected posts.

Runs WITHOUT any API key. Labels are approximate — you MUST review
and correct them in a spreadsheet before using for training.

Usage:
    python3 label_heuristic.py
"""

import json, re, sys
import pandas as pd

# ── Heuristic label rules ─────────────────────────────────────────────────
# Each rule returns True if it fires. Rules are checked in priority order:
# hype first, then analysis, then opinion as the default.

HYPE_PATTERNS = [
    # achievement / milestone
    r"\b(just\s+)?(hit|reached|got|made it to|finally|achieved)\b.{0,60}\b(challenger|grandmaster|master|diamond|platinum|plat|gold|silver|bronze|iron|emerald|rank[12]|promo|promotion)\b",
    r"\b(i made it|got promoted|just hit|finally hit|hit my peak|season high)\b",
    # emotional reaction to an event
    r"\b(oh\s+my\s+(god|lord)|i\s+can'?t\s+breathe|this\s+is\s+insane|what\s+just\s+happened|holy\s+(shit|crap|moly))\b",
    r"(!{2,}|\?{2,})",  # multiple !! or ??
    # esports reaction
    r"\b(just\s+watched|best\s+play|insane\s+play|clip|montage|highlight)\b",
    r"\b(win streak|lose streak|winning streak|losing streak)\b",
    r"\bfirst\s+time\s+(hitting|reaching|getting|winning)\b",
    r"\b(crying|tearing up|i'?m\s+shaking|can'?t\s+believe\s+i)\b",
    r"\b(pog|poggers|pogchamp|lets\s+go|letsgo|gg\s+ez|ez\s+game)\b",
]

# Checked on ORIGINAL (non-lowercased) text for case sensitivity
HYPE_CASE_PATTERNS = [
    r"[A-Z]{5,}",  # ALL CAPS word — must check on original text
]

ANALYSIS_PATTERNS = [
    # stats
    r"\b\d+\.?\d*\s*%\s*(win\s*rate|pick\s*rate|ban\s*rate|presence)\b",
    r"\bwin\s*rate\s*(of|is|was|climbed|dropped|at)\s+\d",
    r"\b(patch|update)\s+\d+\.\d+\b",
    # structured reasoning
    r"\b(the\s+reason\s+(is|why|for|that)|because\s+of|this\s+is\s+because|as\s+a\s+result|therefore|however|whereas)\b",
    r"\b(tier\s+list|meta\s+analysis|breakdown|deep\s+dive|analysis|explained|guide)\b",
    r"\b(statistics|mathematically|objectively|data|numbers|sample\s+size)\b",
    r"\b(compared\s+to|relative\s+to|in\s+contrast|on\s+the\s+other\s+hand)\b",
    r"\b(nerf|buff|rework)\b.{0,80}\b(because|due\s+to|as\s+a\s+result|means\s+that|results\s+in)\b",
    r"\b(cs|creep\s+score|gold\s+differential|damage\s+per\s+second|dps)\b.{0,30}\b\d+",
    r"\b(first\s+clear|jungle\s+path|rotation|wave\s+management|macro)\b",
]

OPINION_PATTERNS = [
    r"\b(i\s+think|i\s+believe|in\s+my\s+opinion|imo|imho|personally|i\s+feel\s+(like|that))\b",
    r"\b(should\s+(be|have|get)|needs?\s+to\s+be|needs?\s+a\s+rework|is\s+broken|is\s+too\s+(strong|weak|op|broken))\b",
    r"\b(unpopular\s+opinion|hot\s+take|change\s+my\s+mind|am\s+i\s+the\s+only\s+one|does\s+anyone\s+else)\b",
    r"\b(favorite|least\s+favorite|worst|best\s+(?!play|game\s+ever))\b",
    r"\b(riot\s+(should|needs|has\s+to|please)|dear\s+riot|open\s+letter)\b",
    r"\b(why\s+is\s+\w+\s+(so|still)|why\s+does\s+riot|why\s+can'?t\s+riot)\b",
]


def heuristic_label(text: str) -> tuple[str, str]:
    """Return (label, reason) for a post text."""
    t = text.lower()

    # Check hype first (most distinctive)
    # Case-sensitive patterns run on original text
    for pat in HYPE_CASE_PATTERNS:
        m = re.search(pat, text)  # no IGNORECASE — must be real caps
        if m:
            return "hype", f"hype pattern (caps): {m.group()[:20]}"
    # Case-insensitive patterns run on lowercased text
    for pat in HYPE_PATTERNS:
        m = re.search(pat, t)
        if m:
            return "hype", f"hype pattern: {pat[:40]}"

    # Check analysis (stats OR reasoning structure → 1 strong hit is enough)
    analysis_hits = sum(1 for pat in ANALYSIS_PATTERNS if re.search(pat, t, re.IGNORECASE))
    if analysis_hits >= 1:
        return "analysis", f"analysis patterns: {analysis_hits} hits"

    # Check opinion
    for pat in OPINION_PATTERNS:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            return "opinion", f"opinion pattern: {pat[:40]}"

    # Single analysis signal — could go either way, flag for review
    if analysis_hits == 1:
        return "REVIEW", "1 analysis signal — borderline, check manually"

    # Default: short posts with no clear signal → opinion or hype, needs human
    if len(text) < 120:
        return "REVIEW", "short post, no clear signal"

    return "opinion", "default (medium-length, no strong pattern)"


def main():
    # Load from temp JSON if it exists, else from existing CSV
    try:
        with open("/tmp/lol_posts3.json") as f:
            posts = json.load(f)
        # Deduplicate by text content
        seen_texts: set[str] = set()
        unique_posts = []
        for p in posts:
            key = (p.get("text", "") or "")[:120]
            if key not in seen_texts:
                seen_texts.add(key)
                unique_posts.append(p)
        print(f"Loaded {len(posts)} posts → {len(unique_posts)} after deduplication.")
        posts = unique_posts
    except FileNotFoundError:
        try:
            df = pd.read_csv("dataset_prelabeled.csv")
            posts = df.to_dict("records")
            print(f"Loaded {len(posts)} posts from existing CSV.")
        except FileNotFoundError:
            print("No posts found. Run collect_data.py first.")
            sys.exit(1)

    labeled = []
    counts = {"analysis": 0, "opinion": 0, "hype": 0, "REVIEW": 0}

    for post in posts:
        text = post.get("text", "")
        label, reason = heuristic_label(text)
        counts[label] = counts.get(label, 0) + 1
        labeled.append({
            "text": text,
            "label": label,
            "ai_labeled": False,
            "label_reason": reason,
            "permalink": post.get("permalink", ""),
            "sort": post.get("sort", ""),
        })

    df = pd.DataFrame(labeled)
    total = len(df)

    print(f"\nHeuristic label distribution ({total} posts):")
    for lbl in ("analysis", "opinion", "hype", "REVIEW"):
        n = counts.get(lbl, 0)
        pct = n / total * 100
        flag = "  ⚠️" if lbl != "REVIEW" and pct > 70 else ""
        print(f"  {lbl:<12} {n:>4}  ({pct:.0f}%){flag}")

    out = "dataset_prelabeled.csv"
    df.to_csv(out, index=False)
    print(f"\n✅ Saved {total} rows → {out}")
    print("""
IMPORTANT — these labels are heuristic guesses, not ground truth.
Open dataset_prelabeled.csv in a spreadsheet and:
  1. Read every post
  2. Fix wrong labels (especially REVIEW rows — assign a label manually)
  3. The 'label_reason' column explains why the heuristic chose each label
  4. Once done, delete all columns except 'text' and 'label', save as dataset.csv
""")


if __name__ == "__main__":
    main()
