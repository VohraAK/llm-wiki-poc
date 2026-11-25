# Results notes (LLM-Wiki vs RAG PoC)

Reference notes for writing up and for the viva. Not a report. Numbers come from `runs/report.md`
(built by `scripts/report.py` from `runs/scores.jsonl`). Decisions and deviations are in `NOTES.md`.

## 1. Setup in one paragraph

Same 16 papers (climate science + AI ethics and law, 294 pages), same model (`qwen3.5:9b`, thinking off),
same answer rules and citation format `[<paper-id>, p.<N>]`, 7 questions x 2 runs x 2 systems = 28 answers.
RAG: LangChain/LangGraph, page text split into chunks, `embeddinggemma-2`, Chroma, top-8 chunks, one generate step.
Wiki: the LLM compiles each paper into a source-summary page plus shared topic pages (OKF bundle, git-tracked),
and at query time reads the index and then the relevant whole pages. Neither system was tuned after the `frozen` tag.

## 2. Results

14 answers per system, both runs pooled.

| | Correct | Partial | Wrong | Declined | Citation precision | Run consistency |
|---|---|---|---|---|---|---|
| RAG | 2 | 0 | 12 | 12 | 39/43 (91%) | 7/7 |
| Wiki | 4 | 9 | 1 | 0 | 116/131 (89%) | 6/7 |

Per question (seed 1 / seed 2):

| Question | Tier | Expected favour | RAG | Wiki |
|---|---|---|---|---|
| B3 CIFAR-10 trap | bias-check | rag | correct / correct | correct / correct |
| B2 He & Tyka uptake range | bias-check | rag | wrong / wrong (declined) | correct / correct |
| T1 MIA evolution | chronological | neutral | wrong / wrong (declined) | partial / partial |
| T2 fair use vs opt-in | conflict | wiki | wrong / wrong (declined) | partial / partial |
| T2 OAE bio vs chemical | conflict | wiki | wrong / wrong (declined) | partial / wrong |
| T3 MIA as copyright evidence | multi-hop | wiki | wrong / wrong (declined) | partial / partial |
| T4 eelgrass MRV gaps | emergence | wiki | wrong / wrong (declined) | partial / partial |

From the logs (not analysed): mean answer time RAG 32 s vs wiki 75 s; mean tokens in 3.8k vs 8.2k;
mean tokens out 310 vs 530. Wiki ingest took roughly 4 to 6 minutes per paper on the M1 Pro (mean 389 s
over the logged ingests, which include re-runs). RAG ingest is embedding only.

## 3. What the results mean

- **RAG's failure is retrieval.** 12 of 14 RAG answers said "the documents don't cover this" about papers that are in the corpus.
  Top-8 chunks over 633 chunks from 16 papers often missed the right paper. Questions that name papers by author make it worse
  because chunks mostly don't contain author names, while the wiki index lists authors and years. Where RAG retrieved the
  right chunks (B3) it answered correctly.
- **The wiki found the papers but synthesised only partly.** It never declined, but on the five synthesis questions
  it got partial on 9 of 10 answers: it hedged ("the text doesn't state the link"), overstated some claims,
  missed some reference points, and a few quotes or numbers were not on the cited page. A 9B model with thinking off is the likely limit.
- **Expected vs observed.** Wiki-favoured questions (T2, T3, T4): wiki better, as expected, but "partial vs wrong", not "correct vs wrong".
  RAG-favoured questions (B2, B3): not as expected. B3 tied. On B2 the wiki won outright because RAG's retrieval missed He & Tyka.
  Neutral (T1): wiki slightly better.
- **Not a statistical result.** Effectively 7 independent questions per system. The two runs of a question almost always agree,
  so they add little. Indicative only.

## 4. How the judging was done, and its weak points

