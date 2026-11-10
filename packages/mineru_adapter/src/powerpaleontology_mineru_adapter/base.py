# =====================================================================
# base.py
# 这个文件定义 MinerU Adapter 的公共接口。
#
# 它的作用是：
# 1. 固定 MinerU Adapter 对外暴露的能力；
# 2. 让 worker、API、测试代码不依赖具体的 MinerU 实现；
# 3. 后续可以自由替换：
#    - FakeMinerUAdapter
#    - MinerUAdapterImpl
#    - 未来其他文档解析服务 Adapter
#
# 这个文件只定义接口，不写具体网络请求逻辑。
# =====================================================================

# 启用现代化类型注解。
# 这样在 Python 3.11 中可以直接使用 Path、ParsedDocument 等类型。
from __future__ import annotations

# pathlib.Path 用来表示本地 PDF 文件路径。
from pathlib import Path

# Protocol 是 Python 的结构化接口工具。
# 只要某个类实现了下面的方法，它就可以被视为 MinerUAdapter，
# 不需要强制继承某个父类。
from typing import Protocol, runtime_checkable

# ParsedDocument 是项目核心包里的通用文档模型。
# 后续 MinerUAdapter 的返回值统一使用它。
#
# 核心模型位置：
# packages/core/src/powerpaleontology_core/models.py
from powerpaleontology_core import ParsedDocument


# runtime_checkable 允许代码运行时做类似这样的判断：
# isinstance(adapter, MinerUAdapter)
#
# 注意：
# 这种判断只检查对象是否有对应方法，不检查方法签名和返回类型。
# 但在当前项目中已经足够用。
@runtime_checkable
class MinerUAdapter(Protocol):
    """MinerU 文档解析适配器的统一接口。

    这个接口刻意保持简单：

    - 输入：本地 PDF 或远程 PDF URL；
    - 输出：项目内部统一的 ParsedDocument；
    - 不暴露 MinerU 原始 HTTP 响应；
    - 不暴露 MinerU 原始 JSON；
    - 不暴露 zip 文件对象。

    上层模块以后只应该依赖这个接口，例如：

        worker 代码       -> 依赖 MinerUAdapter
        review API 代码   -> 依赖 MinerUAdapter
        测试代码          -> 使用 FakeMinerUAdapter

    这样 MinerU API 变化时，只需要修改具体实现，
    不需要修改业务代码。
    """

    def parse_file(self, path: Path) -> ParsedDocument:
        """解析本地 PDF 文件。

        参数：
            path:
                本地 PDF 文件路径。

                例如：
                    Path("data/sample.pdf")

        返回：
            ParsedDocument:
                项目内部统一的文档模型。

                其中应该包含：
                - document_id
                - source_path
                - title
                - pages
                - blocks

        可能抛出的异常：
            MinerUResponseError:
                MinerU API 返回非 2xx 响应。

            MinerUTaskFailedError:
                MinerU 任务最终失败。

            MinerUTimeoutError:
                等待 MinerU 任务完成时超时。

            MinerUResultError:
                MinerU 返回的结果 zip 缺失或不可解析。

        实现说明：
            这个方法不应该写在本文件里。
            具体逻辑由后续实现类提供，例如：

                FakeMinerUAdapter.parse_file()
                MinerUAdapterImpl.parse_file()
        """

        # Protocol 中的方法不提供实现。
        # 这里使用 ... 表示方法签名已经定义，但逻辑由具体类实现。
        ...

    def parse_url(self, url: str) -> ParsedDocument:
        """解析远程 PDF 文件。

        参数：
            url:
                可公网访问的 PDF 链接。

                例如：
                    "https://example.com/paper.pdf"

        返回：
            ParsedDocument:
                项目内部统一的文档模型。

        使用场景：
            MinerU 的 URL 解析接口适合这种流程：

                提交远程 URL
                -> MinerU 返回 task_id
                -> 轮询任务状态
                -> state == done
                -> 下载 full_zip_url
                -> 解析 zip
                -> 转成 ParsedDocument

        可能抛出的异常：
            MinerUResponseError:
                MinerU API 返回非 2xx 响应。

            MinerUTaskFailedError:
                MinerU 任务最终失败。

            MinerUTimeoutError:
                等待 MinerU 任务完成时超时。

            MinerUResultError:
                MinerU 返回的结果 zip 缺失或不可解析。
        """

        # 同样，这里只定义接口，不实现。
        ...