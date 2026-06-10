# -*- coding: utf-8 -*-
import asyncio
import time
import json
import io
import os
import random
from datetime import datetime
from pyrogram import Client, filters, idle
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, ChatJoinRequest,
    ReplyKeyboardMarkup, KeyboardButton
)
from pyrogram.errors import UserNotParticipant, MessageNotModified
from pyrogram.enums import ChatMemberStatus, ParseMode

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
API_ID = 31721040
API_HASH = "60a197f65d26b97fcd7c144a820cc21a"
BOT_TOKEN = os.environ.get("HOSTED_BOT_TOKEN", "8712598979:AAEJX9ZUY8fyHiIkKQx7p6isZ9bSWDHNJUc")
BOT_ID = BOT_TOKEN.split(":")[0] if ":" in BOT_TOKEN else "ultra_bot"
ADMIN_ID = 6506984391

app = Client(f"bot_{BOT_ID}", api_id=API_ID, api_hash=API_HASH,
             bot_token=BOT_TOKEN, in_memory=True)

CONFIG_FILE = f"config_{BOT_ID}.json"

def load_config():
    # ✅ Railway-তে file reset হয়, তাই env variable থেকে নেওয়া হচ্ছে
    db_ch = os.environ.get("DB_CHANNEL_ID")
    db_ch = int(db_ch) if db_ch else None
    vid_max = int(os.environ.get("VID_MAX_ID", "500"))
    min_id = int(os.environ.get("MIN_ID", "2"))
    max_id_str = os.environ.get("MAX_ID")
    max_id = int(max_id_str) if max_id_str else None
    # fallback: config file থাকলে সেটাও চেক করো
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                db_ch = db_ch or data.get("DB_CHANNEL_ID")
                vid_max = data.get("VID_MAX_ID", vid_max)
                min_id = data.get("MIN_ID", min_id)
                max_id = max_id or data.get("MAX_ID")
        except:
            pass
    return db_ch, vid_max, min_id, max_id

def save_config(db_id=None, vid_max=None, min_id=None, max_id=None):
    existing = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                existing = json.load(f)
        except:
            pass
    if db_id is not None:
        existing["DB_CHANNEL_ID"] = db_id
    if vid_max is not None:
        existing["VID_MAX_ID"] = vid_max
    if min_id is not None:
        existing["MIN_ID"] = min_id
    if max_id is not None:
        existing["MAX_ID"] = max_id
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f)
    except:
        pass  # Railway-তে write fail হলে silent ignore

_cfg = load_config()
DB_CHANNEL_ID = _cfg[0]
VID_MAX_ID = _cfg[1]
MIN_ID = _cfg[2]
MAX_ID = _cfg[3]

# ==========================================
# 🗄️ DATABASE
# ==========================================
db = {
    "main_channel": None,
    "backup_channel": None,
    "fsub_channels": [],
    "video_channels": [],
    "delete_time": 15,
    "cooldown_hours": 3,
    "protect_content": True,
    "custom_buttons": [],
    "fake_leaderboard": [],
    "moderators": [],
    "vip_users": [],               
    "users": {},
    "join_requests": {},
    "stats": {"today_new": 0, "unbacked_users": 0},
    "start_message": "🎬 <b>Welcome to Ultra Premium Bot!</b>\n\nRoll the dice and get exclusive videos! 🎲",
    "vip_purchase_message": "💎 <b>VIP 3-Day Access</b>\n\nCost: 100 Points\nYour Points: {points}\n\nClick below to buy."
}
admin_states = {}
bot_info = {}

# ─── DB helpers ─────────────────────────────
def merge_databases(old_db, new_db):
    for uid, data in new_db.get("users", {}).items():
        if uid not in old_db["users"]:
            old_db["users"][uid] = data
        else:
            old_db["users"][uid]["total_media"] = max(
                old_db["users"][uid].get("total_media", 0),
                data.get("total_media", 0))
            old_db["users"][uid]["ref_count"] = max(
                old_db["users"][uid].get("ref_count", 0),
                data.get("ref_count", 0))
            old_db["users"][uid]["roll_count"] = max(
                old_db["users"][uid].get("roll_count", 0),
                data.get("roll_count", 0))
            old_db["users"][uid]["points"] = old_db["users"][uid].get("points", 0) + data.get("points", 0)
    for key in ["fsub_channels", "custom_buttons", "fake_leaderboard", "moderators", "vip_users", "video_channels"]:
        if key in new_db:
            for item in new_db[key]:
                if item not in old_db[key]:
                    old_db[key].append(item)
    for ch_id, users in new_db.get("join_requests", {}).items():
        if ch_id not in old_db["join_requests"]:
            old_db["join_requests"][ch_id] = []
        for u in users:
            if u not in old_db["join_requests"][ch_id]:
                old_db["join_requests"][ch_id].append(u)
    return old_db

