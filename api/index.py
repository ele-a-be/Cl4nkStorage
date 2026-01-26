import os
import json
import time
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    Update, BufferedInputFile, InlineKeyboardMarkup, 
    InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

app = FastAPI()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def get_db():
    """Fetch DB. If empty, return strict schema."""
    structure = {
        "files": [],
        "next_id": 1,
        "clipboard": {}
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
    contents = [f for f in db["files"] if f.get("parent_id", 0) == folder_id]
    
    contents.sort(key=lambda x: (x["type"] != 'folder', x["name"].lower()))
    
    path_str = get_path_string(db, folder_id)
    kb = []

    user_clip = db["clipboard"].get(str(user_id))
    if user_clip:
        op_icon = "✂️" if user_clip['op'] == 'move' else "📋"
        kb.append([InlineKeyboardButton(text=f"{op_icon} Paste Here", callback_data=f"paste_{folder_id}")])
    if folder_id != 0:
        curr_folder = next((f for f in db["files"] if f["id"] == folder_id), None)
        parent = curr_folder["parent_id"] if curr_folder else 0
        kb.append([InlineKeyboardButton(text="🔙 Go Up", callback_data=f"nav_{parent}")])

    for item in contents:
        icon = "📁" if item["type"] == "folder" else "📄"
        cb = f"nav_{item['id']}" if item["type"] == "folder" else f"ctx_{item['id']}"
        kb.append([InlineKeyboardButton(text=f"{icon} {item['name']}", callback_data=cb)])
    tools = [
        InlineKeyboardButton(text="➕ New Folder", callback_data=f"mkd_{folder_id}"),
        InlineKeyboardButton(text="🔍 Search", callback_data="search_ui")
    ]
    kb.append(tools)
    
    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    text = f"📂 **Location:** `{path_str}`\nItems: {len(contents)}"
    
    if edit_mode:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("👋 **Welcome to Ghost Explorer.**\nLoading Root...")
    db = await get_db()
    await render_browser(message, db, 0, message.from_user.id)

@dp.message(F.document | F.photo | F.video | F.audio)
async def handle_upload(message: types.Message):
    status = await message.answer("⏳ Uploading...")
    
    if message.document:
        fid, fname = message.document.file_id, message.document.file_name or "Doc"
    elif message.photo:
        fid, fname = message.photo[-1].file_id, "Photo.jpg"
    elif message.video:
        fid, fname = message.video.file_id, message.video.file_name or "Video.mp4"
    else:
        return

    backup = await bot.send_document(CHANNEL_ID, fid, caption=f"File: {fname}")
    
    db = await get_db()
    new_file = {
        "id": db["next_id"],
        "parent_id": 0,
        "name": fname,
        "type": "file",
        "tg_id": fid,
        "msg_id": backup.message_id
    }
    db["files"].append(new_file)
    db["next_id"] += 1
    await save_db(db)
    
    await status.delete()
    await message.answer(f"✅ **{fname}** uploaded to Root.")
    await render_browser(message, db, 0, message.from_user.id)

@dp.callback_query(F.data.startswith("nav_"))
async def nav_folder(cal: types.CallbackQuery):
    folder_id = int(cal.data.split("_")[1])
    db = await get_db()
    await render_browser(cal.message, db, folder_id, cal.from_user.id, edit_mode=True)
    await cal.answer()

@dp.callback_query(F.data.startswith("ctx_"))
async def file_context(cal: types.CallbackQuery):
    item_id = int(cal.data.split("_")[1])
    db = await get_db()
    item = next((x for x in db["files"] if x["id"] == item_id), None)
    
    if not item: return await cal.answer("Item not found.", show_alert=True)
    
    kb = [
        [InlineKeyboardButton(text="⬇️ Download", callback_data=f"dl_{item_id}")],
        [
            InlineKeyboardButton(text="✏️ Rename", callback_data=f"ren_ask_{item_id}"),
            InlineKeyboardButton(text="✂️ Move", callback_data=f"mv_start_{item_id}")
        ],
        [InlineKeyboardButton(text="🗑 Delete", callback_data=f"del_{item_id}")],
        [InlineKeyboardButton(text="🔙 Back", callback_data=f"nav_{item.get('parent_id', 0)}")]
    ]
    
    await cal.message.edit_text(
        f"📄 **File:** `{item['name']}`\nSelect action:", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )

@dp.callback_query(F.data.startswith("dl_"))
async def action_download(cal: types.CallbackQuery):
    item_id = int(cal.data.split("_")[1])
    db = await get_db()
    item = next((x for x in db["files"] if x["id"] == item_id), None)
    
    if item:
        await bot.copy_message(cal.from_user.id, CHANNEL_ID, item["msg_id"], caption=item["name"])
        await cal.answer()
    else:
        await cal.answer("Error.", show_alert=True)

@dp.callback_query(F.data.startswith("del_"))
async def action_delete(cal: types.CallbackQuery):
    item_id = int(cal.data.split("_")[1])
    db = await get_db()
    
    def get_all_children(pid):
        kids = [f["id"] for f in db["files"] if f.get("parent_id") == pid]
        for k in kids: kids.extend(get_all_children(k))
        return kids

    to_delete = [item_id] + get_all_children(item_id)
    
    original_len = len(db["files"])
    db["files"] = [f for f in db["files"] if f["id"] not in to_delete]
    
    if len(db["files"]) < original_len:
        await save_db(db)
        await cal.answer("🗑 Deleted.")
        await render_browser(cal.message, db, 0, cal.from_user.id, edit_mode=True)
    else:
        await cal.answer("Delete failed.")

@dp.callback_query(F.data.startswith("mkd_"))
async def action_mkdir_start(cal: types.CallbackQuery):
    parent = cal.data.split("_")[1]
    await cal.message.answer(f"📂 Send me the name for the new folder.\n\nReply with: `/mkdir {parent} Name`")
    await cal.answer()

@dp.message(Command("mkdir"))
async def action_mkdir_exec(message: types.Message, command: CommandObject):
    args = command.args.split(" ", 1)
    if len(args) < 2: return await message.answer("Usage: `/mkdir <id> <name>`")
    
    pid, name = int(args[0]), args[1]
    db = await get_db()
    
    db["files"].append({
        "id": db["next_id"],
        "parent_id": pid,
        "name": name,
        "type": "folder"
    })
    db["next_id"] += 1
    await save_db(db)
    
    await message.answer(f"✅ Created folder `{name}`")
    await render_browser(message, db, pid, message.from_user.id)

@dp.callback_query(F.data.startswith("mv_start_"))
async def action_move_start(cal: types.CallbackQuery):
    item_id = int(cal.data.split("_")[1])
    db = await get_db()
    
    db["clipboard"][str(cal.from_user.id)] = {"op": "move", "id": item_id}
    await save_db(db)
    
    await cal.answer("✂️ Item in Clipboard. Go to destination and click Paste.")
    item = next((x for x in db["files"] if x["id"] == item_id), None)
    await render_browser(cal.message, db, item["parent_id"], cal.from_user.id, edit_mode=True)

@dp.callback_query(F.data.startswith("paste_"))
async def action_paste(cal: types.CallbackQuery):
    dest_id = int(cal.data.split("_")[1])
    db = await get_db()
    clip = db["clipboard"].get(str(cal.from_user.id))
    
    if not clip: return await cal.answer("Clipboard empty.")
    
    item_idx = next((i for i, x in enumerate(db["files"]) if x["id"] == clip["id"]), None)
    
    if item_idx is not None:
        if clip["op"] == "move":
            db["files"][item_idx]["parent_id"] = dest_id
            del db["clipboard"][str(cal.from_user.id)]
            await save_db(db)
            await cal.answer("✅ Moved.")
            await render_browser(cal.message, db, dest_id, cal.from_user.id, edit_mode=True)
    else:
        await cal.answer("Item gone.")

@dp.callback_query(F.data == "search_ui")
async def action_search_ui(cal: types.CallbackQuery):
    await cal.message.answer("🔍 Type `/search name` or `/filter pdf`")
    await cal.answer()

@dp.message(Command("search"))
async def cmd_search(message: types.Message, command: CommandObject):
    if not command.args: return
    query = command.args.lower()
    db = await get_db()
    
    results = [f for f in db["files"] if query in f["name"].lower()]
    
    kb = []
    for item in results[:10]:
        icon = "📁" if item["type"] == "folder" else "📄"
        cb = f"nav_{item['id']}" if item["type"] == "folder" else f"ctx_{item['id']}"
        kb.append([InlineKeyboardButton(text=f"{icon} {item['name']}", callback_data=cb)])
        
    await message.answer(f"🔍 Results for `{query}`:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.message(Command("filter"))
async def cmd_filter(message: types.Message, command: CommandObject):
    if not command.args: return
    ext = command.args.lower()
    db = await get_db()
    
    results = [f for f in db["files"] if f["name"].lower().endswith(ext)]
    
    kb = []
    for item in results[:10]:
        kb.append([InlineKeyboardButton(text=f"📄 {item['name']}", callback_data=f"ctx_{item['id']}")])
        
    await message.answer(f"🔍 Filter `.{ext}`:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@app.post("/api/telegram")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = Update(**data)
        await dp.feed_update(bot, update)
    except Exception as e:
        print(f"Error: {e}")
    return {"status": "ok"}