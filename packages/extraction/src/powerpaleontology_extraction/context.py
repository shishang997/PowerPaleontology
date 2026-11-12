from __future__ import annotations

from collections.abc import Sequence

from powerpaleontology_retrieval import (
    Retriever,
    RetrievalRequest,
    RetrievalResult,
)
from pydantic import BaseModel, ConfigDict, Field

from .schema import DESCRIPTION_FIELDS, EXTRACTION_FIELDS, TAXONOMIC_RANKS, ExtractionRequest


FIELD_RETRIEVAL_TERMS: dict[str, str] = {
    "scientific_name": "scientific name taxonomic identification",
    "taxonomic_classification": "taxonomic classification phylum class order family genus species",
    "descriptions": "morphology diagnosis description remarks dimensions occurrence",
    **{rank: f"taxonomy {rank}" for rank in TAXONOMIC_RANKS},
    **{
        field_name: field_name.replace("_", " ")
        for field_name in DESCRIPTION_FIELDS
    },
}


class EvidenceContext(BaseModel):
    """检索到的可溯源证据。"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    chunk_id: str
    document_id: str
    page_no: int
    block_ids: tuple[str, ...]
    section: str | None = None
    text: str
    score: float
    embedding_model: str
    metadata: dict[str, object] = Field(default_factory=dict)
    requested_fields: tuple[str, ...]

    @classmethod
    def from_retrieval_result(
        cls,
        result: RetrievalResult,
        *,
        requested_fields: Sequence[str],
    ) -> "EvidenceContext":
        """把检索结果转换为可传给抽取器的证据上下文。"""

        return cls(
            chunk_id=result.chunk_id,
            document_id=result.document_id,
            page_no=result.page_no,
            block_ids=tuple(result.block_ids),
            section=result.section,
            text=result.text,
            score=result.score,
            embedding_model=result.embedding_model,
            metadata=dict(result.metadata),
            requested_fields=tuple(requested_fields),
        )


def _selected_fields(request: ExtractionRequest) -> tuple[str, ...]:
    """返回本次请求要检索/抽取的目标字段。"""

    return request.fields or EXTRACTION_FIELDS


def _retrieval_filters(request: ExtractionRequest) -> dict[str, object]:
    """合并用户过滤条件，并强制限定在请求的 document_id 内。"""

    filter_document_id = request.filters.get("document_id")
    if filter_document_id is not None and filter_document_id != request.document_id:
        raise ValueError("filters.document_id must match document_id")

    return {
        **request.filters,
        "document_id": request.document_id,
    }


def build_retrieval_query(request: ExtractionRequest) -> str:
    """根据目标分类单元和目标字段构造一个面向混合检索的查询。"""

    query_terms = [
        FIELD_RETRIEVAL_TERMS.get(field_name, field_name.replace("_", " "))
        for field_name in _selected_fields(request)
    ]
    return "; ".join(dict.fromkeys((request.target_taxon, *query_terms)))


def build_retrieval_request(request: ExtractionRequest) -> RetrievalRequest:
    """把抽取请求转换为带 document_id 过滤的检索请求。"""

    return RetrievalRequest(
        query=build_retrieval_query(request),
        limit=request.top_k,
        where=_retrieval_filters(request),
    )


def build_evidence_contexts(
    request: ExtractionRequest,
    *,
    retriever: Retriever,
) -> list[EvidenceContext]:
    """执行检索，并把结果转换为 EvidenceContext。"""

    retrieval_request = build_retrieval_request(request)
    requested_fields = _selected_fields(request)
    return [
        EvidenceContext.from_retrieval_result(
            result,
            requested_fields=requested_fields,
        )
        for result in retriever.retrieve(retrieval_request)
    ]
