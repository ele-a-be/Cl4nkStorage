import os
import json
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    Update, 
    BufferedInputFile, 
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

app = FastAPI()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def get_db():
    """
    Downloads the 'system.json' from the storage channel.
    Returns a dict with default structure if not found.
    """
    default_db = {"files": [], "next_id": 1}
    try:
        chat = await bot.get_chat(CHANNEL_ID)
        if chat.pinned_message and chat.pinned_message.document:
            f = await bot.download(chat.pinned_message.document)
            return json.load(f)
    except Exception as e:
        print(f"⚠️ DB Fetch Warning: {e}")
    return default_db

async def save_db(db_data):
    """
    Uploads the JSON to the channel and Pins it.
    """
    json_bytes = json.dumps(db_data, indent=2).encode('utf-8')
    input_file = BufferedInputFile(json_bytes, filename="system.json")
    
    msg = await bot.send_document(
        chat_id=CHANNEL_ID, 
        document=input_file, 
        caption="[DB_BACKUP] Do not delete."
    )
    
    await bot.pin_chat_message(
        chat_id=CHANNEL_ID, 
        message_id=msg.message_id, 
        disable_notification=True
    )

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """
    Shows the Persistent Menu (Type 1 Buttons).
    """
    kb = [
        [KeyboardButton(text="📂 My Files"), KeyboardButton(text="☁️ Storage Usage")],
        [KeyboardButton(text="❓ Help")]
    ]
    menu = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, persistent=True)

    await message.answer(
        "👻 **Ghost Drive Ready.**\n\nUse the menu below to navigate.", 
        reply_markup=menu
    )

@dp.message(F.text == "❓ Help")
async def btn_help(message: types.Message):
    text = (
        "**How to use Ghost Drive:**\n\n"
        "1. **Upload:** Just drag & drop any file here.\n"
        "2. **Download:** Click '📂 My Files' and select a file.\n"
        "3. **Storage:** Infinite & Free (hosted on Telegram)."
    )
    await message.answer(text)

@dp.message(F.text == "☁️ Storage Usage")
async def btn_usage(message: types.Message):
    db = await get_db()
    file_count = len(db.get("files", []))
    
    await message.answer(f"📊 **Drive Status:**\n\n📁 Total Files: {file_count}\n💾 Space Used: 0 MB (Unlimited)")

@dp.message(F.text == "📂 My Files")
async def btn_my_files(message: types.Message):
    """
    Lists files using Inline Buttons (Type 2).
    Includes error handling for corrupted DB entries.
    """
    db = await get_db()
    files = db.get("files", [])
    
    if not files:
        return await message.answer("📂 Drive is empty. Upload a file first!")

    valid_files = [f for f in files if isinstance(f, dict) and 'id' in f and 'name' in f]
    
    if not valid_files:
        return await message.answer("⚠️ Files exist but appear corrupted. Try uploading a new file.")
    recent_files = sorted(valid_files, key=lambda x: x['id'], reverse=True)[:10]

    keyboard = []
    for f in recent_files:
        btn = InlineKeyboardButton(text=f"⬇️ {f['name']}", callback_data=f"dl_{f['id']}")
        keyboard.append([btn])
    
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer("📂 **Your Recent Files:**", reply_markup=markup)

@dp.callback_query(F.data.startswith("dl_"))
async def callback_download(callback: types.CallbackQuery):
    """
    Triggered when user clicks an Inline Button (⬇️ filename).
    """
    file_id_internal = int(callback.data.split("_")[1])
    db = await get_db()
    
    target_file = next((f for f in db["files"] if f["id"] == file_id_internal), None)
    
    if target_file:
        await callback.answer("Fetching file...")
        await bot.copy_message(
            chat_id=callback.from_user.id,
            from_chat_id=CHANNEL_ID,
            message_id=target_file["msg_id"],
            caption=f"Here is your file: {target_file['name']}"
        )
    else:
        await callback.answer("❌ File not found in index.", show_alert=True)

@dp.message(F.document | F.photo | F.video | F.audio)
async def handle_upload(message: types.Message):
    """
    Catches any file sent to the bot.
    """
    if message.document:
        f_id = message.document.file_id
        f_name = message.document.file_name or "Document"
    elif message.photo:
        f_id = message.photo[-1].file_id
        f_name = f"Photo_{message.photo[-1].file_unique_id}.jpg"
    elif message.video:
        f_id = message.video.file_id
        f_name = message.video.file_name or "Video.mp4"
    elif message.audio:
        f_id = message.audio.file_id
        f_name = message.audio.file_name or "Audio.mp3"
    else:
        return

    status_msg = await message.answer("⏳ Uploading to cloud...")

    backup_msg = await bot.send_document(
        chat_id=CHANNEL_ID,
        document=f_id,
        caption=f"Filename: {f_name}"
    )

    db = await get_db()
    new_entry = {
        "id": db["next_id"],
        "name": f_name,
        "tg_file_id": f_id,
        "msg_id": backup_msg.message_id
    }
    
    db["files"].append(new_entry)
    db["next_id"] += 1
    
    await save_db(db)
    
    await bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
    await message.answer(f"✅ **{f_name}** saved safely!")

@app.post("/api/telegram")
async def telegram_webhook(request: Request):
    """
    Receives updates from Telegram and feeds them to Aiogram.
    """
    try:
        data = await request.json()
        update = Update(**data)
        await dp.feed_update(bot, update)
    except Exception as e:
        print(f"Error processing update: {e}")
    return {"status": "ok"}