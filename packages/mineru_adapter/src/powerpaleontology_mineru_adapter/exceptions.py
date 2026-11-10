# =====================================================================
# exceptions.py
# 这个文件定义 MinerU Adapter 内部专用的异常类型。
#
# 它的作用是：
# 1. 让 MinerU 网络请求失败时抛出统一异常；
# 2. 让任务解析失败时抛出统一异常；
# 3. 让上层 worker / API 不需要直接理解 MinerU 的 HTTP 错误细节；
# 4. 后续所有 MinerU 相关错误都可以被统一捕获。
#
# 这个文件不依赖 httpx、requests 或其他第三方库。
# =====================================================================


# ---------------------------------------------------------------------
# 基础异常
# 所有 MinerU Adapter 的异常都继承自这个类。
#
# 这样上层代码可以很简单地这样捕获：
#
# try:
#     adapter.parse_url("https://example.com/sample.pdf")
# except MinerUError:
#     ...
# ---------------------------------------------------------------------
class MinerUError(Exception):
    """MinerU Adapter 的基础异常类型。"""

    def __init__(self, message: str) -> None:
        # message 是给人看的错误描述。
        # 这里直接把 message 传给 Python 原生 Exception。
        super().__init__(message)


# ---------------------------------------------------------------------
# HTTP 请求失败
# 当访问 MinerU API 时，如果返回非 2xx 状态码，就抛这个异常。
#
# 例如：
# - 401：API Key 无效
# - 403：没有权限
# - 429：请求频率太高
# - 500：MinerU 服务端错误
# ---------------------------------------------------------------------
class MinerUResponseError(MinerUError):
    """MinerU API 返回了非成功响应。"""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_text: str | None = None,
    ) -> None:
        # status_code 记录 HTTP 状态码，比如 401、429、500。
        # response_text 记录 MinerU 返回的原始错误文本，方便调试。
        #
        # 注意：
        # 不要在这里保存 API Key。
        # response_text 只应包含服务端返回的错误信息。
        self.status_code = status_code
        self.response_text = response_text

        # 如果有 HTTP 状态码，就把状态码拼进错误信息里。
        if status_code is not None:
            full_message = f"MinerU API error, status {status_code}: {message}"
        else:
            full_message = f"MinerU API error: {message}"

        super().__init__(full_message)


# ---------------------------------------------------------------------
# 任务失败
# MinerU 的解析任务是异步的。
#
# 流程大致是：
# 提交任务 -> 轮询任务状态 -> state == done -> 下载结果 zip
#
# 如果轮询时发现：
# state == failed
#
# 就抛出这个异常。
# ---------------------------------------------------------------------
class MinerUTaskFailedError(MinerUError):
    """MinerU 解析任务最终失败。"""

    def __init__(
        self,
        task_id: str,
        error_message: str | None = None,
    ) -> None:
        # task_id 是 MinerU 返回的任务 ID。
        # error_message 是 MinerU 返回的错误原因。
        self.task_id = task_id
        self.error_message = error_message

        # 如果有错误原因，就把它放进异常信息。
        if error_message:
            message = f"MinerU task failed, task_id={task_id}, error={error_message}"
        else:
            message = f"MinerU task failed, task_id={task_id}"

        super().__init__(message)


# ---------------------------------------------------------------------
# 超时异常
# MinerU 解析一个 PDF 可能需要一段时间。
#
# 我们不能无限轮询，所以需要设置最大等待时间。
# 如果超过最大时间，任务还没有完成，就抛这个异常。
# ---------------------------------------------------------------------
class MinerUTimeoutError(MinerUError):
    """等待 MinerU 任务完成时超时。"""

    def __init__(
        self,
        task_id: str,
        timeout_seconds: int | float,
    ) -> None:
        # task_id 记录哪个任务超时。
        # timeout_seconds 记录最多等待了多少秒。
        self.task_id = task_id
        self.timeout_seconds = timeout_seconds

        message = (
            f"MinerU task did not finish in time, "
            f"task_id={task_id}, timeout_seconds={timeout_seconds}"
        )
        super().__init__(message)


# ---------------------------------------------------------------------
# 结果文件缺失
# MinerU 完成解析后通常会返回一个 zip 下载地址。
#
# 如果：
# - full_zip_url 为空；
# - 或者 zip 里找不到 full.md；
# - 或者 zip 文件损坏；
#
# 就抛这个异常。
# ---------------------------------------------------------------------
class MinerUResultError(MinerUError):
    """MinerU 返回的解析结果不可用。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)