async def force_backup(client):
    if not DB_CHANNEL_ID:
        return
    try:
        db["stats"]["unbacked_users"] = 0
        file = io.BytesIO(json.dumps(db, indent=4).encode('utf-8'))
        file.name = f"db_{BOT_ID}.json"
        await client.send_document(
            DB_CHANNEL_ID, document=file,
            caption=f"☁️ Cloud DB Backup\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    except:
        pass

async def backup_db_loop():
    while True:
        await asyncio.sleep(300)
        try:
            await force_backup(app)
        except:
            pass

async def load_db():
    global db
    if not DB_CHANNEL_ID:
        return
    try:
        async for message in app.get_chat_history(DB_CHANNEL_ID, limit=5):
            if message.document and message.document.file_name.endswith(".json"):
                file_in_memory = await app.download_media(message.document, in_memory=True)
                loaded_db = json.loads(file_in_memory.getvalue().decode('utf-8'))
                db = merge_databases(db, loaded_db)
                print("✅ Smart DB Restored!")
                return
    except:
        pass

# ─── Scan video channel max ID (fixed) ─────
async def scan_video_channel_max_id():
    global VID_MAX_ID
    if not db.get("video_channels"):
        return
    highest = 0
    for vid_ch in db["video_channels"]:
        try:
            chat = await app.get_chat(vid_ch)
            if chat.last_message:
                highest = max(highest, chat.last_message.id)
            else:
                async for msg in app.get_chat_history(vid_ch, limit=1):
                    highest = max(highest, msg.id)
                    break
        except Exception as e:
            print(f"⚠️ Could not scan video channel {vid_ch}: {e}")
    if highest > 0:
        VID_MAX_ID = highest
        save_config(vid_max=highest)
        print(f"✅ Video channel max ID: {VID_MAX_ID}")

# ─── Join request handler ──
@app.on_chat_join_request()
async def on_join_request(c, req: ChatJoinRequest):
    uid_str = str(req.from_user.id)
    ch_id_str = str(req.chat.id)
    if ch_id_str not in db["join_requests"]:
        db["join_requests"][ch_id_str] = []
    if uid_str not in db["join_requests"][ch_id_str]:
        db["join_requests"][ch_id_str].append(uid_str)
        print(f"✅ Join request: user={uid_str} ch={ch_id_str}")

# ─── 🌟 UPDATED: Helper: check if user has pending join request or is already a member ──
async def has_pending_join_request(client, chat_id, user_id):
    """Return True if user_id has a pending join request OR is already a member in chat_id."""
    ch_id_str = str(chat_id)
    uid_str = str(user_id)

    # 1. প্রথমে চেক করবে ইউজার আগে থেকেই চ্যানেলে জয়েন করে আছে কি না
    try:
        member = await client.get_chat_member(chat_id, user_id)
        if member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED]:
            return True
    except Exception:
        pass # জয়েন করা নেই, তাই রিকোয়েস্ট চেক করবে

    # 2. এরপর ডাটাবেজের লোকাল ক্যাশ চেক করবে (সবচেয়ে দ্রুত)
    if uid_str in db.get("join_requests", {}).get(ch_id_str, []):
        return True

    # 3. সবশেষে টেলিগ্রাম এপিআই থেকে চেক করবে
    try:
        async for req in client.get_chat_join_requests(chat_id, limit=200):
            if req.from_user.id == user_id:
                # ফিউচারের জন্য ডাটাবেজে সেভ করে রাখা
                if ch_id_str not in db["join_requests"]:
                    db["join_requests"][ch_id_str] = []
                if uid_str not in db["join_requests"][ch_id_str]:
                    db["join_requests"][ch_id_str].append(uid_str)
                return True
    except Exception as e:
        print(f"API check join requests failed: {e}")

    return False

# ─── VIP helpers ───────────────────────────
def is_admin(uid):
    return uid == ADMIN_ID or uid in db["moderators"]

def is_vip(uid_str):
    if uid_str in db["vip_users"]:
        return True
    user = db["users"].get(uid_str)
    if user and user.get("vip_expiry", 0) > time.time():
        return True
    return False

def get_vip_expiry_text(uid_str):
    user = db["users"].get(uid_str)
    if uid_str in db["vip_users"]:
        return "♾️ Permanent"
    if user and user.get("vip_expiry"):
        exp = user["vip_expiry"]
        if exp > time.time():
            return f"⏳ Until {datetime.fromtimestamp(exp).strftime('%Y-%m-%d %H:%M')}"
        else:
            return "❌ Expired"
    return ""

# ─── Admin Panel ───────────────────────────
def get_admin_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 START MSG", callback_data="set_start"),
         InlineKeyboardButton("🛡️ FORCE SUB", callback_data="manage_fsub")],
        [InlineKeyboardButton("👥 MODS & VIP", callback_data="manage_users"),
         InlineKeyboardButton("⏱️ TIMERS", callback_data="manage_timers")],
        [InlineKeyboardButton("🔗 CUSTOM BTNS", callback_data="manage_btns"),
         InlineKeyboardButton("🏆 LEADERBOARD", callback_data="manage_lb")],
        [InlineKeyboardButton("🎥 VIDEO CHs", callback_data="manage_vid_ch"),
         InlineKeyboardButton("🔢 RANGE", callback_data="set_range")],
        [InlineKeyboardButton("🔄 TRANSFER DB", callback_data="req_db_upload"),
         InlineKeyboardButton("📢 BROADCAST", callback_data="req_broadcast")],
        [InlineKeyboardButton("☁️ EXPORT DB", callback_data="export_db"),
         InlineKeyboardButton("🗑️ CLEAR LB", callback_data="clear_lb")],
        [InlineKeyboardButton("🔍 SCAN VIDEO CH", callback_data="scan_vid_ch"),
         InlineKeyboardButton("🔐 PROTECT", callback_data="toggle_protect")],
        [InlineKeyboardButton("💬 VIP MSG", callback_data="set_vip_msg")]
    ])

def admin_stats_text():
    total = len(db["users"])
    vips = len(db["vip_users"])
    vid_ch_count = len(db.get("video_channels", []))
    return (
        "<b>⚙️ ULTRA CLOUD CONTROL PANEL</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>Total Users:</b> {total}\n"
        f"💎 <b>VIP Members:</b> {vips}\n"
        f"📈 <b>New Today:</b> {db['stats']['today_new']}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📢 <b>Main Ch:</b> {'✅' if db['main_channel'] else '❌'} | "
        f"<b>Backup:</b> {'✅' if db['backup_channel'] else '❌'}\n"
        f"📚 <b>Serial Channels:</b> {len(db['fsub_channels'])}\n"
        f"🎥 <b>Video Channels:</b> {vid_ch_count} (max_id={VID_MAX_ID})\n"
        f"🔢 <b>Range:</b> {MIN_ID}-{MAX_ID if MAX_ID else VID_MAX_ID}\n"
        f"🔐 <b>Protect:</b> {'✅' if db['protect_content'] else '❌'}\n"
        f"⏱️ <b>Auto-Del:</b> {db['delete_time']}m | "
        f"<b>Cooldown:</b> {db['cooldown_hours']}h"
    )

@app.on_message(filters.command("admin") & filters.private)
async def admin_panel(c, m):
    if not is_admin(m.from_user.id):
        return
    await m.reply_text(admin_stats_text(), reply_markup=get_admin_kb(), parse_mode=ParseMode.HTML)

