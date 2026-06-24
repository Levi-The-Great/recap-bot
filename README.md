# recap-bot
# RecapBot

A Slack bot that summarizes long threads using Claude AI. Mention `@RecapBot` in any thread and it replies with a structured summary — what the discussion is about, decisions made, open questions, and action items.

## Demo

![RecapBot in action](demo.png)

## How it works

1. User mentions `@RecapBot` in a Slack thread
2. Bot fetches all messages in the thread
3. Sends them to Claude AI for summarization
4. Posts a structured summary back in the thread

## Setup

### Prerequisites
- Python 3.10+
- A Slack workspace
- Anthropic API key

### 1. Clone the repo
```bash
git clone https://github.com/Levi-The-Great/recap-bot.git
cd recap-bot
```

### 2. Install dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Create a Slack app
- Go to [api.slack.com/apps](https://api.slack.com/apps) and create a new app
- Enable Socket Mode and generate an App Token (`xapp-...`)
- Add these Bot Token Scopes under OAuth & Permissions:
  - `app_mentions:read`
  - `channels:history`
  - `groups:history`
  - `chat:write`
- Subscribe to the `app_mention` bot event under Event Subscriptions
- Install the app to your workspace and copy the Bot Token (`xoxb-...`)

### 4. Configure environment variables
Create a `.env` file in the project root:
SLACK_BOT_TOKEN=xoxb-...

SLACK_SIGNING_SECRET=...

SLACK_APP_TOKEN=xapp-...

ANTHROPIC_API_KEY=sk-ant-...

### 5. Run locally
```bash
python main.py
```

### 6. Deploy to Railway
- Connect your GitHub repo to [Railway](https://railway.app)
- Add the environment variables in Railway's Variables tab
- Railway auto-deploys on every push

## Running tests
```bash
python -m pytest tests.py -v
```

## Tech stack
- Python
- [Slack Bolt SDK](https://slack.dev/bolt-python/)
- [Anthropic Claude API](https://docs.anthropic.com/)
- [Railway](https://railway.app) for deployment

## CI
GitHub Actions runs the test suite on every push to main.