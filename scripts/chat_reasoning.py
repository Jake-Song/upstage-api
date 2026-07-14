"""Send a prompt to Solar Pro 3 and print its reasoning and answer."""

import argparse
import os

import requests


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ask Solar Pro 3 a question with high reasoning effort."
    )
    parser.add_argument("prompt", help="Prompt to send to the model")
    args = parser.parse_args()

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
            "messages": [{"role": "user", "content": args.prompt}],
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
