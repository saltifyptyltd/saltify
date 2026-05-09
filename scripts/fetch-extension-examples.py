#!/usr/bin/env python3
"""
One-shot fetcher: pulls example YAML blocks from each extension module's
official Salt docs page, picks the most useful one (one that actually
shows the state being used), and writes the result to:

    data/salt-states-extension-examples.json

Run once when extension list changes. The file is committed to the repo so
the main build script doesn't need network access.

Usage:
    python3 scripts/fetch-extension-examples.py
"""

import html
import json
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "data" / "salt-states-extension-examples.json"
DOC_URL = "https://docs.saltproject.io/en/3006/ref/states/all/salt.states.{name}.html"

# Pattern matches each <div class="highlight-yaml ..."><div class="highlight"><pre>...</pre> block.
YAML_BLOCK_RE = re.compile(
    r'<div class="highlight-yaml[^"]*"><div class="highlight"><pre>(.*?)</pre>',
    re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")


def strip_html(snippet: str) -> str:
    """Remove all HTML tags + decode entities, return clean text."""
    text = TAG_RE.sub("", snippet)
    text = html.unescape(text)
    return text.strip()


def fetch_examples(name: str) -> list[str]:
    """Fetch docs page for a state module, return up to 2 cleanest YAML snippets."""
    url = DOC_URL.format(name=name)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "saltify-state-map-fetcher"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"  ! {name}: fetch failed — {e}", file=sys.stderr)
        return []

    blocks = [strip_html(m.group(1)) for m in YAML_BLOCK_RE.finditer(body)]
    if not blocks:
        return []

    # Prefer blocks that show the module being used (i.e. mention "<name>.")
    state_pattern = f"{name}."
    preferred = [b for b in blocks if state_pattern in b]
    pool = preferred if preferred else blocks

    # Skip noise — most modules have a "profile" config block as the first example.
    cleaned = []
    for b in pool:
        if len(b) < 8 or len(b) > 2000:
            continue
        cleaned.append(b)
        if len(cleaned) >= 2:
            break
    return cleaned


def load_extension_names() -> list[str]:
    """Parse the EXTENSIONS list out of build-states-json.py."""
    script_path = ROOT / "scripts" / "build-states-json.py"
    src = script_path.read_text()
    # Match tuples like: ("name", "category", [...
    return re.findall(r'\(\s*"([a-z_0-9]+)"\s*,\s*"(?:cloud|containers|monitoring|networking|sysconfig|auth|data|packages|files|salt-meta)"\s*,', src)


def main():
    cache = {}
    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text())
        print(f"Loaded {len(cache)} cached examples from {CACHE_PATH.name}")

    names = load_extension_names()
    seen = set()
    fresh_names = [n for n in names if not (n in seen or seen.add(n))]
    todo = [n for n in fresh_names if n not in cache]
    print(f"Total extensions: {len(fresh_names)}  ({len(todo)} to fetch, {len(fresh_names) - len(todo)} cached)")

    for i, name in enumerate(todo, 1):
        print(f"  [{i}/{len(todo)}] {name}…", end=" ", flush=True)
        examples = fetch_examples(name)
        cache[name] = examples
        print(f"{len(examples)} example(s)")
        time.sleep(0.25)

        # Save every 25 fetches so we don't lose progress on Ctrl+C
        if i % 25 == 0:
            CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False))

    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False))
    have_examples = sum(1 for v in cache.values() if v)
    print(f"\nWrote {CACHE_PATH}")
    print(f"  {len(cache)} entries, {have_examples} with at least one example.")


if __name__ == "__main__":
    main()
