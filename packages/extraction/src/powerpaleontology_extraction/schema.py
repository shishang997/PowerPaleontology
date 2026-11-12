from __future__ import annotations

from collections.abc import Collection
from typing import Any, Literal, get_args
from typing_extensions import TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


TAXONOMIC_RANKS: tuple[str, ...] = (
    "superphylum",
    "phylum",
    "subphylum",
    "infraphylum",
    "superclass",
    "class",
    "subclass",
    "infraclass",
    "superorder",
    "order",
    "suborder",
    "infraorder",
    "parvorder",
    "superfamily",
    "family",
    "subfamily",
    "tribe",
    "subtribe",
    "genus",
    "subgenus",
    "species",
)

DESCRIPTION_FIELDS: tuple[str, ...] = (
    "type_species",
    "type_material",
    "type_locality",
    "type_horizon",
    "etymology",
    "material",
    "diagnosis",
    "comparisons",
    "description",
    "remarks",
    "dimensions",
    "occurrence",
    "internal_morphology",
    "shell_microstructure",
    "stratigraphic_and_geographic_range",
)

TaxonLevel: TypeAlias = Literal[
    "genus",
    "subgenus",
    "species",
    "subspecies",
    "variety",
    "form",
    "open_nomenclature",
]

TAXON_LEVELS: tuple[str, ...] = get_args(TaxonLevel)

EXTRACTION_FIELDS: tuple[str, ...] = (
    "scientific_name",
    "taxon_level",
    "taxonomic_classification",
    *TAXONOMIC_RANKS,
    "synonymy",
    "descriptions",
    *DESCRIPTION_FIELDS,
)

EVIDENCE_FIELD_PATHS: tuple[str, ...] = (
    "record.scientific_name",
    "record.taxon_level",
    *(f"record.taxonomic_classification.{rank}" for rank in TAXONOMIC_RANKS),
    "record.synonymy",
    *(f"record.descriptions.{field_name}" for field_name in DESCRIPTION_FIELDS),
)


class TaxonomicClassification(BaseModel):
    """阶元信息；文献中不存在的阶元必须为 null。"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    superphylum: str | None = None
    phylum: str | None = None
    subphylum: str | None = None
    infraphylum: str | None = None
    superclass: str | None = None
    class_: str | None = Field(default=None, alias="class")
    subclass: str | None = None
    infraclass: str | None = None
    superorder: str | None = None
    order: str | None = None
    suborder: str | None = None
    infraorder: str | None = None
    parvorder: str | None = None
    superfamily: str | None = None
    family: str | None = None
    subfamily: str | None = None
    tribe: str | None = None
    subtribe: str | None = None
    genus: str | None = None
    subgenus: str | None = None
    species: str | None = None

    @model_validator(mode="after")
    def normalize_missing_ranks(self) -> "TaxonomicClassification":
        """把空字符串视为未提取到，而不是允许模型输出空值占位。"""

        for rank in TAXONOMIC_RANKS:
            python_field = "class_" if rank == "class" else rank
            value = getattr(self, python_field)
            if value is not None and not value.strip():
                setattr(self, python_field, None)
        return self


class TaxonDescriptions(BaseModel):
    """描述字段；文献中不存在的段落或句子必须为 null。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type_species: list[str] | None = None
    type_material: list[str] | None = None
    type_locality: list[str] | None = None
    type_horizon: list[str] | None = None
    etymology: list[str] | None = None
    material: list[str] | None = None
    diagnosis: list[str] | None = None
    comparisons: list[str] | None = None
    description: list[str] | None = None
    remarks: list[str] | None = None
    dimensions: list[str] | None = None
    occurrence: list[str] | None = None
    internal_morphology: list[str] | None = None
    shell_microstructure: list[str] | None = None
    stratigraphic_and_geographic_range: list[str] | None = None

    @model_validator(mode="after")
    def normalize_missing_descriptions(self) -> "TaxonDescriptions":
        """过滤空句/空段；如果全部为空，则归一化为 null。"""

        for field in DESCRIPTION_FIELDS:
            value = getattr(self, field)
            if value is None:
                continue

            normalized_items = [item.strip() for item in value if item.strip()]
            setattr(self, field, normalized_items or None)
        return self


