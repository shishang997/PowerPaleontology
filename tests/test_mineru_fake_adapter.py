# =====================================================================
# test_mineru_fake_adapter.py
# 这个文件测试 FakeMinerUAdapter 的基础行为。
#
# 目标：
# 1. 确认 FakeMinerUAdapter 满足 MinerUAdapter 接口；
# 2. 确认它能返回核心 ParsedDocument；
# 3. 确认同一个输入会生成稳定的 document_id；
# 4. 确认空 URL 会被拒绝。
# =====================================================================

import pytest

from powerpaleontology_core import ParsedDocument
from powerpaleontology_mineru_adapter.base import MinerUAdapter
from powerpaleontology_mineru_adapter.fake import FakeMinerUAdapter


def test_fake_adapter_satisfies_mineru_adapter_protocol():
    """FakeMinerUAdapter 应该满足 MinerUAdapter 结构化接口。"""

    adapter = FakeMinerUAdapter()
    assert isinstance(adapter, MinerUAdapter)


def test_parse_file_returns_core_parsed_document(tmp_path):
    """parse_file 应该返回结构正确的核心 ParsedDocument。"""

    # 创建一个假的本地 PDF 文件。
    # FakeMinerUAdapter 不读取内容，只使用路径生成稳定的测试数据。
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% fake test pdf\n")

    adapter = FakeMinerUAdapter()
    document = adapter.parse_file(pdf_path)

    # 返回类型必须是核心文档模型。
    assert isinstance(document, ParsedDocument)

    # document_id 应该使用默认前缀，方便识别测试数据。
    assert document.document_id.startswith("fake-mineru-doc-")

    # source_path 应该保留输入路径，方便溯源。
    assert document.source_path == str(pdf_path.resolve())

    # fake 文档应该有标题、页面和文本块。
    assert document.title is not None
    assert document.title.startswith("Fake MinerU Result:")
    assert document.pages
    assert document.pages[0].page_no == 1
    assert document.blocks

    # fake 数据里至少应该有一个标题块和摘要章节。
    assert any(block.block_type == "heading" for block in document.blocks)
    assert any(block.section == "Abstract" for block in document.blocks)

    # 所有 fake block 都应该明确标记 is_fake，避免以后误当真实数据。
    assert all(block.metadata.get("is_fake") is True for block in document.blocks)


def test_same_file_path_produces_stable_document_id(tmp_path):
    """同一个输入路径应该生成稳定的 document_id。"""

    pdf_path = tmp_path / "stable.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% stable id test\n")

    adapter = FakeMinerUAdapter()

    first_document = adapter.parse_file(pdf_path)
    second_document = adapter.parse_file(pdf_path)

    assert first_document.document_id == second_document.document_id


def test_parse_url_rejects_empty_url():
    """空 URL 应该被拒绝。"""

    adapter = FakeMinerUAdapter()

    with pytest.raises(ValueError):
        adapter.parse_url("   ")