@app.on_message(filters.command("addvip") & filters.private)
async def add_vip(c, m):
    if not is_admin(m.from_user.id): return
    if len(m.command) < 2: return await m.reply_text("Usage: /addvip USER_ID")
    uid_str = m.command[1]
    if uid_str not in db["vip_users"]:
        db["vip_users"].append(uid_str)
        await m.reply_text(f"✅ <code>{uid_str}</code> → VIP!", parse_mode=ParseMode.HTML)
    else:
        await m.reply_text("⚠️ Already VIP.")

@app.on_message(filters.command("removevip") & filters.private)
async def remove_vip(c, m):
    if not is_admin(m.from_user.id): return
    if len(m.command) < 2: return await m.reply_text("Usage: /removevip USER_ID")
    uid_str = m.command[1]
    if uid_str in db["vip_users"]:
        db["vip_users"].remove(uid_str)
        await m.reply_text(f"✅ VIP removed: <code>{uid_str}</code>", parse_mode=ParseMode.HTML)
    else:
        await m.reply_text("⚠️ Not a VIP.")

@app.on_message(filters.command("addmod") & filters.private)
async def add_mod(c, m):
    if m.from_user.id != ADMIN_ID: return
    if len(m.command) < 2: return await m.reply_text("Usage: /addmod USER_ID")
    uid = int(m.command[1])
    if uid not in db["moderators"]:
        db["moderators"].append(uid)
        await m.reply_text(f"✅ <code>{uid}</code> → Moderator!", parse_mode=ParseMode.HTML)
    else:
        await m.reply_text("⚠️ Already a Moderator.")

@app.on_message(filters.command("removemod") & filters.private)
async def remove_mod(c, m):
    if m.from_user.id != ADMIN_ID: return
    if len(m.command) < 2: return await m.reply_text("Usage: /removemod USER_ID")
    uid = int(m.command[1])
    if uid in db["moderators"]:
        db["moderators"].remove(uid)
        await m.reply_text(f"✅ Moderator removed: <code>{uid}</code>", parse_mode=ParseMode.HTML)
    else:
        await m.reply_text("⚠️ Not a Moderator.")

@app.on_message(filters.command("removechannel") & filters.private)
async def remove_channel_cmd(c, m):
    """
    Usage:
      /removechannel main
      /removechannel backup
      /removechannel serial -1001234567890
      /removechannel video  -1001234567890
    """
    global DB_CHANNEL_ID
    if m.from_user.id != ADMIN_ID: return
    if len(m.command) < 2:
        return await m.reply_text(
            "📋 <b>Usage:</b>\n"
            "<code>/removechannel main</code>\n"
            "<code>/removechannel backup</code>\n"
            "<code>/removechannel serial -1001234567890</code>\n"
            "<code>/removechannel video  -1001234567890</code>\n"
            "<code>/removechannel db</code>",
            parse_mode=ParseMode.HTML
        )

    ch_type = m.command[1].lower()

    if ch_type == "main":
        if db["main_channel"]:
            old = db["main_channel"]["id"]
            db["main_channel"] = None
            await force_backup(c)
            return await m.reply_text(f"✅ Main channel removed: <code>{old}</code>", parse_mode=ParseMode.HTML)
        return await m.reply_text("⚠️ Main channel already not set.")

    elif ch_type == "backup":
        if db["backup_channel"]:
            old = db["backup_channel"]["id"]
            db["backup_channel"] = None
            await force_backup(c)
            return await m.reply_text(f"✅ Backup channel removed: <code>{old}</code>", parse_mode=ParseMode.HTML)
        return await m.reply_text("⚠️ Backup channel already not set.")

    elif ch_type == "db":
        DB_CHANNEL_ID = None
        save_config(db_id=None)
        return await m.reply_text("✅ DB channel removed.")

    elif ch_type in ("serial", "video"):
        if len(m.command) < 3:
            return await m.reply_text(f"⚠️ Channel ID দাও: <code>/removechannel {ch_type} -1001234567890</code>", parse_mode=ParseMode.HTML)
        try:
            ch_id = int(m.command[2])
        except:
            return await m.reply_text("❌ Invalid channel ID.")

        if ch_type == "serial":
            before = len(db["fsub_channels"])
            db["fsub_channels"] = [ch for ch in db["fsub_channels"] if ch["id"] != ch_id]
            if len(db["fsub_channels"]) < before:
                await force_backup(c)
                return await m.reply_text(f"✅ Serial channel removed: <code>{ch_id}</code>", parse_mode=ParseMode.HTML)
            return await m.reply_text("⚠️ Serial channel not found.")

        else:  # video
            if ch_id in db["video_channels"]:
                db["video_channels"].remove(ch_id)
                await force_backup(c)
                return await m.reply_text(f"✅ Video channel removed: <code>{ch_id}</code>", parse_mode=ParseMode.HTML)
            return await m.reply_text("⚠️ Video channel not found.")

    else:
        await m.reply_text("❌ Type must be: main / backup / serial / video / db")

