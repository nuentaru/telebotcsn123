import json
import logging
import base64
import time
from pymongo import MongoClient
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import os

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_ENV = os.getenv("ADMIN_ID")

if not TOKEN or not ADMIN_ID_ENV:
    raise Exception("❌ Thiếu BOT_TOKEN hoặc ADMIN_ID trong Environment Variables")

ADMINS = list(map(int, ADMIN_ID_ENV.split(",")))
ADMIN_LINK = "https://t.me/NGUYENNAM_888"
WELCOME_IMG = "images/welcome.jpg"
LA_BAI_IMG = "images/la_bai.jpg"
TOTAL_VAN_IMG = "images/total_van.jpg"

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise Exception("❌ Thiếu MONGO_URI trong Environment Variables")

client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000
)
mongo_db = client["telebot"]

col_keys = mongo_db["keys"]
col_users = mongo_db["users"]
col_admins = mongo_db["admins"]

# ================= DATABASE =================

def load_db():
    data = {
        "keys": {},
        "users": {},
        "admins": ADMINS.copy()
    }

    try:
        for k in col_keys.find():
            data["keys"][str(k["_id"])] = k.get("data", {})

        for u in col_users.find():
            data["users"][str(u["_id"])] = u.get("data", {})

        admin_doc = col_admins.find_one({"_id": "admins"})
        if admin_doc:
            data["admins"] = admin_doc.get("data", ADMINS.copy())

    except Exception as e:
        logging.error(f"Lỗi load MongoDB: {e}")

    return data


def save_db():
    try:
        for k, v in db["keys"].items():
            col_keys.update_one({"_id": k}, {"$set": {"data": v}}, upsert=True)

        for u, v in db["users"].items():
            col_users.update_one({"_id": u}, {"$set": {"data": v}}, upsert=True)

        col_admins.update_one(
            {"_id": "admins"},
            {"$set": {"data": db["admins"]}},
            upsert=True
        )

    except Exception as e:
        logging.error(f"Lỗi save MongoDB: {e}")


def is_admin(uid):
    try:
        return int(uid) in db.get("admins", [])
    except:
        return False


def get_user(uid):
    uid = str(uid)
    if uid not in db["users"]:
        db["users"][uid] = {}
    return db["users"][uid]


db = load_db()

# ================= ADMIN =================

async def genkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("❌ KHÔNG CÓ QUYỀN")

    if not context.args:
        return await update.message.reply_text("❌ /genkey KEY")

    key = context.args[0].strip()

    if key in db["keys"]:
        return await update.message.reply_text("❌ KEY ĐÃ TỒN TẠI")

    db["keys"][key] = {
        "active": False,
        "pin": None,
        "xu": 0,
        "owner": None
    }

    save_db()
    await update.message.reply_text(f"✅ ĐÃ TẠO KEY: {key}")


async def active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("❌ KHÔNG CÓ QUYỀN")

    if len(context.args) < 3:
        return await update.message.reply_text("❌ /active KEY PIN XU")

    try:
        key = context.args[0]
        pin = context.args[1]
        xu = int(context.args[2])
    except:
        return await update.message.reply_text("❌ PIN hoặc XU không hợp lệ")

    data = db["keys"].get(key)
    if not data:
        return await update.message.reply_text("❌ KEY KHÔNG TỒN TẠI")

    data.update({
        "active": True,
        "pin": pin,
        "xu": xu
    })

    save_db()
    await update.message.reply_text(f"🔥 ĐÃ KÍCH HOẠT {key}")


async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("❌ KHÔNG CÓ QUYỀN")

    if not context.args:
        return await update.message.reply_text("❌ /addadmin USER_ID")

    try:
        new_admin = int(context.args[0])
    except:
        return await update.message.reply_text("❌ USER_ID không hợp lệ")

    if new_admin in db["admins"]:
        return await update.message.reply_text("⚠️ ĐÃ LÀ ADMIN")

    db["admins"].append(new_admin)
    save_db()

    await update.message.reply_text(f"✅ ĐÃ THÊM ADMIN: {new_admin}")


