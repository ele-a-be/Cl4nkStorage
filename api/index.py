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
        clip = db["clipboard"][str_uid]
        op_icon = "✂️" if clip['op'] == 'move' else "📋"
        kb.append([InlineKeyboardButton(text=f"{op_icon} Paste Item Here", callback_data=f"paste_{folder_id}")])

    if folder_id != 0:
        curr = next((f for f in db["files"] if f["id"] == folder_id), None)
        pid = curr["parent_id"] if curr else 0
        kb.append([InlineKeyboardButton(text="🔙 Go Up", callback_data=f"nav_{pid}")])
    for item in contents:
        icon = "📁" if item["type"] == "folder" else "📄"
        kb.append([InlineKeyboardButton(text=f"{icon} {item['name']}", callback_data=f"ctx_{item['id']}")])
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

@dp.callback_query(F.data.startswith("ctx_"))
async def ctx_menu(c: types.CallbackQuery):
    iid = int(c.data.split("_")[1])
    db = await get_db()
    item = next((x for x in db["files"] if x["id"] == iid), None)
    if not item: return await c.answer("Missing.")
    
    kb = []
    
    if item["type"] == "folder":
        kb.append([InlineKeyboardButton(text="📂 Open Folder", callback_data=f"nav_{iid}")])
    else:
        kb.append([InlineKeyboardButton(text="⬇️ Download", callback_data=f"dl_{iid}")])
    
    kb.append([
        InlineKeyboardButton(text="✏️ Rename", callback_data=f"ren_ask_{iid}"),
        InlineKeyboardButton(text="✂️ Move", callback_data=f"cp_move_{iid}"),
        InlineKeyboardButton(text="📋 Copy", callback_data=f"cp_copy_{iid}")
    ])
    kb.append([InlineKeyboardButton(text="🗑 Delete", callback_data=f"del_{iid}")])
    kb.append([InlineKeyboardButton(text="🔙 Cancel", callback_data=f"nav_{item.get('parent_id',0)}")])
    
    icon = "📁" if item["type"] == "folder" else "📄"
    await c.message.edit_text(f"{icon} **{item['name']}**\nSelect action:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("mkd_"))
async def ask_new_folder(cal: types.CallbackQuery):
    pid = cal.data.split("_")[1]
    await cal.message.answer(f"📂 Name for new folder in location #{pid}?", reply_markup=ForceReply())
    await cal.answer()

@dp.message(F.reply_to_message.text.contains("Name for new folder"))
async def create_new_folder(message: types.Message):
    match = re.search(r"#(\d+)", message.reply_to_message.text)
    if not match: return
    pid, name = int(match.group(1)), message.text
    db = await get_db()
    db["files"].append({"id": db["next_id"], "parent_id": pid, "name": name, "type": "folder"})
    db["next_id"] += 1
    await save_db(db)
    await message.answer(f"✅ Created `{name}`")
    await render_browser(message, db, pid, message.from_user.id)

@dp.callback_query(F.data.startswith("ren_ask_"))
async def ask_rename(cal: types.CallbackQuery):
    iid = cal.data.split("_")[1]
    await cal.message.answer(f"✏️ New name for item #{iid}:", reply_markup=ForceReply())
    await cal.answer()

@dp.message(F.reply_to_message.text.contains("New name for item"))
async def exec_rename(message: types.Message):
    match = re.search(r"#(\d+)", message.reply_to_message.text)
    if not match: return
    iid, new_name = int(match.group(1)), message.text
    db = await get_db()
    pid = 0
    for f in db["files"]:
        if f["id"] == iid:
            f["name"] = new_name
            pid = f.get("parent_id", 0)
            break
    await save_db(db)
    await message.answer(f"✅ Renamed.")
    await render_browser(message, db, pid, message.from_user.id)

@dp.callback_query(F.data.startswith("cp_"))
async def clipboard_action(c: types.CallbackQuery):
    _, op, iid = c.data.split("_")
    iid = int(iid)
    db = await get_db()
    
    db["clipboard"][str(c.from_user.id)] = {"op": op, "id": iid}
    await save_db(db)
    
    op_text = "Move" if op == "move" else "Copy"
    await c.answer(f"{op_text} started. Navigate to destination -> Paste.")
    
    item = next((x for x in db["files"] if x["id"] == iid), None)
    await render_browser(c.message, db, item["parent_id"], c.from_user.id, edit_mode=True)

@dp.callback_query(F.data.startswith("paste_"))
async def paste_action(c: types.CallbackQuery):
    dest_id = int(c.data.split("_")[1])
    db = await get_db()
    uid = str(c.from_user.id)
    clip = db["clipboard"].get(uid)
    
    if not clip: return await c.answer("Clipboard empty.")
    
    src_item = next((x for x in db["files"] if x["id"] == clip["id"]), None)
    if not src_item: return await c.answer("Item gone.")

    if clip["op"] == "move":
        src_item["parent_id"] = dest_id
        msg_text = "Moved."
    
    elif clip["op"] == "copy":
        def recursive_copy(item, new_parent):
            new_entry = item.copy()
            new_entry["id"] = db["next_id"]
            new_entry["parent_id"] = new_parent
            db["files"].append(new_entry)
            db["next_id"] += 1
            
            if item["type"] == "folder":
                children = [x for x in db["files"] if x.get("parent_id") == item["id"] and x["id"] != new_entry["id"]]
                for child in children:
                    recursive_copy(child, new_entry["id"])

        recursive_copy(src_item, dest_id)
        msg_text = "Copied."

    del db["clipboard"][uid]
    await save_db(db)
    await c.answer(msg_text)
    await render_browser(c.message, db, dest_id, c.from_user.id, edit_mode=True)

@dp.callback_query(F.data.startswith("del_"))
async def delete_item(c: types.CallbackQuery):
    iid = int(c.data.split("_")[1])
    db = await get_db()
    
    def get_all_descendants(pid):
        kids = [f["id"] for f in db["files"] if f.get("parent_id")==pid]
        for k in kids: kids.extend(get_all_descendants(k))
        return kids
    
    to_kill = [iid] + get_all_descendants(iid)
    item = next((x for x in db["files"] if x["id"] == iid), None)
    pid = item["parent_id"] if item else 0
    
    db["files"] = [f for f in db["files"] if f["id"] not in to_kill]
    await save_db(db)
    await c.answer("Deleted.")
    await render_browser(c.message, db, pid, c.from_user.id, edit_mode=True)

@dp.callback_query(F.data.startswith("dl_"))
async def dl(c: types.CallbackQuery):
    iid = int(c.data.split("_")[1])
    db = await get_db()
    item = next((x for x in db["files"] if x["id"] == iid), None)
    if item: await bot.copy_message(c.from_user.id, CHANNEL_ID, item["msg_id"])
    await c.answer()

@dp.callback_query(F.data.startswith("nav_"))
async def nav(c: types.CallbackQuery):
    fid = int(c.data.split("_")[1])
    db = await get_db()
    await render_browser(c.message, db, fid, c.from_user.id, edit_mode=True)
    await c.answer()

@dp.message(F.document | F.photo | F.video)
async def handle_upload(message: types.Message):
    status = await message.answer("⏳ Uploading...")
    if message.document: fid, fname = message.document.file_id, message.document.file_name or "Doc"
    elif message.photo: fid, fname = message.photo[-1].file_id, "Photo.jpg"
    elif message.video: fid, fname = message.video.file_id, message.video.file_name or "Video.mp4"
    else: return
    
    backup = await bot.send_document(CHANNEL_ID, fid, caption=f"File: {fname}")
    db = await get_db()
    uid = str(message.from_user.id)
    curr = db.get("sessions", {}).get(uid, 0)
    
    db["files"].append({
        "id": db["next_id"], "parent_id": curr, "name": fname, 
        "type": "file", "tg_id": fid, "msg_id": backup.message_id
    })
    db["next_id"] += 1
    await save_db(db)
    await status.delete()
    await message.answer(f"✅ `{fname}` saved.")
    await render_browser(message, db, curr, message.from_user.id)

@dp.callback_query(F.data == "search_ui")
async def search_ask(c: types.CallbackQuery):
    await c.message.answer("🔍 Search query?", reply_markup=ForceReply())
    await c.answer()

@dp.message(F.reply_to_message.text == "🔍 Search query?")
async def search_exec(message: types.Message):
    q = message.text.lower()
    db = await get_db()
    res = [f for f in db["files"] if q in f["name"].lower()][:10]
    kb = []
    for item in res:
        icon = "📁" if item["type"] == "folder" else "📄"
        kb.append([InlineKeyboardButton(text=f"{icon} {item['name']}", callback_data=f"ctx_{item['id']}")])
    await message.answer(f"🔍 Results for `{q}`:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@app.post("/api/telegram")
async def webhook(request: Request):
    try: await dp.feed_update(bot, Update(**await request.json()))
    except: pass
    return {"status": "ok"}