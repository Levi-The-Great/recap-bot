import json
import unittest
from unittest.mock import MagicMock, patch
from main import summarize_thread, build_summary_blocks as build_blocks


class TestSummarizeThread(unittest.TestCase):

    def test_filters_out_bot_mentions(self):
        messages = [
            {"text": "hey what should we do for the project?"},
            {"text": "I think we should use Python"},
            {"text": "<@U0BDT0SLGGY>"},
        ]
        with patch("main.claude") as mock_claude:
            mock_response = MagicMock()
            mock_response.content[0].text = json.dumps({
                "about": "Discussing project language choice",
                "decisions": ["Use Python"]
            })
            mock_claude.messages.create.return_value = mock_response

            result = summarize_thread(messages, ["decisions"])

            call_args = mock_claude.messages.create.call_args
            prompt = call_args[1]["messages"][0]["content"]

            self.assertNotIn("<@U0BDT0SLGGY>", prompt)

class TestBuildBlocks(unittest.TestCase):

    def test_about_renders_in_quote_block(self):
        summary = {
            "about": "This is what the thread is about"
        }
        blocks = build_blocks(summary, ["decisions"])

        about_block = blocks[2]
        quote = about_block["elements"][1]

        self.assertEqual(quote["type"], "rich_text_quote")
        self.assertEqual(quote["elements"][0]["text"], "This is what the thread is about")

    def test_renders_decisions_correctly(self):
        summary = {
            "about": "Test thread",
            "decisions": ["Ship on Friday", "Use Python"]
        }
        blocks = build_blocks(summary, ["decisions"])

        decisions_block = blocks[3]
        list_items = decisions_block["elements"][1]["elements"]

        self.assertEqual(len(list_items), 2)
        self.assertEqual(list_items[0]["elements"][0]["text"], "Ship on Friday")
        self.assertEqual(list_items[1]["elements"][0]["text"], "Use Python")

    def test_only_selected_sections_appear(self):
        summary = {
            "about": "Test thread",
            "decisions": ["Decision 1"],
            "actions": ["Person: task"],
            "who": ["John: argued for Python"]
        }
        blocks = build_blocks(summary, ["decisions"])

        labels = []
        for block in blocks:
            if block.get("type") == "rich_text":
                elements = block.get("elements", [])
                if elements:
                    section_elements = elements[0].get("elements", [])
                    if section_elements:
                        labels.append(section_elements[0].get("text", ""))

        self.assertIn("Decisions made", labels)
        self.assertNotIn("Action items", labels)
        self.assertNotIn("Who said what", labels)

    def test_empty_decisions_not_rendered(self):
        summary = {
            "about": "Test thread",
            "decisions": []
        }
        blocks = build_blocks(summary, ["decisions"])

        labels = []
        for block in blocks:
            if block.get("type") == "rich_text":
                elements = block.get("elements", [])
                if elements:
                    section_elements = elements[0].get("elements", [])
                    if section_elements:
                        labels.append(section_elements[0].get("text", ""))

        # Empty decisions should not render a block
        self.assertNotIn("Decisions made", labels)


if __name__ == "__main__":
    unittest.main()