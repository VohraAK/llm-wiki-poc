"""Parse and check [<paper-id>, p.<N>] citations."""
from __future__ import annotations

import re

CITE = re.compile(r"\b([a-z]+\d{4}),\s*p\.\s*(\d+)")


# The model sometimes copies the prompt placeholder: "[<he2023, p.1]", "[<he2023>, p.1]" or "[<he2023, p.1>]".
STRAY_BRACKET = re.compile(r"\[\s*(<?)\s*([a-z]+\d{4})\s*(>?)\s*,\s*p\.\s*(\d+)\s*(>?)\s*\]")


def normalize_citations(answer: str) -> tuple[str, bool]:
    """Strip stray < and > from [<paper-id>, p.<N>] citations. Returns (text, changed)."""
    changed = False

    def fix(m: re.Match) -> str:
        nonlocal changed
        if m.group(1) or m.group(3) or m.group(5):
            changed = True
            return f"[{m.group(2)}, p.{m.group(4)}]"
        return m.group(0)

    return STRAY_BRACKET.sub(fix, answer), changed


def extract_citations(answer: str) -> list[tuple[str, int]]:
    seen, out = set(), []
    for pid, page in CITE.findall(answer):
        key = (pid, int(page))
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def check_citations(answer: str, allowed: set[tuple[str, int]]) -> dict:
    """allowed = (paper_id, page) pairs the system actually showed the model."""
    cites = extract_citations(answer)
    bad = [c for c in cites if c not in allowed]
    return {"citations": cites, "not_in_context": bad}
