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

# Font paths (Render might not have system fonts; Pillow default font will be used)
DEFAULT_FONT = ImageFont.load_default()

# -------- Setup bot & flask ----------
bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- Handlers ----------
@bot.message_handler(commands=['start'])
def handle_start(message: types.Message):
    bot.reply_to(message, "Lets Talk Each Other")

@bot.message_handler(func=lambda m: isinstance(m.text, str) and m.text.strip().lower() == "hi")
def handle_hi(message: types.Message):
    bot.reply_to(message, "Hello")

def add_watermarks(image: Image.Image) -> Image.Image:
    """
    Add Facebook (top) and Telegram (center) watermark to an image.
    """
    draw = ImageDraw.Draw(image)
    w, h = image.size

    # -------- Facebook watermark (top-left) ----------
    fb_text = "Glimxoo"
    fb_logo = "🔵"  # Simple emoji as FB logo placeholder
    fb_full_text = f"{fb_logo} {fb_text}"
    fb_font_size = max(20, w // 25)
    try:
        fb_font = ImageFont.truetype("arial.ttf", fb_font_size)
    except:
        fb_font = DEFAULT_FONT
    text_w, text_h = draw.textsize(fb_full_text, font=fb_font)
    margin = 10
    draw.text((margin, margin), fb_full_text, fill=(255, 255, 255, 255), font=fb_font)

    # -------- Telegram watermark (center) ----------
    tg_logo = "📲"
    tg_line1 = "search = avc"
    tg_line2 = "search & join all channel"
    tg_font_size = max(25, w // 20)
    try:
        tg_font = ImageFont.truetype("arial.ttf", tg_font_size)
    except:
        tg_font = DEFAULT_FONT

    # Calculate positions
    line1_w, line1_h = draw.textsize(tg_line1, font=tg_font)
    line2_w, line2_h = draw.textsize(tg_line2, font=tg_font)
    center_x = (w - line1_w) // 2
    center_y = h // 2 - line1_h

    draw.text((center_x, center_y - 20), f"{tg_logo} {tg_line1}", fill=(255, 255, 255, 255), font=tg_font)
    draw.text((center_x, center_y + 20), tg_line2, fill=(255, 255, 255, 255), font=tg_font)

    return image

def apply_blur_to_image_bytes(image_bytes: bytes, radius: float) -> bytes:
    """
    Apply Gaussian blur to image bytes and add watermarks.
    """
    with Image.open(io.BytesIO(image_bytes)) as im:
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        blurred = im.filter(ImageFilter.GaussianBlur(radius=radius))
        # Add watermarks
        final_img = add_watermarks(blurred)
        out_io = io.BytesIO()
        final_img.convert("RGB").save(out_io, format="JPEG", quality=85)
        out_io.seek(0)
        return out_io.read()

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

        processed_bytes = apply_blur_to_image_bytes(file_bytes, BLUR_RADIUS)
        bot.send_photo(chat_id=message.chat.id, photo=io.BytesIO(processed_bytes), reply_to_message_id=message.message_id)
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
        logger.warning("WEBHOOK_URL not set. Webhook won't be set automatically.")
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
