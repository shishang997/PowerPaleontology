# =====================================================================
# adapter.py
# 这个文件是 MinerU Adapter 的真实实现层。
#
# 它的位置在项目架构里是：
#
#     worker / API / tests
#         -> MinerUAdapter 接口
#         -> MinerUAdapterImpl
#         -> MinerUClient
#         -> MinerU HTTP API
#
# 它的作用：
# 1. 对上层隐藏 MinerU HTTP 细节；
# 2. 让 worker 不需要知道 task_id、轮询、zip 下载等逻辑；
# 3. 保持和 FakeMinerUAdapter 相同的使用方式；
# 4. 后续如果 MinerU API 变化，只需要改 client.py 或 parser.py。
#
# 当前版本：
# - parse_url 已经可用；
# - parse_file 已经通过 client.py 的本地上传批次流程实现。
# =====================================================================

# 启用现代化类型注解。
from __future__ import annotations

# pathlib.Path 用于表示本地 PDF 文件路径。
# parse_file 接口的参数就是 Path。
from pathlib import Path

# 导入核心文档模型。
# MinerUAdapter 的两个方法最终都返回 ParsedDocument。
from powerpaleontology_core import ParsedDocument

# 导入 base.py 中定义的接口。
# 这里不是为了继承，而是为了保持架构上的对应关系。
# Python Protocol 是结构化接口，只要方法匹配即可。
from .base import MinerUAdapter

# 导入真实 HTTP client。
# adapter 不自己写 HTTP 请求，而是委托给 client.py。
from .client import MinerUClient

# 导入项目自己的 MinerU 异常。
# 输出校验失败时抛出 MinerUResultError，
# 保持 Adapter 层的错误类型统一。
from .exceptions import MinerUResultError


class MinerUAdapterImpl:
    """真实的 MinerU Adapter 实现。

    这个类和 FakeMinerUAdapter 的对外行为保持一致：

        输入本地 PDF 路径或远程 URL
        -> 返回核心 ParsedDocument

    但它内部会使用 MinerUClient 访问真实 MinerU API。

    目前支持的流程：
        parse_url:
            远程 PDF URL
            -> MinerU task
            -> 轮询状态
            -> 下载 zip
            -> parser.py
            -> ParsedDocument

    已支持的流程：
        parse_file:
            本地 PDF 上传
            -> MinerU batch 上传接口
            -> PUT 文件
            -> 轮询 batch 状态
            -> 下载 zip
            -> parser.py
    """

    def __init__(self, client: MinerUClient) -> None:
        """初始化真实 Adapter。

        参数：
            client:
                已经构造好的 MinerUClient。

                这里使用依赖注入，而不是在 adapter 内部直接创建 client。
                好处：
                - 测试时可以替换成 fake client；
                - 配置来源更清晰；
                - HTTP client 的生命周期更好管理。
        """

        # 保存 client。
        # 下划线表示这是类内部使用的对象，不属于公共 API。
        self._client = client

    @classmethod
    def from_env(cls) -> "MinerUAdapterImpl":
        """从环境变量创建真实 Adapter。

        这个方法适合在 worker 或 API 启动时使用。

        它会读取环境变量：
            MINERU_API_BASE
            MINERU_API_KEY
            MINERU_TIMEOUT_SECONDS
            MINERU_POLL_INTERVAL_SECONDS
            MINERU_MODEL_VERSION

        返回：
            MinerUAdapterImpl。

        说明：
            API Key 不应该写死在代码里。
            推荐通过环境变量注入。
        """

        # 创建真实 HTTP client。
        client = MinerUClient.from_env()

        # 把 client 注入 adapter。
        return cls(client=client)

    def parse_url(self, url: str) -> ParsedDocument:
        """解析远程 PDF URL。

        这个方法直接委托给 MinerUClient。

        MinerUClient 内部会完成：
            1. POST /api/v4/extract/task
            2. GET  /api/v4/extract/task/{task_id}
            3. 轮询任务状态
            4. 下载 full_zip_url
            5. 调用 parser.py
            6. 返回 ParsedDocument

        参数：
            url:
                可公网访问的 PDF URL。

        返回：
            ParsedDocument:
                项目内部统一的文档模型。

        可能抛出的异常：
            MinerUResponseError:
                MinerU API 请求失败。

            MinerUTaskFailedError:
                MinerU 任务失败。

            MinerUTimeoutError:
                等待任务完成时超时。

            MinerUResultError:
                结果 zip 缺失或不可解析。
        """

        # 这里不做 HTTP 细节处理。
        # adapter 只负责把接口请求转给 client。
        #
        # 如果 client 抛出异常，也直接继续向外抛，
        # 因为异常类型已经是项目统一的 MinerUError 系列。
        document = self._client.parse_url(url=url)
        self._validate_document(document=document)
        return document

    def parse_file(self, path: Path) -> ParsedDocument:
        """解析本地 PDF 文件。

        参数：
            path:
                本地 PDF 路径。

        返回：
            ParsedDocument。
        """

        document = self._client.parse_file(path)
        self._validate_document(document=document)
        return document

    @staticmethod
    def _validate_document(document: ParsedDocument) -> None:
        """校验解析结果中的最小可用信息。"""

        if not document.title or not document.title.strip():
            raise MinerUResultError("Parsed document is missing a title")

        if not document.source_path:
            raise MinerUResultError("Parsed document is missing source_path")

        if not document.pages:
            raise MinerUResultError("Parsed document has no pages")

        if not document.blocks:
            raise MinerUResultError("Parsed document has no blocks")

        if any(not str(block.text or "").strip() for block in document.blocks):
            raise MinerUResultError("Parsed document contains an empty block")

        if any(block.page_no is None for block in document.blocks):
            raise MinerUResultError("Parsed document contains a block without page_no")

    def close(self) -> None:
        """关闭底层 HTTP client。

        这个方法不是 MinerUAdapter 接口要求的，
        但对真实 HTTP client 的资源管理很有用。
        """

        # 委托给 client 关闭 httpx.Client。
        self._client.close()

    def __enter__(self) -> "MinerUAdapterImpl":
        """支持 with 语句。

        示例：
            with MinerUAdapterImpl.from_env() as adapter:
                document = adapter.parse_url("https://example.com/sample.pdf")
        """

        # 直接返回自身。
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """with 语句退出时自动关闭底层 HTTP client。"""

        # 无论是否发生异常，都关闭 client。
        self.close()