# ─── Callback Handler ─────────────────────
@app.on_callback_query()
async def cb_handler(c, q: CallbackQuery):
    data = q.data
    uid = q.from_user.id
    uid_str = str(uid)

    if data == "check_join":
        await q.answer("Checking...")
        if uid_str not in db["users"]:
            db["users"][uid_str] = {"total_media": 0, "cooldown_until": 0,
                                    "ref_count": 0, "history_msgs": [],
                                    "roll_count": 0, "points": 0}
        await process_user_request(c, q.message.chat.id, uid_str, q.message, clicked_btn=True)
        return

    if data == "roll_dice":
        await q.answer("🎲 Rolling...")
        if uid_str not in db["users"]:
            db["users"][uid_str] = {"total_media": 0, "cooldown_until": 0,
                                    "ref_count": 0, "history_msgs": [],
                                    "roll_count": 0, "points": 0}
        await process_user_request(c, q.message.chat.id, uid_str, q.message, clicked_btn=True)
        return

    if data == "show_profile":
        await q.answer()
        await show_profile_text(c, q.message.chat.id, uid_str)
        return

    if data == "show_leaderboard":
        await q.answer()
        await show_leaderboard_text(c, q.message.chat.id)
        return

    if data == "show_referral":
        await q.answer()
        ref_link = f"https://t.me/{bot_info.get('username','bot')}?start=ref_{uid_str}"
        user = db["users"].get(uid_str, {})
        text = (
            "🔗 <b>Your Referral Link</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"<code>{ref_link}</code>\n\n"
            f"👥 <b>Total Referrals:</b> {user.get('ref_count', 0)}\n"
            f"💰 <b>Points:</b> {user.get('points', 0)}\n\n"
            "<i>Each referral gives you 10 points. 100 points = 3-day VIP.</i>"
        )
        await c.send_message(q.message.chat.id, text, parse_mode=ParseMode.HTML)
        return

    if data == "show_vip":
        await q.answer()
        vip_now = is_vip(uid_str)
        expiry = get_vip_expiry_text(uid_str)
        points = db["users"].get(uid_str, {}).get("points", 0)
        if vip_now:
            text = (
                "💎 <b>VIP Membership</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"Status: ✅ <b>ACTIVE</b>\n"
                f"Expiry: {expiry}\n\n"
                "<i>Enjoy all VIP benefits!</i>"
            )
            kb = None
        else:
            text = db.get("vip_purchase_message", "").format(points=points)
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Buy VIP (100 Points)", callback_data="buy_vip")]
            ])
        await c.send_message(q.message.chat.id, text, reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    if data == "buy_vip":
        await q.answer()
        await buy_vip_command(c, q.message.chat.id, uid_str, message=q.message)
        return

    if data == "show_help":
        await q.answer()
        text = (
            "ℹ️ <b>How to Use</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🎲 Press <b>Get Videos</b> to roll the dice\n"
            "🎯 Higher roll = more videos (max 6)\n"
            "⏳ Videos auto-delete after set time\n"
            "🔗 Refer friends → 10 Points each\n"
            "💎 100 Points = 3-Day VIP\n"
            "💬 Use /buyvip to purchase\n\n"
            "<i>VIP: no force sub, no cooldown.</i>"
        )
        await c.send_message(q.message.chat.id, text, parse_mode=ParseMode.HTML)
        return

    if not is_admin(uid):
        return await q.answer("❌ Access Denied!", show_alert=True)

    if data == "set_vip_msg":
        admin_states[uid] = "set_vip_msg"
        await q.message.reply_text("💬 Send the new VIP purchase message.\nUse {points} to show user points.")
        await q.answer()
        return

    if data == "scan_vid_ch":
        await q.answer("Scanning...")
        await scan_video_channel_max_id()
        await q.message.reply_text(f"✅ Scanned! Max ID = {VID_MAX_ID}")

    elif data == "toggle_protect":
        db["protect_content"] = not db["protect_content"]
        state = "ON" if db["protect_content"] else "OFF"
        await q.answer(f"🔐 Protect Content {state}", show_alert=True)

    elif data == "manage_vid_ch":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Add Video Channel", callback_data="add_vid_ch")],
            [InlineKeyboardButton("📋 List Video Channels", callback_data="list_vid_ch")],
            [InlineKeyboardButton("🗑 Remove Video Channel", callback_data="remove_vid_ch")],
            [InlineKeyboardButton("◀ BACK", callback_data="back_admin")]
        ])
        await q.message.edit_text("<b>🎥 Manage Video Channels</b>", reply_markup=kb, parse_mode=ParseMode.HTML)

    elif data == "add_vid_ch":
        admin_states[uid] = "add_vid_ch"
        await q.message.reply_text("Forward a message from the video channel (bot must be admin).")
        await q.answer()

    elif data == "list_vid_ch":
        if not db["video_channels"]:
            txt = "No video channels set."
        else:
            txt = "<b>🎥 Video Channels:</b>\n" + "\n".join(f"• <code>{ch}</code>" for ch in db["video_channels"])
        await q.message.edit_text(txt, parse_mode=ParseMode.HTML)

    elif data == "remove_vid_ch":
        admin_states[uid] = "remove_vid_ch"
        await q.message.reply_text("Send the channel ID to remove.")
        await q.answer()

    elif data == "set_range":
        admin_states[uid] = "set_range"
        await q.message.reply_text(
            f"Current range: <code>{MIN_ID}</code> - <code>{MAX_ID if MAX_ID else 'auto'}</code>\n"
            "Send new range as: <code>MIN_ID MAX_ID</code>",
            parse_mode=ParseMode.HTML)
        await q.answer()

    elif data == "manage_fsub":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Set Main Channel", callback_data="set_main_ch")],
            [InlineKeyboardButton("Set Backup Channel", callback_data="set_backup_ch")],
            [InlineKeyboardButton("Add Serial Channel", callback_data="add_serial_ch")],
            [InlineKeyboardButton("Set DB Channel", callback_data="set_db_ch")],
            [InlineKeyboardButton("Set Video Channel", callback_data="set_vid_ch")],
            [InlineKeyboardButton("📋 View Channels", callback_data="view_channels")],
            [InlineKeyboardButton("◀ BACK", callback_data="back_admin")]
        ])
        await q.message.edit_text("<b>🛡️ Channel Management</b>", reply_markup=kb, parse_mode=ParseMode.HTML)

    elif data == "view_channels":
        main = db["main_channel"]["id"] if db["main_channel"] else "Not set"
        backup = db["backup_channel"]["id"] if db["backup_channel"] else "Not set"
        vid_chs = ", ".join(str(ch) for ch in db.get("video_channels", [])) or "None"
        serials = "\n".join([f"  • {ch['id']}" for ch in db["fsub_channels"]]) or "  None"
        text = (
            f"<b>📋 Channel Info</b>\n\n"
            f"🔴 Main: <code>{main}</code>\n"
            f"🟡 Backup: <code>{backup}</code>\n"
            f"🎥 Video: <code>{vid_chs}</code> (max={VID_MAX_ID})\n"
            f"📚 Serial:\n{serials}\n"
            f"🗄️ DB: <code>{DB_CHANNEL_ID or 'Not set'}</code>"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀ BACK", callback_data="manage_fsub")]])
        await q.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

    elif data == "manage_timers":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Del: 3m", callback_data="td_3"),
             InlineKeyboardButton("15m", callback_data="td_15"),
             InlineKeyboardButton("30m", callback_data="td_30")],
            [InlineKeyboardButton("Cool: 1h", callback_data="tc_1"),
             InlineKeyboardButton("3h", callback_data="tc_3"),
             InlineKeyboardButton("5h", callback_data="tc_5")],
            [InlineKeyboardButton("7h", callback_data="tc_7"),
             InlineKeyboardButton("12h", callback_data="tc_12"),
             InlineKeyboardButton("24h", callback_data="tc_24")],
            [InlineKeyboardButton("◀ BACK", callback_data="back_admin")]
        ])
        await q.message.edit_text(
            f"<b>⏱️ Timers</b>\nAuto-Del: {db['delete_time']}m | Cooldown: {db['cooldown_hours']}h",
            reply_markup=kb, parse_mode=ParseMode.HTML)

    elif data.startswith("td_"):
        db["delete_time"] = int(data.split("_")[1])
        await q.answer(f"✅ Auto-Delete → {db['delete_time']}m", show_alert=True)

    elif data.startswith("tc_"):
        db["cooldown_hours"] = int(data.split("_")[1])
        await q.answer(f"✅ Cooldown → {db['cooldown_hours']}h", show_alert=True)

    elif data == "export_db":
        await q.answer("Exporting...")
        await force_backup(c)
        await q.message.reply_text("✅ DB exported!")

    elif data == "req_broadcast":
        await q.message.reply_text("📢 Reply to any message with <code>/broadcast</code>", parse_mode=ParseMode.HTML)
        await q.answer()

    elif data == "set_start":
        admin_states[uid] = "set_start"
        await q.message.reply_text("📝 Send the new start message (HTML supported).")
        await q.answer()

    elif data == "clear_lb":
        db["fake_leaderboard"] = []
        await q.answer("✅ Leaderboard cleared!", show_alert=True)

    elif data in ["set_main_ch", "set_backup_ch", "add_serial_ch",
                  "set_db_ch", "set_vid_ch", "manage_btns",
                  "manage_lb", "req_db_upload", "manage_users"]:
        admin_states[uid] = data
        hints = {
            "set_main_ch":   "Forward from <b>Main Channel</b> (bot must be admin).",
            "set_backup_ch": "Forward from <b>Backup Channel</b>.",
            "add_serial_ch": "Forward from a <b>Serial Channel</b>.",
            "set_db_ch":     "Forward from <b>DB Channel</b>.",
            "set_vid_ch":    "Forward from a <b>Video Channel</b> (bot must be admin).",
            "manage_btns":   "Send: <code>Button Name | https://link.com</code>",
            "manage_lb":     "Send: <code>User Name | 150</code>",
            "req_db_upload": "Upload the <code>.json</code> DB file.",
            "manage_users":  "Use /addvip ID · /removevip ID · /addmod ID · /removemod ID"
        }
        await q.message.reply_text(f"💬 <b>Input Required:</b>\n{hints[data]}", parse_mode=ParseMode.HTML)
        await q.answer()

    elif data == "back_admin":
        await q.message.edit_text(admin_stats_text(), reply_markup=get_admin_kb(), parse_mode=ParseMode.HTML)

