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

async def delete_previous_dashboard(user_id, db):
    last_msg_id = db["ui_state"].get(str(user_id))
    if last_msg_id:
        try:
            await bot.delete_message(chat_id=user_id, message_id=last_msg_id)
        except:
            pass 

async def webhook(request: Request):
    try: 
        await dp.feed_update(bot, Update(**await request.json()))
    except Exception as e:
        print(f"WEBHOOK ERROR: {e}")
    return {"status": "ok"}

async def delete_user_message(message: types.Message):
    try:
        await message.delete()
    except:
        pass

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

async def render_browser(user_id, db, folder_id, message_to_edit=None):
    str_uid = str(user_id)
    if db["sessions"].get(str_uid) != folder_id:
        db["sessions"][str_uid] = folder_id
        await save_db(db)

    contents = [f for f in db["files"] if f.get("parent_id", 0) == folder_id]
    contents = [f for f in db["files"] if f.get("parent_id", 0) == folder_id]
    
    # Sorting
    pref = db["sort_prefs"].get(str_uid, {'field': 'name', 'order': 'asc'})
    field = pref['field']
    reverse = (pref['order'] == 'desc')
    
    def sort_key(x):
        if field == 'name': return x["name"].lower()
        if field == 'date': return x.get("date", 0)
        if field == 'size': return x.get("size", 0)
        if field == 'type': return x["type"]
        return x["name"].lower()
    
    contents.sort(key=lambda x: (x["type"] != 'folder', sort_key(x)), reverse=reverse if field != 'name' else False)

    folders = [x for x in contents if x["type"] == "folder"]
    files = [x for x in contents if x["type"] != "file"] # wait, type is 'file' or 'folder'
    # Actually just re-filter
    folders = [x for x in contents if x["type"] == "folder"]
    files_only = [x for x in contents if x["type"] == "file"]
    
    folders.sort(key=sort_key, reverse=reverse)
    files_only.sort(key=sort_key, reverse=reverse)
    
    contents = folders + files_only
    
    path_str = get_path_string(db, folder_id)
    kb = []

    if db["clipboard"].get(str_uid):
        clip = db["clipboard"][str_uid]
        op_icon = "✂️" if clip['op'] == 'move' else "📋"
        kb.append([InlineKeyboardButton(text=f"{op_icon} Paste Here", callback_data=f"paste_{folder_id}")])

    if folder_id != 0:
        curr = next((f for f in db["files"] if f["id"] == folder_id), None)
        pid = curr["parent_id"] if curr else 0
        kb.append([InlineKeyboardButton(text="🔙 Go Up", callback_data=f"nav_{pid}")])

    for item in contents:
        icon = "📁" if item["type"] == "folder" else "📄"
        cb = f"ctx_{item['id']}"
        kb.append([InlineKeyboardButton(text=f"{icon} {item['name']}", callback_data=cb)])

    kb.append([
        InlineKeyboardButton(text="➕ New Folder", callback_data=f"mkd_{folder_id}"),
        InlineKeyboardButton(text="🔍 Search", callback_data="search_ui"),
        InlineKeyboardButton(text="🔃 Sort", callback_data="sort_ui")
    ])
    
    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    text = f"📂 **Location:** `{path_str}`\n__Drag & Drop files to upload here.__"
    
    if message_to_edit:
        try:
            await message_to_edit.edit_text(text, reply_markup=markup)
        except Exception:
            pass
    else:
        await delete_previous_dashboard(user_id, db)
        new_msg = await bot.send_message(user_id, text, reply_markup=markup)
        db["ui_state"][str_uid] = new_msg.message_id
        await save_db(db)

