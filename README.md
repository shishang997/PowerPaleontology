# PowerPaleontology

This folder contains the architecture skeleton for a batch PDF parsing and structured
information extraction project for palaeontological literature.

The system is designed around five principles:

1. Separate document parsing from semantic extraction.
2. Retrieve evidence before asking an LLM to extract information.
3. Require explicit evidence for every extracted value.
4. Validate, normalize, and route low-confidence records to human review.
5. Store all results with document, page, block, and coordinate provenance.

## Intended stack

- FastAPI backend
- Worker processes for batch extraction
- PostgreSQL for structured data
- pgvector or Qdrant for embeddings
- Redis for task queues
- MinerU for PDF parsing
- GeoGPT or another LLM for extraction
- React or Vue for the human review interface

## Main directories

```text
apps/         Backend API, workers, and review interface
packages/     Reusable domain and infrastructure modules
configs/      Runtime configuration, schemas, and prompts
docs/         Architecture, data model, and retrieval design
infra/        Deployment and service configuration
scripts/      Maintenance and batch utilities
tests/        Unit and integration tests
data/         Local development data
```
