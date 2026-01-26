import os
import json
import re
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    Update, BufferedInputFile, InlineKeyboardMarkup, 
    InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ForceReply
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

app = FastAPI()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def get_db():
    structure = {
        "files": [], 
        "next_id": 1, 
        "clipboard": {}, 
        "sessions": {} 
    }
    try:
        chat = await bot.get_chat(CHANNEL_ID)
        if chat.pinned_message and chat.pinned_message.document:
            f = await bot.download(chat.pinned_message.document)
            data = json.load(f)
            for k, v in structure.items():
                if k not in data: data[k] = v
            return data
    except:
        pass
    return structure

async def save_db(db_data):
    json_bytes = json.dumps(db_data).encode('utf-8')
    input_file = BufferedInputFile(json_bytes, filename="system.json")
    msg = await bot.send_document(CHANNEL_ID, input_file, caption="[DB_SYSTEM]")
    await bot.pin_chat_message(CHANNEL_ID, msg.message_id, disable_notification=True)

def get_path_string(db, folder_id):
    if folder_id == 0: return "🏠 /Root"
    path = []
    curr = folder_id
    while curr != 0:
        f = next((x for x in db["files"] if x["id"] == curr), None)
        if not f: break
        path.append(f["name"])
        curr = f.get("parent_id", 0)
    return "🏠 /" + "/".join(reversed(path))

async def render_browser(message, db, folder_id, user_id, edit_mode=False):
    str_uid = str(user_id)
    if db["sessions"].get(str_uid) != folder_id:
        db["sessions"][str_uid] = folder_id
        await save_db(db)

    contents = [f for f in db["files"] if f.get("parent_id", 0) == folder_id]
    contents.sort(key=lambda x: (x["type"] != 'folder', x["name"].lower()))
    
    path_str = get_path_string(db, folder_id)
    kb = []

    if db["clipboard"].get(str_uid):
        op = db["clipboard"][str_uid]['op']
        icon = "✂️" if op == 'move' else "📋"
        kb.append([InlineKeyboardButton(text=f"{icon} Paste Here", callback_data=f"paste_{folder_id}")])

    if folder_id != 0:
        curr = next((f for f in db["files"] if f["id"] == folder_id), None)
        pid = curr["parent_id"] if curr else 0
        kb.append([InlineKeyboardButton(text="🔙 Go Up", callback_data=f"nav_{pid}")])

    for item in contents:
        icon = "📁" if item["type"] == "folder" else "📄"
        cb = f"nav_{item['id']}" if item["type"] == "folder" else f"ctx_{item['id']}"
        kb.append([InlineKeyboardButton(text=f"{icon} {item['name']}", callback_data=cb)])

    kb.append([
        InlineKeyboardButton(text="➕ New Folder", callback_data=f"mkd_{folder_id}"),
        InlineKeyboardButton(text="🔍 Search", callback_data="search_ui")
    ])
    
    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    text = f"📂 **Location:** `{path_str}`\n__Drag & Drop files to upload here.__"
    
    if edit_mode:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    kb = [[KeyboardButton(text="📂 Open Drive"), KeyboardButton(text="❓ Help")]]
    menu = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, persistent=True)
    await message.answer("👻 **Ready.**", reply_markup=menu)
    
    db = await get_db()
    await render_browser(message, db, 0, message.from_user.id)

@dp.message(F.text == "📂 Open Drive")
async def menu_open(message: types.Message):
    db = await get_db()
    await render_browser(message, db, 0, message.from_user.id)

@dp.callback_query(F.data.startswith("mkd_"))
async def ask_new_folder(cal: types.CallbackQuery):
    parent_id = cal.data.split("_")[1]
    await cal.message.answer(
        f"📂 Name for new folder in location #{parent_id}?", 
        reply_markup=ForceReply(input_field_placeholder="Folder Name...")
    )
    await cal.answer()

@dp.message(F.reply_to_message.text.contains("Name for new folder"))
async def create_new_folder(message: types.Message):
    match = re.search(r"#(\d+)", message.reply_to_message.text)
    if not match: return
    parent_id = int(match.group(1))
    folder_name = message.text
    
    db = await get_db()
    db["files"].append({
        "id": db["next_id"],
        "parent_id": parent_id,
        "name": folder_name,
        "type": "folder"
    })
    db["next_id"] += 1
    await save_db(db)
    
    await message.answer(f"✅ Folder `{folder_name}` created.")
    await render_browser(message, db, parent_id, message.from_user.id)

@dp.callback_query(F.data.startswith("ren_ask_"))
async def ask_rename(cal: types.CallbackQuery):
    item_id = cal.data.split("_")[1]
    await cal.message.answer(
        f"✏️ Enter new name for item #{item_id}:",
        reply_markup=ForceReply(input_field_placeholder="New Name...")
    )
    await cal.answer()

@dp.message(F.reply_to_message.text.contains("Enter new name for item"))
async def exec_rename(message: types.Message):
    match = re.search(r"#(\d+)", message.reply_to_message.text)
    if not match: return
    item_id = int(match.group(1))
    new_name = message.text
    
    db = await get_db()
    pid = 0
    for f in db["files"]:
        if f["id"] == item_id:
            f["name"] = new_name
            pid = f.get("parent_id", 0)
            break
            
    await save_db(db)
    await message.answer(f"✅ Renamed to `{new_name}`")
    await render_browser(message, db, pid, message.from_user.id)

