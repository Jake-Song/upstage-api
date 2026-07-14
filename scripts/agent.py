"""Run a local document through an Upstage Agent."""

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


OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs" / "agent"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process a document with an Agent created in Upstage Studio."
    )
    parser.add_argument("document", type=Path, help="Path to a local document")
    parser.add_argument("--agent-id", required=True, help="Upstage Agent ID")
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
            uploaded = response.json()
            file_id = uploaded["id"]
        except requests.HTTPError:
            detail = response.text.strip()
            parser.error(f"file upload failed: {detail or response.status_code}")
        except (requests.JSONDecodeError, ValueError, KeyError, TypeError):
            parser.error("file upload returned an invalid response")
        if not isinstance(file_id, str):
            parser.error("file upload returned an invalid response")

        response = requests.post(
            "https://api.upstage.ai/v2/responses",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "model": args.agent_id,
                "include": ["last"],
                "input": [
                    {
                        "role": "user",
                        "content": [{"type": "input_file", "file_id": file_id}],
                    }
                ],
            },
        )
        try:
            response.raise_for_status()
            result = response.json()
        except requests.HTTPError:
            detail = response.text.strip()
            parser.error(f"agent job creation failed: {detail or response.status_code}")
        except (requests.JSONDecodeError, ValueError):
            parser.error("agent job creation returned an invalid response")
        if not isinstance(result, dict):
            parser.error("agent job creation returned an invalid response")

        while result.get("status") in {"queued", "in_progress"}:
            job_id = result.get("id")
            if not isinstance(job_id, str):
                parser.error("agent job returned an invalid response")
            time.sleep(2)
            response = requests.get(
                f"https://api.upstage.ai/v2/responses/{job_id}",
                headers=headers,
                params={"include[]": "last"},
            )
            try:
                response.raise_for_status()
                result = response.json()
            except requests.HTTPError:
                detail = response.text.strip()
                parser.error(
                    f"agent job retrieval failed: {detail or response.status_code}"
                )
            except (requests.JSONDecodeError, ValueError):
                parser.error("agent job retrieval returned an invalid response")
            if not isinstance(result, dict):
                parser.error("agent job retrieval returned an invalid response")

        if result.get("status") != "completed":
            parser.error(f"agent job ended with status {result.get('status')}")

    output_text = result.get("output_text")
    if not isinstance(output_text, str):
        output_items = result.get("output")
        if isinstance(output_items, list):
            for item in reversed(output_items):
                if not isinstance(item, dict) or item.get("type") != "message":
                    continue
                content = item.get("content")
                if not isinstance(content, list):
                    continue
                for part in reversed(content):
                    if (
                        isinstance(part, dict)
                        and part.get("type") == "output_text"
                        and isinstance(part.get("text"), str)
                    ):
                        output_text = part["text"]
                        break
                if isinstance(output_text, str):
                    break
    if not isinstance(output_text, str):
        parser.error("agent job returned no output text")

    try:
        parsed_output = json.loads(output_text)
    except json.JSONDecodeError:
        output = output_text
        extension = ".txt"
    else:
        output = json.dumps(parsed_output, indent=2, ensure_ascii=False)
        extension = ".json"

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / f"{args.document.stem}{extension}").write_text(f"{output}\n")

    print(output)


if __name__ == "__main__":
    main()
