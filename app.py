# app.py
import os
from flask import Flask, request, abort
import telebot
import logging

# ---------------------------
# Credentials (env preferred)
# ---------------------------
API_ID = os.getenv("API_ID") or "22134923"
API_HASH = os.getenv("API_HASH") or "d3e9d2f01d3291e87ea65298317f86b8"
BOT_TOKEN = os.getenv("BOT_TOKEN") or "8285636468:AAFPRQ1oS1N3I4MBI85RFEOZXW4pwBrWHLg"
# Set webhook URL via env WEBHOOK_URL (recommended)
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://your-service.onrender.com/<BOT_TOKEN>

# ---------------------------
# Bot & Flask setup
# ---------------------------
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required")

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
app = Flask(__name__)

# optional: basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------
# Handlers
# ---------------------------
@bot.message_handler(commands=['start'])
def handle_start(message):
    """
    1. বট Start করলে রিপ্লে আসবে Lets Talk Each Other
    """
    try:
        bot.reply_to(message, "Lets Talk Each Other")
    except Exception as e:
        logger.exception("Error in /start handler: %s", e)

@bot.message_handler(func=lambda m: isinstance(m.text, str) and m.text.strip().lower() == "hi")
def handle_hi(message):
    """
    2. বটে Hi লেখলে বট আমাকে রিপ্লে দিবে Hello
    """
    try:
        bot.reply_to(message, "Hello")
    except Exception as e:
        logger.exception("Error in Hi handler: %s", e)


# Fallback: if you want to reply to anything else, uncomment:
# @bot.message_handler(func=lambda m: True)
# def echo_all(message):
#     bot.reply_to(message, "আপনি কি বললেন?")

# ---------------------------
# Webhook endpoints for Render
# ---------------------------
@app.route("/", methods=["GET"])
def index():
    return "Bot is running."

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook_handler():
    """
    Telegram will POST updates here.
    """
    if request.headers.get("content-type") != "application/json":
        abort(400)
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "", 200

# ---------------------------
# Startup: set webhook if WEBHOOK_URL provided
# ---------------------------
def setup_webhook():
    # prefer explicit WEBHOOK_URL env var
    global WEBHOOK_URL
    if not WEBHOOK_URL:
        # If not provided, try to build from RENDER_EXTERNAL_URL env (Render provides)
        render_external = os.getenv("RENDER_EXTERNAL_URL")
        if render_external:
            WEBHOOK_URL = f"https://{render_external}/{BOT_TOKEN}"
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL not set. Please set WEBHOOK_URL env var to your service URL "
                       "(e.g. https://your-service.onrender.com/{BOT_TOKEN}). Webhook won't be set automatically.")
        return

    try:
        # remove previous webhook then set new one
        bot.remove_webhook()
        ok = bot.set_webhook(url=WEBHOOK_URL)
        if ok:
            logger.info("Webhook set to %s", WEBHOOK_URL)
        else:
            logger.error("Failed to set webhook to %s", WEBHOOK_URL)
    except Exception as e:
        logger.exception("Exception while setting webhook: %s", e)


if __name__ == "__main__":
    # When running locally for testing you can set WEBHOOK_URL manually
    setup_webhook()
    port = int(os.environ.get("PORT", 5000))
    # For Render/Gunicorn you might not run this block; Render will launch via 'python app.py'
    app.run(host="0.0.0.0", port=port)
