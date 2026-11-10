# =====================================================================
# client.py
# 这个文件负责与 MinerU 的 HTTP API 通信。
#
# 它只做三件事：
# 1. 提交远程 PDF URL 给 MinerU；
# 2. 轮询解析任务状态；
# 3. 任务完成后下载结果 zip。
#
# 它不负责把 zip 转成 ParsedDocument，那部分交给 parser.py。
# 它也不应该被 worker / API 直接当成业务层使用；
# 上层更推荐使用后面要写的 MinerUAdapterImpl。
# =====================================================================

# 启用现代化类型注解。
from __future__ import annotations

# os 用于读取环境变量，例如 MINERU_API_BASE 和 MINERU_API_KEY。
import os

# time 用于轮询等待和控制超时。
import time
import hashlib

# pathlib.Path 用于表示本地 PDF 文件路径。
from pathlib import Path

# quote 用于安全地拼接 task_id 到 URL 中。
from urllib.parse import quote

# dataclass 用于定义轻量级配置和任务状态对象。
from dataclasses import dataclass

# typing 类型辅助。
from typing import Any

# httpx 是 HTTP 客户端。
# 后续应加入 packages/mineru_adapter 的 dependencies。
import httpx

# 导入 MinerU Adapter 自己的异常。
from .exceptions import (
    MinerUError,
    MinerUResponseError,
    MinerUResultError,
    MinerUTaskFailedError,
    MinerUTimeoutError,
)

# 导入 parser，把下载到的 zip 转成核心 ParsedDocument。
from .parser import parse_mineru_zip

# 导入核心模型，client.parse_url 的最终返回值是 ParsedDocument。
from powerpaleontology_core import ParsedDocument


# ---------------------------------------------------------------------
# MinerU Client 配置
# ---------------------------------------------------------------------
@dataclass(frozen=True)
class MinerUClientConfig:
    """MinerU HTTP client 的配置。

    注意：
        API Key 不应该写死在代码里。
        推荐通过环境变量 MINERU_API_KEY 注入。
    """

    # MinerU API 的基础地址。
    # 默认使用官方地址。
    endpoint: str = "https://mineru.net"

    # MinerU API Token。
    # 不要把它提交到 Git。
    api_key: str = ""

    # 单次 HTTP 请求超时时间，单位秒。
    timeout_seconds: float = 120.0

    # 轮询任务状态的间隔，单位秒。
    poll_interval_seconds: float = 2.0

    # MinerU 模型版本。
    # 当前默认使用 vlm。
    model_version: str = "vlm"

    @classmethod
    def from_env(cls) -> "MinerUClientConfig":
        """从环境变量创建配置。

        支持的环境变量：
            MINERU_API_BASE
                MinerU API 地址，默认 https://mineru.net

            MINERU_API_KEY
                MinerU API Token

            MINERU_TIMEOUT_SECONDS
                单次 HTTP 请求超时时间

            MINERU_POLL_INTERVAL_SECONDS
                轮询间隔

            MINERU_MODEL_VERSION
                模型版本，默认 vlm

        返回：
            MinerUClientConfig

        异常：
            MinerUError:
                缺少 MINERU_API_KEY。
        """

        # 读取 API 地址。
        # 如果没有配置，使用官方默认地址。
        endpoint = os.getenv("MINERU_API_BASE", "https://mineru.net")

        # 读取 API Key。
        # 这里不要写死 key。
        api_key = os.getenv("MINERU_API_KEY", "")

        # 如果没有 API Key，直接抛出清晰错误。
        if not api_key.strip():
            raise MinerUError("Missing MINERU_API_KEY environment variable")

        # 读取超时时间。
        # 环境变量里是字符串，需要转成 float。
        raw_timeout = os.getenv("MINERU_TIMEOUT_SECONDS")
        timeout_seconds = float(raw_timeout) if raw_timeout else 120.0

        # 读取轮询间隔。
        raw_poll_interval = os.getenv("MINERU_POLL_INTERVAL_SECONDS")
        poll_interval_seconds = float(raw_poll_interval) if raw_poll_interval else 2.0

        # 读取模型版本。
        model_version = os.getenv("MINERU_MODEL_VERSION", "vlm")

        # 创建配置对象。
        return cls(
            endpoint=endpoint,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
            model_version=model_version,
        )


