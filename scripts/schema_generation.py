"""Generate a JSON Schema from a local document."""

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


OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs" / "schema_generation"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate an extraction schema from a document with Upstage."
    )
    parser.add_argument("document", type=Path, help="Path to a local document")
    parser.add_argument(
        "--prompt",
        default=(
            "Generate a schema for extracting structured "
            "information from this document."
        ),
        help="Instruction guiding what the schema should extract",
    )
    args = parser.parse_args()

    api_key = os.environ.get("UPSTAGE_API_KEY")
    if not api_key:
        parser.error("UPSTAGE_API_KEY must be set")
    if not args.document.is_file():
        parser.error(f"document does not exist or is not a file: {args.document}")

    encoded_document = base64.b64encode(args.document.read_bytes()).decode("ascii")
    with progress_bar("Generating schema"):
        response = requests.post(
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
                        "content": args.prompt,
                    },
                    {
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
                    },
                ],
            },
        )
        try:
            response.raise_for_status()
        except requests.HTTPError:
            detail = response.text.strip()
            parser.error(f"schema generation failed: {detail or response.status_code}")

    try:
        generated_format = json.loads(
            response.json()["choices"][0]["message"]["content"]
        )
        schema = generated_format["json_schema"]["schema"]
    except (json.JSONDecodeError, KeyError, TypeError, IndexError):
        parser.error("schema generation returned an invalid schema")
    if not isinstance(schema, dict):
        parser.error("generated schema must be a JSON object")

    output = json.dumps(schema, indent=2, ensure_ascii=False)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / f"{args.document.stem}-schema.json").write_text(f"{output}\n")

    print(output)


if __name__ == "__main__":
    main()
