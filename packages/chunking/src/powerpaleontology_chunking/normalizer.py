from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import replace

from powerpaleontology_core import Block

from .config import ChunkingConfig


_MULTIPLE_BLANK_LINES = re.compile(r"\n{3,}")
_MULTIPLE_WHITESPACES = re.compile(r"\s+")
_ZERO_WIDTH_CHARACTERS = ("\u200b", "\u200c", "\u200d", "\ufeff")


def _clean_text(text: str) -> str:
    """清理 Block 中的常见空白和不可见字符。

    参数：
        text: 原始 Block 文本。

    返回：
        统一换行符并去掉首尾空白后的文本。
    """

    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized_text = normalized_text.replace("\u00a0", " ")

    for character in _ZERO_WIDTH_CHARACTERS:
        normalized_text = normalized_text.replace(character, "")

    lines = [line.rstrip() for line in normalized_text.split("\n")]
    cleaned_text = "\n".join(lines).strip()
    cleaned_text = _MULTIPLE_BLANK_LINES.sub("\n\n", cleaned_text)
    return cleaned_text


def _normalize_section(value: str | None) -> str | None:
    """归一化 section 名称。

    参数：
        value: 原始 section 名称，可能包含多余空白。

    返回：
        去掉首尾空白并压缩空白后的 section 名称；无效时返回 None。
    """

    if value is None:
        return None

    normalized_value = _MULTIPLE_WHITESPACES.sub(" ", value).strip()
    return normalized_value or None


def normalize_blocks(
    blocks: Iterable[Block],
    config: ChunkingConfig | None = None,
) -> list[Block]:
    """清理 Block，并让每个 Block 都带有可用的 section 信息。

    处理规则：

    1. 空文本 Block 会被丢弃；
    2. 换行符统一为 LF；
    3. 不可见空白字符会被清理；
    4. heading Block 会更新当前 section；
    5. 普通 Block 如果缺少 section，会继承最近的 heading section；
    6. 如果普通 Block 已带 section，则只做空白归一化。

    参数：
        blocks: 待清理的 Block 列表。
        config: Chunking 配置；不传时使用默认配置。

    返回：
        清理后的 Block 列表。
    """

    effective_config = config or ChunkingConfig()
    current_section: str | None = None
    normalized_blocks: list[Block] = []

    for block in blocks:
        cleaned_text = _clean_text(block.text)

        if not cleaned_text:
            continue

        if block.block_type == effective_config.heading_block_type:
            normalized_section = _normalize_section(cleaned_text)

            if normalized_section is None:
                continue

            current_section = normalized_section
            section = normalized_section
        else:
            normalized_section = _normalize_section(block.section)

            if normalized_section is not None:
                current_section = normalized_section
                section = normalized_section
            else:
                section = current_section

        normalized_blocks.append(
            replace(
                block,
                text=cleaned_text,
                section=section,
                metadata=dict(block.metadata),
            )
        )

    return normalized_blocks
