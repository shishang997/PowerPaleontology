from __future__ import annotations

import re

from powerpaleontology_core import Block, Chunk, ParsedDocument

from .config import ChunkingConfig
from .normalizer import normalize_blocks


_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?。！？])\s+")


class SemanticBlockChunker:
    """按语义边界合并和切分 Block 的默认 Chunker。"""

    def __init__(self, config: ChunkingConfig | None = None) -> None:
        """初始化分块器。

        参数：
            config: 分块配置；不传时使用默认配置。
        """

        self.config = config or ChunkingConfig()

    def chunk_document(self, document: ParsedDocument) -> list[Chunk]:
        """把解析文档转换为一组可检索的 Chunk。

        参数：
            document: MinerU 解析后的文档。

        返回：
            保留原始 block_ids 的 Chunk 列表。

        异常：
            ValueError:
                document_id 无效，或文档中没有可分块的正文块。
        """

        if not document.document_id.strip():
            raise ValueError("document_id must not be empty")

        blocks = normalize_blocks(
            blocks=document.blocks,
            config=self.config,
        )
        chunkable_blocks = [
            block
            for block in blocks
            if block.block_type in self.config.block_types_to_chunk
        ]

        if not chunkable_blocks:
            raise ValueError("ParsedDocument does not contain chunkable blocks")

        chunks: list[Chunk] = []
        chunk_counter = 1

        for block_group in self._group_blocks(blocks=chunkable_blocks):
            group_text = "\n\n".join(block.text for block in block_group)
            group_section = block_group[0].section

            for piece_text in self._split_text(text=group_text):
                chunk = Chunk(
                    chunk_id=(
                        f"{document.document_id}-chunk-{chunk_counter:04d}"
                    ),
                    document_id=document.document_id,
                    page_no=block_group[0].page_no,
                    block_ids=[block.block_id for block in block_group],
                    text=piece_text,
                    section=group_section,
                    bbox=block_group[0].bbox,
                )
                chunks.append(chunk)
                chunk_counter += 1

        return chunks

    def _group_blocks(self, blocks: list[Block]) -> list[list[Block]]:
        """把相邻且 section 相同的 Block 分组。

        参数：
            blocks: 已经过滤为可分块的 Block 列表。

        返回：
            一个或多个 Block 分组；每组内的 section 保持一致。
        """

        if not self.config.merge_adjacent_blocks:
            return [[block] for block in blocks]

        groups: list[list[Block]] = []
        current_group: list[Block] = []

        for block in blocks:
            if not current_group:
                current_group = [block]
                continue

            previous_block = current_group[-1]

            if block.section == previous_block.section:
                current_group.append(block)
            else:
                groups.append(current_group)
                current_group = [block]

        if current_group:
            groups.append(current_group)

        return groups

    def _split_text(self, text: str) -> list[str]:
        """按语义边界切分文本。

        优先按段落切分；如果段落仍然太长，则继续按换行、句子、空白切分。

        参数：
            text: 待切分文本。

        返回：
            每项长度都不超过配置最大值的文本片段。
        """

        max_characters = self.config.max_chunk_characters
        overlap_characters = self.config.overlap_characters

        if len(text) <= max_characters:
            return [text]

        paragraph_pieces = self._split_and_pack(
            text=text,
            delimiter="\n\n",
        )

        if len(paragraph_pieces) > 1:
            return paragraph_pieces

        line_pieces = self._split_and_pack(
            text=text,
            delimiter="\n",
        )

        if len(line_pieces) > 1:
            return line_pieces

        sentence_pieces = self._split_and_pack(
            text=text,
            delimiter=" ",
            sentence_split=True,
        )

        if len(sentence_pieces) > 1:
            return sentence_pieces

        return self._slice_text(
            text=text,
            max_characters=max_characters,
            overlap_characters=overlap_characters,
        )

    def _split_and_pack(
        self,
        text: str,
        delimiter: str,
        sentence_split: bool = False,
    ) -> list[str]:
        """按指定分隔符切分，并重新打包到最大长度以内。

        参数：
            text: 原始文本。
            delimiter: 分隔符。
            sentence_split: 是否在空白处进一步按句子边界切分。

        返回：
            重新打包后的文本片段列表。
        """

        if sentence_split:
            parts = _SENTENCE_SPLIT_PATTERN.split(text)
        else:
            parts = text.split(delimiter)

        parts = [part.strip() for part in parts if part.strip()]

        if len(parts) <= 1:
            return [text] if len(text) <= self.config.max_chunk_characters else [text]

        pieces: list[str] = []
        current_piece = ""

        for part in parts:
            part_pieces = (
                self._split_text(text=part)
                if len(part) > self.config.max_chunk_characters
                else [part]
            )

            for part_piece in part_pieces:
                candidate = (
                    current_piece + delimiter + part_piece
                    if current_piece
                    else part_piece
                )

                if len(candidate) <= self.config.max_chunk_characters:
                    current_piece = candidate
                    continue

                if current_piece:
                    pieces.append(current_piece)

                suffix = self._take_suffix(
                    text=current_piece,
                    max_characters=self.config.overlap_characters,
                )
                next_piece = suffix + delimiter + part_piece if suffix else part_piece

                if len(next_piece) <= self.config.max_chunk_characters:
                    current_piece = next_piece
                else:
                    current_piece = part_piece

        if current_piece:
            pieces.append(current_piece)

        return pieces

    def _slice_text(
        self,
        text: str,
        max_characters: int,
        overlap_characters: int,
    ) -> list[str]:
        """在没有可用语义边界时执行固定窗口切分。

        参数：
            text: 原始文本。
            max_characters: 单个片段最大长度。
            overlap_characters: 片段之间的重叠长度。

        返回：
            固定窗口切分后的文本片段。
        """

        pieces: list[str] = []
        start = 0

        while start < len(text):
            end = min(len(text), start + max_characters)

            if end < len(text):
                boundary = text.rfind(" ", start, end)

                if boundary > start:
                    end = boundary

            piece = text[start:end].strip()

            if piece:
                pieces.append(piece)

            if end >= len(text):
                break

            if overlap_characters <= 0:
                start = end
            else:
                start = max(start + 1, end - overlap_characters)

        return pieces

    def _take_suffix(self, text: str, max_characters: int) -> str:
        """取文本末尾的少量字符作为下一个片段的上下文。"""

        if max_characters <= 0 or not text:
            return ""

        suffix = text[-max_characters:]
        stripped_suffix = suffix.lstrip()
        return stripped_suffix or ""
