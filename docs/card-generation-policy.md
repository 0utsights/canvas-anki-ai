# Assignment Coverage Policy

Assignments are strong evidence of what an instructor expects a student to
understand, but they are not automatically trustworthy answer sources. The
generator will use assignment prompts to identify and prioritize concepts, then
ground answers in course pages, slides, readings, worked examples, and other
instructional material.

## Coverage-First Middle Ground

The default policy favors more than the minimum number of cards without
creating several cards that test the same fact in nearly identical wording.
Each concept receives a difficulty ladder based on its complexity:

| Complexity | Target | Card intentions |
| --- | ---: | --- |
| Basic | 3 | core recall, boundaries, direct application |
| Intermediate | 5 | recall, boundaries, mechanism, application, error diagnosis |
| Advanced | 7 | all intermediate forms plus alternate representation and transfer |

These are targets rather than quotas. A card is omitted when the sources do not
support it or when it would duplicate an existing card.

## Assignment Processing

1. Remove due dates, points, submission steps, grading rules, and boilerplate.
2. Extract every explicit concept, skill, constraint, and learning objective.
3. Break multi-part tasks into a coverage matrix of independently testable ideas.
4. Find supporting explanations and examples elsewhere in the current course material.
5. Estimate each concept's complexity and generate its card-intention ladder.
6. Verify every answer against a source passage, page, slide, formula, or diagram.
7. Show missing coverage, weak evidence, and duplicates in the approval interface.

## Guardrails

- Never turn submission logistics into cards.
- Never invent an answer from an underspecified assignment prompt.
- Keep cards atomic even when several cards cover the same broader concept.
- Prefer meaningful variation in cognitive demand over paraphrased duplicates.
- Preserve source references and the assignment relationship on every draft.
- Let the student reduce density per course or concept before importing cards.
