
import os
import json
import asyncio
import random
import string
import logging

from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.ext import Defaults

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
VIDEO_DB_FILE = "videos.json"

user_state = {}
videos_map = {}

if not os.path.exists(VIDEO_DB_FILE):
    with open(VIDEO_DB_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f)

def load_videos():
    with open(VIDEO_DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_videos(data):
    with open(VIDEO_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def generate_code(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

async def is_member(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or user.id != ADMIN_ID:
        await update.message.reply_text("❌ دسترسی فقط برای ادمین است.")
        return
    keyboard = [[InlineKeyboardButton("📤 آپلود ویدیو", callback_data="upload_video")]]
    await update.message.reply_text(
        "🔧 پنل ادمین:
برای آپلود ویدیو کلیک کن:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if not user or user.id != ADMIN_ID:
        await query.edit_message_text("❌ دسترسی فقط برای ادمین است.")
        return
    if query.data == "upload_video":
        user_state[ADMIN_ID] = "uploading"
        await query.edit_message_text("🎬 لطفاً ویدیوی خود را ارسال کنید.")

async def handle_video_from_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or user.id != ADMIN_ID or user_state.get(ADMIN_ID) != "uploading":
        return
    video = update.message.video or update.message.document
    if not video:
        await update.message.reply_text("❌ لطفاً یک فایل ویدیو ارسال کنید.")
        return

    code = generate_code()
    file_id = video.file_id

    vids = load_videos()
    vids[code] = file_id
    save_videos(vids)

    link = f"https://t.me/{context.bot.username}?start={code}"
    await update.message.reply_text(f"✅ ویدیو ذخیره شد!
🔗 لینک اختصاصی:
{link}")

    user_state[ADMIN_ID] = None

async def start_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    args = context.args
    if not args:
        await update.message.reply_text("سلام! برای دریافت ویدیو از لینک اختصاصی استفاده کنید.")
        return

    code = args[0]
    vids = load_videos()
    if code not in vids:
        await update.message.reply_text("❌ لینک نامعتبر است.")
        return

    if not await is_member(user.id, context):
        btn = InlineKeyboardButton(
            "📢 عضویت در کانال",
            url=f"https://t.me/{CHANNEL_USERNAME}"
        )
        await update.message.reply_text(
            "❌ ابتدا عضو کانال شوید و سپس مجددا روی لینک فیلم بزنید.",
            reply_markup=InlineKeyboardMarkup([[btn]])
        )
        return

    msg = await update.message.reply_video(
        vids[code],
        caption="🎥 این ویدیو تا ۲۰ ثانیه در دسترس است. لطفاً ذخیره‌اش کنید."
    )
    await asyncio.sleep(20)
    try:
        await context.bot.delete_message(chat_id=msg.chat.id, message_id=msg.message_id)
    except:
        pass

async def process_update(application: Application, update_json: dict):
    update = Update.de_json(update_json, application.bot)
    await application.process_update(update)

@app.route("/", methods=["POST"])
async def webhook():
    await process_update(app.bot_app, request.get_json(force=True))
    return "ok"

@app.before_first_request
def setup_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(handle_admin_buttons))
    application.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video_from_admin))
    application.add_handler(CommandHandler("start", start_link))
    app.bot_app = application
    asyncio.create_task(application.initialize())

