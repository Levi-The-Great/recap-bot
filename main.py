import os
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import anthropic

load_dotenv() #get info from the .env file

app = App(
    token=os.environ["SLACK_BOT_TOKEN"], #refering to .env
    signing_secret=os.environ["SLACK_SIGNING_SECRET"]
)

claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def summarize_thread(messages):
    # Format messages as readable text
    formatted = "\n".join([
        f"- {msg.get('text', '')}"
        for msg in messages
        if msg.get('text') and not msg['text'].startswith('<@')  # skip bot mentions
    ])

    # Send to Claude
    response = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"""Summarize this thread using bullet points. Make sure to include: 
                1. TL;DR: A 1-2 sentence bottom-line up front.Context/Problem: 
                2. The core issue or question being discussed.Key Arguments/Points: 
                3. Bulleted highlights of the main perspectives.
                4. Decisions Made: A clear record of what was agreed upon.
                5. Action Items: Specific tasks assigned to individuals, complete with deadlines.

Thread messages:
{formatted}"""
        }]
    )

    return response.content[0].text


@app.event("app_mention")
def handle_mention(event, client, say):
    channel_id = event["channel"]
    thread_ts = event.get("thread_ts") or event["ts"]

    # Let user know we're working on it
    say(
        text="⏳ Summarizing thread...",
        thread_ts=thread_ts
    )

    try:
        # Fetch all messages in the thread
        result = client.conversations_replies(
            channel=channel_id,
            ts=thread_ts
        )
        messages = result["messages"]

        # Need at least 2 real messages to summarize
        if len(messages) < 2:
            say(
                text="This thread is too short to summarize!",
                thread_ts=thread_ts
            )
            return

        # Get summary from Claude
        summary = summarize_thread(messages)

        # Post summary back
        say(
            text=f"📝 *Thread Summary*\n\n{summary}",
            thread_ts=thread_ts
        )

    except Exception as e:
        print(f"Error: {e}")
        say(
            text="Sorry, something went wrong. Please try again!",
            thread_ts=thread_ts
        )


if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("RecapBot is running...")
    handler.start()