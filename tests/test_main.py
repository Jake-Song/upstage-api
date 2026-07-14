import base64
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import requests

import main


class CLITestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.doc_dir = self.root / "doc"
        doc_dir_patch = patch("main.DOC_DIR", self.doc_dir)
        doc_dir_patch.start()
        self.addCleanup(doc_dir_patch.stop)
        self.document = self.root / "document.bin"
        self.document.write_bytes(b"document bytes")
        self.schema = self.root / "schema.json"
        self.schema_value = {
            "type": "object",
            "properties": {"invoice_number": {"type": "string"}},
        }
        self.schema.write_text(json.dumps(self.schema_value), encoding="utf-8")

    def response(self, value, status=200):
        response = Mock(spec=requests.Response)
        response.status_code = status
        response.json.return_value = value
        response.raise_for_status.return_value = None
        return response

    def invoke(self, argv, response=None, *, api_key="test-key"):
        stdout = StringIO()
        stderr = StringIO()
        environment = {} if api_key is None else {"UPSTAGE_API_KEY": api_key}
        with (
            patch.dict(os.environ, environment, clear=True),
            patch("main.requests.post", return_value=response) as post,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            status = main.main(argv)
        return status, stdout.getvalue(), stderr.getvalue(), post

    def test_chat_readable_output_and_request(self):
        response = self.response(
            {"choices": [{"message": {"content": "Hello from Solar"}}]}
        )
        status, stdout, stderr, post = self.invoke(["chat", "Hello"], response)

        self.assertEqual(status, 0)
        self.assertEqual(stdout, "Hello from Solar\n")
        self.assertEqual(stderr, "")
        post.assert_called_once_with(
            "https://api.upstage.ai/v1/chat/completions",
            headers={
                "Authorization": "Bearer test-key",
                "Content-Type": "application/json",
            },
            json={
                "model": "solar-pro3",
                "messages": [{"role": "user", "content": "Hello"}],
                "reasoning_effort": "medium",
                "stream": False,
            },
        )

    def test_chat_forwards_reasoning_effort(self):
        response = self.response(
            {"choices": [{"message": {"content": "Considered answer"}}]}
        )
        status, _, _, post = self.invoke(
            ["chat", "Think carefully", "--reasoning-effort", "high"], response
        )

        self.assertEqual(status, 0)
        self.assertEqual(post.call_args.kwargs["json"]["reasoning_effort"], "high")

    def test_chat_json_prints_complete_response(self):
        value = {"id": "chat-1", "choices": [{"message": {"content": "Hi"}}]}
        status, stdout, _, _ = self.invoke(["chat", "Hello", "--json"], self.response(value))
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(stdout), value)

    def test_parse_defaults_to_markdown(self):
        value = {"content": {"markdown": "# Parsed"}}
        status, stdout, _, post = self.invoke(
            ["digitize", str(self.document)], self.response(value)
        )
        self.assertEqual(status, 0)
        self.assertEqual(stdout, "# Parsed\n")
        self.assertEqual(
            (self.doc_dir / "document.md").read_text(encoding="utf-8"),
            "# Parsed",
        )
        _, kwargs = post.call_args
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer test-key"})
        self.assertEqual(
            kwargs["data"],
            {"model": "document-parse", "output_formats": '["markdown"]'},
        )
        self.assertEqual(kwargs["files"]["document"].name, str(self.document))

    def test_parse_supports_text_html_and_raw_json(self):
        for output_format in ("text", "html"):
            with self.subTest(output_format=output_format):
                value = {"content": {output_format: f"value-{output_format}"}}
                status, stdout, _, post = self.invoke(
                    ["digitize", str(self.document), "--format", output_format],
                    self.response(value),
                )
                self.assertEqual(status, 0)
                self.assertEqual(stdout, f"value-{output_format}\n")
                extension = ".txt" if output_format == "text" else ".html"
                self.assertEqual(
                    (self.doc_dir / f"document{extension}").read_text(
                        encoding="utf-8"
                    ),
                    f"value-{output_format}",
                )
                self.assertEqual(
                    post.call_args.kwargs["data"]["output_formats"],
                    json.dumps([output_format]),
                )

        value = {"content": {"markdown": "raw"}, "api": "2.0"}
        status, stdout, _, _ = self.invoke(
            ["digitize", str(self.document), "--json"], self.response(value)
        )
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(stdout), value)
        self.assertEqual(
            json.loads((self.doc_dir / "document.json").read_text(encoding="utf-8")),
            value,
        )

    def test_ocr_defaults_to_text(self):
        status, stdout, _, post = self.invoke(
            ["digitize", str(self.document), "--mode", "ocr"],
            self.response({"text": "recognized"}),
        )
        self.assertEqual(status, 0)
        self.assertEqual(stdout, "recognized\n")
        self.assertEqual(
            (self.doc_dir / "document.txt").read_text(encoding="utf-8"),
            "recognized",
        )
        self.assertEqual(post.call_args.kwargs["data"], {"model": "ocr"})

    def test_ocr_rejects_markup_formats_without_request(self):
        for output_format in ("markdown", "html"):
            with self.subTest(output_format=output_format):
                status, _, stderr, post = self.invoke(
                    [
                        "digitize",
                        str(self.document),
                        "--mode",
                        "ocr",
                        "--format",
                        output_format,
                    ],
                    self.response({}),
                )
                self.assertEqual(status, 1)
                self.assertIn("not supported", stderr)
                post.assert_not_called()

    def test_extract_encodes_document_and_forwards_schema(self):
        value = {
            "choices": [
                {"message": {"content": '{"invoice_number":"INV-1"}'}}
            ]
        }
        status, stdout, _, post = self.invoke(
            ["extract", str(self.document), "--schema", str(self.schema)],
            self.response(value),
        )
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(stdout), {"invoice_number": "INV-1"})
        post.assert_called_once()
        self.assertEqual(
            post.call_args.args[0],
            "https://api.upstage.ai/v1/information-extraction",
        )
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "information-extract")
        self.assertEqual(
            payload["messages"][0]["content"][0]["image_url"]["url"],
            "data:application/octet-stream;base64,"
            + base64.b64encode(b"document bytes").decode("ascii"),
        )
        self.assertEqual(
            payload["response_format"],
            {
                "type": "json_schema",
                "json_schema": {
                    "name": "document_schema",
                    "schema": self.schema_value,
                },
            },
        )

    def test_extract_json_prints_complete_response(self):
        value = {"id": "iex-1", "choices": []}
        status, stdout, _, _ = self.invoke(
            [
                "extract",
                str(self.document),
                "--schema",
                str(self.schema),
                "--json",
            ],
            self.response(value),
        )
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(stdout), value)

    def test_agent_uploads_document_runs_job_and_polls(self):
        uploaded = self.response({"id": "file-abc123"})
        created = self.response({"id": "resp-123", "status": "queued"})
        completed_value = {
            "id": "resp-123",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"invoice_number":"INV-1"}',
                        }
                    ],
                }
            ],
        }
        stdout, stderr = StringIO(), StringIO()
        with (
            patch.dict(os.environ, {"UPSTAGE_API_KEY": "test-key"}, clear=True),
            patch("main.requests.post", side_effect=[uploaded, created]) as post,
            patch("main.requests.get", return_value=self.response(completed_value)) as get,
            patch("main.time.sleep") as sleep,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            status = main.main(
                ["agent", str(self.document), "--agent-id", "agt-example"]
            )

        self.assertEqual(status, 0)
        self.assertEqual(json.loads(stdout.getvalue()), {"invoice_number": "INV-1"})
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(post.call_count, 2)
        upload_call, create_call = post.call_args_list
        self.assertEqual(upload_call.args[0], "https://api.upstage.ai/v2/files")
        self.assertEqual(upload_call.kwargs["data"], {"purpose": "user_data"})
        self.assertEqual(upload_call.kwargs["files"]["file"].name, str(self.document))
        self.assertEqual(create_call.args[0], "https://api.upstage.ai/v2/responses")
        self.assertEqual(
            create_call.kwargs["json"],
            {
                "model": "agt-example",
                "include": ["last"],
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_file", "file_id": "file-abc123"}
                        ],
                    }
                ],
            },
        )
        sleep.assert_called_once_with(2)
        get.assert_called_once_with(
            "https://api.upstage.ai/v2/responses/resp-123",
            headers={"Authorization": "Bearer test-key"},
            params={"include": ["last"]},
        )

    def test_agent_json_prints_completed_response(self):
        completed_value = {
            "id": "resp-123",
            "status": "completed",
            "output_text": "done",
        }
        stdout, stderr = StringIO(), StringIO()
        with (
            patch.dict(os.environ, {"UPSTAGE_API_KEY": "test-key"}, clear=True),
            patch(
                "main.requests.post",
                side_effect=[
                    self.response({"id": "file-abc123"}),
                    self.response(completed_value),
                ],
            ),
            patch("main.requests.get") as get,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            status = main.main(
                [
                    "agent",
                    str(self.document),
                    "--agent-id",
                    "agt-example",
                    "--json",
                ]
            )

        self.assertEqual(status, 0)
        self.assertEqual(json.loads(stdout.getvalue()), completed_value)
        self.assertEqual(stderr.getvalue(), "")
        get.assert_not_called()

    def test_agent_rejects_malformed_upload_and_failed_job(self):
        cases = (
            ([self.response({})], "file upload"),
            (
                [
                    self.response({"id": "file-abc123"}),
                    self.response({"id": "resp-123", "status": "failed"}),
                ],
                "failed",
            ),
        )
        for responses, expected_error in cases:
            with self.subTest(expected_error=expected_error):
                stdout, stderr = StringIO(), StringIO()
                with (
                    patch.dict(
                        os.environ, {"UPSTAGE_API_KEY": "test-key"}, clear=True
                    ),
                    patch("main.requests.post", side_effect=responses),
                    redirect_stdout(stdout),
                    redirect_stderr(stderr),
                ):
                    status = main.main(
                        ["agent", str(self.document), "--agent-id", "agt-example"]
                    )
                self.assertEqual(status, 1)
                self.assertIn(expected_error, stderr.getvalue())

    def test_missing_api_key(self):
        status, stdout, stderr, post = self.invoke(
            ["chat", "Hello"], self.response({}), api_key=None
        )
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertIn("UPSTAGE_API_KEY", stderr)
        post.assert_not_called()

    def test_progress_bar_is_shown_only_on_a_terminal(self):
        class TerminalBuffer(StringIO):
            def isatty(self):
                return True

        terminal = TerminalBuffer()
        with patch("main.sys.stderr", terminal):
            with main.progress_bar("Working"):
                pass

        self.assertIn("Working", terminal.getvalue())
        self.assertIn("done", terminal.getvalue())

        redirected = StringIO()
        with patch("main.sys.stderr", redirected):
            with main.progress_bar("Working"):
                pass
        self.assertEqual(redirected.getvalue(), "")

    def test_missing_document_and_schema_files(self):
        missing = self.root / "missing"
        cases = [
            ["digitize", str(missing)],
            ["extract", str(missing), "--schema", str(self.schema)],
            ["extract", str(self.document), "--schema", str(missing)],
        ]
        for argv in cases:
            with self.subTest(argv=argv):
                status, _, stderr, post = self.invoke(argv, self.response({}))
                self.assertEqual(status, 1)
                self.assertIn("does not exist", stderr)
                post.assert_not_called()

    def test_invalid_schema_json_and_non_object(self):
        schemas = ("not json", "[]")
        for content in schemas:
            with self.subTest(content=content):
                self.schema.write_text(content, encoding="utf-8")
                status, _, stderr, post = self.invoke(
                    ["extract", str(self.document), "--schema", str(self.schema)],
                    self.response({}),
                )
                self.assertEqual(status, 1)
                self.assertIn("schema", stderr.lower())
                post.assert_not_called()

    def test_http_and_network_errors_are_safe(self):
        http_response = self.response({}, status=429)
        error_response = requests.Response()
        error_response.status_code = 429
        http_response.raise_for_status.side_effect = requests.HTTPError(
            response=error_response
        )
        status, _, stderr, _ = self.invoke(["chat", "Hello"], http_response)
        self.assertEqual(status, 1)
        self.assertIn("429", stderr)
        self.assertNotIn("test-key", stderr)

        with patch("main.requests.post", side_effect=requests.ConnectionError()):
            stdout, stderr = StringIO(), StringIO()
            with (
                patch.dict(os.environ, {"UPSTAGE_API_KEY": "secret"}, clear=True),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                status = main.main(["chat", "Hello"])
        self.assertEqual(status, 1)
        self.assertIn("connect", stderr.getvalue().lower())
        self.assertNotIn("secret", stderr.getvalue())

    def test_malformed_api_responses(self):
        values = (
            {},
            {"choices": []},
            {"choices": [{"message": {"content": None}}]},
        )
        for value in values:
            with self.subTest(value=value):
                status, _, stderr, _ = self.invoke(
                    ["chat", "Hello"], self.response(value)
                )
                self.assertEqual(status, 1)
                self.assertIn("unexpected response shape", stderr)

    def test_invalid_extracted_json(self):
        value = {"choices": [{"message": {"content": "not json"}}]}
        status, _, stderr, _ = self.invoke(
            ["extract", str(self.document), "--schema", str(self.schema)],
            self.response(value),
        )
        self.assertEqual(status, 1)
        self.assertIn("not valid JSON", stderr)


if __name__ == "__main__":
    unittest.main()
