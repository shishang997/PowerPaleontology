from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from powerpaleontology_core import Chunk


@runtime_checkable
class EmbeddingAdapter(Protocol):
    """Embedding 适配器的统一接口。"""

    def get_dimension(self) -> int:
        """返回当前模型输出的向量维度。"""

        ...

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """把文本列表转换为向量列表。"""

        ...

    def embed_chunks(self, chunks: Sequence[Chunk]) -> list[list[float]]:
        """把 Chunk 列表转换为向量列表。"""

        ...
