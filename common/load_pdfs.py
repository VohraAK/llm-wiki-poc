"""Phase 1: PDFs -> shared per-page text.

Both RAG and the wiki read data/md/<paper-id>.md, so answer differences cannot come
from PDF parsing. One LangChain Document per page (PyMuPDFLoader), page numbers
1-based, reference lists stripped (NOTES.md, decision 3).

    uv run python -m common.load_pdfs
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import tiktoken
import yaml
from langchain_core.documents import Document

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
MD = ROOT / "data" / "md"
PAPERS_YAML = ROOT / "data" / "papers.yaml"
STATS_YAML = ROOT / "data" / "corpus_stats.yaml"

ENC = tiktoken.get_encoding("cl100k_base")  # approximation: Qwen's tokenizer differs

REF_HEADING = re.compile(
    r"^\W*(?:\d+\.?|[IVX]+\.?)?\s*(references|bibliography|literature cited|works cited|reference list)\W*$",
    re.I,
)
# Appendix resuming after a reference list: "Appendix ...", "Supplementary material",
# or a lettered section heading such as "A. Background" (no commas, short).
APPENDIX_HEADING = re.compile(
    r"^\W*(?:(?i:appendix\b.*|supplementary (?:material|information)\b.*)|[A-Z]\.\s+[A-Z][a-z]+(?: [A-Za-z]+){0,3})$"
)


def load_paper_pages(paper: dict) -> list[Document]:
    """One Document per PDF page, metadata page = 1-based."""
    from langchain_community.document_loaders import PyMuPDFLoader

    docs = PyMuPDFLoader(str(RAW / paper["file"])).load()
    for d in docs:
        d.page_content = d.page_content.replace("​", "")
        d.metadata = {
            "paper_id": paper["id"],
            "domain": paper["domain"],
            "role": paper["role"],
            "page": d.metadata["page"] + 1,
        }
    return docs


def _line_is(pattern: re.Pattern, line: str, max_len: int) -> bool:
    s = line.strip()
    return 0 < len(s) <= max_len and "," not in s and bool(pattern.match(s))


def strip_references(pages: list[Document]) -> tuple[list[Document], dict]:
    """Drop the reference list. Cuts mid-page at the last 'References' heading in the
    second half of the paper; resumes at an appendix heading if one follows."""
    n = len(pages)
    ref_at = None  # (page_idx, line_idx)
    for pi, d in enumerate(pages):
        if pi < n * 0.3:
            continue
        for li, line in enumerate(d.page_content.splitlines()):
            if _line_is(REF_HEADING, line, 40):
                ref_at = (pi, li)
    info = {"refs_from_page": None, "resume_from_page": None}
    if ref_at is None:
        return pages, info

    rp, rl = ref_at
    info["refs_from_page"] = pages[rp].metadata["page"]

    # find where content resumes after the reference list
    resume = None
    for pi in range(rp, n):
        lines = pages[pi].page_content.splitlines()
        start = rl + 1 if pi == rp else 0
        for li in range(start, len(lines)):
            if _line_is(APPENDIX_HEADING, lines[li], 60):
                resume = (pi, li)
                break
        if resume:
            break

    out: list[Document] = []
    for pi, d in enumerate(pages):
        lines = d.page_content.splitlines()
        if pi < rp:
            keep = lines
        elif pi == rp:
            keep = lines[:rl]
            if resume and resume[0] == pi:
                keep = keep + lines[resume[1]:]
        elif resume and pi == resume[0]:
            keep = lines[resume[1]:]
        elif resume and pi > resume[0]:
            keep = lines
        else:
            keep = []
        text = "\n".join(keep).strip()
        # after a cut, a page left with only a running header (<80 chars) is dropped
        if text and (pi < rp or len(text) >= 80):
            out.append(Document(page_content=text, metadata=d.metadata))
    if resume:
        info["resume_from_page"] = pages[resume[0]].metadata["page"]
    return out, info


def n_tokens(text: str) -> int:
    return len(ENC.encode(text, disallowed_special=()))


def to_markdown(pages: list[Document]) -> str:
    return "\n\n".join(f"<!-- page {d.metadata['page']} -->\n{d.page_content}" for d in pages) + "\n"


def read_markdown_pages(paper_id: str) -> list[tuple[int, str]]:
    """Read data/md/<id>.md back as [(page, text)]. Used by RAG ingest and the wiki."""
    text = (MD / f"{paper_id}.md").read_text()
    parts = re.split(r"<!-- page (\d+) -->\n", text)
    return [(int(parts[i]), parts[i + 1].strip()) for i in range(1, len(parts), 2)]


def ranges(nums: list[int]) -> str:
    out, start, prev = [], None, None
    for x in nums:
        if start is None:
            start = prev = x
        elif prev is not None and x == prev + 1:
            prev = x
        else:
            out.append(f"{start}-{prev}" if start != prev else str(start))
            start = prev = x
    if start is not None:
        out.append(f"{start}-{prev}" if start != prev else str(start))
    return ",".join(out)


def main() -> int:
    papers = yaml.safe_load(PAPERS_YAML.read_text())["papers"]
    MD.mkdir(parents=True, exist_ok=True)
    stats, problems = [], []
    for p in papers:
        raw_pages = load_paper_pages(p)
        if len(raw_pages) != p["pages"]:
            problems.append(f"{p['id']}: PDF has {len(raw_pages)} pages, papers.yaml says {p['pages']}")
        kept, info = strip_references(raw_pages)
        md = to_markdown(kept)
        (MD / f"{p['id']}.md").write_text(md)
        markers = [int(m) for m in re.findall(r"<!-- page (\d+) -->", md)]
        if markers != [d.metadata["page"] for d in kept] or any(m > p["pages"] for m in markers):
            problems.append(f"{p['id']}: page markers inconsistent")
        stats.append(
            {
                "id": p["id"],
                "pdf_pages": len(raw_pages),
                "kept_pages": ranges(markers),
                "refs_from_page": info["refs_from_page"],
                "resume_from_page": info["resume_from_page"],
                "tokens_raw": sum(n_tokens(d.page_content) for d in raw_pages),
                "tokens_kept": n_tokens(md),
                "min_page_chars": min(len(d.page_content) for d in kept),
            }
        )
        s = stats[-1]
        print(f"{p['id']:<14} pdf={s['pdf_pages']:>2} kept={s['kept_pages']:<8} "
              f"refs@{s['refs_from_page']} resume@{s['resume_from_page']} "
              f"tok {s['tokens_raw']:>6} -> {s['tokens_kept']:>6}")
    STATS_YAML.write_text(yaml.safe_dump({"tokenizer": "cl100k_base", "papers": stats}, sort_keys=False))
    total = sum(s["tokens_kept"] for s in stats)
    print(f"\n{len(stats)} files, {total} tokens kept (cl100k_base)")
    for pr in problems:
        print("PROBLEM:", pr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
