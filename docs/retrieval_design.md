# Retrieval Design

The retrieval layer should combine lexical and semantic retrieval.

## Candidate generation

```text
query
  -> BM25 or PostgreSQL FTS candidates
  -> vector search candidates
  -> merged candidate list
```

## Reranking

A reranker receives the merged candidates and returns a smaller set of high-quality chunks.

```text
BM25 top-50
vector top-50
  -> merge
  -> rerank
  -> final top-10
```

## Metadata filtering

Retrieval should support filters such as:

```text
document_id
page
section
block_type
entity_type
geological_period
taxonomic_group
```

## Result contract

Each retrieved chunk should expose:

```text
chunk_id
document_id
page
block_id
section
text
score
bbox
```

This allows extracted attributes to be traced back to exact evidence.
