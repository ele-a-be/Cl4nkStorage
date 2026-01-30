
import os
import json
import re
import asyncio
import redis.asyncio as redis
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    Update, BufferedInputFile, InlineKeyboardMarkup, 
    InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ForceReply
)
from fastapi.responses import HTMLResponse, RedirectResponse
import uuid
from api.dashboard_html import HTML_CONTENT

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
KV_URL = os.environ.get("KV_URL") or os.environ.get("REDIS_URL")

app = FastAPI()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
r = redis.from_url(KV_URL)

async def get_db():
    structure = {
        "files": [], 
        "next_id": 1, 
        "clipboard": {}, 
        "sessions": {},
        "ui_state": {},
        "sort_prefs": {},
        "pending_ops": {} 
    }
    
    # Try Redis First
    try:
        raw = await r.get("cl4nk_db")
        if raw: 
            data = json.loads(raw)
            for k, v in structure.items():
                if k not in data: data[k] = v
            return data
    except: pass

    # Fallback: Migration from Telegram
    print("MIGRATION: Fetching from Telegram...")
    try:
        chat = await bot.get_chat(CHANNEL_ID)
        if chat.pinned_message and chat.pinned_message.document:
            f = await bot.download(chat.pinned_message.document)
            data = json.load(f)
            for k, v in structure.items():
                if k not in data: data[k] = v
            
            # Save to Redis immediately
            await r.set("cl4nk_db", json.dumps(data))
            return data
    except Exception as e:
        print(f"Migration Failed: {e}")
    return structure

async def save_db(db_data):
    try:
        await r.set("cl4nk_db", json.dumps(db_data))
        return True
    except Exception as e:
        print(f"Redis Save Error: {e}")
        return False

def check_collision(db, folder_id, name, exclude_id=None):
    for f in db["files"]:
        if f.get("parent_id", 0) == folder_id and f["name"] == name:
            if exclude_id and f["id"] == exclude_id: continue
            return f
    return None

def delete_recursive(db, iid):
    def get_descendants(pid):
        kids = [f["id"] for f in db["files"] if f.get("parent_id")==pid]
        for k in kids: kids.extend(get_descendants(k))
        return kids
    to_kill = [iid] + get_descendants(iid)
    db["files"] = [f for f in db["files"] if f["id"] not in to_kill]

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 **Welcome to Cl4nkStorage!**\n\n"
        "📤 **Upload**: Drag & drop files here to save them (Max 2GB).\n"
        "🖥️ **Manage**: Type `/login` to use the Web Dashboard."
    )

@dp.message(F.document | F.photo | F.video)
async def handle_upload(message: types.Message):
    fsize = 0
    if message.document: 
        fid, fname = message.document.file_id, message.document.file_name or "Doc"
        fsize = message.document.file_size or 0
    elif message.photo: 
        fid, fname = message.photo[-1].file_id, "Photo.jpg"
        fsize = message.photo[-1].file_size or 0
    elif message.video: 
        fid, fname = message.video.file_id, message.video.file_name or "Video.mp4"
        fsize = message.video.file_size or 0
    else: return
    
    db = await get_db()
    pid = 0 # Default to Root

    # Auto-Rename Logic
    original_name = fname
    counter = 1
    while check_collision(db, pid, fname):
         name, ext = os.path.splitext(original_name)
         fname = f"{name} ({counter}){ext}"
         counter += 1

    backup = await bot.send_document(CHANNEL_ID, fid, caption=f"File: {fname}")
    db["files"].append({
        "id": db["next_id"], "parent_id": pid, "name": fname, 
        "type": "file", "tg_id": fid, "msg_id": backup.message_id,
        "size": fsize, "date": int(message.date.timestamp())
    })
    db["next_id"] += 1
    await save_db(db)
    
    try: await message.delete()
    except: pass
    
    confirm = await message.answer(f"✅ Saved **{fname}** to Drive.")
    await asyncio.sleep(5)
    try: await confirm.delete()
    except: pass

@dp.message(Command("login"))
async def cmd_login(message: types.Message):
    token = str(uuid.uuid4())
    uid = str(message.from_user.id)
    # Token valid for 1 hour
    await r.setex(f"session:{token}", 3600, uid)
    
    # Construct URL
    host = os.environ.get("VERCEL_URL", "example.com")
    url = f"https://{host}/?token={token}"
    
    await message.answer(
        f"🔐 **Dashboard Login**\n\nClick the link below to access your files on the web:\n\n[🔗 Open Dashboard]({url})\n\n_Link expires in 1 hour._",
        parse_mode="Markdown"
    )

# --- Web Dashboard Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    return HTML_CONTENT

