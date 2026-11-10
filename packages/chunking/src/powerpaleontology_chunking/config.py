from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkingConfig:
    """Chunking 模块的统一配置。

    该配置只描述“如何把 Block 转成 Chunk”，不包含具体实现逻辑。
    使用 frozen=True 可以避免流水线运行过程中意外修改配置。
    """

    # 单个 Chunk 的最大字符数。
    # 超过该长度的文本应该在后续实现中继续切分。
    max_chunk_characters: int = 1200

    # 相邻 Chunk 之间的重叠字符数。
    # 适当重叠可以减少句子在切分边界处丢失上下文。
    # 该值必须小于 max_chunk_characters。
    overlap_characters: int = 150

    # 期望的单个 Chunk 最小字符数。
    # 后续实现应优先把过短的相邻 Block 合并，避免产生过多碎片 Chunk。
    min_chunk_characters: int = 200

    # 是否允许把同一 section 内的相邻 Block 合并。
    # True 适合大多数论文文本；False 可用于需要严格按原始 Block 保留的场景。
    merge_adjacent_blocks: bool = True

    # 参与正文分块的 Block 类型。
    # heading 通常作为 section 边界使用，默认不直接参与正文 Chunk。
    block_types_to_chunk: tuple[str, ...] = ("text", "list", "table", "code")

    # 标题 Block 的类型名称。
    # 后续 Chunker 可以根据该类型识别 section 边界。
    heading_block_type: str = "heading"

    def __post_init__(self) -> None:
        """校验配置，避免无效参数进入流水线。"""

        if self.max_chunk_characters <= 0:
            raise ValueError("max_chunk_characters must be greater than 0")

        if self.overlap_characters < 0:
            raise ValueError("overlap_characters must not be negative")

        if self.overlap_characters >= self.max_chunk_characters:
            raise ValueError(
                "overlap_characters must be smaller than max_chunk_characters"
            )

        if self.min_chunk_characters < 0:
            raise ValueError("min_chunk_characters must not be negative")

        if self.min_chunk_characters > self.max_chunk_characters:
            raise ValueError(
                "min_chunk_characters must not be greater than max_chunk_characters"
            )

        if not self.heading_block_type.strip():
            raise ValueError("heading_block_type must not be empty")
