# app.py
import os
import io
import logging
from flask import Flask, request, abort
import telebot
from telebot import types
from PIL import Image, ImageFilter, ImageDraw, ImageFont

# -------- Configuration (env preferred) ----------
API_ID = os.getenv("API_ID") or "22134923"
API_HASH = os.getenv("API_HASH") or "d3e9d2f01d3291e87ea65298317f86b8"
BOT_TOKEN = os.getenv("BOT_TOKEN") or "8285636468:AAFPRQ1oS1N3I4MBI85RFEOZXW4pwBrWHLg"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  
try:
    BLUR_RADIUS = float(os.getenv("BLUR_RADIUS", "12"))
except:
    BLUR_RADIUS = 12.0

# -------- Setup bot & flask ----------
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required")

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_watermarks(image):
    """
    Add two watermarks to the image:
    1. Left middle: "fb page = Glimxoo"
    2. Right middle: "search = avc\nsearch & join all channel"
    """
    draw = ImageDraw.Draw(image)
    width, height = image.size
    
    # Fixed font size (same for all images)
    font_size = 100  
    
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        try:
            font = ImageFont.truetype("Arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
    
    # Left watermark: "fb page = Glimxoo"
    left_text = "fb page = Glimxoo"
    left_bbox = draw.textbbox((0, 0), left_text, font=font)
    left_text_width = left_bbox[2] - left_bbox[0]
    left_text_height = left_bbox[3] - left_bbox[1]
    left_x = 30
    left_y = (height - left_text_height) // 2
    
    # Right watermark
    right_text = "search = avc\nsearch & join all channel"
    right_bbox = draw.textbbox((0, 0), right_text, font=font)
    right_text_width = right_bbox[2] - right_bbox[0]
    right_text_height = right_bbox[3] - right_bbox[1]
    right_x = width - right_text_width - 30
    right_y = (height - right_text_height) // 2
    
    # Stroke for visibility
    stroke_width = 3
    
    # Draw left watermark
    for x_offset in range(-stroke_width, stroke_width + 1):
        for y_offset in range(-stroke_width, stroke_width + 1):
            if x_offset == 0 and y_offset == 0:
                continue
            draw.text((left_x + x_offset, left_y + y_offset), left_text, font=font, fill="black")
    draw.text((left_x, left_y), left_text, font=font, fill="white")
    
    # Draw right watermark
    for x_offset in range(-stroke_width, stroke_width + 1):
        for y_offset in range(-stroke_width, stroke_width + 1):
            if x_offset == 0 and y_offset == 0:
                continue
            draw.text((right_x + x_offset, right_y + y_offset), right_text, font=font, fill="black")
    draw.text((right_x, right_y), right_text, font=font, fill="white")
    
    return image

def apply_blur_to_image_bytes(image_bytes: bytes, radius: float) -> bytes:
    with Image.open(io.BytesIO(image_bytes)) as im:
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        blurred = im.filter(ImageFilter.GaussianBlur(radius=radius))
        watermarked = add_watermarks(blurred)
        out_io = io.BytesIO()
        watermarked.convert("RGB").save(out_io, format="JPEG", quality=85)
        out_io.seek(0)
        return out_io.read()

# ---------- Handlers ----------
@bot.message_handler(commands=['start'])
def handle_start(message: types.Message):
    bot.reply_to(message, "Lets Talk Each Other")

@bot.message_handler(func=lambda m: isinstance(m.text, str) and m.text.strip().lower() == "hi")
def handle_hi(message: types.Message):
    bot.reply_to(message, "Hello")

@bot.message_handler(content_types=['photo', 'document'])
def handle_image(message: types.Message):
    try:
        file_id = None
        if message.photo:
            file_id = message.photo[-1].file_id
        elif message.document and message.document.mime_type and message.document.mime_type.startswith("image"):
            file_id = message.document.file_id

        if not file_id:
            return

        file_info = bot.get_file(file_id)
        file_path = file_info.file_path
        file_bytes = bot.download_file(file_path)

        blurred_bytes = apply_blur_to_image_bytes(file_bytes, BLUR_RADIUS)

        bot.send_photo(chat_id=message.chat.id, photo=io.BytesIO(blurred_bytes), reply_to_message_id=message.message_id)
    except Exception as e:
        logger.exception("Error processing image: %s", e)
        try:
            bot.reply_to(message, "দুঃখিত—ছবি প্রসেস করতে সমস্যা হয়েছে।")
        except:
            pass

# ---------- Webhook endpoints ----------
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

# ---------- webhook setup on startup ----------
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
        logger.warning("WEBHOOK_URL not set. Please set WEBHOOK_URL or manually setWebhook.")
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

# ---------- start ----------
if __name__ == "__main__":
    setup_webhook()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
