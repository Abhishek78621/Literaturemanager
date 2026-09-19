"""
embeddings.py
-------------
Local, offline semantic search.

Per the spec (section 7), semantic search must work without an internet
connection and must NOT require a local LLM -- only a lightweight embedding
model. Two backends are supported:

1. SentenceTransformerBackend (preferred): uses `sentence-transformers`
   (e.g. all-MiniLM-L6-v2, ~80MB). Needs internet the *first* time to
   download the model; after that it runs fully offline. Produces true
   semantic embeddings (understands synonyms/paraphrasing).

2. HashingBackend (automatic fallback, zero setup): uses scikit-learn's
   HashingVectorizer + TF-IDF re-weighting. Works fully offline from the
   very first run with no download, no corpus-wide fitting step (so it
   scales incrementally as papers are added one at a time). It's a weaker
   "bag of words" style similarity rather than true semantic understanding,
   but it satisfies the offline requirement and is a reasonable MVP default.

Swap backends any time via EMBEDDING_BACKEND env var: "auto" (default),
"sentence_transformers", or "hashing".
"""

import os
import numpy as np

_BACKEND_CHOICE = os.environ.get("EMBEDDING_BACKEND", "auto")

_model = None
_backend_name = None


def _init_backend():
    global _model, _backend_name
    if _model is not None:
        return

    if _BACKEND_CHOICE in ("auto", "sentence_transformers"):
        try:
            from sentence_transformers import SentenceTransformer
            import sys
            import os
            model_name = "all-MiniLM-L6-v2"
            
            if getattr(sys, "frozen", False):
                # When packaged as an EXE, load the bundled offline model
                bundled_path = os.path.join(sys._MEIPASS, "models", model_name)
                _model = SentenceTransformer(bundled_path, local_files_only=True)
            else:
                _model = SentenceTransformer(model_name)
                
            _backend_name = "sentence_transformers"
            return
        except Exception:
            if _BACKEND_CHOICE == "sentence_transformers":
                raise
            # fall through to hashing backend

    from sklearn.feature_extraction.text import HashingVectorizer
    _model = HashingVectorizer(n_features=512, alternate_sign=False, norm="l2")
    _backend_name = "hashing"


def backend_name() -> str:
    """Returns the backend name, initializing the model if not already done."""
    _init_backend()
    return _backend_name


def backend_name_lazy() -> str:
    """Returns the backend name WITHOUT triggering model initialization.
    Safe to call on lightweight pages (e.g. Settings) where the model
    doesn't need to be loaded just to display status information."""
    if _backend_name is not None:
        return _backend_name
    # Peek which backend *would* be used without loading it
    if _BACKEND_CHOICE in ("auto", "sentence_transformers"):
        try:
            import importlib.util
            if importlib.util.find_spec("sentence_transformers") is not None:
                return "sentence_transformers (not yet loaded)"
        except Exception:
            pass
        return "hashing (not yet loaded)"
    return "hashing (not yet loaded)"


def embed_text(text: str) -> list:
    """Return a plain python list of floats representing the embedding."""
    _init_backend()
    text = (text or "").strip() or "empty document"

    if _backend_name == "sentence_transformers":
        vec = _model.encode(text, normalize_embeddings=True)
        return vec.tolist()
    else:
        vec = _model.transform([text]).toarray()[0]
        return vec.tolist()


def paper_searchable_text(paper: dict) -> str:
    """
    Builds the combined representation recommended in section 12 of the spec:
    title + abstract + technical summary + simple explanation + keywords + domain.
    """
    parts = [
        paper.get("title") or "",
        paper.get("abstract") or "",
        paper.get("technical_summary") or "",
        paper.get("simple_explanation") or "",
        paper.get("keywords") or "",
        " ".join(paper.get("domains") or []),
    ]
    return "\n".join(p for p in parts if p)


def cosine_sim(a, b) -> float:
    a = np.array(a)
    b = np.array(b)
    if a.shape != b.shape:
        # Can happen if the embedding backend changed (e.g. you installed
        # sentence-transformers after some papers were already embedded with
        # the offline hashing fallback) so vector sizes don't match. Rather
        # than crash the whole search, treat this one paper as "no match" --
        # the fix is to rebuild the index (see Settings page).
        return 0.0
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def semantic_search(query: str, candidates: list, top_k: int = 10):
    """
    candidates: list of (paper_id, title, vector)
    Returns list of (paper_id, title, score) sorted by descending score.
    """
    if not candidates:
        return []
    q_vec = embed_text(query)
    scored = [(pid, title, cosine_sim(q_vec, vec)) for pid, title, vec in candidates]
    scored.sort(key=lambda x: x[2], reverse=True)
    return scored[:top_k]
