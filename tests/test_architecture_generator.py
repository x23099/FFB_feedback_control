import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "tools" / "generate_architecture.py"
SPEC = importlib.util.spec_from_file_location("architecture_generator", SCRIPT)
generator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(generator)


class ArchitectureGeneratorTest(unittest.TestCase):
    def test_parse_responses_api_text(self):
        response = {"output": [{"content": [{"type": "output_text", "text": '{"nodes": []}'}]}]}
        self.assertEqual(generator.response_text(response, "responses"), '{"nodes": []}')

    def test_parse_chat_completions_text(self):
        response = {"choices": [{"message": {"content": '{"nodes": []}'}}]}
        self.assertEqual(generator.response_text(response, "chat-completions"), '{"nodes": []}')

    def test_validate_repairs_ai_output(self):
        data = {
            "repository": {"name": "Example"},
            "nodes": [
                {"id": "sender", "label": "Sender", "group": "runtime"},
                {"id": "receiver", "label": "Receiver", "group": "runtime"},
            ],
            "edges": [
                {"source": "sender", "target": "receiver", "label": "data"},
                {"source": "missing", "target": "receiver"},
            ],
            "flows": [],
        }
        result = generator.validate_ai_architecture(data)
        self.assertEqual(len(result["edges"]), 1)
        self.assertEqual(len(result["flows"]), 1)
        self.assertTrue(all("x" in node and "y" in node for node in result["nodes"]))
        self.assertIn("runtime", result["groups"])

    def test_context_excludes_sensitive_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("safe overview", encoding="utf-8")
            (root / "api_key.txt").write_text("do-not-send", encoding="utf-8")
            context = generator.collect_ai_context(root, [Path("README.md"), Path("api_key.txt")], 5000)
            self.assertIn("safe overview", context)
            self.assertNotIn("do-not-send", context)

    def test_markdown_json_is_accepted(self):
        self.assertEqual(generator.parse_ai_json("```json\n{\"ok\": true}\n```"), {"ok": True})

    def test_ai_generation_end_to_end_with_mock_response(self):
        ai_data = {
            "repository": {"name": "Semantic Example"},
            "groups": {"system": {"label": "System", "color": "#123456"}},
            "nodes": [
                {"id": "input", "label": "Input", "group": "system", "x": 100, "y": 100},
                {"id": "output", "label": "Output", "group": "system", "x": 400, "y": 100},
            ],
            "edges": [{"id": "e1", "source": "input", "target": "output", "label": "data"}],
            "flows": [{"id": "f1", "name": "Input flow", "steps": ["input", "output"], "edgeIds": ["e1"]}],
        }
        mock_response = {"output_text": json.dumps(ai_data)}
        with patch.object(generator, "post_json", return_value=mock_response) as request:
            result = generator.generate_with_ai({}, "README", "https://example.test/v1", "test-model", "key", "responses", 10)
        self.assertEqual(result["repository"]["name"], "Semantic Example")
        self.assertEqual(len(result["flows"]), 1)
        self.assertTrue(request.call_args.args[0].endswith("/responses"))


if __name__ == "__main__":
    unittest.main()
