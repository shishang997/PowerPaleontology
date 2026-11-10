import os
from dataclasses import replace
from pathlib import Path

import pytest

from powerpaleontology_mineru_adapter.adapter import MinerUAdapterImpl
from powerpaleontology_mineru_adapter.client import MinerUClient, MinerUClientConfig
from powerpaleontology_core import Block, Page, ParsedDocument


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF_PATH = PROJECT_ROOT / "data" / "1.pdf"
REAL_TESTS_ENABLED = os.getenv("MINERU_ENABLE_REAL_TESTS", "").strip().lower() in {
    "1", "true", "yes", "on"
}

pytestmark = pytest.mark.skipif(
    not REAL_TESTS_ENABLED,
    reason="Set MINERU_ENABLE_REAL_TESTS=1 to run the MinerU integration test",
)


class _StubMinerUClient:
    """不访问网络的 MinerUClient 委托测试替身。"""

    def __init__(self, pdf_path: Path) -> None:
        self.pdf_path = pdf_path

    def parse_file(self, path: Path) -> ParsedDocument:
        assert path == self.pdf_path
        return ParsedDocument(
            document_id="stub-document",
            source_path=str(path),
            title="Stub Title",
            pages=[Page(page_no=1)],
            blocks=[
                Block(
                    block_id="block-1",
                    page_no=1,
                    text="Stub body text",
                )
            ],
        )


def _load_env_file(path: Path) -> None:
    """读取简单的 KEY=VALUE 环境变量文件，并兼容带引号的值。"""

    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_value = value.strip()
        if (
            len(normalized_value) >= 2
            and normalized_value[0] == normalized_value[-1]
            and normalized_value[0] in {'"', "'"}
        ):
            normalized_value = normalized_value[1:-1]
        os.environ.setdefault(key.strip(), normalized_value)


def _create_adapter() -> MinerUAdapterImpl:
    """创建适用于真实集成测试的 Adapter。"""

    _load_env_file(PROJECT_ROOT / ".env")
    os.environ.setdefault("MINERU_TIMEOUT_SECONDS", "1800")

    client_config = MinerUClientConfig.from_env()
    client_config = replace(
        client_config,
        timeout_seconds=1800.0,
        poll_interval_seconds=2.0,
    )
    return MinerUAdapterImpl(client=MinerUClient(config=client_config))


def test_real_parse_file_returns_valid_document():
    """真实解析本地 PDF，并校验最小可用输出。"""

    pdf_path = Path(os.getenv("MINERU_TEST_PDF", str(DEFAULT_PDF_PATH)))
    if not pdf_path.is_file():
        pytest.fail(f"Test PDF does not exist: {pdf_path}")

    with _create_adapter() as adapter:
        document = adapter.parse_file(pdf_path)

    assert document.title and document.title.strip()
    assert document.source_path == str(pdf_path)
    assert document.pages
    assert document.pages[0].page_no is not None
    assert document.blocks
    assert all(str(block.text or "").strip() for block in document.blocks)
    assert all(block.page_no is not None for block in document.blocks)
    assert not any(block.metadata.get("is_fake") for block in document.blocks)


def test_adapter_parse_file_delegates_to_client():
    """Adapter 应该委托 client.parse_file，并在返回前校验结果。"""

    pdf_path = DEFAULT_PDF_PATH
    adapter = MinerUAdapterImpl(client=_StubMinerUClient(pdf_path=pdf_path))

    document = adapter.parse_file(pdf_path)

    assert document.title == "Stub Title"
    assert document.source_path == str(pdf_path)
    assert document.blocks[0].text == "Stub body text"