@dp.message(F.document | F.photo | F.video | F.audio)
async def handle_upload(message: types.Message):
    status = await message.answer("⏳ Uploading...")
    
    if message.document: fid, fname = message.document.file_id, message.document.file_name or "Doc"
    elif message.photo: fid, fname = message.photo[-1].file_id, "Photo.jpg"
    elif message.video: fid, fname = message.video.file_id, message.video.file_name or "Video.mp4"
    elif message.audio: fid, fname = message.audio.file_id, message.audio.file_name or "Audio"
    else: return
    
    backup = await bot.send_document(CHANNEL_ID, fid, caption=f"File: {fname}")
    
    db = await get_db()
    
    user_id = str(message.from_user.id)
    current_folder = db.get("sessions", {}).get(user_id, 0)
    
    db["files"].append({
        "id": db["next_id"], 
        "parent_id": current_folder, 
        "name": fname, 
        "type": "file", 
        "tg_id": fid, 
        "msg_id": backup.message_id
    })
    db["next_id"] += 1
    await save_db(db)
    
    await status.delete()
    await message.answer(f"✅ `{fname}` saved.")
    
    await render_browser(message, db, current_folder, message.from_user.id)

@dp.callback_query(F.data.startswith("nav_"))
async def nav(c: types.CallbackQuery):
    fid = int(c.data.split("_")[1])
    db = await get_db()
    await render_browser(c.message, db, fid, c.from_user.id, edit_mode=True)
    await c.answer()

@dp.callback_query(F.data.startswith("ctx_"))
async def ctx(c: types.CallbackQuery):
    iid = int(c.data.split("_")[1])
    db = await get_db()
    item = next((x for x in db["files"] if x["id"] == iid), None)
    if not item: return await c.answer("Missing.")
    
    kb = [
        [InlineKeyboardButton(text="⬇️ Download", callback_data=f"dl_{iid}")],
        [InlineKeyboardButton(text="✏️ Rename", callback_data=f"ren_ask_{iid}"),
         InlineKeyboardButton(text="✂️ Move", callback_data=f"mv_{iid}")],
        [InlineKeyboardButton(text="🗑 Delete", callback_data=f"del_{iid}")],
        [InlineKeyboardButton(text="🔙 Back", callback_data=f"nav_{item.get('parent_id',0)}")]
    ]
    await c.message.edit_text(f"📄 `{item['name']}`", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("dl_"))
async def dl(c: types.CallbackQuery):
    iid = int(c.data.split("_")[1])
    db = await get_db()
    item = next((x for x in db["files"] if x["id"] == iid), None)
    if item: await bot.copy_message(c.from_user.id, CHANNEL_ID, item["msg_id"])
    await c.answer()

@dp.callback_query(F.data.startswith("del_"))
async def delete(c: types.CallbackQuery):
    iid = int(c.data.split("_")[1])
    db = await get_db()
    def get_kids(pid):
        kids = [f["id"] for f in db["files"] if f.get("parent_id")==pid]
        for k in kids: kids.extend(get_kids(k))
        return kids
    to_del = [iid] + get_kids(iid)
    db["files"] = [f for f in db["files"] if f["id"] not in to_del]
    await save_db(db)
    await c.answer("Deleted.")
    await render_browser(c.message, db, 0, c.from_user.id, edit_mode=True)

@dp.callback_query(F.data.startswith("mv_"))
async def move_start(c: types.CallbackQuery):
    iid = int(c.data.split("_")[1])
    db = await get_db()
    db["clipboard"][str(c.from_user.id)] = {"op": "move", "id": iid}
    await save_db(db)
    await c.answer("✂️ In Clipboard. Navigate to destination & Paste.")

@dp.callback_query(F.data.startswith("paste_"))
async def paste(c: types.CallbackQuery):
    dest = int(c.data.split("_")[1])
    db = await get_db()
    clip = db["clipboard"].get(str(c.from_user.id))
    if clip:
        for f in db["files"]:
            if f["id"] == clip["id"]:
                f["parent_id"] = dest
                break
        del db["clipboard"][str(c.from_user.id)]
        await save_db(db)
        await c.answer("Moved.")
        await render_browser(c.message, db, dest, c.from_user.id, edit_mode=True)

@dp.callback_query(F.data == "search_ui")
async def search_ask(c: types.CallbackQuery):
    await c.message.answer("🔍 Search query?", reply_markup=ForceReply())
    await c.answer()

@dp.message(F.reply_to_message.text == "🔍 Search query?")
async def search_exec(message: types.Message):
    query = message.text.lower()
    db = await get_db()
    res = [f for f in db["files"] if query in f["name"].lower()][:10]
    kb = []
    for item in res:
        icon = "📁" if item["type"] == "folder" else "📄"
        cb = f"nav_{item['id']}" if item["type"] == "folder" else f"ctx_{item['id']}"
        kb.append([InlineKeyboardButton(text=f"{icon} {item['name']}", callback_data=cb)])
    await message.answer(f"🔍 Results for `{query}`:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@app.post("/api/telegram")
async def webhook(request: Request):
    try:
        await dp.feed_update(bot, Update(**await request.json()))
    except Exception as e:
        print(f"Error: {e}")
    return {"status": "ok"}