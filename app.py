# app.py
import os
import io
import logging
import time
from flask import Flask, request, abort
import telebot
from telebot import types

# -------- Configuration ----------
API_ID = os.getenv("API_ID") or "22134923"
API_HASH = os.getenv("API_HASH") or "d3e9d2f01d3291e87ea65298317f86b8"
BOT_TOKEN = os.getenv("BOT_TOKEN") or "8285636468:AAFPRQ1oS1N3I4MBI85RFEOZXW4pwBrWHLg"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  

try:
    BLUR_RADIUS = float(os.getenv("BLUR_RADIUS", "12"))
except:
    BLUR_RADIUS = 12.0

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required")

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Source and target channel IDs
SOURCE_CHANNEL_ID = -1003244320166
TARGET_CHANNEL_ID = -1003395725940

# Dictionary to store media groups temporarily
media_groups = {}

# ---------- Helper Functions ----------
def process_single_image(message, file_id):
    """Process and send single image to target channel"""
    try:
        file_info = bot.get_file(file_id)
        file_bytes = bot.download_file(file_info.file_path)
        
        bot.send_photo(
            chat_id=TARGET_CHANNEL_ID,
            photo=file_bytes
        )
        logger.info(f"Image sent to target channel from message ID: {message.message_id}")
    except Exception as e:
        logger.error(f"Error processing single image: {e}")

def process_media_group(media_group_id):
    """Process media group and send as album to target channel"""
    try:
        if media_group_id not in media_groups:
            return
        
        messages = media_groups[media_group_id]
        if not messages:
            return
        
        # Sort messages by message_id to maintain order
        messages.sort(key=lambda x: x.message_id)
        
        # Prepare media list for album
        media_list = []
        for msg in messages:
            if msg.photo:
                file_id = msg.photo[-1].file_id
                file_info = bot.get_file(file_id)
                file_bytes = bot.download_file(file_info.file_path)
                
                media_list.append(
                    types.InputMediaPhoto(media=file_bytes)
                )
        
        # Send as media group (album)
        if media_list:
            bot.send_media_group(
                chat_id=TARGET_CHANNEL_ID,
                media=media_list
            )
            logger.info(f"Album sent to target channel, media group ID: {media_group_id}, total images: {len(media_list)}")
        
        # Clean up
        del media_groups[media_group_id]
        
    except Exception as e:
        logger.error(f"Error processing media group {media_group_id}: {e}")
        # Clean up even if error occurs
        if media_group_id in media_groups:
            del media_groups[media_group_id]

# ---------- Handlers ----------
@bot.message_handler(commands=['start'])
def handle_start(message: types.Message):
    if message.from_user.id != 7383046042:
        bot.reply_to(message, "❌ You are not authorized to use this bot.")
        return
    bot.reply_to(message, "Lets Talk Each Other")

@bot.message_handler(func=lambda m: isinstance(m.text, str) and m.text.strip().lower() == "hi")
def handle_hi(message: types.Message):
    if message.from_user.id != 7383046042:
        bot.reply_to(message, "❌ You are not authorized to use this bot.")
        return
    bot.reply_to(message, "Hello")

@bot.message_handler(content_types=['photo'])
def handle_forwarded_images(message: types.Message):
    """Handle forwarded images from source channel"""
    try:
        # Check if message is forwarded from source channel
        if not message.forward_from_chat or message.forward_from_chat.id != SOURCE_CHANNEL_ID:
            return
        
        # Check if user is authorized
        if message.from_user.id != 7383046042:
            return
        
        # Check if it's part of a media group (album)
        if message.media_group_id:
            # Initialize media group if not exists
            if message.media_group_id not in media_groups:
                media_groups[message.media_group_id] = []
                # Schedule processing after 2 seconds to collect all images
                import threading
                timer = threading.Timer(2.0, process_media_group, args=[message.media_group_id])
                timer.start()
            
            # Add message to media group
            media_groups[message.media_group_id].append(message)
            logger.info(f"Added to media group {message.media_group_id}, total: {len(media_groups[message.media_group_id])}")
            
        else:
            # Single image
            file_id = message.photo[-1].file_id
            process_single_image(message, file_id)
            
    except Exception as e:
        logger.error(f"Error in handle_forwarded_images: {e}")

# ---------- Webhook ----------
@app.route("/", methods=["GET"])
def index():
    return "Bot is running."

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook_handler():
    if request.headers.get("content-type", "").startswith("application/json"):
        json_string = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "", 200
    else:
        abort(400)

def setup_webhook():
    global WEBHOOK_URL
    if not WEBHOOK_URL:
        render_external = os.getenv("RENDER_EXTERNAL_URL")
        if render_external:
            if render_external.startswith("http://") or render_external.startswith("https://"):
                base = render_external
            else:
                base = f"https://{render_external}"
            WEBHOOK_URL = f"{base}/{BOT_TOKEN}"
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL not set. Webhook won't be set automatically.")
        return

    try:
        bot.remove_webhook()
        ok = bot.set_webhook(url=WEBHOOK_URL)
        if ok:
            logger.info("Webhook successfully set.")
        else:
            logger.error("Failed to set webhook.")
    except Exception as ex:
        logger.exception("Exception while setting webhook: %s", ex)

# ---------- Start ----------
if __name__ == "__main__":
    setup_webhook()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