- Judge: Claude (Sonnet 5.5) in the Claude Code session, blind (answer key not opened until after scoring). Not the separate workflow in the plan.
- Each citation was checked per occurrence against the cited page text. Unsupported means the page does not make the claim, or a quote or number is not on it.
- **Hand spot-check skipped** (Abdullah's choice, 2026-11-25). Judge agreement is unmeasured. Labels are one pass from a model in the same family as the generator.
- **Decline policy.** An answer that says the corpus lacks something that it has, with no real attempt, is `declined` and counts as wrong.
  B3 is a trap question whose correct answer is "no single CIFAR-10 value", so those answers are correct, not declines.
- **Sensitivity.** Four wiki answers (T3 s1, T2 fair-use s1, T1 s1 and s2) are partial but say the text doesn't link the papers.
  Counted as declines, wiki goes from 9 partial / 1 wrong to 5 partial / 5 wrong. RAG's result does not depend on this call.
- Strictness: marked unsupported when a quote or number is not on the cited page, and wrong when an answer asserts a paper is absent that is present.

## 5. Disclosed limitations (short list)

- Small local model (9B, thinking off). Results may differ with larger models.
- 7 questions, 2 domains, 2 runs. No unanswerable questions, so declining well is not tested.
- The wiki is built once. Variation between wiki builds is not measured. RAG's index is deterministic.
- Context differs by design (RAG: top-k chunks; wiki: whole pages). Logged, not equalised.
- Questions name papers by author. The wiki index helps with that, RAG chunks mostly don't. Inherent difference, reported as a finding.
- Style tells for a blind judge: wiki answers are longer, a few contain LaTeX, RAG declines more.
- RAG was a standard baseline (top-8 dense retrieval), not a tuned one. A stronger retriever might close much of the gap.
- Reference key points were drafted by Claude from the page text, not by domain experts.

## 6. RAG vs wiki in general

Everything below the first line of each bullet is general reasoning, not something this experiment measured
unless it says so.

### How they differ

| | RAG | LLM-Wiki |
|---|---|---|
| When understanding happens | At query time, from retrieved chunks | At ingest time, written into pages. Queries read the result |
| Unit the model sees | Chunks (a few paragraphs, little context) | Whole pages (summaries, topic syntheses) |
| Build cost | Low: split and embed | High: many LLM calls per paper (about 5 minutes per paper here) |
| Query cost | Low context, fast (32 s, 3.8k tokens here) | More context, slower (75 s, 8.2k tokens here) |
| Knowledge across documents | Only what one query happens to retrieve | Already linked into topic pages |
| Failure mode | Retrieval miss: wrong chunks, so a decline or an answer from the wrong paper | Compile error: a wrong or lost detail is baked into a page and reused |
| Inspectable | The chunks, not much else | Pages, links and git diffs a person can read and edit |
| Update a source | Re-embed that document | Re-run ingest. Touches the summary and any topic pages that cite it (see the update demo) |
| Scale | Large corpora, thousands of documents | Small to mid. Index-first navigation is claimed to work to about 100 sources |

### Where RAG should shine

- **Exact lookup** of a number, quote or definition, where the source wording is what you want.
- **Large or fast-changing corpora**, where compiling everything with an LLM is too slow or expensive.
- **Cheap, fast, repeatable** setups. Indexes are deterministic and easy to rebuild.
- **No compile step to get wrong.** The answer is grounded in the original text.
- Improvable without changing the idea: hybrid keyword + dense search, reranking, bigger k, chunk headers with title and author, query rewriting.
  That matters here, because the plan froze RAG as a plain baseline.

### Where the wiki should shine

- **Cross-document questions**: compare, contrast, trace an evolution, find what is missing across papers. The linking is done once, not per query.
- **Questions phrased by paper, author or concept**, because navigation starts from titles and an index and not from embedding similarity.
- **Small, stable, high-value corpora** where an ingest cost is paid once and read many times.
- **Auditability and maintenance**: a person can read, correct and diff the knowledge base, and lint it for contradictions.
- **Accumulation**: each new source improves the pages for later questions.

### Where each is weak

- RAG: multi-hop and synthesis, anything that needs several documents at once, questions that depend on who wrote what.
- Wiki: detail loss and hallucination at compile time, ordering effects (earlier pages shape later ones), cost and time at ingest,
  poor scaling past a modest size, and quality capped by the compile model. If the summary drops a number, the query step may never see it.

### How this experiment lines up with that picture

- **Consistent:** the wiki did better on the cross-paper synthesis and by-author questions (T1 to T4), and RAG was cheaper and faster.
- **Not shown:** the claim that RAG shines at exact lookup. B3 (lookup, trap) was a tie. B2 (lookup) was won by the wiki because
  RAG missed the paper. So this setup mostly exposed RAG's retrieval weakness, not its strengths.
- **Not tested:** scale, freshness, cost of updates (only demoed), and how a tuned RAG or a stronger model would compare.
- **Reasonable summary line:** with a small model and plain top-8 retrieval, the wiki was much more reliable at finding and combining the right papers,
  at about twice the query cost and a large upfront ingest. It was not reliably correct on synthesis.

## 7. Likely viva questions

- *Why did RAG decline so often?* Retrieval missed the named papers; top-8 chunks, no author text in chunks. Not tuned after freeze, by design.
- *Is that a fair comparison?* Same corpus, model, prompts and citation rules. RAG was a standard baseline. Fairness limits are in section 5.
- *Does the wiki win?* On these 7 questions with this model, yes on finding and combining papers, no on being fully correct. Not statistically conclusive.
- *Who judged, and how reliable is it?* One blind Claude pass, citations checked against pages, no human spot-check. Section 4 has the sensitivity.
- *What does the wiki cost?* About 5 minutes of ingest per paper, about 2.3x query latency and 2.1x input tokens.
- *When would you pick RAG?* Large or changing corpora, exact lookup, tight budgets. *Wiki?* Small stable corpora, cross-paper synthesis, need to inspect and edit the knowledge.
- *What would you do next?* Tune RAG (hybrid search, author-aware chunks), try a bigger model, add unanswerable questions, run the update demo and measure update cost.
