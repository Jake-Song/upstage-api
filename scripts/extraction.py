"""Extract invoice fields from a local document using JSON Schema."""

import argparse
import base64
import json
import os
from pathlib import Path

import requests


OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs"


INVOICE_SCHEMA = {
    "type": "object",
    "properties": {
        "invoice_number": {
            "type": "string",
            "description": "The invoice identifier",
        },
        "vendor_name": {
            "type": "string",
            "description": "The name of the invoice issuer",
        },
        "total_amount": {
            "type": "number",
            "description": "The total amount due",
        },
    },
    "required": ["invoice_number", "vendor_name", "total_amount"],
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract invoice fields from a document with Upstage."
    )
    parser.add_argument("document", type=Path, help="Path to a local document")
    args = parser.parse_args()

    api_key = os.environ.get("UPSTAGE_API_KEY")
    if not api_key:
        parser.error("UPSTAGE_API_KEY must be set")
    if not args.document.is_file():
        parser.error(f"document does not exist or is not a file: {args.document}")

    encoded_document = base64.b64encode(args.document.read_bytes()).decode("ascii")
    response = requests.post(
        "https://api.upstage.ai/v1/information-extraction",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "information-extract",
            "messages": [
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
                }
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "invoice_schema",
                    "schema": INVOICE_SCHEMA,
                },
            },
        },
    )
    response.raise_for_status()

    content = response.json()["choices"][0]["message"]["content"]
    output = json.dumps(json.loads(content), indent=2, ensure_ascii=False)

    OUTPUTS_DIR.mkdir(exist_ok=True)
    (OUTPUTS_DIR / f"{args.document.stem}.json").write_text(f"{output}\n")

    print(output)


if __name__ == "__main__":
    main()
