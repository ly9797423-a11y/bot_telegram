import asyncio
import logging
import os
import json
import datetime
import tempfile
from typing import Dict, List, Tuple, Optional
from enum import Enum
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile, ChatPermissions
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)
from telegram.constants import ParseMode

import pymongo
from pymongo import MongoClient
import google.generativeai as genai
from bidi.algorithm import get_display
import arabic_reshaper
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import letter
from PyPDF2 import PdfReader, PdfWriter
import requests
from PIL import Image
import io

# ==================== Configuration ====================
TOKEN = "8481569753:AAH3alhJ0hcHldht-PxV7j8TzBlRsMqAqGI"
BOT_USERNAME = "@FC4Xbot"
ADMIN_ID = 6130994941
SUPPORT_USERNAME = "Allawi04@"
CHANNEL_USERNAME = "@FCJCV"
GEMINI_API_KEY = "AIzaSyARsl_YMXA74bPQpJduu0jJVuaku7MaHuY"

# MongoDB setup
client = MongoClient("mongodb://localhost:27017/")
db = client["telegram_learning_bot"]
users_col = db["users"]
courses_col = db["courses"]
questions_col = db["questions"]
materials_col = db["materials"]
vip_subscriptions_col = db["vip_subscriptions"]
vip_lectures_col = db["vip_lectures"]
transactions_col = db["transactions"]
invites_col = db["invites"]
settings_col = db["settings"]

# Initialize Gemini AI
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Register Arabic font
try:
    pdfmetrics.registerFont(TTFont('Arabic', 'arial.ttf'))
except:
    # Fallback font
    pass

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== Enums & States ====================
class UserState(Enum):
    WAITING_COURSE1 = 1
    WAITING_COURSE2 = 2
    WAITING_COURSE3 = 3
    WAITING_PDF = 4
    WAITING_QUESTION = 5
    WAITING_ANSWER = 6
    WAITING_CHARGE_AMOUNT = 7
    WAITING_PRICE_CHANGE = 8
    WAITING_BROADCAST = 9
    WAITING_VIP_PRICE = 10
    WAITING_VIP_LECTURE_TITLE = 11
    WAITING_VIP_LECTURE_DESC = 12
    WAITING_VIP_LECTURE_PRICE = 13
    WAITING_VIP_LECTURE_VIDEO = 14
    WAITING_WITHDRAW_AMOUNT = 15
    WAITING_SERVICE_PRICE = 16
    WAITING_INVITE_REWARD = 17

# ==================== Utility Functions ====================
def format_number(num):
    return f"{num:,}"

def get_user(user_id):
    user = users_col.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "balance": 1000,  # Welcome bonus
            "invited_by": None,
            "invite_code": str(user_id)[-6:],
            "invited_count": 0,
            "vip_balance": 0,
            "vip_until": None,
            "banned": False,
            "course_scores": {},
            "created_at": datetime.datetime.now()
        }
        users_col.insert_one(user)
    return user

def update_user(user_id, update_data):
    users_col.update_one({"user_id": user_id}, {"$set": update_data})

def get_setting(key, default=None):
    setting = settings_col.find_one({"key": key})
    return setting["value"] if setting else default

def update_setting(key, value):
    settings_col.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)

# Initialize default settings
default_settings = {
    "service_price": 1000,
    "vip_subscription_price": 5000,
    "invite_reward": 500,
    "exemption_enabled": True,
    "summary_enabled": True,
    "qa_enabled": True,
    "help_enabled": True,
    "vip_enabled": True,
    "min_withdraw": 1000
}

for key, value in default_settings.items():
    if not settings_col.find_one({"key": key}):
        settings_col.insert_one({"key": key, "value": value})

