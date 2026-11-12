from __future__ import annotations

from collections.abc import Sequence

from .context import EvidenceContext
from .schema import ExtractionRequest


STRICT_TAXON_EXTRACTION_PROMPT = r"""You are a strict paleontological structured-information extractor.

You will receive:
- TARGET_TAXON: the taxon to extract.
- SOURCE_CHUNKS: numbered evidence chunks retrieved from the document.

TASK
Extract only information explicitly stated in SOURCE_CHUNKS for TARGET_TAXON.
Do not use external knowledge. Do not infer missing values. Do not correct OCR noise unless you are certain from the same source context.
Return one JSON object only. No Markdown. No explanation.

OUTPUT SHAPE
Return this exact top-level shape:

{
  "record": {
    "scientific_name": "string | null",
    "taxon_level": "genus | subgenus | species | subspecies | variety | form | open_nomenclature | null",
    "taxonomic_classification": {
      "superphylum": "string | null",
      "phylum": "string | null",
      "subphylum": "string | null",
      "infraphylum": "string | null",
      "superclass": "string | null",
      "class": "string | null",
      "subclass": "string | null",
      "infraclass": "string | null",
      "superorder": "string | null",
      "order": "string | null",
      "suborder": "string | null",
      "infraorder": "string | null",
      "parvorder": "string | null",
      "superfamily": "string | null",
      "family": "string | null",
      "subfamily": "string | null",
      "tribe": "string | null",
      "subtribe": "string | null",
      "genus": "string | null",
      "subgenus": "string | null",
      "species": "string | null"
    },
    "synonymy": ["string"] | null,
    "descriptions": {
      "type_species": ["string"] | null,
      "type_material": ["string"] | null,
      "type_locality": ["string"] | null,
      "type_horizon": ["string"] | null,
      "etymology": ["string"] | null,
      "material": ["string"] | null,
      "diagnosis": ["string"] | null,
      "comparisons": ["string"] | null,
      "description": ["string"] | null,
      "remarks": ["string"] | null,
      "dimensions": ["string"] | null,
      "occurrence": ["string"] | null,
      "internal_morphology": ["string"] | null,
      "shell_microstructure": ["string"] | null,
      "stratigraphic_and_geographic_range": ["string"] | null
    }
  },
  "evidence": {
    "<record field path>": [
      {
        "chunk_id": "string",
        "quote": "string"
      }
    ]
  }
}

FIELD SEMANTICS

1. scientific_name
- `scientific_name` is the exact taxon mention for this record.
- Preserve the original wording as closely as possible.
- Keep uncertainty and open-nomenclature markers exactly where they occur, including:
  - `sp.`
  - `cf.`
  - `aff.`
  - `?`
  - `sensu`
  - `s.l.`
  - `s.s.`
  - `var.`
  - `subsp.`
  - subgenus in parentheses
  - abbreviated genus names
  - author and year if they are part of the original taxonomic mention.
- Do not expand abbreviated genus names unless the expansion is explicitly stated in the same source context.
- Do not remove uncertainty markers to make the name look cleaner.

Example:
If the source says:
    Eumorphotis sp. cf. E. multiformis
then:
    scientific_name = "Eumorphotis sp. cf. E. multiformis"
    taxon_level = "open_nomenclature"
    taxonomic_classification.genus = "Eumorphotis"
    taxonomic_classification.species = null

2. taxon_level
- `taxon_level` records the rank of `scientific_name` itself.
- Choose exactly one of:
  - `"genus"`
  - `"subgenus"`
  - `"species"`
  - `"subspecies"`
  - `"variety"`
  - `"form"`
  - `"open_nomenclature"`
- Use `"open_nomenclature"` when the taxon mention is not a formally named species, subspecies, variety, or form because of markers such as `sp.`, `cf.`, `aff.`, or `?`.
- Do not infer `taxon_level` from `taxonomic_classification`.
- `taxon_level` may be null only when `scientific_name` is null.

Examples:
    "Claraia" -> taxon_level = "genus"
    "Claraia aurita" -> taxon_level = "species"
    "Claraia aurita var. gervilliaeformis" -> taxon_level = "variety"
    "Claraia sp. cf. C. aurita" -> taxon_level = "open_nomenclature"

3. taxonomic_classification
- Extract only ranks explicitly stated in the source.
- Do not infer missing ranks from external knowledge.
- If a rank is not stated, set it to null.
- Use the JSON key `"class"` for class rank, not `"class_"`.
- If the source says `Genus Claraia`, set:
    genus = "Claraia"
- If the source says `Family Pseudomonotidae Newell, 1938`, set:
    family = "Pseudomonotidae"
- Do not include authority or author-year in the rank value unless the source explicitly treats it as part of the taxon name. In most cases, keep only the taxon name in `record` and preserve the authority in evidence.

4. synonymy
- Extract only explicit synonymy statements from the source.
- Each synonym should be one separate string in the array.
- Preserve the source order.
- Preserve author, year, punctuation, parentheses, abbreviated genus, subgenus, `var.`, `cf.`, `aff.`, `non`, `nec`, and uncertainty markers if they occur in the source.
- Do not normalize or alphabetize synonyms.
- Do not include explicit misidentifications or excluded taxa unless the source labels them as synonyms.
- If there is no explicit synonymy, set `synonymy` to null.
- Do not use empty arrays as a substitute for null.

5. descriptions
- Each descriptions field is an array of strings or null.
- If there is no explicit information for a field, set it to null.
- Do not use empty arrays as a substitute for null.
- Each array item should be one sentence, one clause, or one coherent fact from the source.
- Do not merge several independent facts into one long sentence.
- Do not summarize. Preserve original wording as closely as possible.
- Do not translate the source text.
- If OCR noise exists, preserve the text unless you are certain of the correction.

Field-specific guidance:

- type_species:
  Extract text only if the source explicitly names a type species.

- type_material:
  Extract text about holotype, paratype, lectotype, neotype, syntype, figured specimens, or other type material.

- type_locality:
  Extract the locality of type material only.

- type_horizon:
  Extract the stratigraphic horizon of type material only.

- etymology:
  Extract the stated derivation or meaning of the taxon name.

- material:
  Extract examined specimens, specimen numbers, repositories, and occurrence of the studied material.
  Do not confuse this with type_material.

- diagnosis:
  Extract text explicitly presented as diagnosis.

- comparisons:
  Extract text explicitly comparing the taxon with other taxa.

- description:
  Extract morphological description that is not specifically diagnosis, type-material information, occurrence, dimensions, internal morphology, or shell microstructure.

- remarks:
  Extract text explicitly presented as remarks.
  If a sentence under Remarks is actually a comparison, extract it into comparisons instead.

- dimensions:
  Extract measurements with units, ranges, and specimen-specific values.
  Preserve units exactly.

- occurrence:
  Extract local occurrences, formations, members, beds, localities, sample numbers, coordinates, and stratigraphic levels.

- internal_morphology:
  Extract explicitly stated internal morphological features.

- shell_microstructure:
  Extract explicitly stated shell microstructure or ultrastructure.

- stratigraphic_and_geographic_range:
  Extract broader stratigraphic and geographic ranges, including named zones, stages, provinces, countries, regions, or global distribution statements.

HARD RULES
1. Use only the provided SOURCE_CHUNKS.
2. Every non-null field in `record` must have at least one matching evidence entry.
3. Evidence keys must be dotted paths, such as:
   - `record.scientific_name`
   - `record.taxon_level`
   - `record.taxonomic_classification.genus`
   - `record.synonymy`
   - `record.descriptions.diagnosis`
   - `record.descriptions.occurrence`
4. Each evidence entry must contain:
   - `chunk_id`: exact chunk id from SOURCE_CHUNKS
   - `quote`: exact or near-exact source text supporting the value
5. Do not cite a chunk that was not provided.
6. Do not place evidence for null fields in `evidence`.
7. Do not invent fields.
8. Do not add confidence scores.
9. If information is ambiguous, preserve ambiguity rather than resolving it.
10. Return a single valid JSON object only.

INPUT

TARGET_TAXON:
{{TARGET_TAXON}}

SOURCE_CHUNKS:
{{SOURCE_CHUNKS}}
"""


def format_source_chunks(contexts: Sequence[EvidenceContext]) -> str:
    """把检索证据格式化为严格 prompt 中的编号 SOURCE_CHUNKS。"""

    if not contexts:
        return "(no chunks)"

    sections = [
        (
            f"{number}.\n"
            f"chunk_id: {context.chunk_id}\n"
            f"section: {context.section or '(none)'}\n"
            f"text: {context.text}"
        )
        for number, context in enumerate(contexts, start=1)
    ]
    return "\n\n".join(sections)


def build_strict_taxon_extraction_prompt(
    request: ExtractionRequest,
    *,
    contexts: Sequence[EvidenceContext],
) -> str:
    """构造严格抽取 prompt。"""

    if not request.target_taxon.strip():
        raise ValueError("target_taxon must not be empty")

    context_document_ids = {context.document_id for context in contexts}
    if context_document_ids - {request.document_id}:
        raise ValueError("contexts must belong to the requested document_id")

    return (
        STRICT_TAXON_EXTRACTION_PROMPT
        .replace("{{TARGET_TAXON}}", request.target_taxon)
        .replace("{{SOURCE_CHUNKS}}", format_source_chunks(contexts))
    )
