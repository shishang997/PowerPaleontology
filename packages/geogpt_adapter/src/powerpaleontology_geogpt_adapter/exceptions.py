from __future__ import annotations


class GeoGPTError(Exception):
    """GeoGPT 适配器的基础异常。"""


class GeoGPTConfigError(GeoGPTError):
    """GeoGPT 配置无效时抛出。"""


class GeoGPTInputError(GeoGPTError):
    """传给 GeoGPT 适配器的输入无效。"""


class GeoGPTModelError(GeoGPTError):
    """GeoGPT 请求或响应处理失败时抛出。"""