# ─── Keyboard Menu & Input Handler ─────────
MENU_BUTTONS = {
    "🎬 Get Videos": "roll",
    "👤 My Profile": "profile",
    "🏆 Leaderboard": "lb",
    "💎 VIP": "vip",
    "🔗 My Referral": "referral",
    "💬 Help": "help"
}

IGNORED_CMDS = filters.command([
    "start","admin","profile","broadcast","buyvip",
    "addvip","removevip","addmod","removemod"
])

@app.on_message(filters.private & ~IGNORED_CMDS)
async def input_handler(c, m):
    global db, DB_CHANNEL_ID, MIN_ID, MAX_ID
    uid = m.from_user.id
    uid_str = str(uid)
    state = admin_states.get(uid)

    if not state and m.text and m.text in MENU_BUTTONS:
        action = MENU_BUTTONS[m.text]
        if action == "roll":
            if uid_str not in db["users"]:
                db["users"][uid_str] = {"total_media": 0, "cooldown_until": 0,
                                        "ref_count": 0, "history_msgs": [],
                                        "roll_count": 0, "points": 0}
            await process_user_request(c, m.chat.id, uid_str, m, clicked_btn=False)
        elif action == "profile":
            await show_profile_text(c, m.chat.id, uid_str)
        elif action == "lb":
            await show_leaderboard_text(c, m.chat.id)
        elif action == "referral":
            ref_link = f"https://t.me/{bot_info.get('username','bot')}?start=ref_{uid_str}"
            user = db["users"].get(uid_str, {})
            text = (
                "🔗 <b>Your Referral Link</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"<code>{ref_link}</code>\n\n"
                f"👥 <b>Total Referrals:</b> {user.get('ref_count', 0)}\n"
                f"💰 <b>Points:</b> {user.get('points', 0)}\n\n"
                "<i>10 points per referral. 100 points = 3-day VIP.</i>"
            )
            await m.reply_text(text, parse_mode=ParseMode.HTML)
        elif action == "vip":
            vip_now = is_vip(uid_str)
            expiry = get_vip_expiry_text(uid_str)
            points = db["users"].get(uid_str, {}).get("points", 0)
            if vip_now:
                text = (
                    "💎 <b>VIP Membership</b>\n"
                    f"Status: ✅ ACTIVE\nExpiry: {expiry}\n\n"
                    "<i>Enjoy all benefits!</i>"
                )
                await m.reply_text(text, parse_mode=ParseMode.HTML)
            else:
                msg = db.get("vip_purchase_message", "").format(points=points)
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 Buy VIP (100 Points)", callback_data="buy_vip")]
                ])
                await m.reply_text(msg, reply_markup=kb, parse_mode=ParseMode.HTML)
        elif action == "help":
            await m.reply_text(
                "ℹ️ <b>Help</b>\n"
                "🎲 Get Videos → Dice roll\n"
                "👤 Profile → Your stats\n"
                "🏆 Leaderboard → Top referrers\n"
                "💎 VIP → Buy with 100 points (3 days)\n"
                "🔗 My Referral → Get 10 points per friend\n"
                "💬 /buyvip → Buy VIP directly",
                parse_mode=ParseMode.HTML)
        return

    if not state or not is_admin(uid):
        return

    if state == "set_vip_msg" and m.text:
        db["vip_purchase_message"] = m.text
        await m.reply_text("✅ VIP purchase message updated!")
        admin_states[uid] = None
        return

    if state.endswith("_ch") and m.forward_from_chat:
        ch_id = m.forward_from_chat.id
        try:
            if state == "set_main_ch":
                link = (await c.create_chat_invite_link(ch_id, creates_join_request=False)).invite_link
                db["main_channel"] = {"id": ch_id, "link": link}
            elif state == "set_backup_ch":
                link = (await c.create_chat_invite_link(ch_id, creates_join_request=True)).invite_link
                db["backup_channel"] = {"id": ch_id, "link": link}
            elif state == "add_serial_ch":
                link = (await c.create_chat_invite_link(ch_id, creates_join_request=True)).invite_link
                db["fsub_channels"].append({"id": ch_id, "link": link})
            elif state == "set_vid_ch":
                db["video_channels"] = [ch_id]
                await scan_video_channel_max_id()
            elif state == "add_vid_ch":
                if ch_id not in db["video_channels"]:
                    db["video_channels"].append(ch_id)
                await scan_video_channel_max_id()
            elif state == "set_db_ch":
                DB_CHANNEL_ID = ch_id
                save_config(db_id=ch_id)
            await m.reply_text(f"✅ Configured! <code>{ch_id}</code>", parse_mode=ParseMode.HTML)
            admin_states[uid] = None
        except Exception as e:
            await m.reply_text(f"❌ Error: {e}\n(Bot must be admin in that channel)")

    elif state == "remove_vid_ch" and m.text:
        try:
            ch_id = int(m.text.strip())
            if ch_id in db["video_channels"]:
                db["video_channels"].remove(ch_id)
                await m.reply_text(f"🗑 Removed <code>{ch_id}</code>", parse_mode=ParseMode.HTML)
            else:
                await m.reply_text("Not in list.")
        except:
            await m.reply_text("Invalid ID.")
        admin_states[uid] = None

    elif state == "set_range" and m.text:
        try:
            parts = m.text.strip().split()
            if len(parts) == 2:
                min_val = int(parts[0])
                max_val = int(parts[1])
                MIN_ID = min_val
                MAX_ID = max_val
                save_config(min_id=min_val, max_id=max_val)
                await m.reply_text(f"✅ Range set: {MIN_ID} - {MAX_ID}")
            else:
                await m.reply_text("Send exactly two numbers.")
        except:
            await m.reply_text("Invalid numbers.")
        admin_states[uid] = None

    elif state == "set_start" and m.text:
        db["start_message"] = m.text
        await m.reply_text("✅ Start message updated!")
        admin_states[uid] = None

    elif state == "req_db_upload" and m.document and m.document.file_name.endswith(".json"):
        try:
            file_in_memory = await c.download_media(m.document, in_memory=True)
            loaded_db = json.loads(file_in_memory.getvalue().decode('utf-8'))
            db = merge_databases(db, loaded_db)
            await m.reply_text("🎉 <b>Smart DB Merge Successful!</b>", parse_mode=ParseMode.HTML)
            admin_states[uid] = None
        except Exception as e:
            await m.reply_text(f"❌ Corrupted File: {e}")

    elif state == "manage_btns" and m.text and "|" in m.text:
        name, url = m.text.split("|", 1)
        db["custom_buttons"].append({"text": name.strip(), "url": url.strip()})
        await m.reply_text(f"✅ Button added! Total: {len(db['custom_buttons'])}")
        admin_states[uid] = None

    elif state == "manage_lb" and m.text and "|" in m.text:
        db["fake_leaderboard"].append(m.text.strip())
        await m.reply_text(f"✅ Entry added! Total: {len(db['fake_leaderboard'])}")
        admin_states[uid] = None

    else:
        if state.endswith("_ch") and not m.forward_from_chat:
            await m.reply_text("⚠️ Please <b>forward</b> a message from the channel.", parse_mode=ParseMode.HTML)

