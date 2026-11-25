#!/bin/bash
# Overnight: finish climate ingest, validate, footnote sample, pilot (climate only), ethics ingest (RAG + wiki).
# Run: nohup bash scripts/overnight.sh > runs/overnight.log 2>&1 &
# Stops before freeze, full runs and judging. Per-paper wiki ingest is skipped if sources/<id>.md exists.
cd "$(dirname "$0")/.." || exit 1
ts() { date '+%F %T'; }
say() { echo "[$(ts)] $*"; }
FAILED=()

say "waiting for running wiki.ingest"
while pgrep -f "[w]iki.ingest" >/dev/null; do sleep 30; done

wiki_ingest_missing() {  # $1 = domain
  for pid in $(uv run python -c "
import yaml
for p in yaml.safe_load(open('data/papers.yaml'))['papers']:
    if p['domain']=='$1': print(p['id'])"); do
    if [ -f "wiki/bundle/sources/$pid.md" ]; then say "skip $pid (already in bundle)"; continue; fi
    say "wiki ingest $pid"
    perl -e 'alarm 3600; exec @ARGV' uv run python -m wiki.ingest --paper "$pid" || { say "FAILED $pid"; FAILED+=("$pid"); }
  done
}

say "== climate: finish any missing papers"
wiki_ingest_missing climate-science
say "== validate (climate)"
uv run python wiki/validate.py wiki/bundle > runs/validate_climate.txt 2>&1; echo "validate exit $?" | tee -a runs/validate_climate.txt
say "== footnote sample"
if [ -s runs/footnote_check.md ]; then say "skip (runs/footnote_check.md exists)"; else
uv run python scripts/sample_footnotes.py > runs/footnote_check.md 2>runs/footnote_check.err || say "footnote sample failed"; fi
say "== pilot (climate only, before ethics)"
if [ "$(ls runs/pilot/*.json 2>/dev/null | wc -l)" -ge 6 ]; then say "skip (runs/pilot has 6 files)"; else
uv run python scripts/pilot.py || say "pilot script failed"; fi
say "== RAG ethics ingest"
[ "$(uv run python -c "from rag.ingest import get_store; print(get_store()._collection.count())")" -ge 633 ] && say "skip (RAG collection already has ethics)" || uv run python -m rag.ingest --domain ai-ethics-law || { say "FAILED rag ethics"; FAILED+=("rag-ethics"); }
say "== wiki ethics ingest"
wiki_ingest_missing ai-ethics-law
say "== validate (all)"
uv run python wiki/validate.py wiki/bundle > runs/validate_all.txt 2>&1; echo "validate exit $?" | tee -a runs/validate_all.txt
say "DONE. failures: ${FAILED[*]:-none}"
git -C wiki/bundle log --oneline | wc -l
