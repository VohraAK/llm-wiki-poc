# LLM-Wiki vs RAG PoC

Full spec: `IMPLEMENTATION_PLAN.md`. Read it before any work.

## Environment
- Python via uv: `uv sync`, run with `uv run python -m ...`. Python 3.12. No conda.
- Models (Ollama): `qwen3.5:9b` (all generation), `embeddinggemma-2:latest` (embeddings).

## Rules (plan section 9)
- Never commit PDFs or converted paper text.
- One model for every generation step in both systems. Same answer rules and citation format `[<paper-id>, p.<N>]`.
- LLM writes content only. Python handles frontmatter, indexes, logs, validation, git.
- All LLM calls go through the one `ChatOllama` built in `common/llm.py`, and are logged.
- Don't tune RAG after the `frozen` tag. Log post-freeze changes in `NOTES.md` with date and reason.
- No system-specific improvements to win a question. Add to disclosed limitations instead.
- Ask Abdullah before settling anything in plan section 4.

## Status (2026-11-25)
- Done: Phase 0 (setup), Phase 1 (corpus in `data/md/`, `data/papers.yaml`), Phase 2 (`questions/questions.yaml`, 7 questions), Phase 3 (RAG baseline: `common/`, `rag/`), Phase 4 (wiki: `wiki/`, bundle of 16 papers in `wiki/bundle/`, validates clean), Phase 5 pilot and ethics smoke test.
- Frozen 2026-11-25 (git tag `frozen`). From here, changes to RAG or the shared prompts go in `NOTES.md` with date and reason.
- Next: full runs (7 questions x 2 systems x seeds 1, 2 = 28 answers), then Phase 6 judge export, then the update demo.
- Bundle repo (`wiki/bundle/`, own git, gitignored here) tag `ethics-v1-dup` holds the pre-slug-fix state. Scripts in `scripts/` (overnight run, pilot, smoke test, status).
- All plan section 4 decisions settled. None open.
- Settled: 1 (two domains, 16 papers, confirmed 2026-11-25), 2 (PyMuPDFLoader), 3 (strip references), 4 (top-k 8 chunks), 5 (thinking off, for now), 6 (no extra questions; 7 questions, 28 answers, no decline metric), 7 (no 25th paper; update demo re-ingests an existing paper from bundle git history).
- See `NOTES.md` for dated decisions and deviations.
- Helper scripts for reading `data/md/` pages are in the session scratchpad only; use `common.load_pdfs.read_markdown_pages`.
