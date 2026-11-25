# Notes

## 2026-11-24
- Phase 0: env is uv (Python 3.12), not conda. Deps locked in `uv.lock`.
- Repo root is the existing `llmwiki/` dir, not a new `llm-wiki-poc/`. `rag2compare/` (nested clone) is gitignored.
- OKF validator copied from open-knowledge-format `skills/okf-generate/scripts/validate.py` into `wiki/validate.py` (Apache 2.0, Google).

## Deviations from the source study
1. He & Tyka: full article (Biogeosciences 20:27-43, 2023), EGU abstract withdrawn.
2. Stober & Dornis: arXiv 2502.15858v2, source DOI points to a different SSRN paper.
3. Schneider et al.: final Biogeosciences 2026 version, not the preprint.
4. Liu et al. and Atkinson: arXiv preprints, not IEEE/SSRN.
5. Scope: two of three domains. Precision-medicine questions dropped.

## 2026-11-24 Phase 1 decisions
- Decision 2: `PyMuPDFLoader` (langchain-community). It emits a "being sunset" DeprecationWarning; harmless for now. Text quality not yet judged beyond spot checks.
- Decision 3: reference lists stripped for both systems (`common/load_pdfs.py`). Cut at the last "References" heading in the second half of the paper, mid-page if needed. Appendices after the references are kept (Choquette-Choo p12-17, Ranjan p12-14).
  - After a cut, pages left with under 80 chars (running header only) are dropped: Choquette-Choo p10, Hutiri p9, Liu p5 (only a grant line). Liu keeps pages 1-4 of 5.
  - Atkinson has no reference list (law-review footnotes), left whole.
  - Page numbers in `data/md/*.md` are the original PDF pages, so gaps are expected where pages were dropped.
- Token counts use `cl100k_base`, not Qwen's tokenizer. Treat as approximate. Total kept: 228,778 tokens across 16 papers (`data/corpus_stats.yaml`).
- Paper ids: year follows corpus.yaml except Schneider (2026, final version) and Choquette-Choo (2021, ICML). Stober is `stober2026`, as in the plan's example.
- DOI deviations from `corpus_dois.tsv`: He `10.5194/bg-20-27-2023`; Stober `10.48550/arXiv.2502.15858`; Schneider `10.5194/bg-23-137-2026` (verified on Crossref; title differs from the preprint: "Carbon fixation of a temperate plankton community in response to calcium- and silicate-based Ocean Alkalinity Enhancement using air-sea gas exchange measurements"); Liu `10.48550/arXiv.2602.01645`; Atkinson `10.48550/arXiv.2504.00955`. The Stober, Liu and Atkinson DOIs were built from the arXiv ids in the plan and not looked up. Only He and Schneider were checked on Crossref.
- Titles in `papers.yaml` for Savoie, Nagwekar, Ho, Jones, McElhany come from the manifest's `matched_title` / override notes, not from the PDFs.

