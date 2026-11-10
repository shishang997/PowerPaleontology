"""PowerPaleontology 文档解析与分块的核心数据模型

本模块定义了文档处理流水线中使用的不可变（frozen）数据结构，
采用「解析层 / 检索层」两层模型：

    原始文档
      └── ParsedDocument          一个完整解析后的文档
            ├── pages: list[Page]       页面几何信息（宽高）
            └── blocks: list[Block]     内容块（段落/标题/表格等）
                  └── bbox: BBox        块在页面上的边界框

    Chunk                         面向检索的文本单元
      └── block_ids: list[str]          引用若干 Block，可跨块合并

两层职责：
- Block 忠实记录解析结果，粒度细、保留 block_type / bbox / section 等结构信息；
- Chunk 由若干 Block 合并或切分而来，粒度适配 embedding 模型，
  并通过 block_ids 回溯到原始 Block，便于定位与高亮引用。

所有 dataclass 均设置 frozen=True，实例创建后字段不可重新赋值；
可变字段（dict / list）使用 default_factory 保证每个实例独立。
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BBox:
    x0: float
    x1: float
    y0: float
    y1: float


@dataclass(frozen=True)
class Page:
    page_no: int
    width: float | None = None
    height: float | None = None


@dataclass(frozen=True)
class Block:
    block_id: str
    page_no: int
    text: str
    block_type: str = "text"
    section: str | None = None
    bbox: BBox | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedDocument:
    document_id: str
    source_path: str
    title: str | None = None
    pages: list[Page] = field(default_factory=list)
    blocks: list[Block] = field(default_factory=list)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    page_no: int
    block_ids: list[str]
    text: str
    section: str | None = None
    bbox: BBox | None = None