def get_main_menu():
    kb = [[KeyboardButton(text="📂 Open Drive"), KeyboardButton(text="❓ Help")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, persistent=True)

async def restore_menu(message: types.Message):
    try:
        tmp = await message.answer("..", reply_markup=get_main_menu())
        await tmp.delete()
    except: pass

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await delete_user_message(message)
    tmp = await message.answer("👻 Starting...", reply_markup=get_main_menu())
    await asyncio.sleep(0.5)
    await tmp.delete()

    db = await get_db()
    await render_browser(message.from_user.id, db, 0)

@dp.message(F.text == "📂 Open Drive")
async def menu_open(message: types.Message):
    await delete_user_message(message)
    db = await get_db()
    await render_browser(message.from_user.id, db, 0)

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
    msg = await cal.message.answer(
        f"📂 Name for new folder in location #{pid}?", 
        reply_markup=ForceReply()
    )
    await cal.answer()

@dp.message(F.reply_to_message.text.contains("Name for new folder"))
async def create_new_folder(message: types.Message):
    await delete_user_message(message)
    await restore_menu(message)
    try: await bot.delete_message(message.chat.id, message.reply_to_message.message_id)
    except: pass

    try:
        match = re.search(r"#(\d+)", message.reply_to_message.text)
        if not match: 
            return await message.answer("❌ Error: Could not determine parent folder.")
        
        pid, name = int(match.group(1)), message.text.strip()
        if not name:
             return await message.answer("❌ Error: Folder name cannot be empty.")

        db = await get_db()
        
        if check_collision(db, pid, name):
            return await message.answer("❌ Error: A folder/file with that name already exists.")
            
        db["files"].append({"id": db["next_id"], "parent_id": pid, "name": name, "type": "folder"})
        db["next_id"] += 1
        await save_db(db)
        
        await render_browser(message.from_user.id, db, pid)
    except Exception as e:
        await message.answer(f"❌ System Error: {str(e)}")

@dp.callback_query(F.data.startswith("ren_ask_"))
async def ask_rename(cal: types.CallbackQuery):
    print(f"DEBUG: ask_rename triggered for {cal.data}")
    iid = cal.data.split("_")[2]
    await cal.message.answer(f"✏️ New name for item #{iid}:", reply_markup=ForceReply())
    await cal.answer()

@dp.message(F.reply_to_message.text.contains("New name for item"))
async def exec_rename(message: types.Message):
    await delete_user_message(message)
    await restore_menu(message)
    try: await bot.delete_message(message.chat.id, message.reply_to_message.message_id)
    except: pass

    try:
        match = re.search(r"#(\d+)", message.reply_to_message.text)
        if not match: 
            return await message.answer(f"❌ Error: Could not parse item ID from message.\nContent: '{message.reply_to_message.text}'")
            
        iid, new_name = int(match.group(1)), message.text.strip()
        if not new_name:
             return await message.answer("❌ Error: Name cannot be empty.")

        db = await get_db()
        target = next((f for f in db["files"] if f["id"] == iid), None)
        
        if target:
            # Check Collision
            pid = target.get("parent_id", 0)
            if check_collision(db, pid, new_name, exclude_id=iid):
                return await message.answer(f"❌ Error: A file named '{new_name}' already exists in this folder.")

            target["name"] = new_name
            if await save_db(db):
                await render_browser(message.from_user.id, db, pid)
            else:
                await message.answer("⚠️ Warning: Database save failed (Rate Limit?). Changes might not persist.")
        else:
            await message.answer("❌ Error: Item not found/missing.")

    except Exception as e:
        await message.answer(f"❌ System Error: {str(e)}")

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
    
    status = await message.answer("⏳ Processing...")
    
    db = await get_db()
    uid = str(message.from_user.id)
    curr = db.get("sessions", {}).get(uid, 0)
    
    collision = check_collision(db, curr, fname)
    if collision:
        # Save pending state
        db["pending_ops"][uid] = {
            "type": "upload",
            "data": {"fid": fid, "fname": fname, "pid": curr, "size": fsize, "date": int(message.date.timestamp())}
        }
        await save_db(db)
        
        await message.answer(
            f"⚠️ File **{fname}** already exists.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔁 Overwrite", callback_data="col_over")],
                [InlineKeyboardButton(text="✏️ Rename New", callback_data="col_ren")],
                [InlineKeyboardButton(text="❌ Cancel", callback_data="col_cancel")]
            ])
        )
        await delete_user_message(message)
        await status.delete()
        return

    # No collision, proceed normally
    backup = await bot.send_document(CHANNEL_ID, fid, caption=f"File: {fname}")
    db["files"].append({
        "id": db["next_id"], "parent_id": curr, "name": fname, 
        "type": "file", "tg_id": fid, "msg_id": backup.message_id,
        "size": fsize, "date": int(message.date.timestamp())
    })
    db["next_id"] += 1
    await save_db(db)

    await delete_user_message(message) 
    await status.delete()              
    
    await render_browser(message.from_user.id, db, curr)

