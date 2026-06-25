import os
import ssl
import json
import re
import certifi
from dotenv import load_dotenv
import anthropic

load_dotenv()

ssl._create_default_https_context = ssl.create_default_context
os.environ['SSL_CERT_FILE'] = certifi.where()

claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

thread_cache = {}
user_selections = {}
user_custom_input = {}

def parse_thread_link(link):
    match = re.search(r'/archives/([A-Z0-9]+)/p(\d+)', link)
    if not match:
        return None, None
    channel_id = match.group(1)
    raw_ts = match.group(2)
    thread_ts = raw_ts[:-6] + '.' + raw_ts[-6:]
    return channel_id, thread_ts

def resolve_usernames(messages, client):
    user_map = {}
    for msg in messages:
        user_id = msg.get("user")
        if user_id and user_id not in user_map:
            try:
                result = client.users_info(user=user_id)
                user = result["user"]
                name = user.get("real_name") or user.get("display_name") or user_id
                user_map[user_id] = name
            except Exception:
                user_map[user_id] = user_id
    return user_map

def summarize_thread(messages, selected_sections, custom=None, user_map={}):
    formatted = "\n".join([
        f"{user_map.get(msg.get('user'), msg.get('user', 'Unknown'))}: {msg.get('text', '')}"
        for msg in messages
        if msg.get('text') and not msg['text'].startswith('<@')
    ])

    section_map = {
        "decisions": '"decisions": ["decision 1"]  // key decisions made',
        "actions": '"actions": ["Person: task (deadline)"]  // action items',
        "who": '"who": ["Person: their key argument or point"]  // per person breakdown',
        "important": '"important": ["point 1"]  // most important points',
        "questions": '"questions": ["question 1"]  // open/unresolved questions',
        "timeline": '"timeline": ["date/deadline: what happens"]  // timeline and deadlines',
        "context": '"context": "background context for this thread"  // background',
        "sentiment": '"sentiment": "one sentence on the overall tone of the discussion"  // tone',
    }

    requested = []
    for s in selected_sections:
        if s in section_map:
            requested.append(section_map[s])

    if custom:
        requested.append(f'"custom": ["point 1", "point 2"]  // {custom}')

    response = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"""Summarize this Slack thread. Reply ONLY with a JSON object, no other text, no backticks.

ONLY include the sections listed below. Do not add any other sections.

Use this structure:
{{
    "about": "2-3 sentences summarizing what this thread is about",
    {chr(10).join(requested)}
}}

For empty sections use [].

Thread:
{formatted}"""
        }]
    )

    raw = response.content[0].text
    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(clean)

def answer_followup(question, messages, user_map={}):
    formatted = "\n".join([
        f"{user_map.get(msg.get('user'), msg.get('user', 'Unknown'))}: {msg.get('text', '')}"
        for msg in messages
        if msg.get('text') and not msg['text'].startswith('<@')
    ])

    response = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""Based on this Slack thread, answer the following question concisely:

Question: {question}

Thread:
{formatted}

Answer directly and concisely. If the answer isn't in the thread, say so."""
        }]
    )

    return response.content[0].text

def build_summary_blocks(summary, selected_sections, custom=None):
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

    blocks = [
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
                    "elements": [{"type": "text", "text": summary.get("about", "")}]
                }
            ]
        }
    ]

    section_config = [
        ("decisions", "Decisions made"),
        ("actions", "Action items"),
        ("who", "Who said what"),
        ("important", "Most important points"),
        ("questions", "Open questions"),
        ("timeline", "Timeline & deadlines"),
        ("sentiment", "Tone & sentiment"),
    ]

    for key, label in section_config:
        if key in selected_sections and summary.get(key):
            items = summary[key]
            if isinstance(items, str):
                items = [items]
            blocks.append({
                "type": "rich_text",
                "elements": [
                    {
                        "type": "rich_text_section",
                        "elements": [{"type": "text", "text": label, "style": {"bold": True}}]
                    },
                    {
                        "type": "rich_text_list",
                        "style": "bullet",
                        "elements": bullet_list(items)
                    }
                ]
            })

    if "context" in selected_sections and summary.get("context"):
        blocks.append({
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_section",
                    "elements": [{"type": "text", "text": "Context & background", "style": {"bold": True}}]
                },
                {
                    "type": "rich_text_quote",
                    "elements": [{"type": "text", "text": summary["context"]}]
                }
            ]
        })

    if custom and summary.get("custom"):
        blocks.append({
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_section",
                    "elements": [{"type": "text", "text": custom, "style": {"bold": True}}]
                },
                {
                    "type": "rich_text_list",
                    "style": "bullet",
                    "elements": bullet_list(summary["custom"])
                }
            ]
        })

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": "Reply in this thread to ask follow-up questions about the thread."
        }]
    })

    return blocks