@app.get("/api/verify")
async def api_verify(token: str):
    uid = await r.get(f"session:{token}")
    if not uid: return {"status": "error"}, 401
    uid_str = uid.decode('utf-8') if hasattr(uid, 'decode') else str(uid)
    return {"status": "ok", "uid": uid_str}

@app.get("/api/files")
async def api_files(token: str, folder: int = 0):
    uid = await r.get(f"session:{token}")
    if not uid: return {"error": "Unauthorized"}
    uid = uid.decode('utf-8') if hasattr(uid, 'decode') else str(uid)
    
    db = await get_db()
    res = [f for f in db["files"] if f.get("parent_id", 0) == folder]
    return {"files": res}

@app.get("/api/download/{item_id}")
async def api_download(item_id: int, token: str):
    uid = await r.get(f"session:{token}")
    if not uid: return {"error": "Unauthorized"}
    
    db = await get_db()
    item = next((x for x in db["files"] if x["id"] == item_id), None)
    if not item: return {"error": "Not found"}
    
    try:
        f = await bot.get_file(item["tg_id"])
        host = "api.telegram.org"
        dl_url = f"https://{host}/file/bot{BOT_TOKEN}/{f.file_path}"
        return RedirectResponse(dl_url)
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/action")
async def api_action(request: Request):
    data = await request.json()
    token = data.get("token")
    uid = await r.get(f"session:{token}")
    if not uid: return {"error": "Unauthorized"}
    
    action = data.get("action")
    db = await get_db()
    
    if action == "mkdir":
        name = data.get("name")
        pid = int(data.get("parent_id", 0))
        if not name: return {"error": "Name required"}
        if check_collision(db, pid, name): return {"error": "Name exists"}
        
        db["files"].append({
            "id": db["next_id"], "parent_id": pid, "name": name, "type": "folder"
        })
        db["next_id"] += 1
        
    elif action == "rename":
        iid = int(data.get("id"))
        name = data.get("name")
        item = next((x for x in db["files"] if x["id"] == iid), None)
        if not item: return {"error": "Not found"}
        
        if check_collision(db, item.get("parent_id", 0), name, exclude_id=iid):
             return {"error": "Name exists"}
        item["name"] = name
        
    elif action == "delete":
        iid = int(data.get("id"))
        delete_recursive(db, iid)
        
    await save_db(db)
    return {"status": "ok"}

@app.post("/api/upload")
async def api_upload(request: Request):
    try:
        data = await request.form()
        token = data.get("token")
        uid = await r.get(f"session:{token}")
        if not uid: return {"error": "Unauthorized"}
        
        uploaded_file = data.get("file")
        if not uploaded_file: return {"error": "No file"}
        
        fname = uploaded_file.filename
        content = await uploaded_file.read()
        fsize = len(content)
        
        doc = BufferedInputFile(content, filename=fname)
        backup = await bot.send_document(CHANNEL_ID, doc, caption=f"Web Upload: {fname}")
        
        fid = backup.document.file_id
        
        db = await get_db()
        pid = int(data.get("parent_id", 0))
        
        # Auto-Rename Logic
        original_name = fname
        counter = 1
        while check_collision(db, pid, fname):
             name, ext = os.path.splitext(original_name)
             fname = f"{name} ({counter}){ext}"
             counter += 1

        db["files"].append({
            "id": db["next_id"], "parent_id": pid, "name": fname, 
            "type": "file", "tg_id": fid, "msg_id": backup.message_id,
            "size": fsize, "date": int(backup.date.timestamp())
        })
        db["next_id"] += 1
        await save_db(db)
        
        return {"status": "ok"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/telegram")
async def webhook(request: Request):
    try:
        data = await request.json()
        update = Update(**data)
        
        # Version Check
        curr_ver = os.environ.get("VERCEL_GIT_COMMIT_SHA")
        if curr_ver:
            last_ver = await r.get("app_version")
            if hasattr(last_ver, 'decode'): last_ver = last_ver.decode('utf-8')
            
            if last_ver != curr_ver:
                await r.set("app_version", curr_ver)
                
                # Notify active user
                uid = None
                if update.message: uid = update.message.from_user.id
                elif update.callback_query: uid = update.callback_query.from_user.id
                
                if uid:
                    try:
                        msg = await bot.send_message(uid, "🚀 **Update Detected!**", disable_notification=True)
                        # Auto-delete notification
                        async def del_later(m):
                            await asyncio.sleep(4)
                            try: await m.delete()
                            except: pass
                        asyncio.create_task(del_later(msg))
                    except: pass

        await dp.feed_update(bot, update)
    except Exception as e:
        print(f"WEBHOOK ERROR: {e}")
    return {"status": "ok"}