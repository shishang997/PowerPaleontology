from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .exceptions import EmbeddingConfigError


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class EmbeddingConfig:
    """Embedding 模块的统一配置。"""

    # Ollama 中已经下载的模型标签。
    model_name: str = "all-minilm:l6-v2"

    # 推理设备，当前阶段固定使用 CPU。
    device: str = "cpu"

    # 单次批量推理的样本数量。
    batch_size: int = 32

    # 是否将输出向量归一化，便于后续使用余弦相似度。
    normalize_embeddings: bool = True

    # 单条文本最大字符数；None 表示不额外限制。
    max_input_characters: int | None = None

    # 本地模型路径；None 表示按 model_name 从缓存或远程加载。
    model_path: Path | None = None

    # Embedding 服务地址；本地 Ollama 默认使用 11434 端口。
    base_url: str = "http://127.0.0.1:11434"

    # 单次 HTTP 请求超时时间，单位秒。
    timeout_seconds: float = 120.0

    # 远程服务 API Key；本地 Ollama 通常留空。
    api_key: str = ""

    def __post_init__(self) -> None:
        """校验配置，避免无效参数进入流水线。"""

        if not self.model_name.strip():
            raise EmbeddingConfigError("model_name must not be empty")

        if not self.device.strip():
            raise EmbeddingConfigError("device must not be empty")

        if self.batch_size <= 0:
            raise EmbeddingConfigError("batch_size must be greater than 0")

        if self.max_input_characters is not None and self.max_input_characters <= 0:
            raise EmbeddingConfigError(
                "max_input_characters must be greater than 0"
            )

        if not self.base_url.strip():
            raise EmbeddingConfigError("base_url must not be empty")

        if self.timeout_seconds <= 0:
            raise EmbeddingConfigError("timeout_seconds must be greater than 0")

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        """从环境变量创建 Embedding 配置。

        支持的环境变量：
            EMBEDDING_MODEL_NAME
            EMBEDDING_DEVICE
            EMBEDDING_BATCH_SIZE
            EMBEDDING_NORMALIZE_EMBEDDINGS
            EMBEDDING_MAX_INPUT_CHARACTERS
            EMBEDDING_MODEL_PATH
            EMBEDDING_BASE_URL
            EMBEDDING_TIMEOUT_SECONDS
            EMBEDDING_API_KEY
        """

        raw_batch_size = os.getenv("EMBEDDING_BATCH_SIZE", "32")
        try:
            batch_size = int(raw_batch_size)
        except ValueError as error:
            raise EmbeddingConfigError(
                "EMBEDDING_BATCH_SIZE must be an integer"
            ) from error

        raw_normalize = os.getenv("EMBEDDING_NORMALIZE_EMBEDDINGS", "true")
        normalized_raw_normalize = raw_normalize.strip().lower()

        if normalized_raw_normalize in _TRUE_VALUES:
            normalize_embeddings = True
        elif normalized_raw_normalize in _FALSE_VALUES:
            normalize_embeddings = False
        else:
            raise EmbeddingConfigError(
                "EMBEDDING_NORMALIZE_EMBEDDINGS must be a boolean"
            )

        raw_max_input_characters = os.getenv("EMBEDDING_MAX_INPUT_CHARACTERS", "")
        max_input_characters: int | None = None

        if raw_max_input_characters.strip():
            try:
                max_input_characters = int(raw_max_input_characters)
            except ValueError as error:
                raise EmbeddingConfigError(
                    "EMBEDDING_MAX_INPUT_CHARACTERS must be an integer"
                ) from error

        raw_model_path = os.getenv("EMBEDDING_MODEL_PATH", "")
        model_path = Path(raw_model_path) if raw_model_path.strip() else None

        raw_timeout_seconds = os.getenv("EMBEDDING_TIMEOUT_SECONDS", "120")
        try:
            timeout_seconds = float(raw_timeout_seconds)
        except ValueError as error:
            raise EmbeddingConfigError(
                "EMBEDDING_TIMEOUT_SECONDS must be a number"
            ) from error

        return cls(
            model_name=os.getenv("EMBEDDING_MODEL_NAME", "all-minilm:l6-v2"),
            device=os.getenv("EMBEDDING_DEVICE", "cpu"),
            batch_size=batch_size,
            normalize_embeddings=normalize_embeddings,
            max_input_characters=max_input_characters,
            model_path=model_path,
            base_url=os.getenv("EMBEDDING_BASE_URL", "http://127.0.0.1:11434"),
            timeout_seconds=timeout_seconds,
            api_key=os.getenv("EMBEDDING_API_KEY", ""),
        )
