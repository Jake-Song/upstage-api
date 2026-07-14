import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests


API_BASE_URL = "https://api.upstage.ai/v1"
AGENT_API_BASE_URL = "https://api.upstage.ai/v2"


class CLIError(Exception):
    """An error that can be shown to the user without a traceback."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Use Upstage Solar, document, and agent APIs from the command line."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    chat_parser = subparsers.add_parser("chat", help="Send a one-shot chat prompt")
    chat_parser.add_argument("prompt", metavar="PROMPT")
    chat_parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high"),
        default="medium",
        help="Reasoning effort (default: medium)",
    )
    chat_parser.add_argument("--json", action="store_true", help="Print the full API response")

    digitize_parser = subparsers.add_parser(
        "digitize", help="Parse a document or run OCR"
    )
    digitize_parser.add_argument("document", metavar="DOCUMENT", type=Path)
    digitize_parser.add_argument(
        "--mode", choices=("parse", "ocr"), default="parse", help="Digitization mode"
    )
    digitize_parser.add_argument(
        "--format",
        choices=("auto", "text", "markdown", "html"),
        default="auto",
        help="Readable output format",
    )
    digitize_parser.add_argument(
        "--json", action="store_true", help="Print the full API response"
    )

    extract_parser = subparsers.add_parser(
        "extract", help="Extract fields using a JSON Schema"
    )
    extract_parser.add_argument("document", metavar="DOCUMENT", type=Path)
    extract_parser.add_argument("--schema", required=True, metavar="SCHEMA", type=Path)
    extract_parser.add_argument(
        "--json", action="store_true", help="Print the full API response"
    )

    agent_parser = subparsers.add_parser(
        "agent", help="Process a document with an Upstage Agent"
    )
    agent_parser.add_argument("document", metavar="DOCUMENT", type=Path)
    agent_parser.add_argument("--agent-id", required=True, metavar="AGENT_ID")
    agent_parser.add_argument(
        "--json", action="store_true", help="Print the final API response"
    )

    return parser


def api_headers(api_key: str, *, json_request: bool = False) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {api_key}"}
    if json_request:
        headers["Content-Type"] = "application/json"
    return headers


def response_json(response: requests.Response) -> dict[str, Any]:
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else response.status_code
        raise CLIError(f"Upstage API request failed with HTTP status {status}.") from None

    try:
        result = response.json()
    except (requests.JSONDecodeError, ValueError):
        raise CLIError("Upstage API returned a response that was not valid JSON.") from None
    if not isinstance(result, dict):
        raise CLIError("Upstage API returned an unexpected response shape.")
    return result


def post(url: str, **kwargs: Any) -> dict[str, Any]:
    try:
        response = requests.post(url, **kwargs)
    except requests.RequestException:
        raise CLIError("Could not connect to the Upstage API.") from None
    return response_json(response)


def get(url: str, **kwargs: Any) -> dict[str, Any]:
    try:
        response = requests.get(url, **kwargs)
    except requests.RequestException:
        raise CLIError("Could not connect to the Upstage API.") from None
    return response_json(response)


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise CLIError(f"{label} file does not exist or is not a regular file: {path}")


def choice_content(result: dict[str, Any]) -> str:
    try:
        content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise CLIError("Upstage API returned an unexpected response shape.") from None
    if not isinstance(content, str):
        raise CLIError("Upstage API returned an unexpected response shape.")
    return content


def run_chat(prompt: str, reasoning_effort: str, api_key: str) -> dict[str, Any]:
    return post(
        f"{API_BASE_URL}/chat/completions",
        headers=api_headers(api_key, json_request=True),
        json={
            "model": "solar-pro3",
            "messages": [{"role": "user", "content": prompt}],
            "reasoning_effort": reasoning_effort,
            "stream": False,
        },
    )


def run_digitize(
    document: Path, mode: str, output_format: str, api_key: str
) -> tuple[dict[str, Any], str]:
    require_file(document, "Document")
    if mode == "ocr" and output_format in {"markdown", "html"}:
        raise CLIError(f"--format {output_format} is not supported with --mode ocr.")

    selected_format = (
        "markdown" if output_format == "auto" and mode == "parse" else output_format
    )
    if selected_format == "auto":
        selected_format = "text"

    data = {"model": "document-parse" if mode == "parse" else "ocr"}
    if mode == "parse":
        data["output_formats"] = json.dumps([selected_format])

    try:
        with document.open("rb") as document_file:
            result = post(
                f"{API_BASE_URL}/document-digitization",
                headers=api_headers(api_key),
                files={"document": document_file},
                data=data,
            )
    except OSError as exc:
        raise CLIError(f"Could not read document {document}: {exc}") from None
    return result, selected_format


def digitized_content(result: dict[str, Any], mode: str, output_format: str) -> str:
    try:
        content = result["text"] if mode == "ocr" else result["content"][output_format]
    except (KeyError, TypeError):
        raise CLIError("Upstage API returned an unexpected response shape.") from None
    if not isinstance(content, str):
        raise CLIError("Upstage API returned an unexpected response shape.")
    return content


def load_schema(path: Path) -> dict[str, Any]:
    require_file(path, "Schema")
    try:
        with path.open(encoding="utf-8") as schema_file:
            schema = json.load(schema_file)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CLIError(f"Could not read a valid JSON schema from {path}: {exc}") from None
    if not isinstance(schema, dict):
        raise CLIError("Schema must be a JSON object.")
    return schema


def run_extract(document: Path, schema_path: Path, api_key: str) -> dict[str, Any]:
    require_file(document, "Document")
    schema = load_schema(schema_path)
    try:
        encoded_document = base64.b64encode(document.read_bytes()).decode("ascii")
    except OSError as exc:
        raise CLIError(f"Could not read document {document}: {exc}") from None

    return post(
        f"{API_BASE_URL}/information-extraction",
        headers=api_headers(api_key, json_request=True),
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
                "json_schema": {"name": "document_schema", "schema": schema},
            },
        },
    )


def run_agent(document: Path, agent_id: str, api_key: str) -> dict[str, Any]:
    require_file(document, "Document")
    try:
        with document.open("rb") as document_file:
            uploaded = post(
                f"{AGENT_API_BASE_URL}/files",
                headers=api_headers(api_key),
                files={"file": document_file},
                data={"purpose": "user_data"},
            )
    except OSError as exc:
        raise CLIError(f"Could not read document {document}: {exc}") from None

    file_id = uploaded.get("id")
    if not isinstance(file_id, str):
        raise CLIError("Upstage API returned an unexpected file upload response.")

    result = post(
        f"{AGENT_API_BASE_URL}/responses",
        headers=api_headers(api_key, json_request=True),
        json={
            "model": agent_id,
            "include": ["last"],
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_file", "file_id": file_id}],
                }
            ],
        },
    )

    while result.get("status") in {"queued", "in_progress"}:
        job_id = result.get("id")
        if not isinstance(job_id, str):
            raise CLIError("Upstage API returned an unexpected agent job response.")
        time.sleep(2)
        result = get(
            f"{AGENT_API_BASE_URL}/responses/{job_id}",
            headers=api_headers(api_key),
            params={"include": ["last"]},
        )

    status = result.get("status")
    if status != "completed":
        if not isinstance(status, str):
            raise CLIError("Upstage API returned an unexpected agent job response.")
        raise CLIError(f"Agent job ended with status {status}.")
    return result


def agent_output_text(result: dict[str, Any]) -> str:
    direct_output = result.get("output_text")
    if isinstance(direct_output, str):
        return direct_output

    output = result.get("output")
    if isinstance(output, list):
        for item in reversed(output):
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
                    return part["text"]
    raise CLIError("Upstage API returned an unexpected agent output response.")


def print_agent_output(result: dict[str, Any]) -> None:
    output = agent_output_text(result)
    try:
        parsed_output = json.loads(output)
    except json.JSONDecodeError:
        print(output)
    else:
        print_json(parsed_output)


def print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    api_key = os.environ.get("UPSTAGE_API_KEY")
    if not api_key:
        print("error: UPSTAGE_API_KEY is not set.", file=sys.stderr)
        return 1

    try:
        if args.command == "chat":
            result = run_chat(args.prompt, args.reasoning_effort, api_key)
            if args.json:
                print_json(result)
            else:
                print(choice_content(result))
        elif args.command == "digitize":
            result, selected_format = run_digitize(
                args.document, args.mode, args.format, api_key
            )
            if args.json:
                print_json(result)
            else:
                print(digitized_content(result, args.mode, selected_format))
        elif args.command == "extract":
            result = run_extract(args.document, args.schema, api_key)
            if args.json:
                print_json(result)
            else:
                content = choice_content(result)
                try:
                    extracted = json.loads(content)
                except json.JSONDecodeError:
                    raise CLIError(
                        "Upstage API returned extraction content that was not valid JSON."
                    ) from None
                print_json(extracted)
        else:
            result = run_agent(args.document, args.agent_id, api_key)
            if args.json:
                print_json(result)
            else:
                print_agent_output(result)
    except CLIError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
