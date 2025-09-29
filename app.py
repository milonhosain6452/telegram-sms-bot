import os
import io
import logging
from flask import Flask, request, abort
import telebot
from telebot import types
from PIL import Image, ImageFilter, ImageDraw, ImageFont

# Configuration (env preferred)
API_ID = os.getenv("API_ID") or "22134923"
API_HASH = os.getenv("API_HASH") or "d3e9d2f01d3291e87ea65298317f86b8"
BOT_TOKEN = os.getenv("BOT_TOKEN") or "8285636468:AAFPRQ1oS1N3I4MBI85RFEOZXW4pwBrWHLg"

# You can optionally set explicit webhook url (preferred)
WEBHOOK_URL = os.getenv("WEBHOOK_URL") # e.g. https://your-app.onrender.com/<BOT_TOKEN>

# Blur radius (adjustable via env). Default 12 -> medium blur
try:
    BLUR_RADIUS = float(os.getenv("BLUR_RADIUS", "12"))
except:
    BLUR_RADIUS = 12.0

# Setup bot & flask
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required")

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Handlers
@bot.message_handler(commands=['start'])
def handle_start(message: types.Message):
    bot.reply_to(message, "Lets Talk Each Other")

@bot.message_handler(func=lambda m: isinstance(m.text, str) and m.text.strip().lower() == "hi")
def handle_hi(message: types.Message):
    bot.reply_to(message, "Hello")

def add_watermarks(image: Image.Image) -> Image.Image:
    """
    Add Facebook page and Telegram channel watermarks to the image
    """
    draw = ImageDraw.Draw(image)
    width, height = image.size
    
    # Calculate font size based on image dimensions
    base_font_size = min(width, height) // 20
    font_large = ImageFont.truetype("arial.ttf", base_font_size)
    font_medium = ImageFont.truetype("arial.ttf", int(base_font_size * 0.8))
    
    # Facebook watermark - middle left with banner style
    fb_text = "Fb page = Glimxoo"
    fb_bbox = draw.textbbox((0, 0), fb_text, font=font_large)
    fb_text_width = fb_bbox[2] - fb_bbox[0]
    fb_text_height = fb_bbox[3] - fb_bbox[1]
    
    # Position for Facebook watermark (middle left)
    fb_x = 20
    fb_y = (height - fb_text_height) // 2
    
    # Draw Facebook watermark background (banner style)
    fb_padding = 15
    draw.rectangle([
        fb_x - fb_padding, 
        fb_y - fb_padding, 
        fb_x + fb_text_width + fb_padding, 
        fb_y + fb_text_height + fb_padding
    ], fill=(0, 0, 0, 128))  # Semi-transparent black background
    
    # Draw Facebook text
    draw.text((fb_x, fb_y), fb_text, font=font_large, fill=(255, 255, 255))
    
    # Telegram channel watermark - middle right with banner style
    telegram_line1 = "search = avc"
    telegram_line2 = "search & join all channel"
    
    # Calculate text dimensions for telegram watermarks
    tg1_bbox = draw.textbbox((0, 0), telegram_line1, font=font_medium)
    tg2_bbox = draw.textbbox((0, 0), telegram_line2, font=font_medium)
    
    tg1_width = tg1_bbox[2] - tg1_bbox[0]
    tg2_width = tg2_bbox[2] - tg2_bbox[0]
    tg1_height = tg1_bbox[3] - tg1_bbox[0]
    tg2_height = tg2_bbox[3] - tg2_bbox[0]
    
    max_tg_width = max(tg1_width, tg2_width)
    total_tg_height = tg1_height + tg2_height + 5
    
    # Position for Telegram watermark (middle right)
    tg_x = width - max_tg_width - 30
    tg_y = (height - total_tg_height) // 2
    
    # Draw Telegram watermark background (banner style)
    tg_padding = 12
    draw.rectangle([
        tg_x - tg_padding, 
        tg_y - tg_padding, 
        tg_x + max_tg_width + tg_padding, 
        tg_y + total_tg_height + tg_padding
    ], fill=(0, 0, 0, 128))  # Semi-transparent black background
    
    # Draw Telegram text
    draw.text((tg_x, tg_y), telegram_line1, font=font_medium, fill=(255, 255, 255))
    draw.text((tg_x, tg_y + tg1_height + 5), telegram_line2, font=font_medium, fill=(255, 255, 255))
    
    return image

def apply_blur_to_image_bytes(image_bytes: bytes, radius: float) -> bytes:
    """
    Apply Gaussian blur to image bytes and return resulting image bytes (JPEG).
    """
    with Image.open(io.BytesIO(image_bytes)) as im:
        # convert to RGB if needed
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        # Optionally: keep size, just blur
        blurred = im.filter(ImageFilter.GaussianBlur(radius=radius))
        
        # Add watermarks to the blurred image
        watermarked_image = add_watermarks(blurred)
        
        out_io = io.BytesIO()
        # Save as JPEG to reduce size (if image had alpha, convert)
        watermarked_image.convert("RGB").save(out_io, format="JPEG", quality=85)
        out_io.seek(0)
        return out_io.read()

@bot.message_handler(content_types=['photo', 'document'])
def handle_image(message: types.Message):
    """
    When user sends/forwards an image (photo or document with image mime),
    download -> blur -> reply with blurred image.
    """
    try:
        file_id = None
        # If photo (array of sizes), pick largest
        if message.photo:
            file_id = message.photo[-1].file_id
        elif message.document and message.document.mime_type and message.document.mime_type.startswith("image"):
            file_id = message.document.file_id

        if not file_id: # not an image document (e.g., pdf), ignore
            return

        # Fetch file info and download file bytes
        file_info = bot.get_file(file_id)
        file_path = file_info.file_path # path on Telegram servers
        file_bytes = bot.download_file(file_path)

        # Apply blur
        blurred_bytes = apply_blur_to_image_bytes(file_bytes, BLUR_RADIUS)

        # Send blurred image back as reply
        bot.send_photo(chat_id=message.chat.id, photo=io.BytesIO(blurred_bytes), reply_to_message_id=message.message_id)

    except Exception as e:
        logger.exception("Error processing image: %s", e)
        # optional fallback reply
        try:
            bot.reply_to(message, "দুঃখিত—ছবি প্রসেস করতে সমস্যা হয়েছে।")
        except:
            pass

# Webhook endpoints
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

# webhook setup on startup
def setup_webhook():
    global WEBHOOK_URL
    # prefer explicit WEBHOOK_URL env var
    if not WEBHOOK_URL:
        render_external = os.getenv("RENDER_EXTERNAL_URL")
        if render_external:
            # Render provides without scheme sometimes; ensure scheme
            if render_external.startswith("http://") or render_external.startswith("https://"):
                base = render_external
            else:
                base = f"https://{render_external}"
            WEBHOOK_URL = f"{base}/{BOT_TOKEN}"
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL not set. Please set WEBHOOK_URL or rely on manual setWebhook. Webhook won't be set automatically.")
        return

    try:
        logger.info("Setting webhook to %s", WEBHOOK_URL)
        bot.remove_webhook()
        ok = bot.set_webhook(url=WEBHOOK_URL)
        if ok:
            logger.info("Webhook successfully set.")
        else:
            logger.error("Failed to set webhook.")
    except Exception as ex:
        logger.exception("Exception while setting webhook: %s", ex)

# start
if __name__ == "__main__":
    setup_webhook()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
