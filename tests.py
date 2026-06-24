import json
import unittest
from unittest.mock import MagicMock, patch
from main import summarize_thread, build_blocks

class TestSummarizeThread(unittest.TestCase):

    def test_filters_out_bot_mentions(self):
        messages = [
            {"text": "hey what should we do for the project?"},
            {"text": "I think we should use Python"},
            {"text": "<@U0BDT0SLGGY>"},  # bot mention — should be filtered
        ]
        # Mock Claude response
        with patch("main.claude") as mock_claude:
            mock_response = MagicMock()
            mock_response.content[0].text = json.dumps({
                "about": "Discussing project language choice",
                "decisions": ["Use Python"],
                "questions": [],
                "actions": []
            })
            mock_claude.messages.create.return_value = mock_response

            result = summarize_thread(messages)

            # Check the prompt sent to Claude
            call_args = mock_claude.messages.create.call_args
            prompt = call_args[1]["messages"][0]["content"]

            # Bot mention should NOT be in the prompt
            self.assertNotIn("<@U0BDT0SLGGY>", prompt)

    def test_caps_at_50_messages(self):
        # Create 60 fake messages
        messages = [{"text": f"message {i}"} for i in range(60)]

        with patch("main.claude") as mock_claude:
            mock_response = MagicMock()
            mock_response.content[0].text = json.dumps({
                "about": "A long thread",
                "decisions": [],
                "questions": [],
                "actions": []
            })
            mock_claude.messages.create.return_value = mock_response

            result = summarize_thread(messages)

            # Should flag that it was capped
            self.assertTrue(result["was_capped"])

            # Prompt should only contain first 50 messages
            call_args = mock_claude.messages.create.call_args
            prompt = call_args[1]["messages"][0]["content"]
            self.assertNotIn("message 50", prompt)

    def test_raises_on_empty_thread(self):
        # All messages are bot mentions — nothing real
        messages = [
            {"text": "<@U0BDT0SLGGY>"},
            {"text": "<@U0BDT0SLGGY>"},
        ]

        with self.assertRaises(ValueError) as ctx:
            with patch("main.claude"):
                summarize_thread(messages)

        self.assertEqual(str(ctx.exception), "empty_thread")


class TestBuildBlocks(unittest.TestCase):

    def test_shows_none_when_no_decisions(self):
        summary = {
            "about": "Test thread",
            "decisions": [],
            "questions": [],
            "actions": []
        }
        blocks = build_blocks(summary)

        # Find the decisions block
        decisions_block = blocks[3]
        list_items = decisions_block["elements"][1]["elements"]

        self.assertEqual(len(list_items), 1)
        self.assertEqual(list_items[0]["elements"][0]["text"], "None")

    def test_renders_decisions_correctly(self):
        summary = {
            "about": "Test thread",
            "decisions": ["Ship on Friday", "Use Python"],
            "questions": [],
            "actions": []
        }
        blocks = build_blocks(summary)

        decisions_block = blocks[3]
        list_items = decisions_block["elements"][1]["elements"]

        self.assertEqual(len(list_items), 2)
        self.assertEqual(list_items[0]["elements"][0]["text"], "Ship on Friday")
        self.assertEqual(list_items[1]["elements"][0]["text"], "Use Python")

    def test_about_renders_in_quote_block(self):
        summary = {
            "about": "This is what the thread is about",
            "decisions": [],
            "questions": [],
            "actions": []
        }
        blocks = build_blocks(summary)

        about_block = blocks[2]
        quote = about_block["elements"][1]

        self.assertEqual(quote["type"], "rich_text_quote")
        self.assertEqual(quote["elements"][0]["text"], "This is what the thread is about")


if __name__ == "__main__":
    unittest.main()