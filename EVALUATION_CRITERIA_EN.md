# Evaluation Criteria

This document defines how to evaluate the repository's three core workflows:
chat reasoning, document digitization, and information extraction. Evaluate each
workflow against a representative, human-verified test set rather than judging
individual examples in isolation.

## General evaluation rules

- Keep the test set separate from prompts and examples used during development.
- Include common, difficult, and malformed inputs, as well as multiple document
  types, layouts, languages, and scan qualities where applicable.
- Create a human-verified reference answer, transcription, or extraction for
  every test case.
- Run the same inputs and settings for every model or version being compared.
- Report averages together with failure counts and results by input category.
- Treat a critical failure as a release blocker even when the average score
  passes the threshold.

Use a 0-4 rating for criteria that require human judgment:

| Rating | Meaning |
| --- | --- |
| 4 | Fully correct; no meaningful issue |
| 3 | Correct overall; minor issue that does not change the result |
| 2 | Partially correct; noticeable omission or error |
| 1 | Mostly incorrect; only limited useful content |
| 0 | Incorrect, unsupported, unusable, or missing |

Convert a rating to a percentage with `rating / 4 * 100` before applying its
weight.

## Chat reasoning

Evaluate both the final `answer` and the returned `reasoning`. A reasoning trace
does not need to match the reference wording or steps; it must reach the answer
through valid, relevant, and internally consistent reasoning.

| Criterion | Weight | What to check |
| --- | ---: | --- |
| Answer correctness | 50% | The final conclusion, calculation, or recommendation matches the verified answer. |
| Reasoning validity | 25% | Each material step is logically valid, assumptions are stated when needed, and no step contradicts another. |
| Instruction fulfillment | 15% | The response follows all requested constraints and addresses every part of the prompt. |
| Clarity and relevance | 10% | The answer is understandable, sufficiently explained, and free of distracting or irrelevant content. |

For questions with an exact answer, record exact-match accuracy in addition to
the weighted score. For open-ended questions, use at least two reviewers and
resolve rating differences greater than one point.

Critical failures include a wrong final answer presented with confidence,
fabricated evidence, unsafe advice, or reasoning that relies on a material
factual or logical error.

Recommended starting release gate:

- Weighted score of at least 85/100.
- At least 95% final-answer accuracy on deterministic questions.
- No unresolved critical failures.

## Document digitization

Compare the generated Markdown with both the source document and a verified
reference transcription. Score only applicable criteria; when a document has
no tables or other structural elements, remove that criterion and normalize the
remaining weights to 100%.

| Criterion | Weight | What to check |
| --- | ---: | --- |
| Text fidelity | 40% | Characters, words, punctuation, symbols, and numbers are transcribed correctly, without omissions or duplicate text. |
| Reading order and layout | 20% | Paragraphs, columns, headers, footers, and page transitions appear in the intended reading order. |
| Table fidelity | 20% | Rows, columns, merged cells, headers, and cell values preserve the source table's meaning. |
| Structural preservation | 10% | Headings, lists, captions, equations, links, and other meaningful elements are represented appropriately. |
| Markdown quality | 10% | Output is valid, readable Markdown without broken syntax or unnecessary artifacts. |

Report character error rate (CER) for all documents. Report word error rate
(WER) when word boundaries are meaningful, and table cell precision, recall,
and F1 for documents containing tables. Normalize inconsequential differences,
such as line-ending style, before calculating automated metrics, but do not
normalize meaningful punctuation, signs, decimal separators, or identifiers.

Critical failures include missing a page or major section, changing a material
number or sign, corrupting the reading order so that meaning changes, or
producing unusable Markdown.

Recommended starting release gate:

- Weighted score of at least 90/100.
- CER no greater than 1% for born-digital documents and 5% for scanned documents.
- Table cell F1 of at least 90% where tables are present.
- No missing pages, major sections, or other unresolved critical failures.

## Information extraction

Evaluate extraction against the exact JSON Schema used for the request and a
human-verified reference JSON object. Validate the output against the schema
before scoring individual fields.

| Criterion | Weight | What to check |
| --- | ---: | --- |
| Field correctness | 50% | Extracted values match the document and the reference after permitted normalization. |
| Completeness | 20% | All fields supported by the document, especially required fields, are returned. |
| Groundedness | 15% | Values are supported by the source; absent information is not invented. |
| Schema and type compliance | 15% | JSON is valid and all names, types, arrays, required fields, enums, and formats follow the supplied schema. |

Use exact matching for identifiers, names, dates, amounts, and other fields
where formatting is significant. A documented normalization may be used for
whitespace, case, Unicode, dates, or numeric formatting when it preserves the
value's meaning. Use element-level comparison for arrays and recursive
field-level comparison for nested objects.

Report required-field accuracy, all-field precision, recall, and micro F1, the
schema-valid response rate, and the unsupported-value rate. Count an incorrect
value as both a false positive and a false negative. Do not silently exclude
missing, extra, or invalidly typed values.

Critical failures include invalid JSON, schema-invalid output, a missing
required field, an invented material value, or a materially incorrect amount,
date, identifier, or party.

Recommended starting release gate:

- 100% valid JSON and schema compliance.
- Required-field accuracy of at least 95%.
- All-field micro F1 of at least 90%.
- Unsupported-value rate no greater than 1%.
- No unresolved critical failures.

## Evaluation report

Each evaluation report should contain:

1. Model, API, prompt, schema, and code versions.
2. Test-set size and distribution by task and difficulty.
3. Aggregate scores and automated metrics for each workflow.
4. Results broken down by input category, language, layout, and scan quality.
5. Critical failures and representative error examples.
6. Comparison with the previous accepted baseline.
7. Final pass or fail decision and the reason for it.

The numeric thresholds above are recommended starting points. After the first
stable baseline, adjust them to the product's risk level and document every
change so that results remain comparable over time.
