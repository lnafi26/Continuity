"""Local text embeddings for Stage 4, using sentence-transformers.

Wraps the all-MiniLM-L6-v2 model (384-dim, normalized) so the rest of the code
never imports the ML stack directly. The model is loaded lazily and cached, so
importing this module is cheap and the (slow) first load only happens when
embeddings are actually requested.
"""

from __future__ import annotations

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384

_model = None


def _get_model():
    """Load and cache the SentenceTransformer model on first use."""
    global _model
    if _model is None:
        # Imported here (not at module top) so importing this file does not pull
        # in PyTorch until embeddings are actually needed.
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return one 384-dim, L2-normalized embedding per input text.

    Normalized embeddings mean cosine similarity equals a dot product, which
    matches the cosine operator class used by the pgvector index.
    """
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return [vector.tolist() for vector in vectors]


def embed_text(text: str) -> list[float]:
    """Embed a single text; convenience wrapper over embed_texts."""
    return embed_texts([text])[0]


def build_embedding_input(title: str | None, text: str | None, limit: int = 2000) -> str:
    """Combine title + cleaned body into the string that gets embedded."""
    parts = [p.strip() for p in (title, text) if p and p.strip()]
    combined = "\n".join(parts)
    return combined[:limit] if combined else ""