class ExtractionRequest(BaseModel):
    """一次结构化抽取请求。"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    target_taxon: str
    document_id: str
    top_k: int = Field(default=10, ge=1)
    filters: dict[str, Any] = Field(default_factory=dict)
    fields: tuple[str, ...] | None = None

    @model_validator(mode="after")
    def normalize_request(self) -> "ExtractionRequest":
        """规范化请求参数，并拒绝抽取 schema 之外的字段。"""

        if not self.target_taxon:
            raise ValueError("target_taxon must not be empty")
        if not self.document_id:
            raise ValueError("document_id must not be empty")

        if self.fields is None:
            return self

        normalized_fields: list[str] = []
        for field_name in self.fields:
            normalized_name = field_name.strip()
            if not normalized_name:
                continue
            if normalized_name not in EXTRACTION_FIELDS:
                raise ValueError(
                    f"unsupported extraction field: {normalized_name}; "
                    f"supported fields: {', '.join(EXTRACTION_FIELDS)}"
                )
            if normalized_name not in normalized_fields:
                normalized_fields.append(normalized_name)

        self.fields = tuple(normalized_fields) or None
        return self


class SpeciesExtraction(BaseModel):
    """prompt 输出中 record 部分的结构化抽取结果。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    scientific_name: str | None = None
    taxon_level: TaxonLevel | None = None
    taxonomic_classification: TaxonomicClassification = TaxonomicClassification()
    synonymy: list[str] | None = None
    descriptions: TaxonDescriptions = TaxonDescriptions()

    @field_validator("taxon_level", mode="before")
    @classmethod
    def normalize_empty_taxon_level(cls, value: object) -> object:
        """空等级在枚举校验前视为未提取到。"""

        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def normalize_record(self) -> "SpeciesExtraction":
        """空值视为未提取到；空数组归一化为 null。"""

        if self.scientific_name is not None and not self.scientific_name.strip():
            self.scientific_name = None
        if self.synonymy is not None:
            self.synonymy = [item for item in self.synonymy if item.strip()] or None
        if (self.scientific_name is None) != (self.taxon_level is None):
            raise ValueError(
                "taxon_level must be null exactly when scientific_name is null"
            )
        return self


class EvidenceCitation(BaseModel):
    """一条抽取结果对应的证据引用。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    chunk_id: str
    quote: str

    @field_validator("chunk_id", "quote")
    @classmethod
    def validate_non_empty_value(cls, value: str) -> str:
        """引用块和原文引句都不能为空。"""

        if not value:
            raise ValueError("chunk_id and quote must not be empty")
        return value


class TaxonExtraction(BaseModel):
    """严格 prompt 约定的完整抽取输出。"""

    model_config = ConfigDict(extra="forbid")

    record: SpeciesExtraction
    evidence: dict[str, tuple[EvidenceCitation, ...]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_evidence(self) -> "TaxonExtraction":
        """校验证据路径，并要求每个非空 record 字段都有证据。"""

        unknown_paths = set(self.evidence) - set(EVIDENCE_FIELD_PATHS)
        if unknown_paths:
            paths = ", ".join(sorted(unknown_paths))
            raise ValueError(f"unsupported evidence field path: {paths}")

        for path, citations in self.evidence.items():
            if not citations:
                raise ValueError(f"evidence for {path} must not be empty")

        missing_paths = self._required_evidence_paths() - set(self.evidence)
        if missing_paths:
            paths = ", ".join(sorted(missing_paths))
            raise ValueError(f"missing evidence for non-null fields: {paths}")
        return self

    def _required_evidence_paths(self) -> set[str]:
        paths: set[str] = set()
        if self.record.scientific_name is not None:
            paths.add("record.scientific_name")
        if self.record.taxon_level is not None:
            paths.add("record.taxon_level")
        if self.record.synonymy is not None:
            paths.add("record.synonymy")

        for rank in TAXONOMIC_RANKS:
            python_field = "class_" if rank == "class" else rank
            if getattr(self.record.taxonomic_classification, python_field) is not None:
                paths.add(f"record.taxonomic_classification.{rank}")

        for field_name in DESCRIPTION_FIELDS:
            if getattr(self.record.descriptions, field_name) is not None:
                paths.add(f"record.descriptions.{field_name}")
        return paths

    def validate_allowed_chunk_ids(
        self,
        allowed_chunk_ids: Collection[str],
    ) -> "TaxonExtraction":
        """确保模型只引用检索上下文中实际提供的 chunk。"""

        allowed = set(allowed_chunk_ids)
        provided = {citation.chunk_id for citations in self.evidence.values() for citation in citations}
        unknown = provided - allowed
        if unknown:
            chunk_ids = ", ".join(sorted(unknown))
            raise ValueError(f"evidence references unknown chunk_id: {chunk_ids}")
        return self
