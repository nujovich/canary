"""Embedding-based drift: detect semantic deviation in reasoning chains."""

import numpy as np
from typing import List


class EmbeddingDriftDetector:
    """Compare reasoning embeddings against a baseline to detect semantic drift.

    Uses cosine similarity between current reasoning traces and a stored
    baseline of "normal" reasoning patterns.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", threshold: float = 0.15):
        self.threshold = threshold
        self._model = None
        self._model_name = model_name
        self.baseline_embeddings: np.ndarray | None = None

    @property
    def model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Run: pip install sentence-transformers"
                )
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def encode(self, texts: List[str]) -> np.ndarray:
        """Encode reasoning texts into embeddings."""
        return self.model.encode(texts, show_progress_bar=False)

    def set_baseline(self, baseline_texts: List[str]) -> None:
        """Set the baseline reasoning patterns (e.g., first week of production)."""
        self.baseline_embeddings = self.encode(baseline_texts)

    def score(self, current_texts: List[str]) -> float:
        """Return drift score [0, 1]. 0 = identical, 1 = completely drifted.

        Uses 1 - mean cosine similarity between current embeddings and
        the centroid of the baseline.
        """
        if self.baseline_embeddings is None:
            raise ValueError("Baseline not set. Call set_baseline() first.")

        current_embeddings = self.encode(current_texts)
        baseline_centroid = self.baseline_embeddings.mean(axis=0)

        similarities = np.dot(current_embeddings, baseline_centroid) / (
            np.linalg.norm(current_embeddings, axis=1) * np.linalg.norm(baseline_centroid)
        )
        drift_score = float(1 - similarities.mean())
        return max(0.0, min(1.0, drift_score))

    def is_drifted(self, current_texts: List[str]) -> tuple[bool, float]:
        """Return (drifted_bool, score)."""
        score = self.score(current_texts)
        return score > self.threshold, score
