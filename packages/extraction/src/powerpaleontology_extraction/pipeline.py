from __future__ import annotations

from typing import Protocol, runtime_checkable

from powerpaleontology_retrieval import Retriever

from .context import build_evidence_contexts
from .parser import parse_taxon_extraction
from .prompt import build_strict_taxon_extraction_prompt
from .schema import ExtractionRequest, TaxonExtraction


@runtime_checkable
class PromptCompleter(Protocol):
    """严格抽取流水线使用的模型补全接口。"""

    def complete(self, prompt: str) -> str:
        """发送 prompt，并返回模型原始输出。"""

        ...


def run_taxon_extraction(
    request: ExtractionRequest,
    *,
    retriever: Retriever,
    adapter: PromptCompleter,
) -> TaxonExtraction:
    """执行检索、构造严格 prompt、调用模型并解析校验结果。"""

    contexts = build_evidence_contexts(request, retriever=retriever)
    prompt = build_strict_taxon_extraction_prompt(request, contexts=contexts)
    raw_response = adapter.complete(prompt)
    return parse_taxon_extraction(
        raw_response,
        allowed_chunk_ids={context.chunk_id for context in contexts},
    )
