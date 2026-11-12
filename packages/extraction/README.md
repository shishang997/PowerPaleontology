# extraction

Defines structured extraction targets for species-level palaeontological data.

Current scope:

- `TAXONOMIC_RANKS` contains the taxonomic rank field names.
- `DESCRIPTION_FIELDS` contains the descriptive section field names.
- Missing values are represented as `null`, never invented by the model.
- `ExtractionRequest` is converted into a filtered `RetrievalRequest`, and retrieval
  chunks are wrapped as traceable `EvidenceContext` objects.
- `TaxonExtraction` validates the strict prompt response and its evidence citations.
- `run_taxon_extraction` connects evidence retrieval, strict prompting, model completion,
  and schema/evidence validation.