# ─── Broadcast ────────────────────────────
@app.on_message(filters.command("broadcast") & filters.private)
async def broadcast_cmd(c, m):
    if not is_admin(m.from_user.id) or not m.reply_to_message:
        return
    msg = await m.reply_text("⏳ <b>Broadcasting...</b>", parse_mode=ParseMode.HTML)
    success, fail = 0, 0
    for uid_str in list(db["users"].keys()):
        try:
            await m.reply_to_message.copy(int(uid_str))
            success += 1
            await asyncio.sleep(0.05)
        except:
            fail += 1
    await msg.edit_text(f"✅ <b>Done!</b>\n📩 Success: {success} | 🚫 Failed: {fail}", parse_mode=ParseMode.HTML)

# ─── /buyvip Command & Function ───────────
@app.on_message(filters.command("buyvip") & filters.private)
async def buyvip_cmd(c, m):
    await buy_vip_command(c, m.chat.id, str(m.from_user.id), message=m)

async def buy_vip_command(c, chat_id, uid_str, message=None):
    if uid_str not in db["users"]:
        db["users"][uid_str] = {"total_media": 0, "cooldown_until": 0,
                                "ref_count": 0, "history_msgs": [],
                                "roll_count": 0, "points": 0}
    user = db["users"][uid_str]
    points = user.get("points", 0)

    if uid_str in db["vip_users"]:
        txt = "✅ You already have <b>Permanent VIP</b>! No need to buy."
        if message:
            await message.reply_text(txt, parse_mode=ParseMode.HTML)
        else:
            await c.send_message(chat_id, txt, parse_mode=ParseMode.HTML)
        return

    if user.get("vip_expiry", 0) > time.time():
        exp = get_vip_expiry_text(uid_str)
        txt = f"⏳ Your VIP is still active ({exp}). Come back after expiry to renew."
        if message:
            await message.reply_text(txt, parse_mode=ParseMode.HTML)
        else:
            await c.send_message(chat_id, txt, parse_mode=ParseMode.HTML)
        return

    if points < 100:
        need = 100 - points
        txt = f"❌ You need <b>{need}</b> more points. You have {points} pts."
        if message:
            await message.reply_text(txt, parse_mode=ParseMode.HTML)
        else:
            await c.send_message(chat_id, txt, parse_mode=ParseMode.HTML)
        return

    user["points"] = points - 100
    user["vip_expiry"] = time.time() + 259200  # 3 days
    txt = (
        "🎉 <b>Congratulations!</b>\n"
        "You've successfully activated <b>3-Day VIP</b>!\n"
        "Enjoy unlimited access, no force sub, no cooldown.\n\n"
        f"Expiry: {get_vip_expiry_text(uid_str)}"
    )
    if message:
        await message.reply_text(txt, parse_mode=ParseMode.HTML)
    else:
        await c.send_message(chat_id, txt, parse_mode=ParseMode.HTML)