@dp.callback_query(F.data.startswith("col_"))
async def resolve_col(c: types.CallbackQuery):
    action = c.data.split("_")[1]
    db = await get_db()
    uid = str(c.from_user.id)
    pending = db["pending_ops"].get(uid)
    
    if not pending: 
        return await c.answer("Expired or invalid.")
    
    if action == "cancel":
        del db["pending_ops"][uid]
        await save_db(db)
        await c.message.delete()
        return await c.answer("Cancelled.")

    # Helper for paste/move logic
    def recursive_copy(item, new_parent, rename_to=None):
        new_entry = item.copy()
        new_entry["id"] = db["next_id"]
        new_entry["parent_id"] = new_parent
        if rename_to: new_entry["name"] = rename_to
        db["files"].append(new_entry)
        db["next_id"] += 1
        if item["type"] == "folder":
            children = [x for x in db["files"] if x.get("parent_id") == item["id"] and x["id"] != new_entry["id"]]
            for child in children: recursive_copy(child, new_entry["id"])

    if pending["type"] == "paste":
        pdata = pending["data"]
        src = next((x for x in db["files"] if x["id"] == pdata["src_id"]), None)
        if not src: return await c.answer("Source item missing.")

        if action == "over":
            ex_id = src["id"] if pdata["clip"]["op"] == "move" else None
            target = check_collision(db, pdata["dest_id"], src["name"], exclude_id=ex_id)
            if target:
                db["files"] = [f for f in db["files"] if f["id"] != target["id"]]
            
            if pdata["clip"]["op"] == "move":
                src["parent_id"] = pdata["dest_id"]
            else:
                recursive_copy(src, pdata["dest_id"])
            
        elif action == "ren":
             await c.message.delete()
             await c.message.answer(f"✏️ Enter new name for **{src['name']}**:", reply_markup=ForceReply())
             pending["type"] = "paste_rename"
             await save_db(db)
             return await c.answer()

        del db["pending_ops"][uid]
        if uid in db["clipboard"]: del db["clipboard"][uid] # Clear clipboard on success
        await save_db(db)
        await c.message.delete()
        await render_browser(c.from_user.id, db, pdata["dest_id"])

    elif pending["type"] == "upload":
        pdata = pending["data"]
        
        if action == "over":
            target = check_collision(db, pdata["pid"], pdata["fname"])
            if target:
                db["files"] = [f for f in db["files"] if f["id"] != target["id"]]
            
            backup = await bot.send_document(CHANNEL_ID, pdata["fid"], caption=f"File: {pdata['fname']}")
            db["files"].append({
                "id": db["next_id"], "parent_id": pdata["pid"], "name": pdata["fname"], 
                "type": "file", "tg_id": pdata["fid"], "msg_id": backup.message_id
            })
            db["next_id"] += 1
            
            del db["pending_ops"][uid]
            await save_db(db)
            await c.message.delete()
            await render_browser(c.from_user.id, db, pdata["pid"])
            
        elif action == "ren":
            await c.message.delete()
            await c.message.answer(f"✏️ Enter new name for **{pdata['fname']}**:", reply_markup=ForceReply())
            pending["type"] = "upload_rename"
            await save_db(db)
            return await c.answer()

@dp.message(F.reply_to_message.text.contains("Enter new name for"))
async def resolve_rename_input(message: types.Message):
    await delete_user_message(message)
    await restore_menu(message)
    try: await bot.delete_message(message.chat.id, message.reply_to_message.message_id)
    except: pass
    
    new_name = message.text.strip()
    if not new_name: return await message.answer("Invalid name.")

    db = await get_db()
    uid = str(message.from_user.id)
    pending = db["pending_ops"].get(uid)
    
    if not pending: return
    
    # Helper for paste/move logic (duplicated because scope)
    def recursive_copy(item, new_parent, rename_to=None):
        new_entry = item.copy()
        new_entry["id"] = db["next_id"]
        new_entry["parent_id"] = new_parent
        if rename_to: new_entry["name"] = rename_to
        db["files"].append(new_entry)
        db["next_id"] += 1
        if item["type"] == "folder":
            children = [x for x in db["files"] if x.get("parent_id") == item["id"] and x["id"] != new_entry["id"]]
            for child in children: recursive_copy(child, new_entry["id"])

    if pending["type"] == "upload_rename":
        pdata = pending["data"]
        if check_collision(db, pdata["pid"], new_name):
            return await message.answer("❌ That name is also taken! Try again.")
            
        backup = await bot.send_document(CHANNEL_ID, pdata["fid"], caption=f"File: {new_name}")
        db["files"].append({
            "id": db["next_id"], "parent_id": pdata["pid"], "name": new_name, 
            "type": "file", "tg_id": pdata["fid"], "msg_id": backup.message_id
        })
        db["next_id"] += 1
        await render_browser(message.from_user.id, db, pdata["pid"])

    elif pending["type"] == "paste_rename":
        pdata = pending["data"]
        src = next((x for x in db["files"] if x["id"] == pdata["src_id"]), None)
        if not src: return await message.answer("Source item missing.")
        
        if check_collision(db, pdata["dest_id"], new_name, exclude_id=src["id"]):
            return await message.answer("❌ That name is also taken! Try again.")
            
        if pdata["clip"]["op"] == "move":
             src["name"] = new_name
             src["parent_id"] = pdata["dest_id"]
        else:
             recursive_copy(src, pdata["dest_id"], rename_to=new_name)
             
        if uid in db["clipboard"]: del db["clipboard"][uid]
        await render_browser(message.from_user.id, db, pdata["dest_id"])

    del db["pending_ops"][uid]
    await save_db(db)

