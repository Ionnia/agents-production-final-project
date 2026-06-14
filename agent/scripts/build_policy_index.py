from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_gigachat import GigaChatEmbeddings


ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "data" / "documents"
INDEX_DIR = ROOT / "data" / "indexes" / "policy_chroma"
COLLECTION_NAME = "policy_docs"


def split_markdown(path: Path) -> list[Document]:
    text = path.read_text(encoding="utf-8")
    main_title = path.stem
    match = re.search(r"^#\s+(.+)$", text, re.M)
    if match:
        main_title = match.group(1).strip()

    sections = re.split(r"(?m)^##\s+", text)
    docs = []
    for idx, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue
        if idx == 0 and section.startswith("#"):
            continue
        lines = section.splitlines()
        title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        if not body:
            continue
        docs.append(
            Document(
                page_content=f"{main_title}\n\n## {title}\n{body}",
                metadata={
                    "source": path.name,
                    "section": title,
                    "chunk_id": f"{path.stem}:{idx}",
                },
            )
        )
    return docs


def main() -> None:
    load_dotenv(ROOT / ".env")
    credentials = os.getenv("GIGACHAT_CREDENTIALS")
    if not credentials:
        raise RuntimeError("GIGACHAT_CREDENTIALS не найден. Создай .env по .env.example.")

    docs = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        docs.extend(split_markdown(path))

    if INDEX_DIR.exists():
        shutil.rmtree(INDEX_DIR)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    embeddings = GigaChatEmbeddings(
        credentials=credentials,
        scope=os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"),
        model=os.getenv("GIGACHAT_EMBEDDINGS_MODEL", "EmbeddingsGigaR"),
        verify_ssl_certs=False,
    )
    client = chromadb.PersistentClient(path=str(INDEX_DIR))
    Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        client=client,
        collection_name=COLLECTION_NAME,
    )

    print(f"Indexed policy chunks: {len(docs)}")
    print(f"Index directory: {INDEX_DIR}")


if __name__ == "__main__":
    main()
