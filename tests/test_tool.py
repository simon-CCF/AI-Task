import os
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

import tool


class ToolTests(unittest.TestCase):
    def test_load_dotenv_reads_values(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tmp:
            tmp.write("OPENROUTER_API_KEY=test-openrouter\n")
            tmp.write("GITHUB_TOKEN=test-github\n")
            env_path = tmp.name

        self.addCleanup(lambda: os.path.exists(env_path) and os.remove(env_path))

        with patch.dict(os.environ, {}, clear=True):
            tool.load_dotenv(env_path)
            self.assertEqual(os.getenv("OPENROUTER_API_KEY"), "test-openrouter")
            self.assertEqual(os.getenv("GITHUB_TOKEN"), "test-github")

    def test_normalize_query_output(self):
        text = "```\nlanguage:python   stars:>500\n```"
        self.assertEqual(tool.normalize_query_output(text), "language:python stars:>500")

    def test_parse_endpoints_filters_noise(self):
        raw = "info, readme.\nunknown, releases"
        self.assertEqual(tool.parse_endpoints(raw), ["info", "readme", "releases"])

    def test_parse_endpoints_falls_back_to_info(self):
        self.assertEqual(tool.parse_endpoints("summary only"), ["info"])

    @patch("tool.requests.post")
    def test_call_llm_raises_readable_error_for_missing_choices(self, mock_post):
        mock_response = mock_post.return_value
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"error": {"message": "blocked by policy"}}

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                tool.call_llm("openai/gpt-oss-120b:free", "system", "user")

        self.assertIn("模型回傳異常", str(ctx.exception))

    @patch("tool.github_search_repos")
    @patch("tool.call_llm", return_value="INVALID_QUERY")
    def test_run_skips_invalid_query(self, mock_call_llm, mock_search):
        with patch("sys.stdout", new_callable=StringIO):
            result = tool.run(tool.AVAILABLE_MODELS["1"], "無關問題")
        self.assertEqual(result["status"], "invalid")
        mock_search.assert_not_called()

    @patch("tool.github_search_repos", return_value=[])
    @patch("tool.call_llm", return_value="language:python")
    def test_run_returns_none_when_no_repos(self, mock_call_llm, mock_search):
        with patch("sys.stdout", new_callable=StringIO):
            result = tool.run(tool.AVAILABLE_MODELS["1"], "Find Python repos")
        self.assertEqual(result["status"], "empty")
        mock_search.assert_called_once_with("language:python")

    @patch("tool.github_get_repo", return_value={"name": "demo"})
    @patch("tool.call_llm", side_effect=["summary only", "整理後的答案"])
    def test_deep_dive_uses_info_fallback(self, mock_call_llm, mock_get_repo):
        with patch("sys.stdout", new_callable=StringIO) as fake_stdout:
            tool.deep_dive(tool.AVAILABLE_MODELS["1"], "owner", "repo", "這是什麼專案？")
        output = fake_stdout.getvalue()
        self.assertIn("需要查詢：info", output)
        mock_get_repo.assert_called_once_with("owner", "repo")
        self.assertIn("整理後的答案", output)


if __name__ == "__main__":
    unittest.main()
