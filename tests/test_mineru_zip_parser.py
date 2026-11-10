# =====================================================================
# test_mineru_zip_parser.py
# 这个文件测试 MinerU 结果 zip 到核心 ParsedDocument 的解析逻辑。
#
# 这些测试不访问 MinerU API，不消耗 quota。
# 它们通过在内存中构造 zip 文件来测试 parser.py。
# =====================================================================

import io
import zipfile

import pytest

from powerpaleontology_core import ParsedDocument
from powerpaleontology_mineru_adapter.exceptions import MinerUResultError
from powerpaleontology_mineru_adapter.parser import parse_mineru_zip


def make_mineru_zip(markdown: str) -> bytes:
    """构造一个模拟 MinerU 返回的结果 zip。

    参数：
        markdown:
            要写入 zip 中 full.md 的内容。

    返回：
        zip 文件的二进制内容。
    """

    # 使用内存缓冲区，不需要在磁盘上创建临时文件。
    buffer = io.BytesIO()

    # 创建一个最小化的 MinerU 结果 zip。
    # 这里包含 full.md 和一个 layout.json 占位文件。
    # 当前 parser 只读取 full.md，layout.json 用于模拟真实 zip 结构。
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("full.md", markdown)
        archive.writestr("layout.json", "{}")

    # 返回 zip 的二进制内容。
    return buffer.getvalue()


def test_parses_full_md_into_parsed_document():
    """正常 Markdown 应该能解析成 ParsedDocument。"""

    markdown = """# A new ichthyosaur from the Triassic

## Abstract

This paper describes a new marine reptile specimen.

## Methods

The specimen was prepared and scanned.
"""

    zip_bytes = make_mineru_zip(markdown)

    document = parse_mineru_zip(
        zip_bytes=zip_bytes,
        document_id="doc-001",
        source_path="data/sample.pdf",
    )

    # 返回类型必须是核心文档模型。
    assert isinstance(document, ParsedDocument)

    # 基本文档字段应该被保留。
    assert document.document_id == "doc-001"
    assert document.source_path == "data/sample.pdf"

    # 第一个一级标题可以作为文档标题。
    assert document.title == "A new ichthyosaur from the Triassic"

    # 第一版 parser 会生成一个逻辑页面。
    assert document.pages
    assert document.pages[0].page_no == 1

    # 第一个 Block 应该是标题。
    assert document.blocks
    assert document.blocks[0].block_type == "heading"
    assert document.blocks[0].text == "A new ichthyosaur from the Triassic"

    # Abstract 下的文本块应该能被找到。
    abstract_block = next(
        block
        for block in document.blocks
        if block.section == "Abstract" and block.block_type == "text"
    )
    assert "This paper describes a new marine reptile specimen." in abstract_block.text

    # 当前策略不解析 layout.json，所以 page_no 暂时都是 1。
    assert all(block.page_no == 1 for block in document.blocks)

    # metadata 应该记录来源文件和解析策略。
    assert all(
        block.metadata.get("source_member") == "full.md"
        for block in document.blocks
    )
    assert all(
        block.metadata.get("parser_strategy") == "markdown_v1"
        for block in document.blocks
    )


def test_infers_title_from_first_block_when_no_heading_exists():
    """没有 Markdown 标题时，应该用第一个文本块的第一行作为标题。"""

    markdown = """Plain text title line

The rest of the document follows here.
"""

    zip_bytes = make_mineru_zip(markdown)
    document = parse_mineru_zip(
        zip_bytes=zip_bytes,
        document_id="doc-002",
    )

    assert document.title == "Plain text title line"
    assert document.blocks


def test_raises_error_when_zip_does_not_contain_full_md():
    """zip 中缺少 full.md 时应该抛出 MinerUResultError。"""

    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        # 这个 zip 没有 full.md，parser 应该拒绝。
        archive.writestr("layout.json", "{}")

    with pytest.raises(MinerUResultError, match="does not contain full.md"):
        parse_mineru_zip(
            zip_bytes=buffer.getvalue(),
            document_id="doc-003",
        )


def test_raises_error_when_full_md_is_empty():
    """full.md 内容为空时应该抛出 MinerUResultError。"""

    zip_bytes = make_mineru_zip("   \n   ")

    with pytest.raises(MinerUResultError, match="Markdown result is empty"):
        parse_mineru_zip(
            zip_bytes=zip_bytes,
            document_id="doc-004",
        )