# ─── Start Command ────────────────────────
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(c, m):
    uid_str = str(m.from_user.id)

    if "username" not in bot_info:
        me = await c.get_me()
        bot_info["username"] = me.username

    if uid_str not in db["users"]:
        db["stats"]["today_new"] += 1
        db["stats"]["unbacked_users"] = db["stats"].get("unbacked_users", 0) + 1
        db["users"][uid_str] = {
            "total_media": 0, "cooldown_until": 0,
            "ref_count": 0, "history_msgs": [],
            "roll_count": 0, "points": 0
        }
        if db["stats"]["unbacked_users"] >= 5:
            asyncio.create_task(force_backup(c))

        if len(m.command) > 1 and m.command[1].startswith("ref_"):
            referrer_str = m.command[1].split("_")[1]
            if referrer_str in db["users"] and referrer_str != uid_str:
                db["users"][referrer_str]["ref_count"] += 1
                db["users"][referrer_str]["points"] = db["users"][referrer_str].get("points", 0) + 10
                try:
                    await c.send_message(
                        int(referrer_str),
                        f"🎉 <b>New Referral!</b>\nTotal: {db['users'][referrer_str]['ref_count']}\n💰 Points: +10 (now {db['users'][referrer_str]['points']})",
                        parse_mode=ParseMode.HTML)
                except:
                    pass

    keyboard = ReplyKeyboardMarkup(
        [
            ["🎬 Get Videos", "👤 My Profile"],
            ["🏆 Leaderboard", "💎 VIP"],
            ["🔗 My Referral"],
            ["💬 Help"]
        ],
        resize_keyboard=True
    )

    await m.reply_text(
        db.get("start_message", "🎬 <b>Welcome!</b>"),
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

# ─── Profile & Leaderboard ────────────────
async def show_profile_text(c, chat_id, uid_str):
    if uid_str not in db["users"]:
        return await c.send_message(chat_id, "⚠️ No profile. Send /start first.")
    user = db["users"][uid_str]
    vip_now = is_vip(uid_str)
    expiry = get_vip_expiry_text(uid_str)
    ref_link = f"https://t.me/{bot_info.get('username','bot')}?start=ref_{uid_str}"
    text = (
        "👤 <b>MY PROFILE</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🔹 <b>Status:</b> {'💎 VIP' if vip_now else '👤 Standard'}\n"
        f"{'⏳ ' + expiry if vip_now else ''}\n"
        f"🎞️ <b>Videos Received:</b> {user.get('total_media', 0)}\n"
        f"🔗 <b>Referrals:</b> {user.get('ref_count', 0)}\n"
        f"💰 <b>Points:</b> {user.get('points', 0)}\n\n"
        f"🔗 <b>Your Link:</b>\n<code>{ref_link}</code>"
    )
    await c.send_message(chat_id, text, parse_mode=ParseMode.HTML)

async def show_leaderboard_text(c, chat_id):
    entries = db.get("fake_leaderboard", [])
    if not entries:
        return await c.send_message(chat_id, "🏆 Leaderboard is empty right now.")
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 10
    lines = "\n".join([f"{medals[i]} {e}" for i, e in enumerate(entries[:10])])
    await c.send_message(chat_id, f"🏆 <b>TOP REFERRERS</b>\n━━━━━━━━━━━━━━━━━━━━\n{lines}", parse_mode=ParseMode.HTML)

@app.on_message(filters.command("profile") & filters.private)
async def user_profile(c, m):
    await show_profile_text(c, m.chat.id, str(m.from_user.id))

# ─── Core Access + Dice / Media ──────────
async def process_user_request(c, chat_id, uid_str, message_obj, clicked_btn=False):
    user = db["users"][uid_str]
    uid = int(uid_str)
    vip = is_vip(uid_str)

    if db["main_channel"] and not vip:
        try:
            member = await c.get_chat_member(db["main_channel"]["id"], uid)
            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                raise UserNotParticipant
        except:
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("🛡️ JOIN MAIN CHANNEL", url=db["main_channel"]["link"])],
                [InlineKeyboardButton("♻️ I Joined — Check Again", callback_data="check_join")]
            ])
            return await send_or_edit(c, message_obj, "🛑 <b>Access Denied!</b>\nJoin our Main Channel to use this bot.", btn)

    if db["backup_channel"] and user["roll_count"] == 0 and not vip:
        backup_id = db["backup_channel"]["id"]
        if not await has_pending_join_request(c, backup_id, uid):
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 Send Join Request", url=db["backup_channel"]["link"])],
                [InlineKeyboardButton("♻️ Sent — Check Now", callback_data="check_join")]
            ])
            return await send_or_edit(c, message_obj, "⚠️ <b>Security Check!</b>\nSend a join request to our backup channel first.", btn)

    serial_index = user.get("roll_count", 0)
    if serial_index < len(db["fsub_channels"]) and not vip:
        ch = db["fsub_channels"][serial_index]
        if not await has_pending_join_request(c, ch["id"], uid):
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 Send Join Request", url=ch["link"])],
                [InlineKeyboardButton("♻️ Sent — Check Now", callback_data="check_join")]
            ])
            return await send_or_edit(c, message_obj, f"🔒 <b>Unlock Next Roll!</b>\nSend a request to Channel #{serial_index+1} to continue.", btn)

    if not vip and serial_index >= len(db["fsub_channels"]):
        now = time.time()
        if user["cooldown_until"] == 0:
            user["cooldown_until"] = now + (db["cooldown_hours"] * 3600)
        if now < user["cooldown_until"]:
            left_hrs = round((user["cooldown_until"] - now) / 3600, 1)
            ref_link = f"https://t.me/{bot_info.get('username','bot')}?start=ref_{uid_str}"
            text = f"⏳ <b>Limit Reached!</b> Come back in <b>{left_hrs}h</b>.\n\n🚀 Share your link:\n<code>{ref_link}</code>"
            return await send_or_edit(c, message_obj, text, None)

    if clicked_btn:
        try:
            await message_obj.edit_text("✅ <b>Verified! Rolling dice...</b>", parse_mode=ParseMode.HTML)
        except:
            pass

    user["roll_count"] = user.get("roll_count", 0) + 1
    user["cooldown_until"] = 0
    await send_dice_and_media(c, chat_id, uid_str)

