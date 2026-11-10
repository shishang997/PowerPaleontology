# =====================================================================
# fake.py
# 这个文件实现一个假的 MinerU Adapter。
#
# 它的目的不是访问真实的 MinerU 服务，而是：
# 1. 在没有网络的情况下测试项目流程；
# 2. 在没有 MinerU API Key 的情况下测试下游模块；
# 3. 让 chunking、embedding、GeoGPT Adapter 可以先独立开发；
# 4. 返回一个结构正确的 ParsedDocument。
#
# 这个类实现的是 base.py 中定义的 MinerUAdapter 接口。
# 它不会真正解析 PDF，也不会调用任何外部 API。
# =====================================================================

# 启用现代化类型注解。
from __future__ import annotations

# hashlib 用于根据文件路径或 URL 生成稳定的假 document_id。
# 这样同一个输入每次都会得到相同的 document_id，方便测试。
import hashlib

# Path 用于表示本地文件路径。
from pathlib import Path

# 导入项目核心模型。
# FakeMinerUAdapter 最终返回的是项目内部统一的 ParsedDocument。
from powerpaleontology_core import BBox, Block, Page, ParsedDocument


class FakeMinerUAdapter:
    """假的 MinerU Adapter。

    这个类模拟真实 MinerUAdapter 的行为：

        输入本地 PDF 路径或远程 URL
        -> 返回 ParsedDocument

    但它不会：
    - 调用 MinerU API；
    - 上传文件；
    - 轮询任务；
    - 下载结果 zip；
    - 解析真实 PDF。

    它适合在项目早期用于：
    - 单元测试；
    - 手工测试；
    - 先跑通 chunking / embedding / GeoGPT 流程。
    """

    def __init__(
        self,
        document_id_prefix: str = "fake-mineru-doc",
    ) -> None:
        """初始化 FakeMinerUAdapter。

        参数：
            document_id_prefix:
                假 document_id 的前缀。

                默认是 "fake-mineru-doc"。

                最终生成的 document_id 形如：
                    fake-mineru-doc-3f8a1c2b4d5e

                这样可以在测试数据里一眼看出这是一个 fake 文档。
        """

        # 保存前缀，后面生成 document_id 时会用到。
        self.document_id_prefix = document_id_prefix

    def parse_file(self, path: Path) -> ParsedDocument:
        """模拟解析本地 PDF。

        参数：
            path:
                本地 PDF 路径。

                真实 MinerUAdapter 会把这个文件上传给 MinerU，
                但 FakeMinerUAdapter 只是用它生成稳定 ID 和 source_path。

        返回：
            ParsedDocument:
                一个结构正确、内容固定的假解析结果。
        """

        # 把传入的路径转换成绝对路径字符串。
        #
        # 例如：
        #   Path("data/sample.pdf")
        # 会被转换成类似：
        #   "D:/.../PowerPaleontology/data/sample.pdf"
        #
        # 这不是为了访问文件，而是为了让测试输出里的 source_path 更清晰。
        normalized_path = path.expanduser().resolve()

        # 根据路径生成稳定的 document_id。
        # 同一个文件路径每次都会得到相同 ID。
        document_id = self._make_document_id(str(normalized_path))

        # 生成一个假的文档标题。
        # 使用文件名可以让测试输出更直观。
        title = f"Fake MinerU Result: {normalized_path.name}"

        # 构造并返回 ParsedDocument。
        return self._build_parsed_document(
            document_id=document_id,
            source_path=str(normalized_path),
            title=title,
            source_kind="local_file",
        )

    def parse_url(self, url: str) -> ParsedDocument:
        """模拟解析远程 PDF URL。

        参数：
            url:
                远程 PDF 地址。

                真实 MinerUAdapter 会把这个 URL 提交给 MinerU，
                但 FakeMinerUAdapter 只是用它生成稳定 ID 和 source_path。

        返回：
            ParsedDocument:
                一个结构正确、内容固定的假解析结果。
        """

        # 简单校验 URL 不能为空。
        # 这里不做复杂 URL 解析，因为 fake 版本不真正访问网络。
        if not url.strip():
            raise ValueError("url must not be empty")

        # 根据远程 URL 生成稳定 document_id。
        # 同一个 URL 每次都会生成同一个 ID。
        document_id = self._make_document_id(url)

        # 生成一个假标题。
        # 真实场景中标题通常会来自 PDF 元数据或 MinerU 解析结果。
        title = f"Fake MinerU Result: {url}"

        # 构造并返回 ParsedDocument。
        return self._build_parsed_document(
            document_id=document_id,
            source_path=url,
            title=title,
            source_kind="remote_url",
        )

    def _make_document_id(self, source: str) -> str:
        """根据来源路径或 URL 生成稳定的假 document_id。

        参数：
            source:
                本地文件路径字符串，或者远程 URL 字符串。

        返回：
            稳定的 document_id 字符串。

        说明：
            这里使用 SHA256 的前 12 位即可。
            FakeMinerUAdapter 不需要数据库级唯一性保证。
        """

        # 对 source 字符串计算 SHA256。
        # encode("utf-8") 是为了支持中文路径和特殊字符。
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()

        # 截取前 12 位，生成较短且可读的 ID。
        short_digest = digest[:12]

        # 拼接前缀和短哈希。
        return f"{self.document_id_prefix}-{short_digest}"

    def _build_parsed_document(
        self,
        document_id: str,
        source_path: str,
        title: str,
        source_kind: str,
    ) -> ParsedDocument:
        """构造一个完整的假 ParsedDocument。

        参数：
            document_id:
                当前假文档的 ID。

            source_path:
                本地文件路径或远程 URL。

            title:
                假文档标题。

            source_kind:
                来源类型，例如：
                - local_file
                - remote_url

        返回：
            ParsedDocument:
                包含 Page 和 Block 的完整核心模型。
        """

        # 创建一个假的 Page。
        #
        # 宽度 612、高度 792 大约对应 Letter 页面大小。
        # 这里只是为了让 fake 数据更像真实页面。
        page = Page(
            page_no=1,
            width=612.0,
            height=792.0,
        )

        # 创建几个稳定的假 Block。
        #
        # 这些 Block 模拟真实论文中的常见结构：
        # - 标题
        # - 摘要
        # - 方法
        # - 结果
        #
        # 后续 chunking 可以把这些 Block 合并或切分成 Chunk。
        blocks = [
            self._make_block(
                document_id=document_id,
                block_counter=1,
                text=title,
                block_type="heading",
                section=title,
            ),
            self._make_block(
                document_id=document_id,
                block_counter=2,
                text=(
                    "This fake abstract describes a palaeontological specimen. "
                    "It is used to test the PowerPaleontology parsing pipeline."
                ),
                block_type="text",
                section="Abstract",
            ),
            self._make_block(
                document_id=document_id,
                block_counter=3,
                text=(
                    "The fake method section describes how the specimen was collected "
                    "and how the parsing pipeline was tested."
                ),
                block_type="text",
                section="Methods",
            ),
            self._make_block(
                document_id=document_id,
                block_counter=4,
                text=(
                    "The fake result section reports that the pipeline successfully "
                    "produced structured blocks and preserved provenance metadata."
                ),
                block_type="text",
                section="Results",
            ),
        ]

        # 组装核心 ParsedDocument。
        return ParsedDocument(
            document_id=document_id,
            source_path=source_path,
            title=title,
            pages=[page],
            blocks=blocks,
            # ParsedDocument 目前没有额外 metadata 字段。
            # 如果以后 core 模型增加 document metadata，可以在这里补充。
        )

    def _make_block(
        self,
        document_id: str,
        block_counter: int,
        text: str,
        block_type: str,
        section: str,
    ) -> Block:
        """构造一个假 Block。

        参数：
            document_id:
                所属文档 ID。

            block_counter:
                Block 序号，从 1 开始。

            text:
                Block 文本内容。

            block_type:
                Block 类型，例如：
                - heading
                - text

            section:
                所属章节。

        返回：
            Block:
                项目核心 Block 模型。
        """

        # 生成一个简单、稳定、可读的 block_id。
        #
        # 格式：
        # {document_id}-page-1-block-{四位序号}
        #
        # 例如：
        # fake-mineru-doc-1234567890ab-page-1-block-0001
        block_id = f"{document_id}-page-1-block-{block_counter:04d}"

        # 生成一个假的 bbox。
        #
        # 真实 MinerU 会返回文本在 PDF 页面中的坐标。
        # 这里按序号在页面上纵向排列，模拟多个文本块的位置。
        #
        # 页面宽 612，高 792。
        # 左边距 72，右边距到 540。
        # 每个 Block 高度 60，间隔 20。
        y0 = 80.0 + (block_counter - 1) * 80.0
        y1 = y0 + 60.0

        bbox = BBox(
            x0=72.0,
            y0=y0,
            x1=540.0,
            y1=y1,
        )

        # 返回核心 Block。
        return Block(
            block_id=block_id,
            page_no=1,
            text=text,
            block_type=block_type,
            section=section,
            bbox=bbox,
            metadata={
                # 标明这是 fake adapter 生成的数据。
                "parser": "fake_mineru_adapter",
                # 标明解析策略，方便以后排查测试数据来源。
                "parser_strategy": "fixed_sample_v1",
                # 标明这不是真实 MinerU 结果，避免以后误当作生产数据。
                "is_fake": True,
            },
        )