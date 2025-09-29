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

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_watermarks(image):
    """
    Add improved Facebook (top) and Telegram (center) watermark
    """
    draw = ImageDraw.Draw(image)
    width, height = image.size

    # Fonts
    try:
        font_fb = ImageFont.truetype("arial.ttf", max(30, width // 20))
        font_tg = ImageFont.truetype("arial.ttf", max(25, width // 25))
    except:
        font_fb = ImageFont.load_default()
        font_tg = ImageFont.load_default()

    # ---------- Facebook watermark ----------
    fb_text = "📘 fb page Glimxoo"
    try:
        bbox = draw.textbbox((0,0), fb_text, font=font_fb)
        text_w, text_h = bbox[2]-bbox[0], bbox[3]-bbox[1]
    except:
        text_w, text_h = len(fb_text)*20, 30

    fb_x = (width - text_w)//2
    fb_y = height // 20
    pad = 12
    # semi-transparent background rectangle
    draw.rectangle([fb_x-pad, fb_y-pad, fb_x+text_w+pad, fb_y+text_h+pad],
                   fill=(255,255,255,200))
    draw.text((fb_x, fb_y), fb_text, fill=(0,0,0), font=font_fb)

    # ---------- Telegram watermark ----------
    tg_line1 = "🔍 search = avc"
    tg_line2 = "📢 search & join all channel"
    try:
        bbox1 = draw.textbbox((0,0), tg_line1, font=font_tg)
        bbox2 = draw.textbbox((0,0), tg_line2, font=font_tg)
        line1_w, line1_h = bbox1[2]-bbox1[0], bbox1[3]-bbox1[1]
        line2_w, line2_h = bbox2[2]-bbox2[0], bbox2[3]-bbox2[1]
    except:
        line1_w, line1_h = len(tg_line1)*15, 25
        line2_w, line2_h = len(tg_line2)*15, 25

    max_w = max(line1_w, line2_w)
    tg_x1 = (width - max_w)//2
    tg_y1 = height//2 - line1_h
    bg_pad = 15
    total_height = line1_h + line2_h + 10
    draw.rectangle([tg_x1-bg_pad, tg_y1-bg_pad, tg_x1+max_w+bg_pad, tg_y1+total_height+bg_pad],
                   fill=(255,255,255,180))
    draw.text((tg_x1, tg_y1), tg_line1, fill=(0,0,0), font=font_tg)
    draw.text((tg_x1, tg_y1+line1_h+5), tg_line2, fill=(0,0,0), font=font_tg)

    return image

def apply_blur_to_image_bytes(image_bytes: bytes, radius: float) -> bytes:
    """
    Apply Gaussian blur to image bytes and add watermarks.
    """
    with Image.open(io.BytesIO(image_bytes)) as im:
        if im.mode not in ("RGB","RGBA"):
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
