import os
import ssl
import json
import certifi
from dotenv import load_dotenv
import anthropic

load_dotenv()

# Fix SSL certificates
ssl._create_default_https_context = ssl.create_default_context
os.environ['SSL_CERT_FILE'] = certifi.where()

claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

def build_blocks(summary):
    def bullet_list(items):
        if not items:
            return [{
                "type": "rich_text_section",
                "elements": [{"type": "text", "text": "None"}]
            }]
        return [
            {
                "type": "rich_text_section",
                "elements": [{"type": "text", "text": item}]
            }
            for item in items
        ]

    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Thread Summary", "emoji": False}
        },
        {"type": "divider"},
        {
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_section",
                    "elements": [{"type": "text", "text": "What's this about", "style": {"bold": True}}]
                },
                {
                    "type": "rich_text_quote",
                    "elements": [{"type": "text", "text": summary["about"]}]
                }
            ]
        },
        {
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_section",
                    "elements": [{"type": "text", "text": "Decisions made", "style": {"bold": True}}]
                },
                {
                    "type": "rich_text_list",
                    "style": "bullet",
                    "elements": bullet_list(summary["decisions"])
                }
            ]
        },
        {
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_section",
                    "elements": [{"type": "text", "text": "Open questions", "style": {"bold": True}}]
                },
                {
                    "type": "rich_text_list",
                    "style": "bullet",
                    "elements": bullet_list(summary["questions"])
                }
            ]
        },
        {
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_section",
                    "elements": [{"type": "text", "text": "Action items", "style": {"bold": True}}]
                },
                {
                    "type": "rich_text_list",
                    "style": "bullet",
                    "elements": bullet_list(summary["actions"])
                }
            ]
        },
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Regenerate", "emoji": False},
                    "action_id": "regenerate_summary"
                }
            ]
        }
    ]

def summarize_thread(messages):
    capped = messages[:50]
    was_capped = len(messages) > 50

    formatted = "\n".join([
        f"- {msg.get('text', '')}"
        for msg in capped
        if msg.get('text') and not msg['text'].startswith('<@')
    ])

    if not formatted.strip():
        raise ValueError("empty_thread")

    response = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"""Summarize this Slack thread. Reply ONLY with a JSON object, no other text, no backticks.

Use this exact structure:
{{
    "about": "one sentence about what this thread is about",
    "decisions": ["decision 1", "decision 2"],
    "questions": ["open question 1"],
    "actions": ["Person: task (deadline)"]
}}

If a section has nothing, use an empty array [].

Thread:
{formatted}"""
        }]
    )

    raw = response.content[0].text
    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    result = json.loads(clean)
    result["was_capped"] = was_capped
    return result


def start_bot():
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    app = App(
        token=os.environ["SLACK_BOT_TOKEN"],
        signing_secret=os.environ["SLACK_SIGNING_SECRET"]
    )

    @app.event("app_mention")
    def handle_mention(event, client, say):
        channel_id = event["channel"]
        thread_ts = event.get("thread_ts") or event["ts"]

        say(text="Summarizing thread...", thread_ts=thread_ts)

        try:
            result = client.conversations_replies(
                channel=channel_id,
                ts=thread_ts
            )
            messages = result["messages"]

            real_messages = [
                m for m in messages
                if m.get('text') and not m['text'].startswith('<@')
            ]

            if len(real_messages) < 2:
                say(
                    text="This thread is too short to summarize. Add more messages and try again!",
                    thread_ts=thread_ts
                )
                return

            summary = summarize_thread(messages)
            blocks = build_blocks(summary)

            if summary.get("was_capped"):
                blocks.insert(1, {
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": "Note: This thread is long — summarized the first 50 messages only."
                    }]
                })

            client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                blocks=blocks,
                text="Thread Summary"
            )

        except ValueError as e:
            if str(e) == "empty_thread":
                say(
                    text="This thread doesn't have any real messages to summarize!",
                    thread_ts=thread_ts
                )
        except json.JSONDecodeError:
            say(
                text="Something went wrong reading the summary. Please try again!",
                thread_ts=thread_ts
            )
        except Exception as e:
            print(f"Unexpected error: {e}")
            say(
                text="Something went wrong. Please try again in a moment!",
                thread_ts=thread_ts
            )

    @app.action("regenerate_summary")
    def handle_regenerate(ack, body, client):
        ack()
        channel_id = body["channel"]["id"]
        thread_ts = body["message"]["thread_ts"]

        try:
            result = client.conversations_replies(
                channel=channel_id,
                ts=thread_ts
            )
            messages = result["messages"]
            summary = summarize_thread(messages)
            blocks = build_blocks(summary)

            client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                blocks=blocks,
                text="Thread Summary"
            )

        except Exception as e:
            print(f"Error: {e}")

    print("RecapBot is running...")
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()


if __name__ == "__main__":
    print("Starting RecapBot...")
    print(f"SLACK_BOT_TOKEN exists: {'SLACK_BOT_TOKEN' in os.environ}")
    print(f"SLACK_SIGNING_SECRET exists: {'SLACK_SIGNING_SECRET' in os.environ}")
    print(f"SLACK_APP_TOKEN exists: {'SLACK_APP_TOKEN' in os.environ}")
    print(f"ANTHROPIC_API_KEY exists: {'ANTHROPIC_API_KEY' in os.environ}")
    start_bot()