## 2026-11-24 Decision 6 settled
- No extra questions (we aren't domain experts). 7 rag2compare questions only, 28 answers total.
- No unanswerable questions, so the "Correct declines" metric is dropped. Declining is only counted as a wrong answer, never tested directly. Disclosed as a limitation.

## 2026-11-24 Decisions 4 and 5 settled
- Decision 4: top-k = 8. One unit = one chunk (~500 tiktoken tokens, single page, single paper). Not a paper, not a page. 8 chunks can come from 1 to 8 papers; ~4K tokens of context.
- Decision 5: thinking off everywhere. Revisit for wiki ingest only if pilot pages are poor (log it here if changed).

## 2026-11-24 Decision 7 settled
- No 25th paper. Update demo re-ingests an existing paper live, starting from the bundle commit just before it was ingested (ingest commits once per paper, so the history gives this for free). Candidate: a Conflict paper such as Nagwekar. Run on a bundle copy or branch, never the measured wiki. Demo only.

## 2026-11-24 Phase 2
- `questions/questions.yaml`: 7 questions copied from rag2compare (`bias` renamed `expected_favour`). Reference key points drafted by Claude from `data/md/` with a paper-page source on each. Not expert-verified.
- Three questions don't match their papers. Each has a `caveats` entry for the judge:
  - B3: Choquette-Choo has no quoted CIFAR-10 number (figures only). The tables are CIFAR-100 and MNIST.
  - T2-oae: He & Tyka and Schneider agree on the equilibration timescale. Neither claims biology speeds or slows equilibration.
  - T3: "counterfactual infringement" and "substantial-similarity threshold" are not terms in Liang & Lut or Stober & Dornis.

## 2026-11-25 Phase 3 RAG baseline built
- Added `common/llm.py` (one ChatOllama via `get_chat(seed)`, JSONL log at `runs/llm_log.jsonl`), `common/prompts.py` (shared `ANSWER_RULES`, the wiki reuses it), `common/citations.py`, `rag/ingest.py`, `rag/graph.py`, `rag/ask.py`.
- Thinking off via `reasoning=False`. Seed is the only per-run setting.
- Climate ingest: 299 chunks from 8 papers. Re-running ingest leaves the count at 299 (a paper's chunks are deleted, then re-added).
- Smoke test on B2 (seed 1): answer ran end to end, all citations came from the retrieved chunks, 4110 tokens in, 36 s. The answer was partial by eye (not judged): it cited he2023 p9 (0.2-0.85 after 1 yr, 0.65-0.80 after 10 yr) but opened with 'does not contain a specific range' and missed the 0.6-0.8 plateau (he2023 p1, p13 were not retrieved). Not tuned. This is the plain-RAG behaviour we measure. Not yet frozen (freeze comes after the Phase 5 pilot).
- Only climate is ingested so far. Ethics papers go in before the full runs.

## 2026-11-25 Phase 4 wiki built
- Added `wiki/okf.py` (page rendering, footnote/sources building, log, git, validator wrapper), `wiki/build_index.py`, `wiki/ingest.py`, `wiki/query.py`, `wiki/lint.py`, `wiki/prompts/*.md`, `wiki/bundle_agents.md` (copied to `bundle/AGENTS.md`).
- `wiki/bundle/` is its own git repo and is gitignored in the main repo.
- Source-page titles are set by Python from `papers.yaml` (`<short_cite>: <title>`), not written by the LLM, so author and year always appear in the index. Topic titles and all descriptions and bodies are LLM-written.
- Validator warnings (not only errors) trigger one retry of a topic page. After that Python turns still-broken links into plain text and drops footnote markers that don't match a real `<paper-id>-p<page>`. Counts are logged in `runs/ingest_times.jsonl`.
- Query: Python converts footnote labels to `[<paper-id>, p.<N>]` before the model sees the pages, so the shared answer rules apply unchanged. Page selection and ingest topic selection use Ollama `format="json"`.
- Ingest uses seed 1. Long papers (over 6K tokens) get section notes (~5K tokens each) before the summary.
- Smoke test on mcelhany2026 alone (test bundle in `runs/test_bundle`): 5 calls, 246 s, validator clean, 3 topic pages that mostly copy the paper summary (expected with one paper). Query answered with valid citations. Quality across papers not yet judged.

## 2026-11-25 Decision 1 settled
- Two domains (climate + AI ethics/law), 16 papers, confirmed by Abdullah. He had expected all three. Precision medicine (8 papers, 231 pages) stays out and remains a possible extension, which would need Phase 1 redone for those papers and its rag2compare questions restored.

## 2026-11-25 Where things stood (for a fresh session)
- Climate wiki ingest was running in the background (`uv run python -m wiki.ingest --domain climate-science`, output `runs/climate_ingest.out`, per-paper stats `runs/ingest_times.jsonl`, one git commit per paper in `wiki/bundle`). Check with `pgrep -f "[w]iki.ingest"` and `git -C wiki/bundle log --oneline`. 2 of 8 papers were done at 02:12 local.
- Next: when it finishes, run `uv run python wiki/validate.py wiki/bundle`, spot-check 10 footnotes against `data/md/`, then pilot (T2-oae, T4, B2) on both systems. Then ingest ethics in both systems (`--domain ai-ethics-law`), freeze (`git tag frozen`), full runs.
- `runs/test_bundle` is a throwaway one-paper smoke-test bundle. Its mcelhany2026 line in `runs/ingest_times.jsonl` is from that test, not the real build.
- Main repo has no commits yet. The 10-minute status cron job lived only in the old session.

## 2026-11-25 Topic-slug bug fixed, ethics wiki ingest redone
- Bug: `select_topics` sanitised the model's slug with a regex, so a returned filename like `model-memorization.md` became the new slug `model-memorization-md`. From liu2026 on, the bundle got duplicate pages (`model-memorization-md`, `membership-inference-attacks-md`). Found by looking at `topics/index.md` after the overnight run.
- Fix (`wiki/ingest.py`): drop any path prefix and trailing `.md` before sanitising.
- Bundle reset to `6a08230` (climate only). The duplicated state is kept as tag `ethics-v1-dup` in the bundle repo. The 8 ethics papers are re-ingested in papers.yaml order. Climate pages and the RAG collection are unchanged. Pre-freeze plumbing fix, not a tuning change.

## 2026-11-25 Stray `<` in citations normalised in code
- Pilot RAG answer for T2-oae had all 9 citations as `[<he2023, p.1]` (the model copied the `<` from the prompt's `[<paper-id>, p.<N>]`). 1 of 6 pilot answers. The citation parser already accepted it (`CITE` does not need the bracket), so checks were unaffected.
- Added `normalize_citations()` in `common/citations.py`. Both `rag.ask` and `wiki.query.ask` apply it. Each result now has `answer` (cleaned), `answer_raw` (as written) and `citation_format_fixed`. Prompts and retrieval untouched. Stored pilot JSON patched the same way.
- To report at the end: the number of answers per system with `citation_format_fixed: true`. Disclosed limitation, not a tuning change.
- Follow-up (ethics smoke test, T1 RAG): the model also wrote `[<chow2025, p.2>]` with a trailing `>`. `normalize_citations()` now strips a stray `<` or `>` in either position. Stored pilot and smoke JSON re-normalised from `answer_raw`.

## 2026-11-25 Freeze
- Tag `frozen` on the first commit of the main repo. Frozen: `config.yaml`, `common/` (incl. `prompts.py`, `citations.py`), `rag/`, `wiki/` (code and prompts), `questions/questions.yaml`.
- State at freeze: RAG collection 633 chunks (16 papers). Wiki bundle 17 commits (init + 16 papers), validator 0 errors, 1 expected warning (`AGENTS.md` has no frontmatter). Bundle tag `ethics-v1-dup` is the superseded duplicated-topic state.
- Pilot (climate) and ethics smoke test (T1, B3) ran on both systems with no errors. 10 sampled footnotes checked against pages: all supported (one cites p.9 for a sentence that starts on p.8).
- Observed, not fixed (so it is measured): RAG misses on T4 and B2 (retrieval), wiki T2 contradicts itself on timescales, wiki output contains LaTeX, RAG T1 retrieval missed Choquette-Choo.

## 2026-11-25 Full runs and judge export
- Full runs (`scripts/full_runs.py`, after `frozen`): 28/28 answers, 0 errors, no gaps in `runs/llm_log.jsonl`, 24.9 min. RAG: 3 answers needed the citation-format fix (T2-oae both seeds, B2 seed 2), 5 have no citations (all declines: B3 s2, T3 s1+s2, T4 s1+s2). Wiki: 0 fixes, 0 without citations.
- `scripts/export_judge.py` wrote 28 blinded packets (`runs/judge_packets.jsonl`) and `runs/answer_key.csv`. Packets carry only answer_id, question, reference_key_points, caveats, answer, cited_pages. Cited pages that are missing in `data/md/`: none.
- Style tells that remain in the answer text (not edited, disclose as limitation): wiki answers are longer (mean 301 words vs 190), 2 wiki answers contain LaTeX (`$...$`), RAG declines more often ("does not contain" / "documents don't cover this" in 14 RAG vs 8 wiki answers). A blind judge can probably guess the system from some of these.

## 2026-11-25 Judging done (Claude, in-session) and spot-check skipped
- Judge: Claude (Sonnet 5.5) in this Claude Code session, not the separate workflow in plan section 6. Blind: `answer_key.csv` was not opened until after scoring. Each citation checked per occurrence against the packet's cited pages. Scores in `runs/scores.jsonl`, one-line reasons in `runs/judge_notes.jsonl`. Both gitignored.
- Abdullah chose to skip the hand spot-check of ~6 answers (plan section 6, section 7 "judge agreement"). Judge agreement is therefore not measured. Labels are one unverified judge pass by a model from the same family as the generator. Report it as a limitation.
- Decline policy: `declined=true` when the answer says the corpus does not cover something that it does cover, with no real attempt at the comparison. Declines are labelled wrong. Mixed cases (see below) were labelled by content and `declined=false`. B3 is a trap question whose correct answer is "no single CIFAR-10 value", so those answers are correct and not declines.
- Sensitivity: 4 wiki answers (T3 s1, T2-fair-use s1, T1 s1 and s2) are partial but say "the text does not contain/state" the link between the papers, while giving accurate per-paper content. Counted as declines they would move wiki from 9 partial / 1 wrong to 5 partial / 5 wrong. RAG's 12 declines are plain refusals (retrieval missed papers), so RAG's result does not depend on this call.
- Judge style notes: strict on quotes or numbers not found on the cited page (marked unsupported), and on answers that assert a paper is absent from the corpus when it is present.