@dp.callback_query(F.data.startswith("cp_"))
async def clipboard_action(c: types.CallbackQuery):
    _, op, iid = c.data.split("_")
    db = await get_db()
    db["clipboard"][str(c.from_user.id)] = {"op": op, "id": int(iid)}
    await save_db(db)
    
    await c.answer(f"Added to clipboard ({op})")
    
    item = next((x for x in db["files"] if x["id"] == int(iid)), None)
    await render_browser(c.from_user.id, db, item["parent_id"], message_to_edit=c.message)

@dp.callback_query(F.data.startswith("paste_"))
async def paste_action(c: types.CallbackQuery):
    dest_id = int(c.data.split("_")[1])
    db = await get_db()
    uid = str(c.from_user.id)
    clip = db["clipboard"].get(uid)
    
    if not clip: return await c.answer("Empty.")
    
    src = next((x for x in db["files"] if x["id"] == clip["id"]), None)
    if not src: return await c.answer("Item gone.")

    # Check Collision
    # Only exclude self if MOVING. If COPYING, self IS the collision in the same folder.
    ex_id = src["id"] if clip["op"] == "move" else None
    collision = check_collision(db, dest_id, src["name"], exclude_id=ex_id)
    if collision:
        # Save pending state for paste
        db["pending_ops"][uid] = {
            "type": "paste",
            "data": {"dest_id": dest_id, "clip": clip, "src_id": src["id"]}
        }
        await save_db(db)
        
        await c.message.edit_text(
            f"⚠️ **{src['name']}** exists in destination.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔁 Overwrite", callback_data="col_over")],
                [InlineKeyboardButton(text="✏️ Rename", callback_data="col_ren")],
                [InlineKeyboardButton(text="❌ Cancel", callback_data="col_cancel")]
            ])
        )
        return

    # No collision, execute
    if clip["op"] == "move":
        src["parent_id"] = dest_id
    elif clip["op"] == "copy":
        def recursive_copy(item, new_parent, rename_to=None):
            new_entry = item.copy()
            new_entry["id"] = db["next_id"]
            new_entry["parent_id"] = new_parent
            if rename_to: new_entry["name"] = rename_to
            db["files"].append(new_entry)
            db["next_id"] += 1
            if item["type"] == "folder":
                children = [x for x in db["files"] if x.get("parent_id") == item["id"] and x["id"] != new_entry["id"]]
                for child in children: recursive_copy(child, new_entry["id"])
        recursive_copy(src, dest_id)

    del db["clipboard"][uid]
    await save_db(db)
    await c.answer("Done.")
    await render_browser(c.from_user.id, db, dest_id, message_to_edit=c.message)

@dp.callback_query(F.data.startswith("del_"))
async def delete_item(c: types.CallbackQuery):
    iid = int(c.data.split("_")[1])
    db = await get_db()
    
    def get_descendants(pid):
        kids = [f["id"] for f in db["files"] if f.get("parent_id")==pid]
        for k in kids: kids.extend(get_descendants(k))
        return kids
    
    to_kill = [iid] + get_descendants(iid)
    item = next((x for x in db["files"] if x["id"] == iid), None)
    pid = item["parent_id"] if item else 0
    
    db["files"] = [f for f in db["files"] if f["id"] not in to_kill]
    await save_db(db)
    await c.answer("Deleted.")
    await render_browser(c.from_user.id, db, pid, message_to_edit=c.message)

