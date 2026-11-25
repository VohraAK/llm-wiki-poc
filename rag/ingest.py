"""Phase 3 ingest: data/md pages -> chunks -> embeddings -> Chroma.

    uv run python -m rag.ingest [--domain climate-science]

Chunks are split per page, so each keeps one exact page number. Chunk ids are
<paper-id>-p<page>-c<n>. A paper's old chunks are deleted before it is re-added, so
re-running leaves the collection size unchanged.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from common.llm import ROOT, get_embeddings, load_config
from common.load_pdfs import PAPERS_YAML, read_markdown_pages

COLLECTION = "corpus"


def get_store() -> Chroma:
    cfg = load_config()["rag"]
    return Chroma(
        collection_name=COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=str(ROOT / cfg["chroma_dir"]),
    )


def chunk_paper(paper: dict, splitter: RecursiveCharacterTextSplitter) -> list[Document]:
    chunks: list[Document] = []
    for page, text in read_markdown_pages(paper["id"]):
        for n, piece in enumerate(splitter.split_text(text)):
            chunks.append(
                Document(
                    page_content=piece,
                    metadata={
                        "paper_id": paper["id"],
                        "domain": paper["domain"],
                        "page": page,
                        "chunk_id": f"{paper['id']}-p{page}-c{n}",
                    },
                )
            )
    return chunks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", help="only ingest papers from this domain")
    args = ap.parse_args()

    cfg = load_config()["rag"]
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=cfg["chunk_size"], chunk_overlap=cfg["chunk_overlap"]
    )
    papers = yaml.safe_load(PAPERS_YAML.read_text())["papers"]
    if args.domain:
        papers = [p for p in papers if p["domain"] == args.domain]

    store = get_store()
    for p in papers:
        chunks = chunk_paper(p, splitter)
        store.delete(where={"paper_id": p["id"]})
        store.add_documents(chunks, ids=[c.metadata["chunk_id"] for c in chunks])
        print(f"{p['id']:<14} {len(chunks):>4} chunks")
    print(f"collection size: {store._collection.count()}")


if __name__ == "__main__":
    main()
