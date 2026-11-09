# Data Model

## documents

```text
document_id
source_path
sha256
title
authors
year
journal
doi
parse_version
status
created_at
updated_at
```

## chunks

```text
chunk_id
document_id
page
section
block_id
text
bbox
chunk_version
embedding_model
created_at
```

## entities

```text
entity_id
document_id
mention
normalized_name
entity_type
description
confidence
status
created_at
updated_at
```

## attributes

```text
attribute_id
entity_id
field
value
normalized_value
confidence
status
validator_status
created_at
updated_at
```

## evidence

```text
evidence_id
entity_id
attribute_id
document_id
page
block_id
bbox
text
char_start
char_end
created_at
```

## tasks

```text
task_id
document_id
task_type
status
retry_count
error_message
started_at
finished_at
```
