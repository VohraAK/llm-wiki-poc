"""The one configured ChatOllama and OllamaEmbeddings, plus JSONL call logging.

Every generation step in both systems goes through get_chat(). Settings come from
config.yaml. Only the seed varies per run. Each call appends one line to
runs/llm_log.jsonl: model, settings, prompt hash, tokens in/out, latency.

Tag a call with config={"metadata": {"system": "rag", "question_id": "...", "step": "..."}};
the tags are copied into the log line.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from langchain_core.callbacks import BaseCallbackHandler
from langchain_ollama import ChatOllama, OllamaEmbeddings

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "runs" / "llm_log.jsonl"


def load_config() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text())


class JsonlLogger(BaseCallbackHandler):
    def __init__(self, settings: dict, path: Path = LOG_PATH):
        self.settings = settings
        self.path = path
        self._start: dict[Any, dict] = {}

    def on_chat_model_start(self, serialized, messages, *, run_id, metadata=None, **kwargs):
        text = "\n".join(f"{m.type}:{m.content}" for m in messages[0])
        self._start[run_id] = {
            "t0": time.perf_counter(),
            "prompt_hash": hashlib.sha256(text.encode()).hexdigest()[:12],
            "tags": {k: v for k, v in (metadata or {}).items() if k in ("system", "question_id", "step", "run", "paper_id")},
        }

    def on_llm_end(self, response, *, run_id, **kwargs):
        s = self._start.pop(run_id, None)
        if s is None:
            return
        msg = response.generations[0][0].message
        usage = getattr(msg, "usage_metadata", None) or {}
        self._write(
            {
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "latency_s": round(time.perf_counter() - s["t0"], 3),
                "prompt_hash": s["prompt_hash"],
                "tokens_in": usage.get("input_tokens"),
                "tokens_out": usage.get("output_tokens"),
                "ok": True,
                **s["tags"],
                **self.settings,
            }
        )

    def on_llm_error(self, error, *, run_id, **kwargs):
        s = self._start.pop(run_id, None)
        if s is not None:
            self._write({"ok": False, "error": repr(error)[:300], "prompt_hash": s["prompt_hash"], **s["tags"]})

    def _write(self, rec: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(rec) + "\n")


def get_chat(seed: int) -> ChatOllama:
    """The single configured chat model. Thinking is off (NOTES.md, decision 5)."""
    cfg = load_config()
    llm = cfg["llm"]
    settings = {
        "model": cfg["models"]["chat"],
        "temperature": llm["temperature"],
        "num_ctx": llm["num_ctx"],
        "thinking": llm["thinking"],
        "seed": seed,
    }
    return ChatOllama(
        model=cfg["models"]["chat"],
        temperature=llm["temperature"],
        num_ctx=llm["num_ctx"],
        reasoning=llm["thinking"],
        seed=seed,
        callbacks=[JsonlLogger(settings)],
    )


def get_embeddings() -> OllamaEmbeddings:
    return OllamaEmbeddings(model=load_config()["models"]["embed"])
