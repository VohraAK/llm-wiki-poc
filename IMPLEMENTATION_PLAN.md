# LLM-Wiki vs RAG PoC: Implementation Plan (lean version)

Last updated: 2026-11-24. Owner: Abdullah (LUMS SProj, Group 9).

This is the handoff for implementation. It is self-contained.

---

## 1. Goal

A small proof-of-concept that answers the same questions over the same papers in two ways:

1. **Traditional RAG**: chunk, embed, retrieve top-k, one answer call.
2. **LLM-Wiki** (Karpathy's pattern): an LLM compiles the papers into a linked markdown
   wiki at ingest time, and questions are answered from the wiki. The wiki follows **OKF v0.3**.

It is for a demo and viva. We need to explain how the LLM-Wiki works, how it differs from
RAG, and the pros and cons of each, backed by a small, fair comparison. Keep everything as
simple as the comparison allows.

Data and inspiration: Cochran (2026), https://arxiv.org/abs/2605.18490, with corpus and
questions from https://github.com/ai4altruism/rag2compare (`experiments/`).

---

## 2. Fixed decisions

| Area | Decision |
|---|---|
| Systems | Plain RAG and a minimal OKF LLM-Wiki |
| RAG framework | **LangChain + LangGraph**: `PyMuPDFLoader`, `RecursiveCharacterTextSplitter`, `OllamaEmbeddings`, `Chroma` (on disk), `ChatOllama`, and a two-node LangGraph `StateGraph` (retrieve, then generate) |
| Generation model | **`qwen3.5:9b`** on Ollama, for wiki ingest, wiki answers and RAG answers. One model everywhere |
| Embedding model | **`embeddinggemma-2:latest`** on Ollama (note the tag spelling: `embeddinggemma-2`, about 1.3 GB) |
| Hardware | 16 GB M1 Pro. `num_ctx` = 32768. Only one chat model loaded at a time |
| Corpus | **Two domains, 16 papers:** climate science + AI ethics and law (294 pages). Precision medicine is left out (231 pages, heaviest) and can be added later |
| Questions | **7** questions from rag2compare, all answerable from the corpus. No extra questions: we are not domain experts |
| Runs | **2 runs per question per system** (seeds 1 and 2): 7 x 2 x 2 = **28 answers** |
| Judging | **Out of scope for this repo.** Abdullah runs a separate Claude Code workflow (Claude Pro) that scores answers. This repo only exports blinded judge packets and imports the scores (Phase 6) |
| Excluded | Cost analysis (tokens are still logged), a second judge, the removal test, access control, model bake-off |

---

## 3. Progress so far

- [x] rag2compare cloned locally.
- [x] All 24 PDFs downloaded to `rag2compare/experiments/papers/<domain>/` and verified as real PDFs
      (the fetch script's dry run reports `24 available`). Only the 16 climate and ethics papers are used.
- [x] Page counts measured (below).
- [x] Phase 0 setup (2026-11-24): uv venv, pinned deps, both models respond, OKF validator in `wiki/validate.py`.
- [x] Phase 1 corpus (2026-11-24): `common/load_pdfs.py`, `data/papers.yaml`, `data/md/` (16 files, ~229K tokens).
- [x] Phase 2 questions (2026-11-24): `questions/questions.yaml`, 7 questions with page-cited key points.
- [ ] Phase 3 RAG baseline, Phase 4 wiki, Phase 5 runs, Phase 6 judge handoff, Phase 7 demo.
- Nothing is committed to git yet. Decisions and deviations are logged in `NOTES.md`.

### Corpus in use (roles and ingest order from `rag2compare/experiments/corpus.yaml`: Anchor, Chrono, Bridge, Conflict)

| Domain | Role | File (in `experiments/papers/<domain>/`) | Pages | Source used |
|---|---|---|---|---|
| climate-science | Anchor | climate-anchor-climate-targets-oschlies.pdf | 9 | Copernicus State of the Planet |
| climate-science | Chrono/Anchor | climate-chrono-limits-co2-he.pdf | 17 | **Biogeosciences 20:27-43 (2023)**, deviation 1 |
| climate-science | Chrono | climate-chrono-novel-field-savoie.pdf | 18 | Frontiers |
| climate-science | Bridge | climate-bridge-monitoring-reporting-ho.pdf | 12 | Copernicus State of the Planet |
| climate-science | Bridge | climate-bridge-lit-tag-mcelhany.pdf | 12 | arXiv 2603.19238 |
| climate-science | Conflict | climate-conflict-biological-response-jones.pdf | 16 | Biogeosciences 22:1615 |
| climate-science | Conflict | climate-conflict-air-sea-schneider.pdf | 17 | **Biogeosciences 23:137 (2026)**, deviation 3 |
| climate-science | Conflict | climate-conflict-modeling-oae-nagwekar.pdf | 15 | IOP Environmental Research Letters |
| ai-ethics-law | Anchor | ethics-anchor-generative-ai-stober.pdf | 16 | **arXiv 2502.15858v2**, deviation 2 |
| ai-ethics-law | Anchor | ethics-anchor-creative-ownership-liang.pdf | 56 | SSRN |
| ai-ethics-law | Chrono | ethics-chrono-assessing-effectiveness-chow.pdf | 10 | arXiv 2512.21762 |
| ai-ethics-law | Chrono | ethics-chrono-label-only-choquette.pdf | 17 | arXiv 2007.14321 |
| ai-ethics-law | Bridge | ethics-bridge-g-drift-ranjan.pdf | 14 | arXiv 2604.00419 |
| ai-ethics-law | Bridge | ethics-bridge-membership-inference-liu.pdf | 5 | **arXiv 2602.01645**, deviation 4 |
| ai-ethics-law | Conflict | ethics-conflict-yes-but-hutiri.pdf | 14 | arXiv 2604.09413 |
| ai-ethics-law | Conflict | ethics-conflict-unfair-learning-atkinson.pdf | 46 | **arXiv 2504.00955**, deviation 4 |

Within a role, keep the order used in rag2compare's `corpus.yaml`.

### Deviations from the source study (keep in `NOTES.md`)

1. **He & Tyka:** the EGU 2023 abstract was withdrawn. We use the full article, doi:10.5194/bg-20-27-2023 (CC BY 4.0).
2. **Stober & Dornis:** the source DOI points to a different SSRN paper. We use arXiv 2502.15858v2 (CC BY 4.0).
3. **Schneider et al.:** final Biogeosciences 2026 version instead of the EGUsphere preprint.
4. **Liu et al. and Atkinson:** arXiv preprints instead of the IEEE and SSRN versions.
5. **Scope:** two of the three domains. Questions that need precision medicine are dropped.

**Never commit PDFs or converted paper text to a public repo.**

---

## 4. Open decisions (ask before settling; defaults are proposals)

| # | Decision | Proposed default |
|---|---|---|
| 1 | Confirm two domains (climate + ethics) rather than all three | Two domains. **Settled 2026-11-25: two domains, 16 papers, confirmed by Abdullah.** Precision medicine stays out |
| 2 | PDF loader (shared by both systems, must keep page numbers) | LangChain `PyMuPDFLoader` (one Document per page). Switch to `PyPDFLoader` only if the text comes out badly **Settled 2026-11-24: `PyMuPDFLoader`** |
| 3 | Strip reference lists from the converted text | Yes, for both systems, noted in `NOTES.md`. **Settled 2026-11-24, implemented** |
| 4 | RAG top-k | 8. **Settled 2026-11-24: 8 chunks (not papers or pages)** |
| 5 | Qwen thinking mode | Off everywhere. Turn it on for ingest only if pilot pages are poor. **Settled 2026-11-24: off for now** |
| 6 | ~~The 3 extra questions~~ | **Settled 2026-11-24: dropped.** We aren't domain experts. Only the 7 rag2compare questions are used, so no unanswerable questions and no decline metric |
| 7 | 25th paper for the update demo | ~~A real paper that updates or contradicts a climate or ethics paper.~~ **Settled 2026-11-24: no extra paper.** The demo re-ingests one of the 16 papers live, from the bundle's git history just before that paper was ingested (see Phase 7). **Demo only, not measured** |

---

## 5. Repo layout

```
llm-wiki-poc/
  CLAUDE.md                 # points to this plan; repeats the rules in section 8
  IMPLEMENTATION_PLAN.md
  NOTES.md                  # deviations and decisions, dated
  config.yaml               # models, num_ctx, temperature, seeds, top_k, chunk sizes
  data/
    raw/                    # the 16 PDFs (gitignored)
    md/                     # converted text, one file per paper, <!-- page N --> markers (gitignored)
    papers.yaml             # id, domain, role, order, doi, title, short_cite, file, pages
  questions/
    questions.yaml          # 7 questions: id, tier, expected favour, domain(s), reference key points
  common/llm.py             # builds the one configured ChatOllama + OllamaEmbeddings; JSONL logging callback
  common/load_pdfs.py       # PyMuPDFLoader -> per-page text in data/md/, shared by RAG and the wiki
  rag/                      # ingest.py (pages -> chunks -> embeddings -> Chroma in data/chroma/),
                            # graph.py (LangGraph retrieve -> generate), ask.py (CLI)
  wiki/
    bundle/                 # the OKF bundle (its own git repo, can be shared: contains no paper text)
    ingest.py  query.py  lint.py  build_index.py
    prompts/                # ingest, topic update, query select, query answer, lint
  eval/
    run.py                  # questions x systems x 2 runs, resumable
    export_judge.py         # blinded packets for the Claude Code judge workflow
    import_scores.py  report.py
  runs/                     # answers, logs, judge packets, scores (gitignored if large)
```

---

## 6. Implementation phases

### Phase 0: Setup
- Create the repo and `.gitignore` (`data/raw/`, `data/md/`, `*.pdf`, vector DB folder).
- Python environment: uv venv (Python 3.12), not conda. Dependencies (LangChain v1): `langchain`, `langchain-core`,
  `langchain-community` (for `PyMuPDFLoader`), `langchain-ollama`, `langchain-chroma`, `langchain-text-splitters`,
  `langgraph`, `pymupdf`, `pyyaml`, `tiktoken`. Pin the versions. Don't use the deprecated `RetrievalQA` chain.
- `ollama pull qwen3.5:9b` and `ollama pull embeddinggemma-2:latest`.
- Copy the OKF validator from https://github.com/open-knowledge-format/open-knowledge-format
  (`skills/okf-generate/scripts/validate.py`, needs PyYAML) into `wiki/`.
- **Check:** both models respond. `git status` shows no PDFs.

### Phase 1: Corpus
- Copy the 16 PDFs into `data/raw/`.
- `common/load_pdfs.py`: load each PDF with LangChain's `PyMuPDFLoader`, which gives one Document per page.
  The page metadata is 0-based, so store `page + 1`. Add `paper_id`, `domain` and `role` to each page's metadata.
  Strip reference-list pages and sections if decision 3 is yes.
- Save the result once as `data/md/<paper-id>.md` with `<!-- page N -->` markers. **Both systems use this
  same page text:** RAG chunks it, and the wiki ingests it. That way a difference in answers can't come from PDF parsing.
- Write `data/papers.yaml`. Each paper gets a short stable `id` (for example `he2023`, `stober2026`)
  and a `short_cite` (for example `He & Tyka (2023)`).
- **Check:** 16 markdown files, page markers match the PDF page counts, and token counts are recorded.

### Phase 2: Questions
- Copy these 7 questions (with tier and expected-favour labels) from `rag2compare/experiments/questions.yaml`:

| ID | Tier | Expected to favour | Domain |
|---|---|---|---|
| T1-mia-evolution | chronological | neutral | ethics |
| T2-oae-bio-vs-chemical | conflict | wiki | climate |
| T2-fair-use-vs-optin | conflict | wiki | ethics |
| T3-mia-as-copyright-evidence | multi-hop | wiki | ethics |
| T4-eelgrass-mrv-gaps | emergence | wiki | climate |
| B2-he-tyka-equilibration-ratios | bias-check | rag | climate |
| B3-mia-attack-success-rate | bias-check | rag | ethics |

- Reference answers: 3-5 bullet key points per question, drafted with LLM help and checked by a
  person against the papers (a spot check, since we aren't domain experts).
- **Check:** all 7 questions have a reference.

### Phase 3: RAG baseline with LangChain + LangGraph (plain, frozen once built)
Use the standard LangChain / LangGraph RAG building blocks, not custom code:

| Step | Component |
|---|---|
| Load | One LangChain `Document` per page of `data/md/<paper>.md`, with metadata `{paper_id, page, domain}` |
| Split | `RecursiveCharacterTextSplitter.from_tiktoken_encoder(chunk_size=500, chunk_overlap=50)`, applied per page so every chunk keeps an exact page number |
| Embed | `OllamaEmbeddings(model="embeddinggemma-2:latest")` (`langchain-ollama`) |
| Store | `Chroma` (`langchain-chroma`) with `persist_directory="data/chroma"`, one collection for the corpus. Deterministic chunk IDs (`<paper-id>-p<page>-c<n>`), so re-running ingest doesn't duplicate chunks |
| Retrieve | `vectorstore.as_retriever(search_kwargs={"k": top_k})` |
| Generate | `ChatOllama(model="qwen3.5:9b", ...)` with the settings from `config.yaml` (temperature, `num_ctx`, seed, thinking off) and a `ChatPromptTemplate` holding the **shared answer rules** |
| Orchestrate | A two-node LangGraph `StateGraph`: `retrieve -> generate`, state `{question, context, answer}`, the standard LangGraph RAG pattern |

- **Shared answer rules** (the same text is used by the wiki's answer step): answer only from the given text,
  cite every claim as `[<paper-id>, p.<N>]`, and say "The documents don't cover this." when they don't.
- Format each retrieved chunk in the prompt with its `[<paper-id>, p.<N>]` header, so the model can cite it.
- Plain baseline only: no query rewriting, no hybrid search, no re-ranking, no multi-query. Those would make it
  "enhanced RAG", which is out of scope here.
- Use the fixed two-node graph, **not** LangChain v1's agent-style RAG, where the model decides when and how
  often to search. One retrieval per question keeps the baseline repeatable.
- Save the retrieved chunk IDs with each answer (useful for debugging and for the viva).
- CLI: `python -m rag.ingest --domain climate-science` and `python -m rag.ask "question" --seed 1`.
- Logging: a LangChain callback handler (or `usage_metadata` on each response) writes the same JSONL
  log fields as the wiki: model, settings, tokens in and out, latency.
- **Check:** one climate question answers end to end with valid citations. Re-running ingest leaves the collection size unchanged.

### Phase 4: Minimal OKF LLM-Wiki

**Bundle** (`wiki/bundle/`):
```
index.md        # root: frontmatter okf_version "0.3", title, description; lists sources/ and topics/
log.md          # OKF format: "## YYYY-MM-DD" headings, newest first, one bullet per event
AGENTS.md       # the schema (not a concept; the validator's W120 warning on it is expected)
sources/
  index.md
  <paper-id>.md # type: Source Summary. One page per paper
topics/
  index.md
  <topic>.md    # type: Topic. Concepts, methods, findings, debates: everything that spans papers
```

**Page format** (the LLM writes only `title`, `description` and the body; Python writes the rest):
```markdown
---
type: Topic
title: CO2 uptake efficiency of alkalinity enhancement
description: How much CO2 the ocean absorbs per unit of added alkalinity, and how fast.
sources:
  - id: he2023-p7
    resource: https://doi.org/10.5194/bg-20-27-2023
    title: He & Tyka (2023), p. 7
generated: { by: "llm-wiki-poc/qwen3.5-9b", at: "2026-11-24T10:00:00Z" }
---
Most coastal sites plateau at 0.6-0.8 mol CO2 per mol of alkalinity after 3-4 years.[^he2023-p7]
See also [Monitoring and verification](mrv.md).

[^he2023-p7]: He & Tyka (2023), p. 7
```

Rules (from OKF v0.3):
- Footnote labels are source `id`s, never `[^1]`. Use `<paper-id>-p<page>` so each footnote points to one page.
- Python builds the `sources` list from the footnote labels in the body, using `data/papers.yaml` for each DOI and short cite.
- `resource` is the paper's DOI URL, so the bundle contains no copyrighted paper text and can be shared.
- Links between pages are standard markdown links, written relative to the file. Never use `[[wikilinks]]`: OKF doesn't count them as links.
- No `verified` entries, because nothing is human-checked. Omit `status` except in the update demo.
- `index.md` in each folder: `* [Title](file.md) - description`, generated by `build_index.py` from frontmatter. The root `index.md` keeps its frontmatter when regenerated.
- `log.md`: no frontmatter, `## YYYY-MM-DD` headings, newest first, entries like
  `* **Ingest**: [He & Tyka (2023)](sources/he2023.md), 4 topics updated`. This uses OKF's log
  format instead of Karpathy's `## [date] ingest | title` prefix, because OKF requires date headings.

**Ingest**, one paper at a time in role order (Karpathy's ingest operation, batch mode):
1. If the paper is over about 6K tokens, Python splits it into page-aligned sections. The LLM writes
   short notes per section, keeping page numbers.
2. The LLM writes `sources/<paper-id>.md`: a summary with footnotes.
3. The LLM reads `topics/index.md` and the new summary, and returns JSON listing up to 5 topic pages to create or update.
4. For each one, the LLM rewrites the whole page (existing text plus the new facts with footnotes, links to related pages).
   Pages from earlier papers keep their existing footnotes.
5. Python fills the frontmatter, regenerates the indexes, appends to `log.md`, runs `validate.py`, and commits to the bundle's git repo.
   If the validator reports errors on a page, retry that page once.

**Query** (fixed two steps, no agent loop):
1. The LLM reads the root, `sources/` and `topics/` indexes, plus the question, and returns JSON with up to 6 page paths.
2. Python loads those pages. The LLM answers using only them, with the **shared answer rules**.
   Python converts footnote labels to `[<paper-id>, p.<N>]` citations.

During measured runs answers are **not** filed back into the wiki (Karpathy's suggestion), so runs stay independent.

**Lint** (demo only): `validate.py`; Python lists orphan pages (no inbound links); one LLM pass over topic pages flags contradictions.

**Update demo** (not measured): re-ingest one of the 16 papers live (decision 7). Topics it changes are
updated, and any page it replaces gets `status: deprecated` and `superseded_by: /topics/<new>.md`.

- **Check:** the climate bundle passes `validate.py` with no errors. 10 sampled footnotes point to pages that support the claim.

### Phase 5: Pilot, then full runs
- Pilot on climate (8 papers): ingest, then run T2-oae-bio-vs-chemical, T4-eelgrass-mrv-gaps and B2 through both systems.
  Fix prompts and plumbing, then freeze prompts and `config.yaml` (git tag `frozen`).
- Ingest the ethics papers.
- Run all 7 questions x 2 systems x 2 runs (seeds 1 and 2, fixed temperature, proposed 0.2).
- Log per LLM call (JSONL): model tag, settings, prompt hash, tokens in and out, latency. Record ingest time per paper.
- **Check:** 28 answers, no gaps in the logs.

### Phase 6: Judge handoff (scoring itself is done in Abdullah's separate Claude Code workflow)
- `export_judge.py` writes `runs/judge_packets.jsonl`, one line per answer:
  `answer_id` (random), `question`, `reference_key_points`, `answer` (citations already in the shared format),
  and `cited_pages` (the text of every cited page, from `data/md/`).
  Nothing in a packet reveals which system wrote the answer, and packets are shuffled.
- `runs/answer_key.csv` maps `answer_id` to system, question and run. Keep it away from the judge.
- Expected scores file back from the judge workflow, `runs/scores.jsonl`, one line per answer:
  `answer_id`, `accuracy` (correct / partial / wrong), `declined` (true/false),
  `citations` ([{citation, supported: true/false}]).
- `import_scores.py` + `report.py` compute the metrics (section 7).
- Spot-check about 6 answers by hand against the judge's scores and note the agreement.

### Phase 7: Demo
- Ingest one paper live and show the new and changed pages and the git diff.
- Browse the bundle in Obsidian (graph view). Set "Use [[Wikilinks]]" to off so new links stay standard markdown.
- Ask both systems the same question side by side.
- Update demo: check out the bundle commit just before a late-ingested paper (a Conflict paper, for example
  `climate-conflict-modeling-oae-nagwekar`), re-ingest it live, show the diff, then run lint. Do this on a
  copy or a branch of the bundle so the measured wiki stays untouched.

---

## 7. Metrics

Computed by `report.py` from the judge's labels, per system, pooling both runs
(per system: 14 answers = 7 questions x 2 runs, all answerable).

| Metric | Formula |
|---|---|
| Answer accuracy | correct / answers to answerable questions. Partial is shown in its own column. A decline on an answerable question counts as wrong |
| Citation precision | supported citations / all citations. Answers without citations add nothing |
| Cited or declined | answers with at least one citation or an explicit decline / all answers |

Also reported:
- Run consistency: the share of questions where run 1 and run 2 got the same accuracy label.
- Breakdowns by tier and expected favour, as raw counts (for example 3/4), because the groups are small.
- From the logs (not analysed): tokens in per answer, query latency, ingest time per paper, wiki size (pages, links).
- Judge agreement on the 6 hand-checked answers.

---

## 8. Invariants and disclosed limitations

The comparison holds the environment fixed and runs each system in its standard form. Neither system
is tuned or optimised for this corpus. Differences that come from how a system works are reported as
findings, not corrected.

**Invariants (identical for both systems):**
- The same 16 papers and the same page text (loaded once, shared).
- The same model (`qwen3.5:9b`), settings (temperature, `num_ctx`, seeds, thinking off) and Ollama install.
- The same answer rules and citation format (`[<paper-id>, p.<N>]`).
- The same 7 questions, 2 runs each.
- The same search scope: each system searches the **whole 16-paper corpus** (no per-domain filter).
- The same judge workflow, blind to which system wrote the answer.

**Disclosed limitations (stated in the results, not engineered away):**
- A small local model (9B, thinking off) does all generation. Results may differ with larger models.
- The wiki is built once, so the variation between wiki builds isn't measured. RAG's index is deterministic.
- Questions often name papers by author. The wiki's index lists authors and years, but RAG chunks
  mostly don't contain author names. This is reported as an inherent difference between the systems.
- The amount of context each system passes to the model differs (RAG: top-k chunks; wiki: whole pages).
  It's logged per answer (tokens in), not equalised.
- 7 questions, 2 of the 3 domains, 2 runs each. There are no unanswerable questions, so how well each system declines isn't tested: results are indicative, not statistically conclusive.

---

## 9. Rules

- Never commit PDFs or converted paper text. The wiki bundle has only LLM-written pages and DOIs.
- One model (`qwen3.5:9b`) for every generation step in both systems. The same answer rules and citation format for both.
- The LLM writes content only. Python handles frontmatter, indexes, logs, validation and git.
- Don't tune RAG after the freeze. Record any change after the freeze in `NOTES.md` with a date and reason.
- All LLM calls, from both systems, use the same `ChatOllama` instance built in `common/llm.py`, and all are logged.
  The wiki calls it directly (no LangGraph needed there); the RAG side wraps it in the LangGraph graph.
- Ask Abdullah before settling anything in section 4.

- Don't add system-specific improvements (chunk headers, re-ranking, page-length caps, extra wiki checks) to
  win a question. If something seems unfair, add it to the disclosed limitations instead.

## 10. Where the minimal choices come from

| Choice | Source |
|---|---|
| Raw sources + wiki + schema file; ingest, query, lint; `index.md` read first at query time; `log.md` | Karpathy's LLM Wiki gist: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f |
| Index-first navigation without search is fine at this size (the gist says it works at about 100 sources and hundreds of pages) | Karpathy's gist |
| Batch ingest instead of discussing each paper with a person | Karpathy's gist allows both. We batch for repeatable runs |
| Only `type` required; `title` and `description` recommended; footnote labels = `sources[].id`; `generated.by` as `<producer>/<version>`; `status` and `superseded_by`; per-folder `index.md`; root `okf_version: "0.3"`; dated `log.md`; standard markdown links only | OKF v0.3 SPEC.md sections 3, 4, 5, 6, 7, 8 and 9: https://github.com/open-knowledge-format/open-knowledge-format/blob/main/SPEC.md |
| Write only what a source supports; no `verified` without a person; run `validate.py` | OKF `okf-generate` skill: https://github.com/open-knowledge-format/open-knowledge-format/tree/main/skills/okf-generate |
