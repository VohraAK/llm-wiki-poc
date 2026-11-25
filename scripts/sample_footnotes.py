"""Sample 10 footnoted sentences from the wiki bundle with the cited page text, for manual spot-check.

    uv run python scripts/sample_footnotes.py > runs/footnote_check.md
"""
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common.load_pdfs import read_markdown_pages  # noqa: E402

cands = []
for p in sorted((ROOT / "wiki/bundle/topics").glob("*.md")):
    if p.name == "index.md":
        continue
    for para in p.read_text().split("\n"):
        if para.startswith("[^"):
            continue
        for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z])", para):
            m = re.findall(r"\[\^([a-z]+\d{4})-p(\d+)\]", sent)
            if len(m) == 1:
                cands.append((p.name, sent.strip(), m[0][0], int(m[0][1])))
import yaml
dom = {x["id"]: x["domain"] for x in yaml.safe_load((ROOT / "data/papers.yaml").read_text())["papers"]}
random.Random(0).shuffle(cands)
# 5 per domain so ethics pages are covered
pick = [c for d in ("climate-science", "ai-ethics-law") for c in [x for x in cands if dom[x[2]] == d][:5]]
cache = {}
for i, (page, sent, pid, n) in enumerate(pick, 1):
    pages = cache.setdefault(pid, dict(read_markdown_pages(pid)))
    print(f"## {i}. topics/{page} -> {pid} p.{n}\n\n**Claim:** {sent}\n\n**Page text:**\n\n{pages.get(n, 'PAGE MISSING')}\n\n---\n")
