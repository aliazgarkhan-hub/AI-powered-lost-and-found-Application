"""
Text similarity abstraction layer.

Tries, in order:
  1. sentence-transformers embeddings + cosine similarity (best quality)
  2. scikit-learn TF-IDF + cosine similarity (no heavy model download needed)
  3. difflib.SequenceMatcher ratio (zero dependencies, always works)

This means the app runs and produces *real* (not hard-coded) similarity
scores even with no internet access and no ML libraries installed at all.
"""
from __future__ import annotations
from difflib import SequenceMatcher
from functools import lru_cache


class TextSimilarityEngine:
    def __init__(self):
        self._mode = "difflib"
        self._model = None
        self._vectorizer = None
        self._try_load_sentence_transformers()

    def _try_load_sentence_transformers(self):
        try:
            from sentence_transformers import SentenceTransformer  # noqa
            from app.config import settings
            self._model = SentenceTransformer(settings.TEXT_SIMILARITY_MODEL)
            self._mode = "sentence-transformers"
        except Exception:
            self._try_load_sklearn()

    def _try_load_sklearn(self):
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer  # noqa
            self._mode = "tfidf"
        except Exception:
            self._mode = "difflib"

    @property
    def mode(self) -> str:
        return self._mode

    def similarity(self, text_a: str | None, text_b: str | None) -> float:
        """Return a similarity score in [0, 1]. Returns 0.0 if either text is empty."""
        a = (text_a or "").strip()
        b = (text_b or "").strip()
        if not a or not b:
            return 0.0

        if self._mode == "sentence-transformers":
            return self._sbert_similarity(a, b)
        if self._mode == "tfidf":
            return self._tfidf_similarity(a, b)
        return self._difflib_similarity(a, b)

    def _sbert_similarity(self, a: str, b: str) -> float:
        import numpy as np
        embeddings = self._model.encode([a, b])
        v1, v2 = embeddings[0], embeddings[1]
        denom = (np.linalg.norm(v1) * np.linalg.norm(v2))
        if denom == 0:
            return 0.0
        cos = float(np.dot(v1, v2) / denom)
        # cosine can be slightly negative for unrelated text; clamp to [0,1]
        return max(0.0, min(1.0, cos))

    def _tfidf_similarity(self, a: str, b: str) -> float:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        try:
            vect = TfidfVectorizer(stop_words="english").fit([a, b])
            matrix = vect.transform([a, b])
            score = cosine_similarity(matrix[0], matrix[1])[0][0]
            return max(0.0, min(1.0, float(score)))
        except ValueError:
            # e.g. both strings are entirely stop-words -> fall back
            return self._difflib_similarity(a, b)

    def _difflib_similarity(self, a: str, b: str) -> float:
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()


@lru_cache(maxsize=1)
def get_text_similarity_engine() -> TextSimilarityEngine:
    return TextSimilarityEngine()
