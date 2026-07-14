"""Run a local document through an Upstage Studio Agent."""

import argparse
import json
import os
import time
from pathlib import Path

import requests

if __package__:
    from .progress import progress_bar
else:
    from progress import progress_bar


DEFAULT_AGENT_ID = "agt_FmUrJTNMchBsSyxm6QrRRq"
OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs" / "agent"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process a document with an Agent created in Upstage Studio."
    )
    parser.add_argument("document", type=Path, help="Path to a local document")
    parser.add_argument(
        "--agent-id",
        default=DEFAULT_AGENT_ID,
        help=f"Upstage Agent ID (default: {DEFAULT_AGENT_ID})",
    )
    parser.add_argument(
        "--config-id",
        help='Agent config version (e.g. "1"); omit to use the latest',
    )
    args = parser.parse_args()

    api_key = os.environ.get("UPSTAGE_API_KEY")
    if not api_key:
        parser.error("UPSTAGE_API_KEY must be set")
    if not args.document.is_file():
        parser.error(f"document does not exist or is not a file: {args.document}")

    headers = {"Authorization": f"Bearer {api_key}"}
    with progress_bar("Running agent"):
        with args.document.open("rb") as document:
            response = requests.post(
                "https://api.upstage.ai/v2/files",
                headers=headers,
                files={"file": document},
                data={"purpose": "user_data"},
            )
        try:
            response.raise_for_status()
        except requests.HTTPError:
            detail = response.text.strip()
            parser.error(f"file upload failed: {detail or response.status_code}")
        file_id = response.json()["id"]

        job = {
            "model": args.agent_id,
            "include": ["last"],
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_file", "file_id": file_id}],
                }
            ],
        }
        if args.config_id:
            job["config_id"] = args.config_id
        response = requests.post(
            "https://api.upstage.ai/v2/responses",
            headers={**headers, "Content-Type": "application/json"},
            json=job,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError:
            detail = response.text.strip()
            parser.error(f"agent job creation failed: {detail or response.status_code}")
        result = response.json()

        while result["status"] in {"queued", "in_progress"}:
            time.sleep(2)
            response = requests.get(
                f"https://api.upstage.ai/v2/responses/{result['id']}",
                headers=headers,
                params={"include[]": "last"},
            )
            try:
                response.raise_for_status()
            except requests.HTTPError:
                detail = response.text.strip()
                parser.error(
                    f"agent job retrieval failed: {detail or response.status_code}"
                )
            result = response.json()

        requests.delete(f"https://api.upstage.ai/v2/files/{file_id}", headers=headers)

        if result["status"] != "completed":
            error = result.get("error") or "check the agent config in Studio"
            parser.error(f"agent job ended with status {result['status']}: {error}")

    output_text = result.get("output_text")
    if output_text is None:
        output_text = result["output"][-1]["content"][0]["text"]
    output = json.dumps(json.loads(output_text), indent=2, ensure_ascii=False)

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / f"{args.document.stem}.json").write_text(f"{output}\n")

    print(output)


if __name__ == "__main__":
    main()
