"""Send a prompt to Solar Pro 3 and print its reasoning and answer."""

import argparse
import json
import os
from pathlib import Path

import requests


EXAMPLES_FILE = Path(__file__).resolve().parent.parent / "examples" / "reasoning.jsonl"
OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs"


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
    parser.add_argument(
        "--all-examples",
        action="store_true",
        help="Run every prompt in examples/reasoning.jsonl",
    )
    args = parser.parse_args()

    selection_count = sum(
        (args.prompt is not None, args.example is not None, args.all_examples)
    )
    if selection_count != 1:
        parser.error("provide a prompt, --example, or --all-examples")

    if args.all_examples:
        runs = sorted(examples.items())
    elif args.example:
        runs = [(args.example, examples[args.example])]
    else:
        runs = [("chat_reasoning", args.prompt)]

    api_key = os.environ.get("UPSTAGE_API_KEY")
    if not api_key:
        parser.error("UPSTAGE_API_KEY must be set")

    OUTPUTS_DIR.mkdir(exist_ok=True)
    output_records = []
    for index, (output_name, prompt) in enumerate(runs):
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
        reasoning = message.get("reasoning", "(No reasoning returned)")
        answer = message["content"]
        output = (
            "Reasoning:\n"
            f"{reasoning}\n\n"
            "Answer:\n"
            f"{answer}"
        )
        output_records.append(
            {
                "name": output_name,
                "prompt": prompt,
                "reasoning": reasoning,
                "answer": answer,
            }
        )

        if args.all_examples:
            if index:
                print()
            print(f"=== {output_name} ===")
        print(output)

    output_text = "".join(
        f"{json.dumps(record, ensure_ascii=False)}\n" for record in output_records
    )
    (OUTPUTS_DIR / "reasoning.jsonl").write_text(output_text)


if __name__ == "__main__":
    main()
