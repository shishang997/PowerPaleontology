class EmbeddingError(Exception):
    """Embedding 模块的基础异常。"""


class EmbeddingConfigError(EmbeddingError):
    """Embedding 配置无效时抛出。"""


class EmbeddingInputError(EmbeddingError):
    """Embedding 输入内容无效时抛出。"""


class EmbeddingModelError(EmbeddingError):
    """Embedding 模型加载或推理失败时抛出。"""
