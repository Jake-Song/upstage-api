"""Digitize a local document and print the result as Markdown."""

import argparse
import os
from pathlib import Path

import requests

if __package__:
    from .progress import progress_bar
else:
    from progress import progress_bar


OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs" / "digitization"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Digitize a document with Upstage Document Parse."
    )
    parser.add_argument("document", type=Path, help="Path to a local document")
    args = parser.parse_args()

    api_key = os.environ.get("UPSTAGE_API_KEY")
    if not api_key:
        parser.error("UPSTAGE_API_KEY must be set")
    if not args.document.is_file():
        parser.error(f"document does not exist or is not a file: {args.document}")

    with progress_bar("Digitizing document"):
        with args.document.open("rb") as document:
            response = requests.post(
                "https://api.upstage.ai/v1/document-digitization",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"document": document},
                data={
                    "model": "document-parse",
                    "output_formats": '["markdown"]',
                },
            )
        response.raise_for_status()

    markdown = response.json()["content"]["markdown"]

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / f"{args.document.stem}.md").write_text(markdown)

    print(markdown)


if __name__ == "__main__":
    main()
