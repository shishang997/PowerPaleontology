from __future__ import annotations

import json
import re
from collections.abc import Collection

from pydantic import ValidationError

from .schema import TaxonExtraction


class TaxonExtractionParseError(ValueError):
    """模型输出不是合法的 TaxonExtraction JSON。"""


_CODE_FENCE_PATTERN = re.compile(
    r"^```(?:json)?\s*(?P<json>.*)\s*```$",
    flags=re.IGNORECASE | re.DOTALL,
)


def _extract_json_text(raw_response: str) -> str:
    """从模型输出中提取一个顶层 JSON 对象文本。"""

    text = raw_response.strip()
    if not text:
        raise TaxonExtractionParseError("model response is empty")

    code_fence_match = _CODE_FENCE_PATTERN.fullmatch(text)
    if code_fence_match:
        text = code_fence_match.group("json").strip()

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace == -1 or last_brace <= first_brace:
        raise TaxonExtractionParseError(
            "model response must contain exactly one JSON object"
        )
    return text[first_brace : last_brace + 1]


def parse_taxon_extraction(
    raw_response: str,
    *,
    allowed_chunk_ids: Collection[str],
) -> TaxonExtraction:
    """解析模型输出，并校验为完整 TaxonExtraction。"""

    json_text = _extract_json_text(raw_response)
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as error:
        raise TaxonExtractionParseError(
            f"model response is not valid JSON: {error.msg}"
        ) from error

    if not isinstance(payload, dict):
        raise TaxonExtractionParseError("model response must be a JSON object")

    try:
        extraction = TaxonExtraction.model_validate(payload)
    except ValidationError as error:
        raise TaxonExtractionParseError(
            "model response failed TaxonExtraction validation"
        ) from error

    try:
        extraction.validate_allowed_chunk_ids(allowed_chunk_ids)
    except ValueError as error:
        raise TaxonExtractionParseError(str(error)) from error

    return extraction
