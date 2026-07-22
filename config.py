import os

# Telegram Bot Token (Get it from @BotFather)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8817752647:AAHuEY8BdgfEMBsrtBss1ubC6hoMQorM6VI")

# Administrator Telegram IDs (List of integers). Only these users can add/delete movies.
# You can get your ID from bots like @userinfobot or @dtgbot
ADMIN_IDS = [int(id_str) for id_str in os.environ.get("ADMIN_IDS", "7637932499").split(",") if id_str.strip()]
