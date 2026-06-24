import os
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv()

app = App(
    token=os.environ["SLACK_BOT_TOKEN"],
    signing_secret=os.environ["SLACK_SIGNING_SECRET"]
)


@app.event("app_mention")
def handle_mention(event, client, say):
    channel_id = event["channel"]
    thread_ts = event.get("thread_ts") or event["ts"]

    # Fetch all messages in the thread
    result = client.conversations_replies(
        channel=channel_id,
        ts=thread_ts
    )
    messages = result["messages"]

    # Print to console for now
    print(f"Found {len(messages)} messages in thread:")
    for msg in messages:
        print(f"  - {msg.get('text', '')}")

    # Reply in the thread
    say(
        text=f"Found {len(messages)} messages in this thread. Summarization coming soon!",
        thread_ts=thread_ts
    )


if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("RecapBot is running...")
    handler.start()