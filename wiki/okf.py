"""Helpers for the OKF bundle. Python owns frontmatter, footnote definitions, sources,
indexes, log and git. The LLM only supplies title, description and body text."""
from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import yaml

from common.llm import ROOT
from common.load_pdfs import PAPERS_YAML, read_markdown_pages
from wiki.validate import Checker, split_frontmatter

BUNDLE = ROOT / "wiki" / "bundle"
GENERATED_BY = "llm-wiki-poc/qwen3.5-9b"

FOOT = re.compile(r"\[\^([^\]\s]+)\]")
FOOT_DEF = re.compile(r"^\[\^[^\]\s]+\]:.*\n?", re.M)
LABEL = re.compile(r"^([a-z]+\d{4})-p(\d+)$")
LINK = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)\)")


@lru_cache
def papers() -> dict[str, dict]:
    return {p["id"]: p for p in yaml.safe_load(PAPERS_YAML.read_text())["papers"]}


@lru_cache
def paper_pages(pid: str) -> frozenset[int]:
    return frozenset(n for n, _ in read_markdown_pages(pid))


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def valid_label(label: str) -> bool:
    m = LABEL.match(label)
    return bool(m) and m.group(1) in papers() and int(m.group(2)) in paper_pages(m.group(1))


def cite_text(label: str) -> str:
    pid, page = LABEL.match(label).groups()
    return f"{papers()[pid]['short_cite']}, p. {page}"


def label_to_citation(label: str) -> str:
    pid, page = LABEL.match(label).groups()
    return f"[{pid}, p.{page}]"


def strip_defs(body: str) -> str:
    return FOOT_DEF.sub("", body).strip()


def split_llm_output(raw: str, want_title: bool) -> tuple[str | None, str, str]:
    """Parse 'title: ..\\ndescription: ..\\n---\\nbody'. Raises ValueError if malformed."""
    raw = re.sub(r"^\s*```(?:markdown|md)?\s*\n|\n```\s*$", "", raw.strip())
    m = re.match(r"\s*((?:(?:title|description)\s*:.*\n)+)\s*---[ \t]*\n(.*)", raw, re.S | re.I)
    if not m:
        raise ValueError("output is not 'title:/description: lines, ---, body'")
    head = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        head[k.strip().lower()] = v.strip().strip('"')
    if not head.get("description") or (want_title and not head.get("title")):
        raise ValueError("missing description or title")
    body = m.group(2).strip()
    if not body:
        raise ValueError("empty body")
    return head.get("title"), head["description"], body


def finalize_body(body: str) -> tuple[str, list[dict], list[str]]:
    """Strip LLM-written definitions and bad footnote markers; append Python-built definitions.
    Returns (body, frontmatter sources list, dropped labels)."""
    body = strip_defs(body)
    body = re.sub(r"\A\s*# .*\n", "", body)
    order: list[str] = []
    dropped: list[str] = []

    def keep(m: re.Match) -> str:
        label = m.group(1)
        if valid_label(label):
            if label not in order:
                order.append(label)
            return m.group(0)
        dropped.append(label)
        return ""

    body = FOOT.sub(keep, body).strip()
    defs = "\n".join(f"[^{label}]: {cite_text(label)}" for label in order)
    sources = [
        {"id": label, "resource": f"https://doi.org/{papers()[LABEL.match(label).group(1)]['doi']}", "title": cite_text(label)}
        for label in order
    ]
    return body + ("\n\n" + defs if defs else "") + "\n", sources, dropped


def write_page(path: Path, ptype: str, title: str, description: str, body: str) -> list[str]:
    body, sources, dropped = finalize_body(body)
    meta = {"type": ptype, "title": title, "description": description}
    if sources:
        meta["sources"] = sources
    meta["generated"] = {"by": GENERATED_BY, "at": now_iso()}
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=10_000)
    path.write_text(f"---\n{fm}---\n{body}")
    return dropped


def read_page(path: Path) -> tuple[dict, str]:
    state, meta, body, _ = split_frontmatter(path.read_text())
    return (meta if state == "ok" else {}), body.strip()


def strip_broken_links(path: Path) -> int:
    """Turn links whose target is missing into plain text. Returns how many."""
    meta_text = path.read_text()
    n = 0

    def fix(m: re.Match) -> str:
        nonlocal n
        text, target = m.groups()
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
            return m.group(0)
        if (path.parent / target.split("#")[0]).resolve().exists():
            return m.group(0)
        n += 1
        return text

    head, sep, rest = meta_text.partition("\n---\n")  # frontmatter | body
    new_rest = LINK.sub(fix, rest)
    if n:
        path.write_text(head + sep + new_rest)
    return n


def validate(bundle: Path) -> list:
    """Errors and warnings from the OKF validator. AGENTS.md is expected to warn (W120)."""
    c = Checker(bundle.resolve(), datetime.now(timezone.utc))
    c.run()
    return [f for f in c.findings if f.level in ("error", "warning") and f.path != "AGENTS.md"]


def append_log(bundle: Path, bullet: str) -> None:
    log = bundle / "log.md"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = log.read_text().splitlines() if log.exists() else []
    head = f"## {today}"
    if head in lines:
        lines.insert(lines.index(head) + 1, bullet)
    else:
        lines = [head, bullet, ""] + lines
    log.write_text("\n".join(lines).rstrip() + "\n")


def git(bundle: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(bundle), *args], capture_output=True, text=True)


def git_commit(bundle: Path, message: str) -> None:
    if not (bundle / ".git").exists():
        git(bundle, "init", "-b", "main")
    git(bundle, "add", "-A")
    if git(bundle, "diff", "--cached", "--quiet").returncode != 0:
        r = git(bundle, "commit", "-m", message)
        if r.returncode != 0:
            raise RuntimeError(r.stderr)
