from fastapi import FastAPI, Request
from aiogram import Bot, types, Dispatcher
from aiogram.types import Update
import os
import json
import io

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID") 

app = FastAPI()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def get_db_and_update(new_file_data=None):
    """
    1. Fetches the pinned JSON from the channel.
    2. Adds new_file_data (if exists).
    3. Re-uploads and Pins.
    """
    db_data = {"files": [], "next_id": 1}
    try:
        chat = await bot.get_chat(CHANNEL_ID)
        if chat.pinned_message and chat.pinned_message.document:
            f_id = chat.pinned_message.document.file_id
            file_obj = await bot.download(chat.pinned_message.document)
            db_data = json.load(file_obj)
    except Exception as e:
        print(f"DB Fetch Error: {e}")

    if new_file_data:
        db_data["files"].append(new_file_data)
        db_data["next_id"] += 1
    
    if new_file_data:
        json_bytes = json.dumps(db_data).encode('utf-8')
        input_file = types.BufferedInputFile(json_bytes, filename="system.json")
        msg = await bot.send_document(CHANNEL_ID, input_file, caption="[DB_BACKUP]")
        await bot.pin_chat_message(CHANNEL_ID, msg.message_id)

    return db_data

@app.post("/api/telegram")
async def telegram_webhook(request: Request):
    """
    Vercel calls this function whenever Telegram sends an update.
    """
    data = await request.json()
    update = Update(**data)
    
    if update.message and update.message.document:
        doc = update.message.document
        
        backup_msg = await bot.send_document(
            chat_id=CHANNEL_ID,
            document=doc.file_id,
            caption=f"File: {doc.file_name}"
        )
        
        new_file = {
            "name": doc.file_name,
            "tg_file_id": doc.file_id,
            "msg_id": backup_msg.message_id,
            "size": doc.file_size
        }
        
        await get_db_and_update(new_file)
        
        await bot.send_message(update.message.chat.id, f"✅ Saved {doc.file_name} to the Cloud!")

    return {"status": "ok"}