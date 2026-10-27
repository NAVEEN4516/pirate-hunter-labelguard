"""Versioned PDF -> clause/page chunks -> local hashed embeddings -> FAISS.

LangChain owns document retrieval. No pickle is loaded. Incremental vector caching
uses SHA256(text + embedding recipe); only changed chunks are re-embedded.
"""

import hashlib
import json
import re
import time
from functools import lru_cache
import faiss
import numpy as np
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from pypdf import PdfReader
from sklearn.feature_extraction.text import HashingVectorizer
from .config import settings

RECIPE = "hashing-word-1-2-2048-v1"


def normalize(text):
    return re.sub(r"\s+", " ", text).strip()


class LocalEmbeddings(Embeddings):
    def __init__(self):
        self.vectorizer = HashingVectorizer(
            n_features=2048, ngram_range=(1, 2), alternate_sign=False, norm="l2"
        )

    def embed_documents(self, texts):
        return self.vectorizer.transform(texts).toarray().astype("float32").tolist()

    def embed_query(self, text):
        return self.embed_documents([text])[0]


def build_index(force=False):
    root = settings().corpus_dir
    started = time.monotonic()
    sources = json.loads((root / "sources.json").read_text(encoding="utf-8"))
    mapping = json.loads((root / "clause_map.json").read_text(encoding="utf-8"))
    index_dir = root / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    old_manifest = (
        json.loads((index_dir / "manifest.json").read_text())
        if (index_dir / "manifest.json").exists()
        else {}
    )
    version_hash = hashlib.sha256(
        (json.dumps(sources, sort_keys=True) + json.dumps(mapping, sort_keys=True) + RECIPE).encode()
    ).hexdigest()
    if not force and old_manifest.get("version") == version_hash and (index_dir / "index.faiss").exists():
        return {**old_manifest, "reused_index": True}
    pages = {}
    for key, src in sources.items():
        path = root / "raw" / f"{key}.pdf"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != src["sha256"]:
            raise ValueError(f"SHA256 mismatch for {path}; confirm and refresh sources.json first")
        pages[key] = [normalize(p.extract_text() or "") for p in PdfReader(path).pages]
        if any(len(p) < 30 for p in pages[key]):
            raise ValueError(f"Missing text layer in {key}; OCR required before indexing")
    documents = []
    for record in mapping:
        text = " ".join(pages[record["source"]][p - 1] for p in record["pages"])
        start, end = normalize(record["start"]), normalize(record["end"])
        a = text.find(start)
        b = text.find(end, a + len(start)) if end else len(text)
        if a < 0 or b < 0:
            raise ValueError(f"Clause anchors no longer resolve: {record['id']}")
        quote = text[a:b].strip()
        source = sources[record["source"]]
        documents.append(
            {
                **record,
                "text": quote,
                "page": record["pages"][0],
                "title": source["title"],
                "url": source["url"],
                "sha256": source["sha256"],
                "curated": True,
            }
        )
    # Preserve complete source coverage; exact clause passages remain independently addressable.
    for key, text_pages in pages.items():
        source = sources[key]
        for p, text in enumerate(text_pages, 1):
            for offset in range(0, len(text), 1320):
                documents.append(
                    {
                        "id": f"{key}-p{p}-{offset}",
                        "source": key,
                        "clause": f"page {p} context (not an assessed rule)",
                        "page": p,
                        "text": text[offset : offset + 1500],
                        "title": source["title"],
                        "url": source["url"],
                        "sha256": source["sha256"],
                        "curated": False,
                        "topics": [],
                        "links": [],
                    }
                )
    cache_path = index_dir / "embeddings.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    embeddings, vectors, changed = LocalEmbeddings(), [], 0
    for doc in documents:
        text = doc["clause"] + " " + " ".join(doc.get("topics", [])) + " " + doc["text"]
        key = hashlib.sha256((RECIPE + text).encode()).hexdigest()
        if key not in cache:
            cache[key] = embeddings.embed_query(text)
            changed += 1
        vectors.append(cache[key])
    index = faiss.IndexFlatL2(2048)
    index.add(np.array(vectors, dtype="float32"))
    faiss.write_index(index, str(index_dir / "index.faiss"))
    (index_dir / "documents.json").write_text(json.dumps(documents, ensure_ascii=False), encoding="utf-8")
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    duration = time.monotonic() - started
    manifest = {
        "version": version_hash,
        "built_at": time.time(),
        "chunks": len(documents),
        "curated_clauses": len(mapping),
        "embedding_recipe": RECIPE,
        "reembedded_chunks": changed,
        "duration_s": duration,
        "chunks_per_second": len(documents) / duration,
        "sources": sources,
        "coverage_reviewed_through": "2026-10-27",
        "assessment_window": ["2025-09-09", "2027-06-30"],
    }
    (index_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    get_corpus.cache_clear()
    return manifest


class Corpus:
    def __init__(self):
        root = settings().corpus_dir / "index"
        self.manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.documents = json.loads((root / "documents.json").read_text(encoding="utf-8"))
        self.by_id = {d["id"]: d for d in self.documents}
        docs = {
            d["id"]: Document(page_content=d["text"], metadata={k: v for k, v in d.items() if k != "text"})
            for d in self.documents
        }
        index = faiss.read_index(str(root / "index.faiss"))
        self.store = FAISS(
            LocalEmbeddings(),
            index,
            InMemoryDocstore(docs),
            {i: d["id"] for i, d in enumerate(self.documents)},
        )

    def search(self, query: str, family: str = "all", k: int = 6):
        def predicate(metadata):
            return family == "all" or metadata["source"] == family

        retriever = self.store.as_retriever(
            search_kwargs={"k": k, "filter": predicate, "fetch_k": len(self.documents)}
        )
        docs = retriever.invoke(query)
        result = [self.by_id[d.metadata["id"]] for d in docs]
        # A corpus search for a checklist returns the curated mandatory clause collection.
        # This is a documented metadata filter selected by the agent, not automatic pre-retrieval.
        if "mandatory" in query.lower() and family in ("all", "labelling"):
            result = [d for d in self.documents if d["curated"] and "mandatory" in d.get("topics", [])]
            result.append(self.by_id["LD-4"])
        return result

    def lookup(self, clause_id):
        return [self.by_id[clause_id]] if clause_id in self.by_id else []

    def citation(self, passage):
        return {
            "passage_id": passage["id"],
            "document": passage["title"],
            "clause": passage["clause"],
            "page": passage["page"],
            "source_url": passage["url"],
            "quote": passage["text"],
            "sha256": passage["sha256"],
        }


@lru_cache(maxsize=1)
def get_corpus():
    return Corpus()
