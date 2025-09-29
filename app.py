import os
import io
import logging
from flask import Flask, request, abort
import telebot
from telebot import types
from PIL import Image, ImageFilter, ImageDraw, ImageFont

-------- Configuration (env preferred) ----------

API_ID = os.getenv("API_ID") or "22134923"
API_HASH = os.getenv("API_HASH") or "d3e9d2f01d3291e87ea65298317f86b8"
BOT_TOKEN = os.getenv("BOT_TOKEN") or "8285636468:AAFPRQ1oS1N3I4MBI85RFEOZXW4pwBrWHLg"

You can optionally set explicit webhook url (preferred)

WEBHOOK_URL = os.getenv("WEBHOOK_URL") # e.g. https://your-app.onrender.com/<BOT_TOKEN>

Blur radius (adjustable via env). Default 12 -> medium blur

try:
BLUR_RADIUS = float(os.getenv("BLUR_RADIUS", "12"))
except:
BLUR_RADIUS = 12.0

-------- Setup bot & flask ----------

if not BOT_TOKEN:
raise RuntimeError("BOT_TOKEN is required")

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
app = Flask(name)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(name)

---------- Handlers ----------

@bot.message_handler(commands=['start'])
def handle_start(message: types.Message):
bot.reply_to(message, "Lets Talk Each Other")

@bot.message_handler(func=lambda m: isinstance(m.text, str) and m.text.strip().lower() == "hi")
def handle_hi(message: types.Message):
bot.reply_to(message, "Hello")

def add_watermark_to_image(im: Image.Image) -> Image.Image:
"""
Add watermark banners to the image with Facebook page and Telegram channel info.
"""
draw = ImageDraw.Draw(im)
width, height = im.size
    
# Calculate font size based on image dimensions
base_font_size = max(width, height) // 25
try:
font = ImageFont.truetype("arial.ttf", base_font_size)
except:
try:
font = ImageFont.truetype("Arial", base_font_size)
except:
font = ImageFont.load_default()

# Facebook watermark (middle left position)
fb_text = "Fb page = Glimxoo"
fb_bbox = draw.textbbox((0, 0), fb_text, font=font)
fb_text_width = fb_bbox[2] - fb_bbox[0]
fb_text_height = fb_bbox[3] - fb_bbox[1]
fb_x = (width - fb_text_width) // 2 - width // 3  # Middle left
fb_y = height // 2 - fb_text_height

# Draw Facebook background banner
fb_padding = 20
fb_bg_coords = [
    fb_x - fb_padding,
    fb_y - fb_padding,
    fb_x + fb_text_width + fb_padding,
    fb_y + fb_text_height + fb_padding
]
draw.rectangle(fb_bg_coords, fill=(0, 0, 0, 180))  # Semi-transparent black background
draw.text((fb_x, fb_y), fb_text, font=font, fill=(255, 255, 255))  # White text

# Telegram channel watermark (middle right position)
tg_text1 = "search = avc"
tg_text2 = "search & join all channel"
tg_bbox1 = draw.textbbox((0, 0), tg_text1, font=font)
tg_bbox2 = draw.textbbox((0, 0), tg_text2, font=font)
tg_text_width = max(tg_bbox1[2] - tg_bbox1[0], tg_bbox2[2] - tg_bbox2[0])
tg_text_height = (tg_bbox1[3] - tg_bbox1[1]) + (tg_bbox2[3] - tg_bbox2[1]) + 10

tg_x = (width - tg_text_width) // 2 + width // 3  # Middle right
tg_y = height // 2 - tg_text_height // 2

# Draw Telegram background banner
tg_padding = 20
tg_bg_coords = [
    tg_x - tg_padding,
    tg_y - tg_padding,
    tg_x + tg_text_width + tg_padding,
    tg_y + tg_text_height + tg_padding
]
draw.rectangle(tg_bg_coords, fill=(0, 0, 0, 180))  # Semi-transparent black background
draw.text((tg_x, tg_y), tg_text1, font=font, fill=(255, 255, 255))  # White text
draw.text((tg_x, tg_y + (tg_bbox1[3] - tg_bbox1[1]) + 5), tg_text2, font=font, fill=(255, 255, 255))

return im

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
    
# Add watermark to blurred image
watermarked = add_watermark_to_image(blurred)
    
out_io = io.BytesIO()
# Save as JPEG to reduce size (if image had alpha, convert)
watermarked.convert("RGB").save(out_io, format="JPEG", quality=85)
out_io.seek(0)
return out_io.read()

@bot.message_handler(content_types=['photo', 'document'])
def handle_image(message: types.Message):
"""
When user sends/forwards an image (photo or document with image mime),
download -> blur -> add watermark -> reply with blurred image.
"""
try:
file_id = None
# If photo (array of sizes), pick largest
if message.photo:
file_id = message.photo[-1].file_id
elif message.document and message.document.mime_type and message.document.mime_type.startswith("image"):
file_id = message.document.file_id

if not file_id: # not an image document (e.g., pdf), ignore return # Fetch file info and download file bytes file_info = bot.get_file(file_id) file_path = file_info.file_path # path on Telegram servers file_bytes = bot.download_file(file_path) # Apply blur and watermark blurred_bytes = apply_blur_to_image_bytes(file_bytes, BLUR_RADIUS) # Send blurred image back as reply bot.send_photo(chat_id=message.chat.id, photo=io.BytesIO(blurred_bytes), reply_to_message_id=message.message_id) except Exception as e: logger.exception("Error processing image: %s", e) # optional fallback reply try: bot.reply_to(message, "দুঃখিত—ছবি প্রসেস করতে সমস্যা হয়েছে।") except: pass 

---------- Webhook endpoints ----------

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

---------- webhook setup on startup ----------

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

try: logger.info("Setting webhook to %s", WEBHOOK_URL) bot.remove_webhook() ok = bot.set_webhook(url=WEBHOOK_URL) if ok: logger.info("Webhook successfully set.") else: logger.error("Failed to set webhook.") except Exception as ex: logger.exception("Exception while setting webhook: %s", ex) 

---------- start ----------

if name == "main":
setup_webhook()
port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)
