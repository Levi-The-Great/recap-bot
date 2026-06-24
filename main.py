import os
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# Load environment variables from .env file
load_dotenv()

# Initialize the app with your bot token and signing secret
app = App(
    token=os.environ["SLACK_BOT_TOKEN"],
    signing_secret=os.environ["SLACK_SIGNING_SECRET"]
)


@app.command("/recap")
def handle_recap(ack, command, client):
    ack()

    channel_id = command["channel_id"]
    thread_ts = command.get("thread_ts")

    # If not in a thread, just post in the channel
    message_args = {
        "channel": channel_id,
        "text": "👋 RecapBot here! Summarization coming soon."
    }

    # Only add thread_ts if we're actually in a thread
    if thread_ts:
        message_args["thread_ts"] = thread_ts

    client.chat_postMessage(**message_args)


# Start the app
if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("RecapBot is running...")
    handler.start()