async def send_or_edit(c, msg_obj, text, markup):
    try:
        if hasattr(msg_obj, 'text') and msg_obj.text and not msg_obj.text.startswith("/"):
            await msg_obj.edit_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
            return
    except:
        pass
    await c.send_message(msg_obj.chat.id, text, reply_markup=markup, parse_mode=ParseMode.HTML)

async def send_dice_and_media(c, chat_id, uid_str):
    if not db["video_channels"]:
        return await c.send_message(chat_id, "⚠️ Video channel not configured yet.")
    user = db["users"][uid_str]
    if user.get("history_msgs"):
        try:
            await c.delete_messages(chat_id, user["history_msgs"])
        except:
            pass
    user["history_msgs"] = []

    suspense = await c.send_message(chat_id, "🎲 <b>Rolling the dice...</b>", parse_mode=ParseMode.HTML)
    user["history_msgs"].append(suspense.id)

    dice_msg = await c.send_dice(chat_id, "🎲")
    user["history_msgs"].append(dice_msg.id)
    await asyncio.sleep(3)
    dice_val = dice_msg.dice.value

    try:
        await suspense.edit_text(f"⚡ <b>Found {dice_val}!</b> Loading rare content...", parse_mode=ParseMode.HTML)
    except:
        pass
    await asyncio.sleep(1)
    try:
        await suspense.edit_text("✅ <b>Sending your videos now!</b>", parse_mode=ParseMode.HTML)
    except:
        pass
    await asyncio.sleep(0.5)

    video_count = 6 if dice_val == 6 else (3 if dice_val in (1, 2) else dice_val)
    if dice_val == 6:
        jackpot = await c.send_message(chat_id, "🎉 <b>JACKPOT! Maximum videos unlocked!</b>", parse_mode=ParseMode.HTML)
        user["history_msgs"].append(jackpot.id)

    protect = db.get("protect_content", True)
    del_mins = db["delete_time"]
    vid_ch = random.choice(db["video_channels"])
    effective_max = MAX_ID if MAX_ID else VID_MAX_ID
    effective_min = MIN_ID
    if effective_max < effective_min:
        effective_max = effective_min + 100

    success = 0
    last_sent_id = None
    tried_ids = set()
    for _ in range(video_count):
        sent_this = False
        for _try in range(20):
            rand_id = random.randint(effective_min, effective_max)
            if rand_id in tried_ids:
                continue
            tried_ids.add(rand_id)
            try:
                sent = await c.copy_message(chat_id, vid_ch, rand_id, protect_content=protect)
                user["history_msgs"].append(sent.id)
                last_sent_id = sent.id
                success += 1
                sent_this = True
                break
            except:
                continue
        if not sent_this:
            await scan_video_channel_max_id()

    if success > 0:
        user["total_media"] += success
        if last_sent_id:
            kb = []
            if db["custom_buttons"]:
                first = db["custom_buttons"][0]
                kb.append([InlineKeyboardButton(first["text"], url=first["url"])])
            kb.append([InlineKeyboardButton("🎲 Roll Again", callback_data="roll_dice")])
            try:
                await c.edit_message_reply_markup(chat_id, last_sent_id, reply_markup=InlineKeyboardMarkup(kb))
            except:
                info = await c.send_message(chat_id, f"✅ <b>Sent {success} video{'s' if success>1 else ''}!</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
                user["history_msgs"].append(info.id)

        note = await c.send_message(chat_id, f"⏳ <b>Note:</b> Videos will self-destruct in <b>{del_mins} minutes</b>.", parse_mode=ParseMode.HTML)
        user["history_msgs"].append(note.id)
        asyncio.create_task(delete_later(c, chat_id, user["history_msgs"].copy(), del_mins, uid_str))
    else:
        await c.send_message(chat_id, "⚠️ Couldn't fetch videos right now. Please try again later.\n<i>Admin tip: Run 🔍 SCAN VIDEO CH to update max ID.</i>", parse_mode=ParseMode.HTML)

async def delete_later(c, chat_id, msg_ids, mins, uid_str):
    await asyncio.sleep(mins * 60)
    try:
        await c.delete_messages(chat_id, msg_ids)
        if uid_str in db["users"] and db["users"][uid_str].get("history_msgs") == msg_ids:
            db["users"][uid_str]["history_msgs"] = []
    except:
        pass

# ─── Startup ──────────────────────────────
async def main():
    global VID_MAX_ID
    await app.start()
    me = await app.get_me()
    bot_info["username"] = me.username
    print(f"🤖 Ultra Premium Bot Started! @{me.username}")
    await load_db()
    if db.get("video_channels"):
        await scan_video_channel_max_id()
    asyncio.create_task(backup_db_loop())
    await idle()
    await app.stop()

if __name__ == "__main__":
    app.run(main())