async def removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("❌ KHÔNG CÓ QUYỀN")

    if not context.args:
        return await update.message.reply_text("❌ /removeadmin USER_ID")

    try:
        uid = int(context.args[0])
    except:
        return await update.message.reply_text("❌ USER_ID không hợp lệ")

    if uid not in db["admins"]:
        return await update.message.reply_text("❌ KHÔNG PHẢI ADMIN")

    db["admins"].remove(uid)
    save_db()

    await update.message.reply_text(f"✅ ĐÃ XOÁ ADMIN: {uid}")


async def listadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return await update.message.reply_text("❌ KHÔNG CÓ QUYỀN")

    text = "📋 DANH SÁCH ADMIN\n━━━━━━━━━━━━━━━━━━\n"
    for a in db["admins"]:
        text += f"{a}\n"

    await update.message.reply_text(text)


async def listkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return await update.message.reply_text("❌ KHÔNG CÓ QUYỀN")

    if not db["keys"]:
        return await update.message.reply_text("❌ KHÔNG CÓ KEY")

    text = "📋 DANH SÁCH KEY\n━━━━━━━━━━━━━━━━━━\n"

    for k, v in db["keys"].items():
        status = "ĐÃ KÍCH HOẠT" if v.get("active") else "CHƯA KÍCH HOẠT"
        text += f"{k} | {status} | {v.get('xu',0)} xu\n"

    await update.message.reply_text(text)


async def delkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return await update.message.reply_text("❌ KHÔNG CÓ QUYỀN")

    if not context.args:
        return await update.message.reply_text("❌ /delkey KEY")

    key = context.args[0]

    if key not in db["keys"]:
        return await update.message.reply_text("❌ KEY KHÔNG TỒN TẠI")

    del db["keys"][key]
    save_db()

    await update.message.reply_text(f"✅ ĐÃ XOÁ KEY: {key}")


async def addxu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return await update.message.reply_text("❌ KHÔNG CÓ QUYỀN")

    if len(context.args) < 2:
        return await update.message.reply_text("❌ /addxu KEY SỐ_XU")

    key = context.args[0]
    try:
        amount = int(context.args[1])
    except:
        return await update.message.reply_text("❌ SỐ XU KHÔNG HỢP LỆ")

    data = db["keys"].get(key)
    if not data:
        return await update.message.reply_text("❌ KEY KHÔNG TỒN TẠI")

    data["xu"] = data.get("xu", 0) + amount
    save_db()

    await update.message.reply_text(f"✅ +{amount} XU cho {key}")


async def removexu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return await update.message.reply_text("❌ KHÔNG CÓ QUYỀN")

    if len(context.args) < 2:
        return await update.message.reply_text("❌ /removexu KEY SỐ_XU")

    key = context.args[0]
    try:
        amount = int(context.args[1])
    except:
        return await update.message.reply_text("❌ SỐ XU KHÔNG HỢP LỆ")

    data = db["keys"].get(key)
    if not data:
        return await update.message.reply_text("❌ KEY KHÔNG TỒN TẠI")

    data["xu"] = max(0, data.get("xu", 0) - amount)
    save_db()

    await update.message.reply_text(f"✅ -{amount} XU của {key}")

# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎉 CHÀO MỪNG BẠN ĐẾN VỚI BOT U888 2026\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🤖 HỖ TRỢ PHÂN TÍCH BCR\n"
        "🛡️ CAM KẾT BẢO MẬT THÔNG TIN\n"
        "📊 ĐƯA RA DỰ ĐOÁN NHANH & ỔN ĐỊNH\n"
        "⚙️ CÔNG CỤ HOẠT ĐỘNG THEO HỆ THỐNG RIÊNG\n\n"
        "⚠️ LƯU Ý:\n"
        "• CHỈ SỬ DỤNG KHI CÓ HƯỚNG DẪN\n"
        "• KHÔNG TỰ Ý ÁP DỤNG SAI CÁCH\n\n"
        "👉 VUI LÒNG CHỌN BÊN DƯỚI ĐỂ TIẾP TỤC"
    )

    kb = [[
        InlineKeyboardButton("✅ ĐỒNG Ý", callback_data="agree"),
        InlineKeyboardButton("❌ TỪ CHỐI", callback_data="deny")
    ]]

    with open(WELCOME_IMG, "rb") as photo:
        await update.message.reply_photo(
            photo=photo,
            caption=text,
            reply_markup=InlineKeyboardMarkup(kb)
        )
    

