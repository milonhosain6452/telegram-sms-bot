# app.py
import os
import io
import logging
from flask import Flask, request, abort
import telebot
from telebot import types
from PIL import Image, ImageFilter

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

# ---------- Helpers ----------
def apply_blur_to_image_bytes(image_bytes: bytes, radius: float) -> bytes:
    """
    Apply Gaussian blur + add Telegram & Facebook watermarks.
    """
    with Image.open(io.BytesIO(image_bytes)) as im:
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")

        # Blur
        blurred = im.filter(ImageFilter.GaussianBlur(radius=radius))

        # Load watermark images
        try:
            telegram_logo = Image.open("telegram.png").convert("RGBA")
            facebook_logo = Image.open("facebook.png").convert("RGBA")
        except Exception as e:
            logger.error("Watermark images not found: %s", e)
            return image_bytes  # fallback (no watermark)

        # Resize watermarks dynamically (~27% of image width, bigger than before)
        wm_width = int(blurred.width * 0.27)
        ratio_tg = telegram_logo.width / telegram_logo.height
        ratio_fb = facebook_logo.width / facebook_logo.height

        tg_resized = telegram_logo.resize((wm_width, int(wm_width / ratio_tg)))
        fb_resized = facebook_logo.resize((wm_width, int(wm_width / ratio_fb)))

        # Paste Telegram bottom-left (but a bit higher)
        pos_tg = (20, blurred.height - tg_resized.height - 50)
        # Paste Facebook bottom-right (but a bit higher)
        pos_fb = (blurred.width - fb_resized.width - 20, blurred.height - fb_resized.height - 50)

        blurred = blurred.convert("RGBA")
        blurred.paste(tg_resized, pos_tg, tg_resized)
        blurred.paste(fb_resized, pos_fb, fb_resized)

        # Save result as JPEG
        out_io = io.BytesIO()
        blurred.convert("RGB").save(out_io, format="JPEG", quality=85)
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
        file_bytes = bot.download_file(file_info.file_path)

        blurred_bytes = apply_blur_to_image_bytes(file_bytes, BLUR_RADIUS)

        bot.send_photo(
            chat_id=message.chat.id,
            photo=io.BytesIO(blurred_bytes),
            reply_to_message_id=message.message_id
        )
    except Exception as e:
        logger.exception("Error processing image: %s", e)
        try:
            bot.reply_to(message, "দুঃখিত—ছবি প্রসেস করতে সমস্যা হয়েছে।")
        except:
            pass

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