# ==================== Keyboard Layouts ====================
def main_menu_keyboard(user_id):
    user = get_user(user_id)
    keyboard = []
    
    # Row 1
    if get_setting("exemption_enabled"):
        keyboard.append([InlineKeyboardButton("📊 حساب درجة الاعفاء", callback_data="service_exemption")])
    
    if get_setting("summary_enabled"):
        keyboard.append([InlineKeyboardButton("📚 تلخيص الملازم", callback_data="service_summary")])
    
    # Row 2
    if get_setting("qa_enabled"):
        keyboard.append([InlineKeyboardButton("❓ سؤال وجواب بالذكاء", callback_data="service_qa")])
    
    if get_setting("help_enabled"):
        keyboard.append([InlineKeyboardButton("🆘 ساعدوني طالب", callback_data="service_help")])
    
    # Row 3
    keyboard.append([InlineKeyboardButton("📖 ملازمي ومرشحاتي", callback_data="materials")])
    
    if get_setting("vip_enabled"):
        if user.get("vip_until") and user["vip_until"] > datetime.datetime.now():
            keyboard.append([InlineKeyboardButton("🎓 محاضرات VIP", callback_data="vip_lectures")])
        else:
            keyboard.append([InlineKeyboardButton("⭐ اشتراك VIP", callback_data="vip_subscribe")])
    
    # Row 4
    keyboard.append([
        InlineKeyboardButton("💰 رصيدي", callback_data="balance"),
        InlineKeyboardButton("👥 دعوة صديق", callback_data="invite")
    ])
    
    # Row 5 - Support & Channel
    keyboard.append([
        InlineKeyboardButton("📢 قناة البوت", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"),
        InlineKeyboardButton("🛟 الدعم الفني", url=f"https://t.me/{SUPPORT_USERNAME.replace('@', '')}")
    ])
    
    # Admin panel button (only for admin)
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👑 لوحة التحكم", callback_data="admin_panel")])
    
    return InlineKeyboardMarkup(keyboard)

def admin_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 الاحصائيات", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 المستخدمين", callback_data="admin_users")],
        [InlineKeyboardButton("💰 شحن رصيد", callback_data="admin_charge")],
        [InlineKeyboardButton("💸 خصم رصيد", callback_data="admin_deduct")],
        [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban")],
        [InlineKeyboardButton("✅ فك حظر مستخدم", callback_data="admin_unban")],
        [InlineKeyboardButton("⚙️ ادارة الخدمات", callback_data="admin_services")],
        [InlineKeyboardButton("💳 تغيير الاسعار", callback_data="admin_prices")],
        [InlineKeyboardButton("📢 اذاعة", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🎓 مشتركين VIP", callback_data="admin_vip_users")],
        [InlineKeyboardButton("📹 ادارة محاضرات VIP", callback_data="admin_vip_lectures")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def services_management_keyboard():
    services = [
        ("exemption", "حساب درجة الاعفاء"),
        ("summary", "تلخيص الملازم"),
        ("qa", "سؤال وجواب"),
        ("help", "ساعدوني طالب"),
        ("vip", "خدمة VIP")
    ]
    
    keyboard = []
    for service_key, service_name in services:
        status = "✅" if get_setting(f"{service_key}_enabled") else "❌"
        keyboard.append([InlineKeyboardButton(f"{status} {service_name}", callback_data=f"toggle_{service_key}")])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def price_management_keyboard():
    keyboard = [
        [InlineKeyboardButton("💰 سعر الخدمات العامة", callback_data="price_service")],
        [InlineKeyboardButton("⭐ سعر اشتراك VIP", callback_data="price_vip")],
        [InlineKeyboardButton("🎁 مكافأة الدعوة", callback_data="price_invite")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== Command Handlers ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    # Check if user is banned
    if user.get("banned"):
        await update.message.reply_text("❌ تم حظرك من استخدام البوت.")
        return
    
    # Welcome message
    welcome_text = f"""
    🎉 أهلاً بك {update.effective_user.first_name} في بوت *يلا نتعلم*!

    *🎁 هدية ترحيبية:* 1,000 دينار
    *💰 رصيدك الحالي:* {format_number(user['balance'])} دينار

    اختر الخدمة التي تريدها من القائمة:
    """
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu_keyboard(user_id)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
    *🆘 طريقة استخدام البوت:*

    1️⃣ اختر الخدمة المطلوبة من القائمة
    2️⃣ كل خدمة تتطلب دفع رسوم (يمكن تغييرها من لوحة التحكم)
    3️⃣ يمكنك شحن رصيدك عبر التواصل مع الدعم الفني
    4️⃣ شارك رابط الدعوة لتحصل على مكافأة

    *📞 الدعم الفني:* @Allawi04
    *📢 قناة البوت:* @FCJCV
    """
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

# ==================== Callback Handlers ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Main menu handler
    if data == "main_menu":
        await query.edit_message_text(
            "🏠 *القائمة الرئيسية*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(user_id)
        )
        return
    
    # Service handlers
    elif data == "service_exemption":
        await exemption_service(query, context)
    elif data == "service_summary":
        await summary_service(query, context)
    elif data == "service_qa":
        await qa_service(query, context)
    elif data == "service_help":
        await help_service(query, context)
    elif data == "materials":
        await materials_service(query, context)
    elif data == "vip_subscribe":
        await vip_subscribe(query, context)
    elif data == "vip_lectures":
        await vip_lectures(query, context)
    elif data == "balance":
        await show_balance(query, context)
    elif data == "invite":
        await invite_friend(query, context)
    
    # Admin handlers
    elif data == "admin_panel":
        if user_id == ADMIN_ID:
            await query.edit_message_text(
                "👑 *لوحة تحكم المدير*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=admin_panel_keyboard()
            )
    elif data == "admin_stats":
        await admin_stats(query, context)
    elif data == "admin_users":
        await admin_users(query, context)
    elif data == "admin_charge":
        await admin_charge(query, context)
    elif data == "admin_deduct":
        await admin_deduct(query, context)
    elif data == "admin_ban":
        await admin_ban(query, context)
    elif data == "admin_unban":
        await admin_unban(query, context)
    elif data == "admin_services":
        await admin_services(query, context)
    elif data == "admin_prices":
        await admin_prices(query, context)
    elif data == "admin_broadcast":
        await admin_broadcast(query, context)
    elif data == "admin_vip_users":
        await admin_vip_users(query, context)
    elif data == "admin_vip_lectures":
        await admin_vip_lectures(query, context)
    
    # Service toggle handlers
    elif data.startswith("toggle_"):
        service = data.replace("toggle_", "")
        await toggle_service(query, context, service)
    
    # Price management handlers
    elif data == "price_service":
        await change_service_price(query, context)
    elif data == "price_vip":
        await change_vip_price(query, context)
    elif data == "price_invite":
        await change_invite_reward(query, context)

async def exemption_service(query, context):
    user_id = query.from_user.id
    user = get_user(user_id)
    
    # Check if service is enabled
    if not get_setting("exemption_enabled"):
        await query.edit_message_text("❌ هذه الخدمة معطلة حالياً.")
        return
    
    # Check balance
    service_price = get_setting("service_price")
    if user["balance"] < service_price:
        await query.edit_message_text(
            f"❌ رصيدك غير كافي. سعر الخدمة: {format_number(service_price)} دينار\n"
            f"💰 رصيدك الحالي: {format_number(user['balance'])} دينار"
        )
        return
    
    # Deduct balance after service completion
    context.user_data['pending_payment'] = service_price
    context.user_data['service'] = 'exemption'
    
    # Start exemption process
    await query.edit_message_text(
        "📊 *حساب درجة الاعفاء*\n\n"
        "أدخل درجة الكورس الأول (0-100):",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['state'] = UserState.WAITING_COURSE1

async def summary_service(query, context):
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if not get_setting("summary_enabled"):
        await query.edit_message_text("❌ هذه الخدمة معطلة حالياً.")
        return
    
    service_price = get_setting("service_price")
    if user["balance"] < service_price:
        await query.edit_message_text(
            f"❌ رصيدك غير كافي. سعر الخدمة: {format_number(service_price)} دينار\n"
            f"💰 رصيدك الحالي: {format_number(user['balance'])} دينار"
        )
        return
    
    context.user_data['pending_payment'] = service_price
    context.user_data['service'] = 'summary'
    
    await query.edit_message_text(
        "📚 *تلخيص الملازم*\n\n"
        "أرسل ملف PDF الذي تريد تلخيصه:",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['state'] = UserState.WAITING_PDF

async def qa_service(query, context):
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if not get_setting("qa_enabled"):
        await query.edit_message_text("❌ هذه الخدمة معطلة حالياً.")
        return
    
    service_price = get_setting("service_price")
    if user["balance"] < service_price:
        await query.edit_message_text(
            f"❌ رصيدك غير كافي. سعر الخدمة: {format_number(service_price)} دينار\n"
            f"💰 رصيدك الحالي: {format_number(user['balance'])} دينار"
        )
        return
    
    context.user_data['pending_payment'] = service_price
    context.user_data['service'] = 'qa'
    
    await query.edit_message_text(
        "❓ *سؤال وجواب بالذكاء الاصطناعي*\n\n"
        "أرسل سؤالك (نص أو صورة):",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['state'] = UserState.WAITING_QUESTION

async def help_service(query, context):
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if not get_setting("help_enabled"):
        await query.edit_message_text("❌ هذه الخدمة معطلة حالياً.")
        return
    
    service_price = get_setting("service_price")
    if user["balance"] < service_price:
        await query.edit_message_text(
            f"❌ رصيدك غير كافي. سعر الخدمة: {format_number(service_price)} دينار\n"
            f"💰 رصيدك الحالي: {format_number(user['balance'])} دينار"
        )
        return
    
    # Deduct payment first for help service
    new_balance = user["balance"] - service_price
    update_user(user_id, {"balance": new_balance})
    
    # Log transaction
    transactions_col.insert_one({
        "user_id": user_id,
        "type": "help_service",
        "amount": -service_price,
        "balance_after": new_balance,
        "timestamp": datetime.datetime.now()
    })
    
    await query.edit_message_text(
        "🆘 *ساعدوني طالب*\n\n"
        "أرسل سؤالك وسيتم عرضه في قسم المساعدة للإجابة عليه:",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['state'] = UserState.WAITING_QUESTION
    context.user_data['service'] = 'help'

async def materials_service(query, context):
    materials = list(materials_col.find({}))
    
    if not materials:
        await query.edit_message_text("📭 لا توجد مواد حالياً.")
        return
    
    keyboard = []
    for material in materials:
        btn_text = f"{material['name']} - {material['stage']}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"material_{material['_id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
    
    await query.edit_message_text(
        "📖 *ملازمي ومرشحاتي*\n\n"
        "اختر المادة التي تريدها:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def vip_subscribe(query, context):
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if not get_setting("vip_enabled"):
        await query.edit_message_text("❌ خدمة VIP معطلة حالياً.")
        return
    
    # Check if already VIP
    if user.get("vip_until") and user["vip_until"] > datetime.datetime.now():
        remaining = user["vip_until"] - datetime.datetime.now()
        days = remaining.days
        await query.edit_message_text(
            f"⭐ أنت مشترك VIP بالفعل!\n"
            f"⏳ المتبقي: {days} يوم"
        )
        return
    
    vip_price = get_setting("vip_subscription_price")
    
    text = f"""
    ⭐ *اشتراك VIP*

    *المميزات:*
    ✅ رفع محاضرات فيديو
    ✅ تحصيل 60% من أرباح المحاضرات
    ✅ قسم خاص للمحاضرات
    ✅ دعم أولوية

    *السعر الشهري:* {format_number(vip_price)} دينار

    *للاستفسار:* @{SUPPORT_USERNAME.replace('@', '')}
    """
    
    keyboard = [
        [InlineKeyboardButton("💳 اشترك الآن", callback_data="confirm_vip_subscription")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def vip_lectures(query, context):
    user_id = query.from_user.id
    user = get_user(user_id)
    
    # Check VIP status
    if not user.get("vip_until") or user["vip_until"] < datetime.datetime.now():
        await query.edit_message_text(
            "❌ هذه الخدمة للمشتركين في VIP فقط.\n"
            "اشترك من زر ⭐ اشتراك VIP"
        )
        return
    
    lectures = list(vip_lectures_col.find({"approved": True}))
    
    if not lectures:
        await query.edit_message_text("📭 لا توجد محاضرات VIP حالياً.")
        return
    
    keyboard = []
    for lecture in lectures:
        price_text = "مجاني" if lecture["price"] == 0 else f"{format_number(lecture['price'])} دينار"
        btn_text = f"{lecture['title']} ({price_text})"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"lecture_{lecture['_id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
    
    await query.edit_message_text(
        "🎓 *محاضرات VIP*\n\n"
        "اختر المحاضرة التي تريدها:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_balance(query, context):
    user_id = query.from_user.id
    user = get_user(user_id)
    
    balance_text = f"""
    💰 *حسابك المالي*

    *الرصيد الرئيسي:* {format_number(user['balance'])} دينار
    *رصيد الأرباح (VIP):* {format_number(user.get('vip_balance', 0))} دينار
    
    *عدد الدعوات:* {user.get('invited_count', 0)}
    """
    
    if user.get("vip_until") and user["vip_until"] > datetime.datetime.now():
        remaining = user["vip_until"] - datetime.datetime.now()
        balance_text += f"\n*⭐ اشتراك VIP:* {remaining.days} يوم متبقي"
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]
    
    await query.edit_message_text(
        balance_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def invite_friend(query, context):
    user_id = query.from_user.id
    user = get_user(user_id)
    
    invite_reward = get_setting("invite_reward")
    invite_link = f"https://t.me/{BOT_USERNAME.replace('@', '')}?start={user['invite_code']}"
    
    # Special description for VIP users
    if user.get("vip_until") and user["vip_until"] > datetime.datetime.now():
        description = "🎓 انضم لأفضل بوت تعليمي مع محاضرات VIP حصرية!"
    else:
        description = "🎓 انضم لأفضل بوت تعليمي واحصل على هدية مجانية!"
    
    text = f"""
    👥 *دعوة صديق*

    {description}

    *مكافأة الدعوة:* {format_number(invite_reward)} دينار لكل صديق

    *رابط الدعوة الخاص بك:*
    `{invite_link}`

    *عدد المدعوين:* {user.get('invited_count', 0)}
    """
    
    keyboard = [
        [InlineKeyboardButton("📤 مشاركة الرابط", url=f"https://t.me/share/url?url={invite_link}&text={description}")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ==================== Admin Handlers ====================
async def admin_stats(query, context):
    total_users = users_col.count_documents({})
    active_users = users_col.count_documents({"balance": {"$gt": 0}})
    vip_users = users_col.count_documents({"vip_until": {"$gt": datetime.datetime.now()}})
    total_balance = users_col.aggregate([{"$group": {"_id": None, "total": {"$sum": "$balance"}}}])
    total_balance = list(total_balance)[0]["total"] if total_balance else 0
    
    stats_text = f"""
    📊 *إحصائيات البوت*

    *إجمالي المستخدمين:* {total_users}
    *المستخدمين النشطين:* {active_users}
    *مشتركين VIP:* {vip_users}
    *إجمالي الأرصدة:* {format_number(total_balance)} دينار
    *الخدمات النشطة:* {sum([1 for s in ['exemption', 'summary', 'qa', 'help', 'vip'] if get_setting(f'{s}_enabled')])}
    """
    
    await query.edit_message_text(
        stats_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_panel_keyboard()
    )

async def admin_users(query, context):
    users = list(users_col.find().sort("created_at", -1).limit(50))
    
    text = "👥 *آخر 50 مستخدم*\n\n"
    for i, user in enumerate(users[:10], 1):
        vip_status = "⭐" if user.get("vip_until") and user["vip_until"] > datetime.datetime.now() else ""
        text += f"{i}. {user.get('user_id')} - {user['balance']} دينار {vip_status}\n"
    
    if len(users) > 10:
        text += f"\n... و {len(users)-10} مستخدم آخر"
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_panel_keyboard()
    )

async def admin_charge(query, context):
    await query.edit_message_text(
        "💰 *شحن رصيد*\n\n"
        "أرسل معرف المستخدم:",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['admin_action'] = 'charge'
    return UserState.WAITING_CHARGE_AMOUNT

async def admin_deduct(query, context):
    await query.edit_message_text(
        "💸 *خصم رصيد*\n\n"
        "أرسل معرف المستخدم:",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['admin_action'] = 'deduct'
    return UserState.WAITING_CHARGE_AMOUNT

async def admin_ban(query, context):
    await query.edit_message_text(
        "🚫 *حظر مستخدم*\n\n"
        "أرسل معرف المستخدم:",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['admin_action'] = 'ban'

async def admin_unban(query, context):
    await query.edit_message_text(
        "✅ *فك حظر مستخدم*\n\n"
        "أرسل معرف المستخدم:",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['admin_action'] = 'unban'

async def admin_services(query, context):
    await query.edit_message_text(
        "⚙️ *إدارة الخدمات*\n\n"
        "تفعيل/تعطيل الخدمات:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=services_management_keyboard()
    )

async def admin_prices(query, context):
    await query.edit_message_text(
        "💳 *تغيير الأسعار*\n\n"
        "اختر السعر الذي تريد تغييره:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=price_management_keyboard()
    )

async def admin_broadcast(query, context):
    await query.edit_message_text(
        "📢 *إرسال إذاعة*\n\n"
        "أرسل النص الذي تريد إذاعته:",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['admin_action'] = 'broadcast'
    return UserState.WAITING_BROADCAST

async def admin_vip_users(query, context):
    vip_users = list(users_col.find({"vip_until": {"$gt": datetime.datetime.now()}}))
    
    if not vip_users:
        await query.edit_message_text("📭 لا يوجد مشتركين VIP حالياً.")
        return
    
    text = "⭐ *مشتركين VIP*\n\n"
    keyboard = []
    
    for user in vip_users:
        remaining = user["vip_until"] - datetime.datetime.now()
        btn_text = f"{user['user_id']} - {remaining.days} يوم"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"vipuser_{user['user_id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")])
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_vip_lectures(query, context):
    lectures = list(vip_lectures_col.find({}).sort("uploaded_at", -1))
    
    text = "📹 *إدارة محاضرات VIP*\n\n"
    keyboard = []
    
    for lecture in lectures[:10]:
        status = "✅" if lecture.get("approved") else "⏳"
        btn_text = f"{status} {lecture['title'][:20]}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"manage_lecture_{lecture['_id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")])
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def toggle_service(query, context, service):
    current = get_setting(f"{service}_enabled")
    new_value = not current
    update_setting(f"{service}_enabled", new_value)
    
    status = "تم تفعيل" if new_value else "تم تعطيل"
    service_names = {
        "exemption": "حساب درجة الاعفاء",
        "summary": "تلخيص الملازم",
        "qa": "سؤال وجواب",
        "help": "ساعدوني طالب",
        "vip": "خدمة VIP"
    }
    
    await query.edit_message_text(
        f"✅ {status} خدمة {service_names[service]}",
        reply_markup=services_management_keyboard()
    )

async def change_service_price(query, context):
    await query.edit_message_text(
        f"💰 *تغيير سعر الخدمات*\n\n"
        f"السعر الحالي: {format_number(get_setting('service_price'))} دينار\n"
        f"أرسل السعر الجديد:",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['admin_action'] = 'change_service_price'
    return UserState.WAITING_SERVICE_PRICE

async def change_vip_price(query, context):
    await query.edit_message_text(
        f"⭐ *تغيير سعر اشتراك VIP*\n\n"
        f"السعر الحالي: {format_number(get_setting('vip_subscription_price'))} دينار\n"
        f"أرسل السعر الجديد:",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['admin_action'] = 'change_vip_price'
    return UserState.WAITING_VIP_PRICE

async def change_invite_reward(query, context):
    await query.edit_message_text(
        f"🎁 *تغيير مكافأة الدعوة*\n\n"
        f"المكافأة الحالية: {format_number(get_setting('invite_reward'))} دينار\n"
        f"أرسل المكافأة الجديدة:",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['admin_action'] = 'change_invite_reward'
    return UserState.WAITING_INVITE_REWARD

# ==================== Message Handlers ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message
    
    # Check if user is banned
    user = get_user(user_id)
    if user.get("banned"):
        return
    
    # Check user state
    state = context.user_data.get('state')
    
    if state == UserState.WAITING_COURSE1:
        await handle_course_score(update, context, 1)
    elif state == UserState.WAITING_COURSE2:
        await handle_course_score(update, context, 2)
    elif state == UserState.WAITING_COURSE3:
        await handle_course_score(update, context, 3)
    elif state == UserState.WAITING_PDF:
        await handle_pdf_summary(update, context)
    elif state == UserState.WAITING_QUESTION:
        await handle_question(update, context)
    elif state == UserState.WAITING_ANSWER:
        await handle_answer(update, context)
    elif state == UserState.WAITING_CHARGE_AMOUNT:
        await handle_admin_amount(update, context)
    elif state == UserState.WAITING_BROADCAST:
        await handle_broadcast(update, context)
    elif state == UserState.WAITING_VIP_PRICE:
        await handle_vip_price_change(update, context)
    elif state == UserState.WAITING_SERVICE_PRICE:
        await handle_service_price_change(update, context)
    elif state == UserState.WAITING_INVITE_REWARD:
        await handle_invite_reward_change(update, context)
    elif state == UserState.WAITING_VIP_LECTURE_TITLE:
        await handle_vip_lecture_title(update, context)
    elif state == UserState.WAITING_VIP_LECTURE_DESC:
        await handle_vip_lecture_desc(update, context)
    elif state == UserState.WAITING_VIP_LECTURE_PRICE:
        await handle_vip_lecture_price(update, context)
    elif state == UserState.WAITING_VIP_LECTURE_VIDEO:
        await handle_vip_lecture_video(update, context)
    elif state == UserState.WAITING_WITHDRAW_AMOUNT:
        await handle_withdraw_amount(update, context)
    else:
        # Check for start with invite code
        if message.text and message.text.startswith('/start'):
            parts = message.text.split()
            if len(parts) > 1:
                invite_code = parts[1]
                await handle_invite(user_id, invite_code)
        
        await update.message.reply_text(
            "اختر الخدمة المطلوبة من القائمة:",
            reply_markup=main_menu_keyboard(user_id)
        )

async def handle_course_score(update: Update, context: ContextTypes.DEFAULT_TYPE, course_num: int):
    try:
        score = float(update.message.text)
        if not (0 <= score <= 100):
            raise ValueError
    except:
        await update.message.reply_text("❌ الرجاء إدخال درجة صحيحة بين 0 و 100:")
        return
    
    user_id = update.effective_user.id
    context.user_data[f'course{course_num}_score'] = score
    
    if course_num == 1:
        await update.message.reply_text("أدخل درجة الكورس الثاني (0-100):")
        context.user_data['state'] = UserState.WAITING_COURSE2
    elif course_num == 2:
        await update.message.reply_text("أدخل درجة الكورس الثالث (0-100):")
        context.user_data['state'] = UserState.WAITING_COURSE3
    elif course_num == 3:
        # Calculate average
        avg = (context.user_data['course1_score'] + 
               context.user_data['course2_score'] + 
               context.user_data['course3_score']) / 3
        
        # Deduct payment after service completion
        if 'pending_payment' in context.user_data:
            user = get_user(user_id)
            new_balance = user["balance"] - context.user_data['pending_payment']
            update_user(user_id, {"balance": new_balance})
            
            # Log transaction
            transactions_col.insert_one({
                "user_id": user_id,
                "type": "exemption_service",
                "amount": -context.user_data['pending_payment'],
                "balance_after": new_balance,
                "timestamp": datetime.datetime.now()
            })
        
        if avg >= 90:
            message = f"🎉 *مبروك!*\n\nمعدلك النهائي: {avg:.2f}\nأنت معفي من المادة!"
        else:
            message = f"📊 *نتيجتك*\n\nمعدلك النهائي: {avg:.2f}\nللأسف أنت غير معفي من المادة."
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(user_id)
        )
        
        # Clear state
        context.user_data.clear()

async def handle_pdf_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document:
        await update.message.reply_text("❌ الرجاء إرسال ملف PDF:")
        return
    
    document = update.message.document
    if not document.file_name.endswith('.pdf'):
        await update.message.reply_text("❌ الرجاء إرسال ملف PDF فقط:")
        return
    
    user_id = update.effective_user.id
    await update.message.reply_text("⏳ جاري تلخيص الملف...")
    
    try:
        # Download file
        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()
        
        # Extract text from PDF
        pdf_text = extract_text_from_pdf(file_bytes)
        
        # Summarize using Gemini
        prompt = f"لخص النص التالي باللغة العربية مع الحفاظ على المعلومات المهمة فقط:\n\n{pdf_text[:3000]}"
        response = model.generate_content(prompt)
        summary = response.text
        
        # Create summarized PDF
        summarized_pdf = create_summarized_pdf(summary, document.file_name)
        
        # Deduct payment after service completion
        if 'pending_payment' in context.user_data:
            user = get_user(user_id)
            new_balance = user["balance"] - context.user_data['pending_payment']
            update_user(user_id, {"balance": new_balance})
            
            # Log transaction
            transactions_col.insert_one({
                "user_id": user_id,
                "type": "summary_service",
                "amount": -context.user_data['pending_payment'],
                "balance_after": new_balance,
                "timestamp": datetime.datetime.now()
            })
        
        # Send summarized PDF
        await update.message.reply_document(
            document=InputFile(summarized_pdf, filename=f"ملخص_{document.file_name}"),
            caption="✅ تم تلخيص الملف بنجاح!",
            reply_markup=main_menu_keyboard(user_id)
        )
        
    except Exception as e:
        logger.error(f"PDF summary error: {e}")
        await update.message.reply_text("❌ حدث خطأ في تلخيص الملف.")
    
    # Clear state
    context.user_data.clear()

def extract_text_from_pdf(pdf_bytes):
    try:
        with io.BytesIO(pdf_bytes) as file:
            reader = PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            return text
    except:
        return ""

def create_summarized_pdf(text, original_filename):
    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    
    # Create PDF
    c = canvas.Canvas(temp_file.name, pagesize=letter)
    c.setFont("Helvetica", 12)
    
    # Reshape Arabic text
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    
    # Split text into lines
    lines = bidi_text.split('\n')
    y = 750
    
    for line in lines:
        if y < 50:
            c.showPage()
            c.setFont("Helvetica", 12)
            y = 750
        
        # Split long lines
        while len(line) > 80:
            c.drawString(50, y, line[:80])
            line = line[80:]
            y -= 20
        
        c.drawString(50, y, line)
        y -= 20
    
    c.save()
    return open(temp_file.name, 'rb')

async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    question_text = ""
    
    if update.message.text:
        question_text = update.message.text
    elif update.message.photo:
        # For image questions, we'll use the caption or ask for clarification
        question_text = update.message.caption or "يرجى وصف السؤال المرتبط بالصورة"
    
    service = context.user_data.get('service')
    
    if service == 'qa':
        # AI Q&A service
        try:
            prompt = f"أجب على السؤال التالي بشكل علمي ومنهجي حسب المنهج العراقي:\n\n{question_text}"
            response = model.generate_content(prompt)
            answer = response.text
            
            # Deduct payment after service completion
            if 'pending_payment' in context.user_data:
                user = get_user(user_id)
                new_balance = user["balance"] - context.user_data['pending_payment']
                update_user(user_id, {"balance": new_balance})
                
                # Log transaction
                transactions_col.insert_one({
                    "user_id": user_id,
                    "type": "qa_service",
                    "amount": -context.user_data['pending_payment'],
                    "balance_after": new_balance,
                    "timestamp": datetime.datetime.now()
                })
            
            await update.message.reply_text(
                f"🤖 *الإجابة:*\n\n{answer}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard(user_id)
            )
            
        except Exception as e:
            logger.error(f"AI Q&A error: {e}")
            await update.message.reply_text("❌ حدث خطأ في معالجة سؤالك.")
    
    elif service == 'help':
        # Help service - add to questions collection for admin approval
        question_id = questions_col.insert_one({
            "user_id": user_id,
            "question": question_text,
            "status": "pending",
            "created_at": datetime.datetime.now()
        }).inserted_id
        
        # Notify admin
        admin_text = f"🆘 *سؤال جديد يحتاج موافقة*\n\nالسؤال: {question_text}\n\nالمرسل: {user_id}"
        keyboard = [
            [
                InlineKeyboardButton("✅ الموافقة", callback_data=f"approve_question_{question_id}"),
                InlineKeyboardButton("❌ الرفض", callback_data=f"reject_question_{question_id}")
            ]
        ]
        
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            pass
        
        await update.message.reply_text(
            "✅ تم إرسال سؤالك وسيتم عرضه بعد موافقة الإدارة.",
            reply_markup=main_menu_keyboard(user_id)
        )
    
    # Clear state
    context.user_data.clear()

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer_text = update.message.text
    question_id = context.user_data.get('answering_question')
    
    if question_id:
        # Update question with answer
        questions_col.update_one(
            {"_id": question_id},
            {"$set": {"answer": answer_text, "answered_at": datetime.datetime.now(), "status": "answered"}}
        )
        
        # Get question to notify user
        question = questions_col.find_one({"_id": question_id})
        if question:
            user_id = question["user_id"]
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ *تمت الإجابة على سؤالك*\n\nسؤالك: {question['question']}\n\nالإجابة: {answer_text}",
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
        
        await update.message.reply_text("✅ تم إرسال الإجابة للمستخدم.")
        
        # Clear state
        context.user_data.clear()

async def handle_admin_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if 'target_user_id' not in context.user_data:
        # First message: get target user ID
        try:
            target_user_id = int(update.message.text)
            context.user_data['target_user_id'] = target_user_id
            
            action = context.user_data.get('admin_action')
            if action in ['charge', 'deduct']:
                await update.message.reply_text("أرسل المبلغ:")
                return
            elif action == 'ban':
                users_col.update_one({"user_id": target_user_id}, {"$set": {"banned": True}})
                await update.message.reply_text(f"✅ تم حظر المستخدم {target_user_id}")
            elif action == 'unban':
                users_col.update_one({"user_id": target_user_id}, {"$set": {"banned": False}})
                await update.message.reply_text(f"✅ تم فك حظر المستخدم {target_user_id}")
            
            # Clear state
            context.user_data.clear()
            await update.message.reply_text(
                "👑 لوحة التحكم",
                reply_markup=admin_panel_keyboard()
            )
            
        except ValueError:
            await update.message.reply_text("❌ الرجاء إرسال معرف مستخدم صحيح:")
    
    else:
        # Second message: get amount
        try:
            amount = int(update.message.text)
            target_user_id = context.user_data['target_user_id']
            target_user = get_user(target_user_id)
            
            action = context.user_data.get('admin_action')
            
            if action == 'charge':
                new_balance = target_user["balance"] + amount
                update_user(target_user_id, {"balance": new_balance})
                
                # Log transaction
                transactions_col.insert_one({
                    "user_id": target_user_id,
                    "type": "admin_charge",
                    "amount": amount,
                    "balance_after": new_balance,
                    "admin_id": user_id,
                    "timestamp": datetime.datetime.now()
                })
                
                # Notify user
                try:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=f"💰 تم شحن {format_number(amount)} دينار لحسابك\n\nرصيدك الجديد: {format_number(new_balance)} دينار"
                    )
                except:
                    pass
                
                await update.message.reply_text(f"✅ تم شحن {format_number(amount)} دينار للمستخدم {target_user_id}")
            
            elif action == 'deduct':
                if target_user["balance"] >= amount:
                    new_balance = target_user["balance"] - amount
                    update_user(target_user_id, {"balance": new_balance})
                    
                    # Log transaction
                    transactions_col.insert_one({
                        "user_id": target_user_id,
                        "type": "admin_deduct",
                        "amount": -amount,
                        "balance_after": new_balance,
                        "admin_id": user_id,
                        "timestamp": datetime.datetime.now()
                    })
                    
                    await update.message.reply_text(f"✅ تم خصم {format_number(amount)} دينار من المستخدم {target_user_id}")
                else:
                    await update.message.reply_text(f"❌ رصيد المستخدم غير كافي. الرصيد الحالي: {target_user['balance']}")
            
            # Clear state
            context.user_data.clear()
            await update.message.reply_text(
                "👑 لوحة التحكم",
                reply_markup=admin_panel_keyboard()
            )
            
        except ValueError:
            await update.message.reply_text("❌ الرجاء إرسال مبلغ صحيح:")

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    broadcast_text = update.message.text
    users = users_col.find({})
    
    await update.message.reply_text("⏳ جاري إرسال الإذاعة...")
    
    success = 0
    fail = 0
    
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user["user_id"],
                text=broadcast_text,
                parse_mode=ParseMode.MARKDOWN
            )
            success += 1
        except:
            fail += 1
    
    await update.message.reply_text(
        f"✅ تم إرسال الإذاعة:\n\n"
        f"✅ الناجح: {success}\n"
        f"❌ الفاشل: {fail}",
        reply_markup=admin_panel_keyboard()
    )
    
    # Clear state
    context.user_data.clear()

async def handle_vip_price_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_price = int(update.message.text)
        update_setting("vip_subscription_price", new_price)
        
        await update.message.reply_text(
            f"✅ تم تغيير سعر اشتراك VIP إلى {format_number(new_price)} دينار",
            reply_markup=admin_panel_keyboard()
        )
    except ValueError:
        await update.message.reply_text("❌ الرجاء إرسال سعر صحيح:")

async def handle_service_price_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_price = int(update.message.text)
        update_setting("service_price", new_price)
        
        await update.message.reply_text(
            f"✅ تم تغيير سعر الخدمات إلى {format_number(new_price)} دينار",
            reply_markup=admin_panel_keyboard()
        )
    except ValueError:
        await update.message.reply_text("❌ الرجاء إرسال سعر صحيح:")

async def handle_invite_reward_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_reward = int(update.message.text)
        update_setting("invite_reward", new_reward)
        
        await update.message.reply_text(
            f"✅ تم تغيير مكافأة الدعوة إلى {format_number(new_reward)} دينار",
            reply_markup=admin_panel_keyboard()
        )
    except ValueError:
        await update.message.reply_text("❌ الرجاء إرسال مكافأة صحيحة:")

async def handle_vip_lecture_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['lecture_title'] = update.message.text
    await update.message.reply_text("أرسل وصف المحاضرة:")
    context.user_data['state'] = UserState.WAITING_VIP_LECTURE_DESC

async def handle_vip_lecture_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['lecture_desc'] = update.message.text
    await update.message.reply_text("أرسل سعر المحاضرة (أرسل 0 للمجانية):")
    context.user_data['state'] = UserState.WAITING_VIP_LECTURE_PRICE

async def handle_vip_lecture_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = int(update.message.text)
        if price < 0:
            raise ValueError
        context.user_data['lecture_price'] = price
        await update.message.reply_text("أرسل فيديو المحاضرة (بحد أقصى 100 ميجابايت):")
        context.user_data['state'] = UserState.WAITING_VIP_LECTURE_VIDEO
    except ValueError:
        await update.message.reply_text("❌ الرجاء إرسال سعر صحيح:")

async def handle_vip_lecture_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.video:
        await update.message.reply_text("❌ الرجاء إرسال ملف فيديو:")
        return
    
    video = update.message.video
    if video.file_size > 100 * 1024 * 1024:  # 100 MB limit
        await update.message.reply_text("❌ حجم الفيديو يتجاوز 100 ميجابايت!")
        return
    
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    # Save lecture to database
    lecture_data = {
        "user_id": user_id,
        "title": context.user_data.get('lecture_title'),
        "description": context.user_data.get('lecture_desc'),
        "price": context.user_data.get('lecture_price', 0),
        "video_file_id": video.file_id,
        "approved": False,
        "uploaded_at": datetime.datetime.now(),
        "revenue": 0,
        "purchases": 0
    }
    
    lecture_id = vip_lectures_col.insert_one(lecture_data).inserted_id
    
    # Notify admin for approval
    admin_text = f"📹 *محاضرة VIP جديدة تحتاج موافقة*\n\n"
    admin_text += f"العنوان: {lecture_data['title']}\n"
    admin_text += f"الوصف: {lecture_data['description']}\n"
    admin_text += f"السعر: {format_number(lecture_data['price'])} دينار\n"
    admin_text += f"المدرس: {user_id}"
    
    keyboard = [
        [
            InlineKeyboardButton("✅ الموافقة", callback_data=f"approve_lecture_{lecture_id}"),
            InlineKeyboardButton("❌ الرفض", callback_data=f"reject_lecture_{lecture_id}")
        ]
    ]
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except:
        pass
    
    await update.message.reply_text(
        "✅ تم رفع المحاضرة وتنتظر موافقة الإدارة.",
        reply_markup=main_menu_keyboard(user_id)
    )
    
    # Clear state
    context.user_data.clear()

async def handle_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = int(update.message.text)
        user_id = update.effective_user.id
        user = get_user(user_id)
        
        min_withdraw = get_setting("min_withdraw", 1000)
        
        if amount < min_withdraw:
            await update.message.reply_text(f"❌ الحد الأدنى للسحب هو {format_number(min_withdraw)} دينار")
            return
        
        if user.get("vip_balance", 0) < amount:
            await update.message.reply_text("❌ رصيد أرباحك غير كافي")
            return
        
        # Deduct from VIP balance
        new_vip_balance = user.get("vip_balance", 0) - amount
        update_user(user_id, {"vip_balance": new_vip_balance})
        
        # Log withdrawal request
        withdrawal_data = {
            "user_id": user_id,
            "amount": amount,
            "status": "pending",
            "requested_at": datetime.datetime.now()
        }
        db["withdrawals"].insert_one(withdrawal_data)
        
        # Notify admin
        admin_text = f"💸 *طلب سحب جديد*\n\nالمستخدم: {user_id}\nالمبلغ: {format_number(amount)} دينار"
        
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_text,
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
        
        await update.message.reply_text(
            f"✅ تم إرسال طلب سحب بقيمة {format_number(amount)} دينار للإدارة.\n"
            f"سيتم التواصل معك عبر @{SUPPORT_USERNAME.replace('@', '')}",
            reply_markup=main_menu_keyboard(user_id)
        )
        
    except ValueError:
        await update.message.reply_text("❌ الرجاء إرسال مبلغ صحيح:")

async def handle_invite(user_id: int, invite_code: str):
    # Check if user already invited by someone
    user = get_user(user_id)
    if user.get("invited_by"):
        return
    
    # Find inviter
    inviter = users_col.find_one({"invite_code": invite_code})
    if inviter and inviter["user_id"] != user_id:
        # Update inviter's invited count and balance
        invite_reward = get_setting("invite_reward")
        new_balance = inviter["balance"] + invite_reward
        users_col.update_one(
            {"user_id": inviter["user_id"]},
            {
                "$set": {"balance": new_balance},
                "$inc": {"invited_count": 1}
            }
        )
        
        # Update invited user
        update_user(user_id, {"invited_by": inviter["user_id"]})
        
        # Log transaction for inviter
        transactions_col.insert_one({
            "user_id": inviter["user_id"],
            "type": "invite_reward",
            "amount": invite_reward,
            "balance_after": new_balance,
            "timestamp": datetime.datetime.now(),
            "invited_user": user_id
        })
        
        # Notify inviter
        try:
            from app import application
            await application.bot.send_message(
                chat_id=inviter["user_id"],
                text=f"🎉 تم دعوة صديق جديد!\n\nمكافأة الدعوة: {format_number(invite_reward)} دينار\nرصيدك الجديد: {format_number(new_balance)} دينار"
            )
        except:
            pass

# ==================== Additional Callback Handlers ====================
async def confirm_vip_subscription(query, context):
    user_id = query.from_user.id
    user = get_user(user_id)
    
    vip_price = get_setting("vip_subscription_price")
    
    if user["balance"] < vip_price:
        await query.edit_message_text(
            f"❌ رصيدك غير كافي. سعر الاشتراك: {format_number(vip_price)} دينار\n"
            f"💰 رصيدك الحالي: {format_number(user['balance'])} دينار"
        )
        return
    
    # Deduct balance
    new_balance = user["balance"] - vip_price
    vip_until = datetime.datetime.now() + datetime.timedelta(days=30)
    
    update_user(user_id, {
        "balance": new_balance,
        "vip_until": vip_until,
        "vip_balance": 0
    })
    
    # Log transaction
    transactions_col.insert_one({
        "user_id": user_id,
        "type": "vip_subscription",
        "amount": -vip_price,
        "balance_after": new_balance,
        "timestamp": datetime.datetime.now()
    })
    
    # Notify admin
    admin_text = f"⭐ *اشتراك VIP جديد*\n\nالمستخدم: {user_id}\nالمبلغ: {format_number(vip_price)} دينار"
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text,
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass
    
    await query.edit_message_text(
        f"✅ تم الاشتراك في VIP بنجاح!\n\n"
        f"⭐ اشتراكك ساري لمدة 30 يوم\n"
        f"💰 يمكنك الآن رفع محاضرات VIP وكسب 60% من الأرباح",
        reply_markup=main_menu_keyboard(user_id)
    )

async def approve_question_callback(query, context):
    question_id = query.data.replace("approve_question_", "")
    
    questions_col.update_one(
        {"_id": question_id},
        {"$set": {"status": "approved", "approved_at": datetime.datetime.now()}}
    )
    
    await query.edit_message_text(
        "✅ تمت الموافقة على السؤال وسيتم عرضه في قسم المساعدة.",
        reply_markup=admin_panel_keyboard()
    )

async def reject_question_callback(query, context):
    question_id = query.data.replace("reject_question_", "")
    
    questions_col.update_one(
        {"_id": question_id},
        {"$set": {"status": "rejected", "rejected_at": datetime.datetime.now()}}
    )
    
    await query.edit_message_text(
        "❌ تم رفض السؤال.",
        reply_markup=admin_panel_keyboard()
    )

async def approve_lecture_callback(query, context):
    lecture_id = query.data.replace("approve_lecture_", "")
    
    vip_lectures_col.update_one(
        {"_id": lecture_id},
        {"$set": {"approved": True, "approved_at": datetime.datetime.now()}}
    )
    
    # Get lecture info
    lecture = vip_lectures_col.find_one({"_id": lecture_id})
    if lecture:
        # Notify lecturer
        try:
            await context.bot.send_message(
                chat_id=lecture["user_id"],
                text=f"✅ تمت الموافقة على محاضرتك:\n{lecture['title']}\n\nيمكنك مشاهدتها في قسم محاضرات VIP"
            )
        except:
            pass
    
    await query.edit_message_text(
        "✅ تمت الموافقة على المحاضرة.",
        reply_markup=admin_panel_keyboard()
    )

async def reject_lecture_callback(query, context):
    lecture_id = query.data.replace("reject_lecture_", "")
    
    vip_lectures_col.update_one(
        {"_id": lecture_id},
        {"$set": {"rejected": True, "rejected_at": datetime.datetime.now()}}
    )
    
    # Get lecture info
    lecture = vip_lectures_col.find_one({"_id": lecture_id})
    if lecture:
        # Notify lecturer
        try:
            await context.bot.send_message(
                chat_id=lecture["user_id"],
                text=f"❌ تم رفض محاضرتك:\n{lecture['title']}"
            )
        except:
            pass
    
    await query.edit_message_text(
        "❌ تم رفض المحاضرة.",
        reply_markup=admin_panel_keyboard()
    )

async def material_callback(query, context):
    material_id = query.data.replace("material_", "")
    material = materials_col.find_one({"_id": material_id})
    
    if material and material.get("file_id"):
        await query.edit_message_text("⏳ جاري تحميل المادة...")
        
        try:
            await context.bot.send_document(
                chat_id=query.from_user.id,
                document=material["file_id"],
                caption=f"📖 {material['name']}\n\n{material.get('description', '')}\n\nالمرحلة: {material.get('stage', '')}"
            )
        except:
            await query.edit_message_text("❌ حدث خطأ في تحميل الملف.")
    else:
        await query.edit_message_text("❌ الملف غير متوفر.")

async def lecture_callback(query, context):
    lecture_id = query.data.replace("lecture_", "")
    lecture = vip_lectures_col.find_one({"_id": lecture_id})
    user_id = query.from_user.id
    
    if not lecture:
        await query.edit_message_text("❌ المحاضرة غير موجودة.")
        return
    
    if lecture["price"] > 0:
        user = get_user(user_id)
        if user["balance"] < lecture["price"]:
            await query.edit_message_text(
                f"❌ رصيدك غير كافي. سعر المحاضرة: {format_number(lecture['price'])} دينار"
            )
            return
        
        # Deduct payment
        new_balance = user["balance"] - lecture["price"]
        update_user(user_id, {"balance": new_balance})
        
        # Calculate earnings (60% to lecturer, 40% to admin)
        lecturer_earnings = int(lecture["price"] * 0.6)
        admin_earnings = lecture["price"] - lecturer_earnings
        
        # Update lecturer's VIP balance
        lecturer = get_user(lecture["user_id"])
        new_vip_balance = lecturer.get("vip_balance", 0) + lecturer_earnings
        update_user(lecture["user_id"], {"vip_balance": new_vip_balance})
        
        # Update lecture stats
        vip_lectures_col.update_one(
            {"_id": lecture_id},
            {
                "$inc": {
                    "revenue": lecture["price"],
                    "purchases": 1
                }
            }
        )
        
        # Log transactions
        transactions_col.insert_many([
            {
                "user_id": user_id,
                "type": "lecture_purchase",
                "amount": -lecture["price"],
                "balance_after": new_balance,
                "timestamp": datetime.datetime.now(),
                "lecture_id": lecture_id
            },
            {
                "user_id": lecture["user_id"],
                "type": "lecture_earning",
                "amount": lecturer_earnings,
                "balance_after": new_vip_balance,
                "timestamp": datetime.datetime.now(),
                "lecture_id": lecture_id
            }
        ])
    
    # Send video
    try:
        await context.bot.send_video(
            chat_id=user_id,
            video=lecture["video_file_id"],
            caption=f"🎓 {lecture['title']}\n\n{lecture.get('description', '')}"
        )
        
        if lecture["price"] > 0:
            await query.edit_message_text(
                f"✅ تم شراء المحاضرة بنجاح!\n\n"
                f"السعر: {format_number(lecture['price'])} دينار\n"
                f"رصيدك الجديد: {format_number(new_balance)} دينار"
            )
    except:
        await query.edit_message_text("❌ حدث خطأ في تحميل المحاضرة.")

async def vipuser_callback(query, context):
    user_id = int(query.data.replace("vipuser_", ""))
    user = get_user(user_id)
    
    if not user.get("vip_until") or user["vip_until"] < datetime.datetime.now():
        await query.edit_message_text("❌ هذا المستخدم ليس مشتركاً في VIP حالياً.")
        return
    
    remaining = user["vip_until"] - datetime.datetime.now()
    
    text = f"""
    👤 *معلومات المشترك VIP*
    
    *المستخدم:* {user_id}
    *البقية:* {remaining.days} يوم
    *رصيد الأرباح:* {format_number(user.get('vip_balance', 0))} دينار
    *تاريخ الانتهاء:* {user['vip_until'].strftime('%Y-%m-%d %H:%M')}
    """
    
    keyboard = [
        [
            InlineKeyboardButton("🔄 تجديد شهر", callback_data=f"renew_vip_{user_id}"),
            InlineKeyboardButton("❌ إلغاء الاشتراك", callback_data=f"cancel_vip_{user_id}")
        ],
        [InlineKeyboardButton("💸 سحب أرباح", callback_data=f"withdraw_vip_{user_id}")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="admin_vip_users")]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def renew_vip_callback(query, context):
    target_user_id = int(query.data.replace("renew_vip_", ""))
    
    # Extend VIP by 30 days
    user = get_user(target_user_id)
    current_end = user.get("vip_until", datetime.datetime.now())
    new_end = current_end + datetime.timedelta(days=30)
    
    update_user(target_user_id, {"vip_until": new_end})
    
    await query.edit_message_text(
        f"✅ تم تجديد اشتراك VIP للمستخدم {target_user_id} لمدة 30 يوم إضافية.",
        reply_markup=admin_panel_keyboard()
    )

async def cancel_vip_callback(query, context):
    target_user_id = int(query.data.replace("cancel_vip_", ""))
    
    update_user(target_user_id, {"vip_until": datetime.datetime.now()})
    
    await query.edit_message_text(
        f"✅ تم إلغاء اشتراك VIP للمستخدم {target_user_id}.",
        reply_markup=admin_panel_keyboard()
    )

async def withdraw_vip_callback(query, context):
    target_user_id = int(query.data.replace("withdraw_vip_", ""))
    user = get_user(target_user_id)
    
    vip_balance = user.get("vip_balance", 0)
    
    await query.edit_message_text(
        f"💸 *سحب أرباح VIP*\n\n"
        f"المستخدم: {target_user_id}\n"
        f"رصيد الأرباح: {format_number(vip_balance)} دينار\n\n"
        f"أرسل المبلغ المراد سحبه:",
        parse_mode=ParseMode.MARKDOWN
    )
    
    context.user_data['withdraw_user'] = target_user_id
    context.user_data['state'] = UserState.WAITING_WITHDRAW_AMOUNT

# ==================== Main Function ====================
def main():
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Add message handler
    application.add_handler(MessageHandler(filters.ALL, handle_message))
    
    # Start bot
    print(f"Bot is running... @{BOT_USERNAME}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
