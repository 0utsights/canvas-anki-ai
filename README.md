# Canvas Anki AI

Canvas Anki AI is an Anki desktop add-on that turns current Canvas course
material into source-grounded draft flashcards. Students choose their courses,
review every generated card, and decide what enters Anki.

> [!IMPORTANT]
> This project is under active development and is not yet ready for everyday
> use. It is not affiliated with Anki, AnkiWeb, Instructure, or Canvas LMS.

## Goals

- Connect to Canvas through its supported API.
- Discover current material from modules, pages, files, and syllabi.
- Extract instructional content from HTML, PDF, and PowerPoint sources.
- Exclude grading policies, deadlines, attendance rules, and other logistics.
- Generate atomic cards that are traceable to a source page or slide.
- Require human approval before adding or updating Anki notes.
- Avoid duplicates through Canvas source IDs and content hashes.

## Why Python?

Anki desktop add-ons are Python modules and use PyQt for their interfaces.
Python also has mature libraries for Canvas API access, document extraction,
OCR, and AI providers, so it minimizes integration code.

## Proposed Pipeline

```text
Canvas API
    -> source discovery and date ranking
    -> document extraction
    -> instructional-content filter
    -> grounded card generation
    -> source verification
    -> student approval
    -> Anki notes
```

AI providers will be optional and replaceable. Course material will never be
sent to an external provider without explicit configuration and confirmation.

## Current State

The repository currently provides:

- An Anki setup dialog for Canvas URL, session token, and course selection.
- Paginated discovery of active Canvas courses.
- Module and module-item discovery with Canvas pagination fallbacks.
- Current-material ranking from dates, module state, position, and source type.
- Local extraction of Canvas pages, assignments, discussions, quizzes, and syllabi.
- Page-aware PDF, slide-aware PowerPoint, DOCX, HTML, and plain-text extraction.
- Source-aware semantic chunks with stable evidence IDs.
- Conservative logistics filtering with uncertain content retained for review.
- Provider-neutral, validated concept and card-generation contracts.
- Deterministic 3/5/7-card concept coverage matrices.
- Session-only token handling; access tokens are not persisted to disk.
- A comprehensive assignment policy spanning multiple difficulty levels.
- Core source and draft-card data models.
- A conservative first-pass logistics filter.
- A standard-library build script and unit tests.

## Development

Requires Python 3.9 or newer. The build vendors the pinned `pypdf` dependency
inside the add-on archive; Anki does not need a separate package installation.

```bash
python -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-addon.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/build.py
```

The build command creates `dist/canvas-anki-ai.ankiaddon`. Install it from
Anki with **Tools -> Add-ons -> Install from file**.

## Roadmap

1. Token-budgeted AI analysis batches
2. First provider adapter and private credential configuration
3. Independent source verification and draft approval
4. Anki note creation and duplicate prevention
5. OCR for scanned PDFs and image-heavy slides
6. Optional operating-system credential storage
7. OAuth support for wider distribution

The assignment card strategy is documented in
[`docs/card-generation-policy.md`](docs/card-generation-policy.md).
The strict provider boundary is documented in
[`docs/ai-provider-contract.md`](docs/ai-provider-contract.md).

## Privacy

Canvas content may be private or copyrighted. Users are responsible for
following their institution's policies. The project will request read-only
access wherever possible and will not submit assignments or modify courses.

## License

[MIT](LICENSE)
