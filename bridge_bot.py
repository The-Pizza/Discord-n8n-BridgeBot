import discord
from discord.ext import commands
import aiohttp
import asyncio
import json
import os
import logging
from datetime import datetime

# ------------------------------------------------------------------------------------
# CONFIGURATION via Environment Variables (k8s friendly)
# ------------------------------------------------------------------------------------
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")                           # Required
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")                       # Required
PARENT_CHANNEL_ID_STR = os.getenv("PARENT_CHANNEL_ID")               # Required - channel to watch for new threads
PARENT_CHANNEL_ID = int(PARENT_CHANNEL_ID_STR) if PARENT_CHANNEL_ID_STR else None

THREADS_FILE = os.getenv("THREADS_FILE", "/data/monitored_threads.json")  # Local file for persistence
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ------------------------------------------------------------------------------------
# Logging setup
# ------------------------------------------------------------------------------------
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("DiscordBridge")

# ------------------------------------------------------------------------------------
# Global in-memory storage
# ------------------------------------------------------------------------------------
MONITORED_THREADS: set[int] = set()

# ------------------------------------------------------------------------------------
# Persistence: Load / Save thread list
# ------------------------------------------------------------------------------------
def load_monitored_threads():
    global MONITORED_THREADS
    if not os.path.exists(THREADS_FILE):
        logger.info(f"No persistence file found at {THREADS_FILE}. Starting empty.")
        return

    try:
        with open(THREADS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            threads = data.get("threads", [])
            MONITORED_THREADS = {int(tid) for tid in threads if str(tid).isdigit()}
        logger.info(f"Loaded {len(MONITORED_THREADS)} thread IDs from {THREADS_FILE}")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {THREADS_FILE}: {e}")
    except Exception as e:
        logger.error(f"Failed to load {THREADS_FILE}: {type(e).__name__} - {e}")


def save_monitored_threads():
    try:
        os.makedirs(os.path.dirname(THREADS_FILE), exist_ok=True)
        data = {"threads": [str(tid) for tid in sorted(MONITORED_THREADS)]}
        with open(THREADS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.debug(f"Saved {len(MONITORED_THREADS)} threads to {THREADS_FILE}")
    except Exception as e:
        logger.error(f"Failed to save {THREADS_FILE}: {type(e).__name__} - {e}")


# ------------------------------------------------------------------------------------
# Discord Bot Setup
# ------------------------------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True   # Needed to read message.content
intents.guilds = True            # Needed for thread/channel events

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


@bot.event
async def on_ready():
    if not BOT_TOKEN or not N8N_WEBHOOK_URL or PARENT_CHANNEL_ID is None:
        logger.critical("Missing required environment variables (DISCORD_BOT_TOKEN, N8N_WEBHOOK_URL, PARENT_CHANNEL_ID)")
        await bot.close()
        return

    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    load_monitored_threads()
    logger.info(f"Currently monitoring {len(MONITORED_THREADS)} threads")
    logger.info(f"Watching for new threads in parent channel ID: {PARENT_CHANNEL_ID}")


@bot.event
async def on_thread_create(thread: discord.Thread):
    if thread.parent_id != PARENT_CHANNEL_ID:
        return  # Ignore threads not in the watched parent channel

    if thread.id in MONITORED_THREADS:
        return  # Already known (e.g. reload or duplicate event)

    try:
        MONITORED_THREADS.add(thread.id)
        save_monitored_threads()
        logger.info(f"New thread added to monitoring: \"{thread.name}\" (ID: {thread.id}) in channel {thread.parent_id}")
    except Exception as e:
        logger.error(f"Error while adding new thread {thread.id}: {e}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return  # Skip bots (including ourselves)

    if not isinstance(message.channel, discord.Thread):
        return  # Only care about threads

    thread_id = message.channel.id
    if thread_id not in MONITORED_THREADS:
        return

    # Log raw inbound message details at DEBUG level
    logger.debug(f"Inbound Discord message: {message}")

    await forward_to_n8n(message)


# ------------------------------------------------------------------------------------
# Forward message payload to n8n webhook
# ------------------------------------------------------------------------------------
async def forward_to_n8n(message: discord.Message):
    #thread = message.channel  # type: discord.Thread

    payload = {
        "event": "message_create",
        "timestamp": message.created_at.isoformat(),
        "thread": {
            "id": str(message.channel.id),
            "name": message.channel.name,
            "parent_channel_id": str(message.channel.parent_id),
            "jump_url": message.channel.jump_url if hasattr(message.channel, 'jump_url') else None,
        },
        "message": {
            "id": str(message.id),
            "content": message.content,
            "clean_content": message.clean_content,
            "author": {
                "id": str(message.author.id),
                "name": message.author.name,
                "display_name": message.author.display_name,
                "bot": message.author.bot,
            },
            "jump_url": message.jump_url,
            "attachments": [{"url": a.url, "filename": a.filename, "size": a.size} for a in message.attachments],
            "embeds": [e.to_dict() for e in message.embeds],
            "mentions": [{"id": str(u.id), "name": u.name} for u in message.mentions],
        }
    }

    async with aiohttp.ClientSession() as session:
        try:
            logger.debug(f"Payload to n8n: {json.dumps(payload, indent=2)}")
            async with session.post(
                N8N_WEBHOOK_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status in (200, 202, 204):
                    logger.debug(f"Forwarded msg {message.id} from thread {message.channel.id} in channel {message.channel.parent_id} to n8n successfully - status {response.status}")
                else:
                    text = await response.text()
                    logger.warning(f"n8n rejected msg {message.id} - status {response.status}: {text[:200]}")
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error forwarding to n8n: {type(e).__name__} - {e}")
        except asyncio.TimeoutError:
            logger.error(f"Timeout forwarding msg {message.id} to n8n")
        except Exception as e:
            logger.exception(f"Unexpected error forwarding message {message.id}: {e}")


# ------------------------------------------------------------------------------------
# Startup
# ------------------------------------------------------------------------------------
async def main():
    async with bot:
        await bot.start(BOT_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.critical(f"Fatal startup error: {e}", exc_info=True)