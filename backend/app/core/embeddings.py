"""Core embedding generation engine using Sentence Transformers."""

import logging
import math
from typing import List, Optional
from app.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingModelError(Exception):
    """Raised when embedding model fails to load or generate vectors."""
    pass


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return max(-1.0, min(1.0, dot_product / (norm_a * norm_b)))


class EmbeddingGenerator:
    """Singleton lazy-loading sentence-transformer embedding generator."""

    _instance: Optional["EmbeddingGenerator"] = None
    _model = None

    def __init__(self, model_name: Optional[str] = None):
        settings = get_settings()
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self.dimension = settings.EMBEDDING_DIMENSION

    @classmethod
    def get_instance(cls, model_name: Optional[str] = None) -> "EmbeddingGenerator":
        """Return singleton embedding generator instance."""
        if cls._instance is None:
            cls._instance = cls(model_name=model_name)
        return cls._instance

    def _load_model(self):
        """Lazy-load the SentenceTransformer model on demand."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading SentenceTransformer model '{self.model_name}'...")
                self._model = SentenceTransformer(self.model_name)
                logger.info(f"SentenceTransformer model '{self.model_name}' loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load SentenceTransformer model '{self.model_name}': {e}")
                raise EmbeddingModelError(f"Could not load embedding model '{self.model_name}': {e}")
        return self._model

    def generate_embedding(self, text: str) -> List[float]:
        """Generate a single 384-dimensional embedding vector for input text."""
        text_clean = text.strip()
        if not text_clean:
            return [0.0] * self.dimension

        model = self._load_model()
        try:
            vector = model.encode(text_clean, convert_to_numpy=True, normalize_embeddings=True)
            return [float(x) for x in vector.tolist()]
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise EmbeddingModelError(f"Embedding generation failed: {e}")

    def generate_embeddings_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Generate embeddings for a batch of text chunks."""
        if not texts:
            return []

        cleaned_texts = [t.strip() if t.strip() else " " for t in texts]
        model = self._load_model()
        try:
            vectors = model.encode(
                cleaned_texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return [[float(x) for x in v.tolist()] for v in vectors]
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            raise EmbeddingModelError(f"Batch embedding generation failed: {e}")