@dp.callback_query(F.data.startswith("nav_"))
async def nav(c: types.CallbackQuery):
    fid = int(c.data.split("_")[1])
    db = await get_db()
    await render_browser(c.from_user.id, db, fid, message_to_edit=c.message)
    await c.answer()

@dp.callback_query(F.data.startswith("dl_"))
async def dl(c: types.CallbackQuery):
    iid = int(c.data.split("_")[1])
    db = await get_db()
    item = next((x for x in db["files"] if x["id"] == iid), None)
    if item: await bot.copy_message(c.from_user.id, CHANNEL_ID, item["msg_id"])
    await c.answer()

@dp.callback_query(F.data == "search_ui")
async def search_ask(c: types.CallbackQuery):
    msg = await c.message.answer("🔍 Query?", reply_markup=ForceReply())
    await c.answer()

@dp.message(F.reply_to_message.text == "🔍 Query?")
async def search_exec(message: types.Message):
    await delete_user_message(message)
    await restore_menu(message)
    try: await bot.delete_message(message.chat.id, message.reply_to_message.message_id)
    except: pass

    q = message.text.lower()
    db = await get_db()
    res = [f for f in db["files"] if q in f["name"].lower()][:10]
    kb = []
    for item in res:
        icon = "📁" if item["type"] == "folder" else "📄"
        kb.append([InlineKeyboardButton(text=f"{icon} {item['name']}", callback_data=f"ctx_{item['id']}")])
    
    kb.append([InlineKeyboardButton(text="❌ Close Results", callback_data="close_search")])
    await message.answer(f"🔍 Results for `{q}`:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "sort_ui")
async def sort_ui(c: types.CallbackQuery):
    db = await get_db()
    uid = str(c.from_user.id)
    pref = db["sort_prefs"].get(uid, {'field': 'name', 'order': 'asc'})
    
    text = f"🔃 **Sort Options**\nCurrent: **{pref['field'].title()}** ({pref['order'].upper()})"
    
    kb = [
        [
            InlineKeyboardButton(text="🔤 Name", callback_data="sort_set_name"),
            InlineKeyboardButton(text="📅 Date", callback_data="sort_set_date"),
        ],
        [
            InlineKeyboardButton(text="⚖️ Size", callback_data="sort_set_size"),
            InlineKeyboardButton(text="📑 Type", callback_data="sort_set_type"),
        ],
        [
            InlineKeyboardButton(text="⬆️ Asc", callback_data="sort_set_asc"),
            InlineKeyboardButton(text="⬇️ Desc", callback_data="sort_set_desc"),
        ],
        [InlineKeyboardButton(text="🔙 Back", callback_data=f"nav_{db['sessions'].get(uid, 0)}")]
    ]
    await c.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await c.answer()

@dp.callback_query(F.data.startswith("sort_set_"))
async def sort_set(c: types.CallbackQuery):
    action = c.data.split("_")[2] # name, date, size, type, asc, desc
    db = await get_db()
    uid = str(c.from_user.id)
    
    if uid not in db["sort_prefs"]: db["sort_prefs"][uid] = {'field': 'name', 'order': 'asc'}
    pref = db["sort_prefs"][uid]
    
    if action in ['asc', 'desc']:
        pref['order'] = action
    else:
        pref['field'] = action
        
    await save_db(db)
    await sort_ui(c) 

@dp.callback_query(F.data == "close_search")
async def close_search(c: types.CallbackQuery):
    await c.message.delete()

@app.post("/api/telegram")
async def webhook(request: Request):
    try: 
        # Version Check
        curr_ver = os.environ.get("VERCEL_GIT_COMMIT_SHA")
        if curr_ver:
            last_ver = await r.get("app_version")
            if hasattr(last_ver, 'decode'): last_ver = last_ver.decode('utf-8')
            
            if last_ver != curr_ver:
                await r.set("app_version", curr_ver)
                db = await get_db()
                for uid in db["sessions"]:
                    try:
                         await bot.send_message(uid, "🚀 **Update Detected!** Refreshing...", disable_notification=True)
                         await render_browser(uid, db, db["sessions"][uid])
                    except: pass

        await dp.feed_update(bot, Update(**await request.json()))
    except Exception as e:
        print(f"WEBHOOK ERROR: {e}")
    return {"status": "ok"}