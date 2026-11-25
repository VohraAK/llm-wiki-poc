"""Shared answer rules. Used verbatim by the RAG generate step and the wiki answer step."""
from langchain_core.prompts import ChatPromptTemplate

ANSWER_RULES = """You answer questions using only the provided text.

Rules:
- Use only the provided text. Do not use outside knowledge.
- Cite every claim as [<paper-id>, p.<N>], for example [he2023, p.7]. Use one citation per bracket. Cite only paper ids and pages that appear in the provided text.
- If the provided text does not cover the question, say exactly: The documents don't cover this.
- If part of the question's premise is not supported by the text, say so instead of accepting it."""

ANSWER_PROMPT = ChatPromptTemplate.from_messages(
    [("system", ANSWER_RULES), ("human", "Text:\n\n{context}\n\nQuestion: {question}")]
)
