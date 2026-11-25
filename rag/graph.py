"""Phase 3: plain RAG as a two-node LangGraph, retrieve -> generate.

One retrieval per question, no rewriting, no re-ranking, no agent loop.
"""
from __future__ import annotations

from typing import TypedDict

from langchain_core.documents import Document
from langgraph.graph import END, START, StateGraph

from common.llm import get_chat, load_config
from common.prompts import ANSWER_PROMPT as PROMPT
from rag.ingest import get_store

class State(TypedDict, total=False):
    question: str
    context: list[Document]
    answer: str


def format_context(docs: list[Document]) -> str:
    return "\n\n".join(f"[{d.metadata['paper_id']}, p.{d.metadata['page']}]\n{d.page_content}" for d in docs)


def build_graph(seed: int, question_id: str | None = None):
    retriever = get_store().as_retriever(search_kwargs={"k": load_config()["rag"]["top_k"]})
    llm = get_chat(seed)
    meta = {"system": "rag", "question_id": question_id, "step": "answer"}

    def retrieve(state: State) -> State:
        return {"context": retriever.invoke(state["question"])}

    def generate(state: State) -> State:
        msgs = PROMPT.invoke({"context": format_context(state["context"]), "question": state["question"]})
        return {"answer": llm.invoke(msgs, config={"metadata": meta}).content}

    g = StateGraph(State)
    g.add_node("retrieve", retrieve)
    g.add_node("generate", generate)
    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", END)
    return g.compile()
