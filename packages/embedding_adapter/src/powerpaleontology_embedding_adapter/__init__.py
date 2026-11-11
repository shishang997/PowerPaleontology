from .base import EmbeddingAdapter
from .config import EmbeddingConfig
from .exceptions import (
    EmbeddingConfigError,
    EmbeddingError,
    EmbeddingInputError,
    EmbeddingModelError,
)
from .fake import FakeEmbeddingAdapter
from .local import OllamaEmbeddingAdapter
from .remote import OpenAICompatibleEmbeddingAdapter

__all__ = [
    "EmbeddingAdapter",
    "EmbeddingConfig",
    "EmbeddingConfigError",
    "EmbeddingError",
    "EmbeddingInputError",
    "EmbeddingModelError",
    "FakeEmbeddingAdapter",
    "OllamaEmbeddingAdapter",
    "OpenAICompatibleEmbeddingAdapter",
]
