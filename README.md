# Upstage API CLI

A small Python CLI for one-shot Solar chat, document agents, document
parsing/OCR, and schema-driven information extraction with the Upstage API.

## Setup

Install the project and its `requests` dependency with [uv](https://docs.astral.sh/uv/):

```shell
uv sync
```

Set your Upstage API key in the environment. The CLI reads credentials only
from `UPSTAGE_API_KEY`:

```shell
export UPSTAGE_API_KEY="up_..."
```

## Standalone scripts

The scripts under `scripts/` call the Upstage API directly with `requests` and
show a progress bar on standard error when run in a terminal.
Run the reasoning script with a prompt or load one of the ten named prompts in
`examples/reasoning/reasoning.jsonl`:

```shell
uv run scripts/chat_reasoning.py "What is the sum of the first 100 integers?"
uv run scripts/chat_reasoning.py --example sum_first_100
uv run scripts/chat_reasoning.py --all-examples
```

Run `uv run scripts/chat_reasoning.py --help` to see all example names. Results
are saved to `outputs/chat_reasoning/reasoning.jsonl` with one record per
prompt. Each record contains the example name, prompt, reasoning, and answer.
`--all-examples` makes one API request for each input JSONL record and writes
all ten results to the output JSONL file.

Digitize your own local document and save the result as Markdown:

```shell
uv run scripts/digitization.py invoice.pdf
```

The Markdown is printed and saved to
`outputs/digitization/<document-name>.md`.

Generate a reusable JSON Schema from your own document:

```shell
uv run scripts/schema_generation.py paper.pdf
```

The bare schema is printed and saved to
`outputs/schema_generation/<document-name>-schema.json`, ready to pass to the
extraction script with `--schema`.

Extract fields using a JSON Schema file:

```shell
uv run scripts/extraction.py invoice.pdf --schema schema/invoice-schema.json
uv run scripts/extraction.py paper.pdf --schema schema/paper-schema.json
uv run scripts/extraction.py paper.pdf --schema outputs/schema_generation/paper-schema.json
uv run scripts/extraction.py paper.pdf --auto-schema
```

The extracted JSON is printed and saved to
`outputs/extraction/<document-name>.json`.
`--auto-schema` first generates a schema from the document and then extracts
with it, so it makes two API requests. Use `--schema` when you want a stable,
repeatable output structure.
Replace the PDF paths with your own documents; the repository does not include
sample documents. Existing output files with the same name are overwritten.

Run a document through an Agent created in Upstage Studio:

```shell
uv run scripts/agent.py invoice.pdf --agent-id <YOUR AGENT ID>
```

The script uploads the document, waits for the Agent job to complete, and saves
the final output to `outputs/agent/<document-name>.json` when it is JSON or
`outputs/agent/<document-name>.txt` otherwise.

## Chat

Send a single, non-streaming prompt to `solar-pro3`:

```shell
uv run main.py chat "Explain why the sky is blue."
uv run main.py chat "Solve this proof." --reasoning-effort high
uv run main.py chat "Explain why the sky is blue." --json
```

Each invocation is stateless and sends only the supplied user prompt.
`--reasoning-effort` accepts `low`, `medium`, or `high` and defaults to
`medium`. Use `--json` to inspect the complete response, including any
reasoning metadata returned by the API.

## Agents

### Get an Agent ID

Agents must be created in Upstage Studio before they can be run through the
API:

1. Sign in to the Upstage Console and open **Studio**.
2. Create a new Agent.
3. Configure its model, instructions, and tools, then save it.
4. Open the Agent's **Code** panel.
5. Copy the Agent ID, which starts with `agt_`.

You need the Agent ID, an Upstage API key, and a document to run the workflow.
See the [Upstage Agents documentation](https://console.upstage.ai/docs/agents)
for the current Studio instructions.

### Run an Agent

Run a document through an Agent created in Upstage Studio:

```shell
uv run main.py agent invoice.pdf --agent-id <YOUR AGENT ID>
uv run main.py agent invoice.pdf --agent-id <YOUR AGENT ID> --json
```

The command follows the [Upstage Agents quickstart](https://console.upstage.ai/docs/agents):
it uploads the document for `user_data`, starts an asynchronous agent job, and
polls until the job completes. By default it prints the agent's final text,
pretty-printing it when the output is JSON. `--json` prints the complete final
job response. Create and configure the agent in Upstage Studio first, then pass
its `agt_...` ID with `--agent-id`.

## Document digitization

Document parsing is the default mode. Its default readable output is Markdown:

```shell
uv run main.py digitize invoice.pdf
uv run main.py digitize invoice.pdf --format html
uv run main.py digitize invoice.pdf --format text
```

Use OCR when you only need recognized plain text:

```shell
uv run main.py digitize scan.png --mode ocr
uv run main.py digitize scan.png --mode ocr --format text
```

`--format auto` is the default: it selects Markdown for document parsing and
text for OCR. OCR does not support Markdown or HTML output. Every successful
digitization is also saved under `docs/`, using the input filename with an
extension matching the output format:

```text
docs/invoice.md
docs/invoice.txt
docs/invoice.html
docs/invoice.json
```

The `.json` file is produced when `--json` is used and contains the complete
upstream response. Existing files with the same name are overwritten.

## Information extraction

Pass a file containing a bare JSON Schema object to `--schema`:

```json
{
  "type": "object",
  "properties": {
    "invoice_number": {
      "type": "string",
      "description": "The invoice identifier"
    },
    "total": {
      "type": "number",
      "description": "The invoice total"
    }
  },
  "required": ["invoice_number"]
}
```

Run extraction with:

```shell
uv run main.py extract invoice.pdf --schema schema/invoice-schema.json
```

The schema file itself is supplied to the API. Do not wrap it in
`response_format` or `json_schema`; the CLI adds those protocol fields.

## Output and errors

By default, commands print only the useful result: assistant text, digitized
document content, or pretty-printed extracted JSON. Add `--json` to any command
to print the complete upstream response instead:

```shell
uv run main.py digitize invoice.pdf --json
uv run main.py extract invoice.pdf --schema schema/invoice-schema.json --json
```

Input, configuration, HTTP, and malformed-response errors are written to
standard error, and the process exits with a nonzero status. API keys are never
included in error output.

## Tests

The test suite mocks all HTTP calls; it does not need credentials or make
billable requests:

```shell
uv run python -m unittest discover
```
