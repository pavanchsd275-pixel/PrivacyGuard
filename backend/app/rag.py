"""
rag.py

Steps 10-11 of the architecture: chunking -> embeddings -> ChromaDB -> retrieval.

It only ever receives the PROTECTED text. Concepts:
  * chunking    - split the document into small passages, because we retrieve
                  passages, not whole documents
  * embedding   - turn each passage into a vector so "similar meaning" becomes
                  "nearby vectors" (sentence-transformers, all-MiniLM-L6-v2)
  * ChromaDB    - stores the vectors and returns the nearest ones to a question
We compute embeddings ourselves and hand them to Chroma, so Chroma never needs
to download a model of its own.
"""

from pathlib import Path

import chromadb

CHROMA_DIR = Path(__file__).resolve().parent.parent / "storage" / "chroma"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def chunk_text(text: str, max_chars: int = 500) -> list[str]:
    """Pack whole lines into chunks of at most max_chars. A line longer than
    max_chars is split on sentence ends. The last line of a chunk is repeated
    at the start of the next one (small overlap) so context isn't cut."""
    pieces: list[str] = []
    for line in (l.strip() for l in text.splitlines()):
        if not line:
            continue
        if len(line) <= max_chars:
            pieces.append(line)
            continue
        current = ""
        for sentence in line.replace("? ", "?|").replace(". ", ".|").replace("! ", "!|").split("|"):
            if current and len(current) + len(sentence) + 1 > max_chars:
                pieces.append(current)
                current = sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            pieces.append(current)

    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for piece in pieces:
        if current and size + len(piece) + 1 > max_chars:
            chunks.append("\n".join(current))
            current, size = ([current[-1]], len(current[-1])) if len(current[-1]) < 120 else ([], 0)
        current.append(piece)
        size += len(piece) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks


class Embedder:
    """Loads the sentence-transformers model on first use (first run downloads ~90 MB)."""

    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self._model = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model.encode(texts, normalize_embeddings=True).tolist()


embedder = Embedder()  # tests swap this for a fake one
_client = None


def _collection_name(doc_id: str) -> str:
    return "doc_" + doc_id.replace("-", "")


def _get_client():
    global _client
    if _client is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client


def index_document(doc_id: str, protected_text: str) -> int:
    client = _get_client()
    name = _collection_name(doc_id)
    try:
        client.delete_collection(name)
    except Exception:
        pass
    chunks = chunk_text(protected_text)
    collection = client.create_collection(name)
    if chunks:
        collection.add(
            ids=[str(i) for i in range(len(chunks))],
            documents=chunks,
            embeddings=embedder.embed(chunks),
        )
    return len(chunks)


def is_indexed(doc_id: str) -> bool:
    try:
        return _get_client().get_collection(_collection_name(doc_id)).count() > 0
    except Exception:
        return False


def retrieve(doc_id: str, question: str, k: int = 4) -> list[str]:
    collection = _get_client().get_collection(_collection_name(doc_id))
    n = min(k, collection.count())
    result = collection.query(query_embeddings=embedder.embed([question]), n_results=n)
    return result["documents"][0]


def keyword_retrieve(protected_text: str, question: str, k: int = 4) -> list[str]:
    """Small local fallback when the optional embedding model cannot load."""
    import re

    terms = {word.lower() for word in re.findall(r"[\w+#.-]+", question) if len(word) > 2}
    lines = [line.strip() for line in protected_text.splitlines() if line.strip()]
    ranked = sorted(enumerate(lines), key=lambda pair: (sum(term in pair[1].lower() for term in terms), -pair[0]), reverse=True)
    matches = [line for _, line in ranked[:k] if not terms or any(term in line.lower() for term in terms)]
    return matches or lines[:k]