# ================= BUTTON =================

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try:
        await q.answer()
    except:
        pass

    uid = str(q.from_user.id)

    # ✅ FIX: tránh crash user chưa tồn tại
    if uid not in db["users"]:
        db["users"][uid] = {}
        save_db()

    if q.data == "agree":
        kb = [
            [InlineKeyboardButton("🔑 ĐĂNG NHẬP", callback_data="login")],
            [InlineKeyboardButton("📞 LIÊN HỆ ADMIN", url=ADMIN_LINK)]
        ]

        await q.message.edit_text(
            f"👋 XIN CHÀO {q.from_user.first_name}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🔐 BẠN CẦN ĐĂNG NHẬP ĐỂ SỬ DỤNG\n\n"
            "📌 CHƯA CÓ KEY → LIÊN HỆ ADMIN",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif q.data == "deny":
        await q.message.edit_text("❌ Bạn đã từ chối sử dụng bot.")

    elif q.data == "login":
        db["users"][uid] = {"step": "login"}
        save_db()
        await q.message.reply_text(
            "🔑 VUI LÒNG NHẬP KEY HOẶC KEY + PIN\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "VD:\nABC123\nABC123 1111"
        )

    elif q.data == "menu":
        if "key" not in db["users"][uid]:
            return await q.answer("❌ CHƯA ĐĂNG NHẬP", show_alert=True)

        key = db["users"][uid]["key"]

        if key not in db["keys"]:
            return await q.answer("❌ KEY KHÔNG TỒN TẠI", show_alert=True)

        xu = db["keys"][key]["xu"]

        kb = [
            [InlineKeyboardButton("🎯 BẮT ĐẦU PHÂN TÍCH", callback_data="chonban")],
            [InlineKeyboardButton("🔙 QUAY LẠI", callback_data="back_login")]
        ]

        await q.message.edit_text(
            f"📊 MENU HỆ THỐNG\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"👤 TÀI KHOẢN: {key}\n"
            f"💰 SỐ DƯ: {xu} XU",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif q.data == "back_login":
        db["users"][uid] = {"step": "login"}
        save_db()
        await q.message.edit_text("🔑 NHẬP LẠI KEY + PIN")

    elif q.data == "chonban":
        kb = []
        row = []
        for i in range(1, 10):
            row.append(InlineKeyboardButton(f"B{i}", callback_data=f"ban_{i}"))
            if len(row) == 3:
                kb.append(row)
                row = []
        if row:
            kb.append(row)

        row = []
        for i in range(1, 16):
            row.append(InlineKeyboardButton(f"C{str(i).zfill(2)}", callback_data=f"ban_C{i}"))
            if len(row) == 5:
                kb.append(row)
                row = []

        kb.append([InlineKeyboardButton("🔙 MENU", callback_data="menu")])

        await q.message.edit_text(
            "🎯 CHỌN BÀN PHÂN TÍCH\n━━━━━━━━━━━━━━━━━━",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif q.data.startswith("ban_"):
        ban = q.data.replace("ban_", "").upper()

        db["users"][uid]["step"] = "nhap_la"
        db["users"][uid]["ban"] = ban
        save_db()

        kb = []
        nums = [str(i) for i in range(10)]
        row = []
        for n in nums:
            row.append(InlineKeyboardButton(n, callback_data=f"la_{n}"))
            if len(row) == 5:
                kb.append(row)
                row = []
        if row:
            kb.append(row)

        kb.append([InlineKeyboardButton("🔙 CHỌN BÀN", callback_data="chonban")])

        try:
            await q.message.delete()
        except:
            pass

        with open(LA_BAI_IMG, "rb") as photo:
            await context.bot.send_photo(
                chat_id=q.message.chat.id,
                photo=photo,
                caption=(
                    f"🎯 BÀN {ban}\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    "📌 BAO NHIÊU LÁ BÀI?"
                ),
                reply_markup=InlineKeyboardMarkup(kb)
            )

    elif q.data.startswith("la_"):
        so_la = int(q.data.split("_")[1])

        db["users"][uid]["la"] = so_la
        db["users"][uid]["step"] = "nhap_van"
        db["users"][uid]["input_van"] = ""

        current = db["users"][uid]["input_van"]
        
        save_db()

        kb = []
        nums = [str(i) for i in range(10)]
        row = []
        for n in nums:
            row.append(InlineKeyboardButton(n, callback_data=f"van_{n}"))
            if len(row) == 5:
                kb.append(row)
                row = []
        if row:
            kb.append(row)

        kb.append([
            InlineKeyboardButton("❌ XÓA", callback_data="van_clear"),
            InlineKeyboardButton("✅ XÁC NHẬN", callback_data="van_ok")
        ])

        kb.append([InlineKeyboardButton("🔙 CHỌN LẠI", callback_data="chonban")])

        try:
            await q.message.delete()
        except:
            pass

        with open(TOTAL_VAN_IMG, "rb") as photo:
            await context.bot.send_photo(
                chat_id=q.message.chat.id,
                photo=photo,
                caption=(
                    "📊 TOTAL (SỐ VÁN BÀI)?\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    f"Đã nhập: {current}"
                ),
                reply_markup=InlineKeyboardMarkup(kb)
            )

    elif q.data.startswith("van_") and q.data not in ["van_ok", "van_clear"]:
        num = q.data.split("_")[1]
        db["users"][uid]["input_van"] += num
        save_db()

        current = db["users"][uid]["input_van"]

        kb = []
        nums = [str(i) for i in range(10)]
        row = []
        for n in nums:
            row.append(InlineKeyboardButton(n, callback_data=f"van_{n}"))
            if len(row) == 5:
                kb.append(row)
                row = []
        if row:
            kb.append(row)

        kb.append([
            InlineKeyboardButton("❌ XÓA", callback_data="van_clear"),
            InlineKeyboardButton("✅ XÁC NHẬN", callback_data="van_ok")
        ])

        kb.append([InlineKeyboardButton("🔙 CHỌN LẠI", callback_data="chonban")])

        try:
            await q.message.delete()
        except:
            pass

        with open(TOTAL_VAN_IMG, "rb") as photo:
            await context.bot.send_photo(
                chat_id=q.message.chat.id,
                photo=photo,
                caption=(
                    "📊 TOTAL (SỐ VÁN BÀI)?\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    f"Đã nhập: {current}"
                ),
                reply_markup=InlineKeyboardMarkup(kb)
            )

    elif q.data == "van_clear":
        db["users"][uid]["input_van"] = ""
        save_db()
        await q.answer("Đã xóa")

    elif q.data == "van_ok":
        data_user = db["users"][uid]

        if not data_user.get("input_van"):
            return await q.answer("❌ CHƯA NHẬP", show_alert=True)

        if "key" not in data_user:
            return await q.answer("❌ CHƯA ĐĂNG NHẬP", show_alert=True)

        if "la" not in data_user:
            return await q.answer("❌ THIẾU DỮ LIỆU", show_alert=True)

        key = data_user["key"]

        so_van = int(data_user["input_van"])
        so_la = data_user["la"]

        tong = so_la + so_van
        if so_la >= 6:
            tong += 1

        ket_qua = "CON" if tong % 2 == 0 else "CÁI"

        if key not in db["keys"]:
            return await q.message.edit_text("❌ KEY KHÔNG TỒN TẠI")
        if db["keys"][key]["xu"] <= 0:
            return await q.message.edit_text(
                "❌ Đã hoàn thành\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "Kết quả kiểm tra \n"
                "-> KHÔNG ĐỦ XU \n"
                "━━━━━━━━━━━━━━━━━━\n"
                "💰 Số dư: 0 xu\n"
                "⚠️  BẠN KHÔNG ĐỦ XU ĐỂ CÓ THỂ TIẾP TỤC, VUI LÒNG LIÊN HỆ ADMIN ĐỂ ĐƯỢC CẤP XU"
            )

        db["keys"][key]["xu"] -= 1
        db["users"][uid]["input_van"] = ""

        save_db()

        logging.info(f"User {uid} dùng 1 xu | Key: {key} | Còn: {db['keys'][key]['xu']}")

        kb = [
            [InlineKeyboardButton("🔁 NHẬP LẠI", callback_data="replay")],
            [InlineKeyboardButton("🔙 CHỌN BÀN KHÁC", callback_data="chonban")]
        ]

        await q.message.edit_text(
            "✅ Đã hoàn thành\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Kết quả kiểm tra\n"
            f"-> {ket_qua}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"💰 Số dư: {db['keys'][key]['xu']} xu",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif q.data == "replay":
        ban = db["users"][uid].get("ban")

        db["users"][uid]["step"] = "nhap_la"
        db["users"][uid]["input_van"] = ""
        save_db()

        kb = []
        nums = [str(i) for i in range(10)]
        row = []
        for n in nums:
            row.append(InlineKeyboardButton(n, callback_data=f"la_{n}"))
            if len(row) == 5:
                kb.append(row)
                row = []
        if row:
            kb.append(row)

        kb.append([InlineKeyboardButton("🔙 CHỌN BÀN", callback_data="chonban")])

        await q.message.edit_text(
            f"🎯 BÀN {ban}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📌 BAO NHIÊU LÁ BÀI?",
            reply_markup=InlineKeyboardMarkup(kb)
        )

# ================= HANDLE =================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.message.from_user.id)
    text = update.message.text.strip()

    if uid not in db["users"]:
        return await update.message.reply_text("👉 /start TRƯỚC")

    if db["users"][uid].get("step") == "login":
        parts = text.split()

        if len(parts) == 1:
            key = parts[0]

            if key not in db["keys"]:
                return await update.message.reply_text("❌ KEY KHÔNG TỒN TẠI")

            if not db["keys"][key]["active"]:
                kb = [[InlineKeyboardButton("📞 LIÊN HỆ ADMIN", url=ADMIN_LINK)]]
                return await update.message.reply_text(
                    "⏳ KEY CHƯA KÍCH HOẠT\nLIÊN HỆ ADMIN",
                    reply_markup=InlineKeyboardMarkup(kb)
                )

            return await update.message.reply_text("👉 NHẬP THÊM PIN")

        if len(parts) == 2:
            key, pin = parts

            if key not in db["keys"]:
                return await update.message.reply_text("❌ KEY SAI")

            data = db["keys"][key]

            if not data["active"]:
                kb = [[InlineKeyboardButton("📞 LIÊN HỆ ADMIN", url=ADMIN_LINK)]]
                return await update.message.reply_text(
                    "❌ CHƯA KÍCH HOẠT",
                    reply_markup=InlineKeyboardMarkup(kb)
                )

            if data["owner"] is None:
                data["owner"] = uid
            elif data["owner"] != uid:
                return await update.message.reply_text("❌ KEY ĐÃ BỊ SỬ DỤNG")

            if pin != data["pin"]:
                return await update.message.reply_text("❌ PIN SAI")

            data["owner"] = uid
            db["users"][uid] = {"step": "menu", "key": key}
            save_db()

            logging.info(f"User {uid} login với key {key}")

            kb = [[InlineKeyboardButton("📊 MENU", callback_data="menu")]]

            return await update.message.reply_text(
                f"✅ ĐĂNG NHẬP THÀNH CÔNG\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"TÊN TÀI KHOẢN: {key}\n"
                f"SỐ DƯ : {data['xu']} XU",
                reply_markup=InlineKeyboardMarkup(kb)
            )

async def error_handler(update, context):
    logging.error(f"Lỗi: {context.error}")

# ================= RUN =================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("addadmin", addadmin))
app.add_handler(CommandHandler("addxu", addxu))
app.add_handler(CommandHandler("removexu", removexu))
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("genkey", genkey))
app.add_handler(CommandHandler("active", active))
app.add_handler(CommandHandler("removeadmin", removeadmin))
app.add_handler(CommandHandler("listadmin", listadmin))
app.add_handler(CommandHandler("listkey", listkey))
app.add_handler(CommandHandler("delkey", delkey))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_error_handler(error_handler)



# ================= MAIN =================

if __name__ == "__main__":
    print("🤖 BOT ĐANG CHẠY...")
import asyncio

async def remove_webhook():
    await app.bot.delete_webhook(drop_pending_updates=True)

asyncio.run(remove_webhook())
    app.run_polling()