# ---------------------------------------------------------------------
# MinerU 任务状态
# ---------------------------------------------------------------------
@dataclass(frozen=True)
class MinerUTaskStatus:
    """MinerU 单个解析任务的状态。

    常见状态：
        pending:     排队中
        running:     正在解析
        converting:  格式转换中
        done:        完成
        failed:      失败
    """

    # MinerU 返回的任务 ID。
    task_id: str

    # 当前任务状态。
    state: str

    # 任务完成后的结果 zip 下载地址。
    full_zip_url: str | None

    # 任务失败时的错误信息。
    error_message: str | None

    # MinerU 返回的原始 JSON。
    # 保留这个字段方便调试，但上层业务尽量不要依赖它。
    raw: dict[str, Any]


@dataclass(frozen=True)
class MinerUFileUploadBatch:
    """本地文件上传批次信息。"""

    batch_id: str
    file_urls: list[str]
    raw: dict[str, Any]


# ---------------------------------------------------------------------
# MinerU HTTP Client
# ---------------------------------------------------------------------
class MinerUClient:
    """MinerU HTTP API 客户端。

    这个类负责 HTTP 细节：
    - 构造请求；
    - 读取 API Key；
    - 处理响应；
    - 轮询任务；
    - 下载结果 zip。

    它不负责：
    - 定义业务流程；
    - 管理 PostgreSQL；
    - 生成 chunk；
    - 调用 GeoGPT。
    """

    def __init__(self, config: MinerUClientConfig) -> None:
        """初始化 HTTP client。

        参数：
            config:
                MinerUClientConfig 配置对象。
        """

        # 保存配置。
        self.config = config

        # 创建 httpx.Client。
        #
        # follow_redirects=True：
        #   MinerU 结果下载可能会发生重定向，
        #   所以允许 httpx 自动跟随。
        #
        # timeout：
        #   单次 HTTP 请求超时时间。
        self._http = httpx.Client(
            follow_redirects=True,
            timeout=self.config.timeout_seconds,
        )

    @classmethod
    def from_env(cls) -> "MinerUClient":
        """从环境变量创建 MinerUClient。"""

        # 先从环境变量构造配置。
        config = MinerUClientConfig.from_env()

        # 再用配置创建 client。
        return cls(config=config)

    # -----------------------------------------------------------------
    # 对象生命周期管理
    # -----------------------------------------------------------------
    def close(self) -> None:
        """关闭底层 HTTP 连接。"""

        # httpx.Client 内部维护连接池，用完后关闭。
        self._http.close()

    def __enter__(self) -> "MinerUClient":
        """支持 with 语句。"""

        # 直接返回自身。
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """with 语句退出时自动关闭连接。"""

        # 关闭 HTTP client。
        self.close()

    # -----------------------------------------------------------------
    # 公共方法：提交远程 URL 解析任务
    # -----------------------------------------------------------------
    def submit_url(self, url: str, model_version: str | None = None) -> str:
        """提交一个远程 PDF URL 给 MinerU。

        参数：
            url:
                可公网访问的 PDF URL。

            model_version:
                可选模型版本。
                如果不传，使用配置里的 model_version。

        返回：
            MinerU task_id。

        异常：
            MinerUResponseError:
                HTTP 请求失败或响应格式错误。
        """

        # 简单校验 URL。
        # 这里不解析复杂 URL，只防止明显错误。
        if not url.strip():
            raise ValueError("url must not be empty")

        # 如果调用方没有指定模型版本，使用默认配置。
        selected_model_version = model_version or self.config.model_version

        # 构造 MinerU 请求体。
        payload = {
            "url": url,
            "model_version": selected_model_version,
        }

        # 向 MinerU 提交任务。
        payload_json = self._request_json(
            method="POST",
            path="/api/v4/extract/task",
            json=payload,
        )

        # MinerU 通常返回：
        # {
        #   "code": 0,
        #   "msg": "ok",
        #   "data": {
        #       "task_id": "..."
        #   }
        # }
        #
        # 这里提取 data 字段。
        data = self._extract_data(payload_json)

        # 读取 task_id。
        task_id = data.get("task_id")

        # 如果 task_id 缺失，说明响应不可用。
        if not task_id:
            raise MinerUResponseError(
                message="MinerU submit response does not contain task_id",
                response_text=str(payload_json),
            )

        # task_id 应该是字符串。
        return str(task_id)

    # -----------------------------------------------------------------
    # 公共方法：查询任务状态
    # -----------------------------------------------------------------
    def get_task(self, task_id: str) -> MinerUTaskStatus:
        """查询 MinerU 解析任务状态。

        参数：
            task_id:
                MinerU 返回的任务 ID。

        返回：
            MinerUTaskStatus。

        异常：
            MinerUResponseError:
                HTTP 请求失败或响应格式错误。
        """

        # 校验 task_id 不能为空。
        if not task_id.strip():
            raise ValueError("task_id must not be empty")

        # 对 task_id 做 URL 转义。
        # 通常 task_id 是 UUID，不需要转义，但这样更稳。
        encoded_task_id = quote(task_id, safe="")

        # 查询 MinerU 任务状态。
        payload_json = self._request_json(
            method="GET",
            path=f"/api/v4/extract/task/{encoded_task_id}",
        )

        # 提取 data 字段。
        data = self._extract_data(payload_json)

        # 读取任务状态。
        state = str(data.get("state", ""))

        # 读取结果 zip 地址。
        # 只有任务完成后才会有。
        full_zip_url = data.get("full_zip_url")

        # 读取错误信息。
        error_message = data.get("err_msg") or data.get("error_message")

        # 构造统一的任务状态对象。
        return MinerUTaskStatus(
            task_id=task_id,
            state=state,
            full_zip_url=str(full_zip_url) if full_zip_url else None,
            error_message=str(error_message) if error_message else None,
            raw=data,
        )

    # -----------------------------------------------------------------
    # 公共方法：等待任务完成
    # -----------------------------------------------------------------
    def wait_for_task(
        self,
        task_id: str,
        timeout_seconds: float | None = None,
        poll_interval_seconds: float | None = None,
    ) -> MinerUTaskStatus:
        """轮询等待 MinerU 任务完成。

        参数：
            task_id:
                MinerU 任务 ID。

            timeout_seconds:
                最长等待时间。
                不传时使用配置里的 timeout_seconds。

            poll_interval_seconds:
                轮询间隔。
                不传时使用配置里的 poll_interval_seconds。

        返回：
            完成状态 MinerUTaskStatus。

        异常：
            MinerUTaskFailedError:
                任务失败。

            MinerUTimeoutError:
                等待超时。
        """

        # 如果调用方没有指定超时时间，使用配置默认值。
        effective_timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else self.config.timeout_seconds
        )

        # 如果调用方没有指定轮询间隔，使用配置默认值。
        effective_poll_interval = (
            poll_interval_seconds
            if poll_interval_seconds is not None
            else self.config.poll_interval_seconds
        )

        # 计算轮询截止时间。
        # 使用 monotonic 可以避免系统时间被修改影响。
        deadline = time.monotonic() + effective_timeout

        while True:
            # 查询一次任务状态。
            status = self.get_task(task_id=task_id)

            # 任务完成。
            if status.state == "done":
                return status

            # 任务失败。
            # 这里把 failed 视为终态。
            if status.state == "failed":
                raise MinerUTaskFailedError(
                    task_id=task_id,
                    error_message=status.error_message,
                )

            # 如果已经超过截止时间，抛出超时异常。
            if time.monotonic() >= deadline:
                raise MinerUTimeoutError(
                    task_id=task_id,
                    timeout_seconds=effective_timeout,
                )

            # 任务还没完成，等待下一次轮询。
            time.sleep(effective_poll_interval)

    # -----------------------------------------------------------------
    # 公共方法：下载结果 zip
    # -----------------------------------------------------------------
    def download_zip(self, url: str) -> bytes:
        """下载 MinerU 返回的结果 zip 文件。

        参数：
            url:
                MinerU 返回的 full_zip_url。

        返回：
            zip 文件的二进制内容。

        异常：
            MinerUResponseError:
                下载失败。
        """

        # 校验下载地址不能为空。
        if not url.strip():
            raise MinerUResultError("MinerU result zip URL is empty")

        try:
            # 下载 zip 文件。
            response = self._http.get(url=url)

        except httpx.RequestError as error:
            # 网络错误、DNS 错误、超时等。
            raise MinerUResponseError(
                message=f"Failed to download MinerU result zip: {error}"
            ) from error

        # 如果下载失败，抛出统一异常。
        if response.status_code >= 400:
            raise MinerUResponseError(
                message="Failed to download MinerU result zip",
                status_code=response.status_code,
                response_text=response.text,
            )

        # 返回 zip 二进制内容。
        return response.content

    # -----------------------------------------------------------------
    # 公共方法：创建本地文件上传批次
    # -----------------------------------------------------------------
    def create_file_upload(
        self,
        path: Path,
        model_version: str | None = None,
    ) -> MinerUFileUploadBatch:
        """向 MinerU 申请本地 PDF 的签名上传地址。"""

        if not path.is_file():
            raise FileNotFoundError(f"PDF file does not exist: {path}")

        if path.suffix.lower() != ".pdf":
            raise ValueError("Only PDF files are supported")

        selected_model_version = model_version or self.config.model_version
        payload = {
            "model_version": selected_model_version,
            "enable_formula": True,
            "enable_table": True,
            "files": [
                {
                    "name": path.name,
                    "is_ocr": True,
                }
            ],
        }

        payload_json = self._request_json(
            method="POST",
            path="/api/v4/file-urls/batch",
            json=payload,
        )
        data = self._extract_data(payload_json)
        batch_id = data.get("batch_id")
        file_urls = data.get("file_urls")

        if not batch_id:
            raise MinerUResponseError(
                message="MinerU upload response does not contain batch_id",
                response_text=str(payload_json),
            )

        if not isinstance(file_urls, list) or not file_urls:
            raise MinerUResponseError(
                message="MinerU upload response does not contain file_urls",
                response_text=str(payload_json),
            )

        return MinerUFileUploadBatch(
            batch_id=str(batch_id),
            file_urls=[str(url) for url in file_urls],
            raw=data,
        )

    # -----------------------------------------------------------------
    # 公共方法：上传本地 PDF
    # -----------------------------------------------------------------
    def upload_file(self, file_url: str, path: Path) -> None:
        """使用签名 URL 上传本地 PDF。"""

        if not file_url.strip():
            raise ValueError("file_url must not be empty")

        try:
            file_bytes = path.read_bytes()
            response = self._http.put(
                url=file_url,
                content=file_bytes,
            )

        except OSError as error:
            raise MinerUError(f"Failed to read local PDF: {path}") from error

        except httpx.RequestError as error:
            raise MinerUResponseError(
                message=f"Failed to upload local PDF: {error}"
            ) from error

        if response.status_code >= 400:
            raise MinerUResponseError(
                message="Failed to upload local PDF",
                status_code=response.status_code,
                response_text=response.text,
            )

    # -----------------------------------------------------------------
    # 公共方法：查询本地文件批次结果
    # -----------------------------------------------------------------
    def get_batch_result(self, batch_id: str, file_name: str) -> MinerUTaskStatus:
        """查询本地文件批次中指定文件的状态。"""

        if not batch_id.strip():
            raise ValueError("batch_id must not be empty")

        if not file_name.strip():
            raise ValueError("file_name must not be empty")

        encoded_batch_id = quote(batch_id, safe="")
        payload_json = self._request_json(
            method="GET",
            path=f"/api/v4/extract-results/batch/{encoded_batch_id}",
        )
        data = self._extract_data(payload_json)
        results = data.get("extract_result", data.get("results", []))

        if not isinstance(results, list):
            raise MinerUResponseError(
                message="MinerU batch result field is not a list",
                response_text=str(payload_json),
            )

        result = next(
            (
                item
                for item in results
                if isinstance(item, dict)
                and str(item.get("file_name", item.get("name", ""))) == file_name
            ),
            None,
        )

        if result is None:
            raise MinerUResultError(
                f"MinerU batch result does not contain file: {file_name}"
            )

        state = str(result.get("state", ""))
        full_zip_url = result.get("full_zip_url")
        error_message = result.get("err_msg") or result.get("error_message")

        return MinerUTaskStatus(
            task_id=batch_id,
            state=state,
            full_zip_url=str(full_zip_url) if full_zip_url else None,
            error_message=str(error_message) if error_message else None,
            raw=result,
        )

    # -----------------------------------------------------------------
    # 公共方法：等待本地文件批次完成
    # -----------------------------------------------------------------
    def wait_for_batch(
        self,
        batch_id: str,
        file_name: str,
        timeout_seconds: float | None = None,
        poll_interval_seconds: float | None = None,
    ) -> MinerUTaskStatus:
        """轮询等待本地文件批次中的指定文件完成。"""

        effective_timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else self.config.timeout_seconds
        )
        effective_poll_interval = (
            poll_interval_seconds
            if poll_interval_seconds is not None
            else self.config.poll_interval_seconds
        )
        deadline = time.monotonic() + effective_timeout

        while True:
            status = self.get_batch_result(
                batch_id=batch_id,
                file_name=file_name,
            )

            if status.state == "done":
                return status

            if status.state == "failed":
                raise MinerUTaskFailedError(
                    task_id=batch_id,
                    error_message=status.error_message,
                )

            if time.monotonic() >= deadline:
                raise MinerUTimeoutError(
                    task_id=batch_id,
                    timeout_seconds=effective_timeout,
                )

            time.sleep(effective_poll_interval)

    # -----------------------------------------------------------------
    # 公共方法：完整解析远程 URL
    # -----------------------------------------------------------------
    def parse_url(self, url: str) -> ParsedDocument:
        """提交远程 PDF URL 并等待解析完成，返回 ParsedDocument。

        流程：
            1. 提交 URL 给 MinerU；
            2. 轮询直到任务完成；
            3. 下载结果 zip；
            4. 使用 parser.py 转成核心 ParsedDocument。

        参数：
            url:
                远程 PDF 地址。

        返回：
            ParsedDocument。

        说明：
            当前用 MinerU task_id 作为 document_id。
            后面接入数据库后，可以改成数据库生成的 document_id。
        """

        # 第一步：提交任务。
        task_id = self.submit_url(url=url)

        # 第二步：等待任务完成。
        status = self.wait_for_task(task_id=task_id)

        # 第三步：检查结果 zip 地址。
        if not status.full_zip_url:
            raise MinerUResultError(
                "MinerU task is done but full_zip_url is missing"
            )

        # 第四步：下载 zip。
        zip_bytes = self.download_zip(url=status.full_zip_url)

        # 第五步：把 zip 转成核心 ParsedDocument。
        return parse_mineru_zip(
            zip_bytes=zip_bytes,
            document_id=task_id,
            source_path=url,
        )

    # -----------------------------------------------------------------
    # 公共方法：完整解析本地 PDF
    # -----------------------------------------------------------------
    def parse_file(self, path: Path) -> ParsedDocument:
        """上传本地 PDF 并等待解析完成，返回 ParsedDocument。"""

        if not path.is_file():
            raise FileNotFoundError(f"PDF file does not exist: {path}")

        file_bytes = path.read_bytes()
        document_id = hashlib.sha256(file_bytes).hexdigest()
        batch = self.create_file_upload(path=path)
        self.upload_file(file_url=batch.file_urls[0], path=path)
        status = self.wait_for_batch(
            batch_id=batch.batch_id,
            file_name=path.name,
        )

        if not status.full_zip_url:
            raise MinerUResultError(
                "MinerU batch is done but full_zip_url is missing"
            )

        zip_bytes = self.download_zip(url=status.full_zip_url)
        return parse_mineru_zip(
            zip_bytes=zip_bytes,
            document_id=document_id,
            source_path=path,
        )

    # -----------------------------------------------------------------
    # 私有方法：构造请求头
    # -----------------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        """构造 MinerU API 请求头。

        注意：
            不要打印这个返回值，因为它包含 API Key。
        """

        # MinerU 使用 Bearer Token 认证。
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Accept": "application/json",
        }

    # -----------------------------------------------------------------
    # 私有方法：发送 JSON API 请求
    # -----------------------------------------------------------------
    def _request_json(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """发送请求并返回 JSON 响应。

        参数：
            method:
                HTTP 方法，例如 GET 或 POST。

            path:
                API 路径，例如 /api/v4/extract/task。

            json:
                请求体。GET 请求通常为 None。

        返回：
            MinerU 返回的 JSON 字典。

        异常：
            MinerUResponseError:
                网络失败、HTTP 非 2xx、JSON 解析失败。
        """

        # 拼接完整 URL。
        url = self._build_url(path=path)

        try:
            # 发送 HTTP 请求。
            response = self._http.request(
                method=method,
                url=url,
                json=json,
                headers=self._headers(),
            )

        except httpx.RequestError as error:
            # 网络层错误，例如 DNS、连接失败、超时。
            raise MinerUResponseError(
                message=f"MinerU request failed: {error}"
            ) from error

        # HTTP 状态码非 2xx 视为失败。
        if response.status_code >= 400:
            raise MinerUResponseError(
                message="MinerU API returned an error response",
                status_code=response.status_code,
                response_text=response.text,
            )

        # 如果响应体为空，返回空字典。
        # 正常 MinerU API 不应该这样，但这里防御一下。
        if not response.content:
            return {}

        try:
            # 解析 JSON。
            payload = response.json()

        except ValueError as error:
            # JSON 解析失败。
            raise MinerUResponseError(
                message="MinerU API returned invalid JSON",
                status_code=response.status_code,
                response_text=response.text,
            ) from error

        # 响应必须是 JSON 对象。
        if not isinstance(payload, dict):
            raise MinerUResponseError(
                message="MinerU API JSON response is not an object",
                status_code=response.status_code,
                response_text=response.text,
            )

        # MinerU 通常使用 code == 0 表示成功。
        # 这里做兼容处理：如果响应里有 code 字段，则校验它。
        if "code" in payload:
            try:
                # code 可能是 int，也可能是字符串。
                normalized_code = int(payload["code"])

            except (TypeError, ValueError):
                # 如果 code 无法转成数字，也视为失败。
                normalized_code = -1

            # 非 0 code 视为业务失败。
            if normalized_code != 0:
                raise MinerUResponseError(
                    message=str(payload.get("msg", "MinerU API business error")),
                    status_code=response.status_code,
                    response_text=response.text,
                )

        # 返回完整 JSON。
        return payload

    # -----------------------------------------------------------------
    # 私有方法：提取响应中的 data 字段
    # -----------------------------------------------------------------
    def _extract_data(self, payload: dict[str, Any]) -> dict[str, Any]:
        """从 MinerU JSON 响应中提取 data 字段。

        MinerU 常见结构：
            {
                "code": 0,
                "msg": "ok",
                "data": {
                    "task_id": "..."
                }
            }

        有些接口可能没有 data 字段。
        这里做一个兼容处理。
        """

        # 如果存在 data 字段，使用 data。
        if "data" in payload:
            data = payload["data"]

            # data 为 null 时返回空字典。
            if data is None:
                return {}

            # data 必须是 JSON 对象。
            if not isinstance(data, dict):
                raise MinerUResponseError(
                    message="MinerU response data field is not an object",
                    response_text=str(payload),
                )

            return data

        # 如果没有 data 字段，就把整个 payload 当作 data。
        # 这样可以兼容一些简化响应。
        return payload

    # -----------------------------------------------------------------
    # 私有方法：构造完整 URL
    # -----------------------------------------------------------------
    def _build_url(self, path: str) -> str:
        """拼接 endpoint 和 API path。"""

        # 去掉 endpoint 末尾多余斜杠，再拼接 path。
        return self.config.endpoint.rstrip("/") + path
