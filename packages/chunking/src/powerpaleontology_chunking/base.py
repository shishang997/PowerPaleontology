from __future__ import annotations

from typing import Protocol, runtime_checkable

from powerpaleontology_core import Chunk, ParsedDocument


@runtime_checkable
class Chunker(Protocol):
    """Turn a parsed document into retrieval-oriented chunks."""

    def chunk_document(self, document: ParsedDocument) -> list[Chunk]:
        """Convert all usable blocks in a document into chunks.

        Args:
            document: A normalized MinerU parsing result.

        Returns:
            Chunks retaining traceable block IDs and document ownership.

        Raises:
            ValueError: If the document cannot produce valid chunks.
        """
        ...