def build_selector(thread_link):
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*What do you want in your summary?*\nSelect one or more options:"
            }
        },
        {
            "type": "actions",
            "block_id": "section_selector",
            "elements": [
                {
                    "type": "checkboxes",
                    "action_id": "selected_sections",
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "Key Decisions"},
                            "value": "decisions"
                        },
                        {
                            "text": {"type": "plain_text", "text": "Action Items"},
                            "value": "actions"
                        },
                        {
                            "text": {"type": "plain_text", "text": "Who Said What"},
                            "value": "who"
                        },
                        {
                            "text": {"type": "plain_text", "text": "Most Important Points"},
                            "value": "important"
                        },
                        {
                            "text": {"type": "plain_text", "text": "Open Questions"},
                            "value": "questions"
                        },
                        {
                            "text": {"type": "plain_text", "text": "Timeline & Deadlines"},
                            "value": "timeline"
                        },
                        {
                            "text": {"type": "plain_text", "text": "Context & Background"},
                            "value": "context"
                        },
                        {
                            "text": {"type": "plain_text", "text": "Tone & Sentiment"},
                            "value": "sentiment"
                        }
                    ]
                }
            ]
        },
        {
            "type": "input",
            "block_id": "custom_input",
            "optional": True,
            "element": {
                "type": "plain_text_input",
                "action_id": "custom_text",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Add your own focus area..."
                }
            },
            "label": {
                "type": "plain_text",
                "text": "Other (optional)"
            }
        },
        {
            "type": "actions",
            "block_id": f"generate_{thread_link}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Generate Summary"},
                    "style": "primary",
                    "action_id": "generate_summary",
                    "value": thread_link
                }
            ]
        }
    ]


def start_bot():
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    app = App(
        token=os.environ["SLACK_BOT_TOKEN"],
        signing_secret=os.environ["SLACK_SIGNING_SECRET"]
    )

    user_map_cache = {}

    @app.action("selected_sections")
    def handle_selection(ack, body, action):
        ack()
        user_id = body["user"]["id"]
        selected = [opt["value"] for opt in action.get("selected_options", [])]
        user_selections[user_id] = selected

    @app.action("custom_text")
    def handle_custom_text(ack):
        ack()

    @app.action("generate_summary")
    def handle_generate(ack, body, client):
        ack()
        user_id = body["user"]["id"]
        thread_link = body["actions"][0]["value"]

        selected = []
        state = body.get("state", {}).get("values", {})
        for block in state.values():
            if "selected_sections" in block:
                selected = [opt["value"] for opt in block["selected_sections"].get("selected_options", [])]
                break

        custom = None
        for block in state.values():
            if "custom_text" in block:
                custom = block["custom_text"].get("value")
                break

        if not selected and not custom:
            client.chat_postMessage(
                channel=user_id,
                text="Please select at least one option before generating!"
            )
            return

        channel_id, thread_ts = parse_thread_link(thread_link)

        if not channel_id or not thread_ts:
            client.chat_postMessage(
                channel=user_id,
                text="Sorry, I couldn't parse that thread link."
            )
            return

        client.chat_postMessage(
            channel=user_id,
            text="Generating your summary..."
        )

        try:
            result = client.conversations_replies(
                channel=channel_id,
                ts=thread_ts
            )
            messages = result["messages"]

            if len(messages) < 2:
                client.chat_postMessage(
                    channel=user_id,
                    text="This thread is too short to summarize!"
                )
                return

            user_map = resolve_usernames(messages, client)
            user_map_cache[user_id] = user_map
            thread_cache[user_id] = messages

            summary = summarize_thread(messages, selected, custom, user_map)
            blocks = build_summary_blocks(summary, selected, custom)

            client.chat_postMessage(
                channel=user_id,
                blocks=blocks,
                text="Thread Summary"
            )

        except Exception as e:
            print(f"Error: {e}")
            client.chat_postMessage(
                channel=user_id,
                text="Something went wrong. Make sure RecapBot is added to that channel."
            )

    @app.event("message")
    def handle_dm(event, client):
        if event.get("channel_type") != "im":
            return
        if event.get("bot_id"):
            return
        if event.get("subtype"):
            return

        user_id = event["user"]
        text = event.get("text", "").strip()
        thread_ts = event.get("thread_ts")

        # Message is inside a thread — treat as follow up
        if thread_ts:
            if user_id in thread_cache:
                user_map = user_map_cache.get(user_id, {})
                answer = answer_followup(text, thread_cache[user_id], user_map)
                client.chat_postMessage(
                    channel=user_id,
                    thread_ts=thread_ts,
                    text=answer
                )
            return

        # Top level DM
        if "slack.com/archives" in text:
            client.chat_postMessage(
                channel=user_id,
                text="Got it! What do you want in your summary?",
                blocks=build_selector(text)
            )
        else:
            if user_id in thread_cache:
                user_map = user_map_cache.get(user_id, {})
                answer = answer_followup(text, thread_cache[user_id], user_map)
                client.chat_postMessage(
                    channel=user_id,
                    text=answer
                )
            else:
                client.chat_postMessage(
                    channel=user_id,
                    text="Hi! Paste a Slack thread link and I'll summarize it for you."
                )

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