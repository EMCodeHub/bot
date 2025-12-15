from typing import Sequence, Tuple

import numpy as np


def normalize_embedding(embedding: Sequence[float], expected_dim: int) -> Tuple[list[float], float]:
    """Ensure the vector has the expected dimension and normalize it."""
    vector = np.array(embedding, dtype=float)
    if vector.ndim != 1 or vector.size != expected_dim:
        raise ValueError(
            f"Embedding dimension {vector.size} does not match expected {expected_dim}"
        )
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm == 0.0:
        raise ValueError("Embedding norm must be finite and non-zero.")
    normalized = (vector / norm).tolist()
    return normalized, norm
