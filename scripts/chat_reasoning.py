"""Send a prompt to Solar Pro 3 and print its reasoning and answer."""

import argparse
import json
import os
from pathlib import Path

import requests


EXAMPLES_FILE = Path(__file__).resolve().parent.parent / "examples" / "reasoning.jsonl"


def main() -> None:
    examples = {}
    with EXAMPLES_FILE.open() as file:
        for line in file:
            example = json.loads(line)
            examples[example["name"]] = example["prompt"]

    parser = argparse.ArgumentParser(
        description="Ask Solar Pro 3 a question with high reasoning effort."
    )
    parser.add_argument("prompt", nargs="?", help="Prompt to send to the model")
    parser.add_argument(
        "--example",
        choices=sorted(examples),
        help="Load a prompt from examples/reasoning.jsonl",
    )
    args = parser.parse_args()

    if (args.prompt is None) == (args.example is None):
        parser.error("provide either a prompt or --example")

    prompt = args.prompt
    if args.example:
        prompt = examples[args.example]

    api_key = os.environ.get("UPSTAGE_API_KEY")
    if not api_key:
        parser.error("UPSTAGE_API_KEY must be set")

    response = requests.post(
        "https://api.upstage.ai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "solar-pro3",
            "messages": [{"role": "user", "content": prompt}],
            "reasoning_effort": "high",
        },
    )
    response.raise_for_status()

    message = response.json()["choices"][0]["message"]
    print("Reasoning:")
    print(message.get("reasoning", "(No reasoning returned)"))
    print("\nAnswer:")
    print(message["content"])


if __name__ == "__main__":
    main()
