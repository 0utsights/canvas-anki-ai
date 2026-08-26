# AI Provider Contract

Canvas Anki AI separates local preparation from external AI processing. The
add-on currently defines and validates the provider contract but does not yet
configure or call a real provider.

Provider credentials and transport are delegated to the separate
[`anki-ai-bridge`](https://github.com/0utsights/anki-ai-bridge) add-on. Canvas
Anki AI includes only a small versioned client and adapter, so the same provider
connection can be reused by other add-ons.

## Local Boundary

Before any provider call, the add-on:

1. extracts text with page, slide, or Canvas locations;
2. creates stable, source-aware chunks;
3. removes only high-confidence logistics chunks;
4. retains uncertain chunks for user inspection;
5. shows the exact prepared corpus and estimated size.

## Provider Interface

A provider implements one method:

```python
complete_json(task: StructuredTask) -> StructuredResponse
```

The task supplies instructions, structured input data, and an output JSON
schema. This keeps API authentication, transport, and model selection separate
from study logic.

## Concept Analysis

The provider proposes concepts with:

- a name and concise summary;
- basic, intermediate, or advanced complexity;
- supporting chunk IDs;
- assignment chunk IDs identifying assessment emphasis.

The add-on rejects unknown chunk IDs, duplicate concepts, concepts without
evidence, and assignment citations that do not come from assignments. Validated
concepts become deterministic 3/5/7-card coverage matrices.

## Card Generation

Each generated card must match a known concept and coverage intention, use the
required difficulty, and cite evidence belonging to that concept. Every target
must produce either one card or an explicit unsupported reason. This prevents
the contract from pressuring a model to invent content when a source cannot
support an application or transfer card.

## Remaining Provider Work

- token-budgeted concept-analysis batches;
- provider configuration and session-only API credentials;
- explicit confirmation before transmitting content;
- retry, rate-limit, and cancellation handling;
- an independent source-verification pass;
- draft approval and Anki note creation.
