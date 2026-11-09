# Architecture

The project uses a modular pipeline architecture. Each stage has a narrow responsibility
so that MinerU, GeoGPT, embedding models, retrieval backends, and databases can be
replaced independently.

```text
PDF
  -> Ingestion
  -> MinerU parsing
  -> Document normalization
  -> Chunking
  -> Embedding
  -> Vector indexing
  -> Hybrid retrieval
  -> Entity extraction
  -> Attribute extraction
  -> Validation
  -> Storage
  -> Human review
```

## Core services

### API service

The API service receives PDFs, creates extraction tasks, exposes task status, returns
structured results, and supports human review actions.

### Worker service

The worker service performs long-running work: PDF parsing, chunking, embedding, vector
indexing, retrieval, LLM extraction, validation, and persistence.

### Review interface

The review interface shows the original PDF beside extracted records. Each record should
be linked to its source evidence and support manual correction, rejection, acceptance, and
re-extraction.

## Storage separation

Structured data belongs in PostgreSQL:

- documents
- chunks
- entities
- attributes
- evidence
- tasks
- audit logs

Vector data belongs in pgvector or Qdrant. It should store chunk embeddings and metadata
such as document ID, page, section, and block ID.

## Adapter boundaries

External systems are hidden behind adapters:

```text
MinerUAdapter
GeoGPTAdapter
EmbeddingAdapter
VectorStoreAdapter
TaskQueueAdapter
RelationalStoreAdapter
```

Business logic should depend on these interfaces, not directly on vendor APIs.
