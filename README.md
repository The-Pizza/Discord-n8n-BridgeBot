# Discord → n8n Bridge Bot

Small Discord bot that watches for new threads in a specified parent channel, records those thread IDs for persistence, and forwards all messages from monitored threads to an n8n webhook as JSON payloads.

## What it does
- Watches a single parent channel for newly created threads and adds their IDs to a monitored set.
- For each message posted in a monitored thread, forwards a structured JSON payload to an `n8n` webhook URL.
- Persists the list of monitored thread IDs to a local JSON file so monitoring survives restarts.

## Key features
- Kubernetes / container friendly via environment variables
- Lightweight: uses `discord.py` + `aiohttp`
- Simple persistent storage (JSON file, configurable path)

## Prerequisites
- Python 3.8+
- A Discord bot token with privileges to view threads and read message content
- `discord.py` and `aiohttp` installed (see `pip` example below)

## Environment variables
- `DISCORD_BOT_TOKEN` (required) — your bot token.
- `N8N_WEBHOOK_URL` (required) — HTTP(S) webhook URL to receive forwarded message payloads.
- `PARENT_CHANNEL_ID` (required) — numeric ID of the parent channel to watch for new threads.
- `THREADS_FILE` (optional) — path to JSON file used to persist monitored thread IDs (default: `/data/monitored_threads.json`).
- `LOG_LEVEL` (optional) — logging level (default: `INFO`).

## Running locally
1. Install dependencies:

```bash
pip install -r requirements.txt
# or
pip install discord.py aiohttp
```

2. Export required env vars and run:

Windows (PowerShell):
```powershell
$env:DISCORD_BOT_TOKEN = "your-token"
$env:N8N_WEBHOOK_URL = "https://example.com/webhook"
$env:PARENT_CHANNEL_ID = "123456789012345678"
python bridge_bot.py
```

Linux / macOS:
```bash
export DISCORD_BOT_TOKEN="your-token"
export N8N_WEBHOOK_URL="https://example.com/webhook"
export PARENT_CHANNEL_ID="123456789012345678"
python bridge_bot.py
```

## Docker / Kubernetes notes
- Mount a writable volume to persist `THREADS_FILE` (default `/data/monitored_threads.json`).
- Provide env vars via `env`/`envFrom` or `Deployment` manifest.

Example `docker run` snippet:

```bash
docker run -e DISCORD_BOT_TOKEN="..." \
  -e N8N_WEBHOOK_URL="https://..." \
  -e PARENT_CHANNEL_ID="1234567890" \
  -v /host/path/to/data:/data \
  my-discord-bridge-image:latest
```

## Message payload
The bot POSTs a JSON object like:

- `event`: `message_create`
- `timestamp`: ISO timestamp of the message
- `thread`: metadata (id, name, parent_channel_id, jump_url)
- `message`: id, content, clean_content, author info, attachments, embeds, mentions, jump_url

This payload is suitable for consuming by n8n HTTP Webhook nodes and chaining workflows.

## Required Discord permissions
- View Channels
- Read Message History
- Read Messages / Message Content intent enabled (bot needs `message_content` intent to read message text).

Note: For privileged intents like `message_content`, enable them in the Discord Developer Portal for your bot and ensure your code sets the intent (this script does set `intents.message_content = True`).

## Troubleshooting
- If the bot shuts down immediately on start, check that `DISCORD_BOT_TOKEN`, `N8N_WEBHOOK_URL`, and `PARENT_CHANNEL_ID` are set.
- If messages aren't forwarded, enable `DEBUG` logging by setting `LOG_LEVEL=DEBUG` and check payload/logs for HTTP errors.
- Verify the bot has access to the parent channel and created threads.

## Files
- `bridge_bot.py` — main script (this file)
- `THREADS_FILE` (configurable path) — JSON persistence used by the bot to store monitored thread IDs.

## License
Pick a license for your repo as appropriate.
