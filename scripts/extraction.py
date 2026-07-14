"""Extract fields from a local document using JSON Schema."""

import argparse
import base64
import json
import os
from pathlib import Path

import requests

if __package__:
    from .progress import progress_bar
else:
    from progress import progress_bar


OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs" / "extraction"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract structured fields from a document with Upstage."
    )
    parser.add_argument("document", type=Path, help="Path to a local document")
    schema_group = parser.add_mutually_exclusive_group(required=True)
    schema_group.add_argument(
        "--schema",
        type=Path,
        help="Path to a JSON Schema file",
    )
    schema_group.add_argument(
        "--auto-schema",
        action="store_true",
        help="Generate a schema from the document before extraction",
    )
    args = parser.parse_args()

    api_key = os.environ.get("UPSTAGE_API_KEY")
    if not api_key:
        parser.error("UPSTAGE_API_KEY must be set")
    if not args.document.is_file():
        parser.error(f"document does not exist or is not a file: {args.document}")
    if args.schema and not args.schema.is_file():
        parser.error(f"schema does not exist or is not a file: {args.schema}")

    encoded_document = base64.b64encode(args.document.read_bytes()).decode("ascii")
    document_message = {
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {
                    "url": (
                        "data:application/octet-stream;base64,"
                        f"{encoded_document}"
                    )
                },
            }
        ],
    }

    if args.auto_schema:
        with progress_bar("Generating schema"):
            schema_response = requests.post(
                "https://api.upstage.ai/v1/information-extraction/schema-generation",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "information-extract",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Generate a schema for extracting structured "
                                "information from this document."
                            ),
                        },
                        document_message,
                    ],
                },
            )
            try:
                schema_response.raise_for_status()
            except requests.HTTPError:
                detail = schema_response.text.strip()
                parser.error(
                    f"schema generation failed: {detail or schema_response.status_code}"
                )

        try:
            generated_format = json.loads(
                schema_response.json()["choices"][0]["message"]["content"]
            )
            schema = generated_format["json_schema"]["schema"]
        except (json.JSONDecodeError, KeyError, TypeError, IndexError):
            parser.error("schema-generate returned an invalid schema")
    else:
        try:
            schema = json.loads(args.schema.read_text())
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            parser.error(f"could not read a valid JSON schema from {args.schema}: {exc}")

    if not isinstance(schema, dict):
        parser.error("schema must be a JSON object")

    with progress_bar("Extracting information"):
        response = requests.post(
            "https://api.upstage.ai/v1/information-extraction",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "information-extract",
                "messages": [document_message],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "document_schema",
                        "schema": schema,
                    },
                },
            },
        )
        response.raise_for_status()

    content = response.json()["choices"][0]["message"]["content"]
    output = json.dumps(json.loads(content), indent=2, ensure_ascii=False)

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / f"{args.document.stem}.json").write_text(f"{output}\n")

    print(output)


if __name__ == "__main__":
    main()
