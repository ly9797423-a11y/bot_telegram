#!/usr/bin/env python3
"""
Bot Name: يلا نتعلم
Bot Username: @FC4Xbot
Admin: 6130994941
Support: @Allawi04
Channel: @FCJCV
Token: 8481569753:AAH3alhJ0hcHldht-PxV7j8TzBlRsMqAqGI
"""

import asyncio
import logging
import os
import json
import datetime
import tempfile
import hashlib
import random
import string
import time
import io
import re
from typing import Dict, List, Tuple, Optional, Any, Union
from enum import Enum
from pathlib import Path
from decimal import Decimal
from collections import defaultdict

from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    InputFile, 
    ChatPermissions,
    ReplyKeyboardRemove,
    BotCommand
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler,
    PicklePersistence
)
from telegram.constants import ParseMode, ChatAction
from telegram.error import TelegramError

import pymongo
from pymongo import MongoClient, ASCENDING, DESCENDING
import google.generativeai as genai
from bidi.algorithm import get_display
import arabic_reshaper
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from PyPDF2 import PdfReader
import requests
from PIL import Image
import pytz

# ==================== Configuration ====================
TOKEN = "8481569753:AAH3alhJ0hcHldht-PxV7j8TzBlRsMqAqGI"
BOT_USERNAME = "@FC4Xbot"
ADMIN_ID = 6130994941
SUPPORT_USERNAME = "Allawi04@"
CHANNEL_USERNAME = "@FCJCV"
GEMINI_API_KEY = "AIzaSyARsl_YMXA74bPQpJduu0jJVuaku7MaHuY"

# Database
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "learning_bot_v3"

# Timezone
IRAQ_TZ = pytz.timezone("Asia/Baghdad")

# Create directories
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Initialize MongoDB
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    db = client[DB_NAME]
    
    # Collections
    users_col = db["users"]
    courses_col = db["courses"]
    questions_col = db["questions"]
    materials_col = db["materials"]
    vip_subscriptions_col = db["vip_subscriptions"]
    vip_lectures_col = db["vip_lectures"]
    transactions_col = db["transactions"]
    invites_col = db["invites"]
    settings_col = db["settings"]
    notifications_col = db["notifications"]
    withdrawals_col = db["withdrawals"]
    broadcasts_col = db["broadcasts"]
    
    # Create indexes
    users_col.create_index([("user_id", ASCENDING)], unique=True)
    users_col.create_index([("invite_code", ASCENDING)], unique=True)
    settings_col.create_index([("key", ASCENDING)], unique=True)
    vip_lectures_col.create_index([("user_id", ASCENDING)])
    transactions_col.create_index([("user_id", ASCENDING)])
    
except Exception as e:
    logging.error(f"Database connection failed: {e}")
    # Fallback to in-memory storage for testing
    users_col = None
    settings_col = None

# Initialize Gemini AI
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
except Exception as e:
    logging.error(f"Gemini AI initialization failed: {e}")
    model = None

# Setup Arabic fonts
try:
    pdfmetrics.registerFont(TTFont('Arabic', 'arial.ttf'))
except:
    pass

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== Enums ====================
class UserState(Enum):
    MAIN_MENU = 0
    WAITING_COURSE1 = 1
    WAITING_COURSE2 = 2
    WAITING_COURSE3 = 3
    WAITING_PDF = 4
    WAITING_QUESTION = 5
    WAITING_CHARGE_USER = 6
    WAITING_CHARGE_AMOUNT = 7
    WAITING_DEDUCT_USER = 8
    WAITING_DEDUCT_AMOUNT = 9
    WAITING_BAN_USER = 10
    WAITING_UNBAN_USER = 11
    WAITING_BROADCAST = 12
    WAITING_VIP_PRICE = 13
    WAITING_SERVICE_PRICE = 14
    WAITING_INVITE_REWARD = 15
    WAITING_VIP_LECTURE_TITLE = 16
    WAITING_VIP_LECTURE_DESC = 17
    WAITING_VIP_LECTURE_PRICE = 18
    WAITING_VIP_LECTURE_VIDEO = 19
    WAITING_WITHDRAW_AMOUNT = 20
    WAITING_MATERIAL_NAME = 21
    WAITING_MATERIAL_DESC = 22
    WAITING_MATERIAL_STAGE = 23
    WAITING_MATERIAL_FILE = 24
    WAITING_QUESTION_APPROVAL = 25

# ==================== Utility Functions ====================
def format_number(num):
    """Format number with commas."""
    return f"{num:,.0f}".replace(",", "٬")

def format_currency(amount):
    """Format currency in Iraqi Dinar."""
    return f"{format_number(amount)} دينار"

def format_date(dt):
    """Format datetime."""
    if isinstance(dt, str):
        dt = datetime.datetime.fromisoformat(dt.replace('Z', '+00:00'))
    local_dt = dt.astimezone(IRAQ_TZ)
    return local_dt.strftime("%Y/%m/%d %I:%M %p")

def generate_invite_code():
    """Generate random invite code."""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(8))

def get_user(user_id, create_if_missing=True):
    """Get user from database."""
    if users_col is None:
        # Fallback for testing
        return {
            "user_id": user_id,
            "balance": 1000,
            "vip_balance": 0,
            "vip_until": None,
            "invite_code": "TEST123",
            "invited_count": 0,
            "banned": False
        }
    
    user = users_col.find_one({"user_id": user_id})
    
    if not user and create_if_missing:
        user = {
            "user_id": user_id,
            "username": "",
            "first_name": "",
            "last_name": "",
            "balance": 1000,
            "vip_balance": 0,
            "vip_until": None,
            "invited_by": None,
            "invite_code": generate_invite_code(),
            "invited_count": 0,
            "total_spent": 0,
            "total_earned": 0,
            "created_at": datetime.datetime.now(),
            "last_active": datetime.datetime.now(),
            "banned": False,
            "ban_reason": None,
            "ban_until": None,
            "warnings": 0
        }
        users_col.insert_one(user)
    elif user:
        # Update last active
        users_col.update_one(
            {"user_id": user_id},
            {"$set": {"last_active": datetime.datetime.now()}}
        )
    
    return user

def update_user(user_id, updates):
    """Update user in database."""
    if users_col is None:
        return True
    
    try:
        users_col.update_one(
            {"user_id": user_id},
            {"$set": updates}
        )
        return True
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")
        return False

def get_setting(key, default=None):
    """Get setting from database."""
    if settings_col is None:
        # Default settings
        defaults = {
            "service_price": 1000,
            "vip_subscription_price": 5000,
            "invite_reward": 500,
            "min_withdraw": 1000,
            "teacher_commission": 60,
            "admin_commission": 40,
            "exemption_enabled": True,
            "summary_enabled": True,
            "qa_enabled": True,
            "help_enabled": True,
            "vip_enabled": True,
            "materials_enabled": True,
            "maintenance_mode": False,
            "maintenance_message": "البوت تحت الصيانة حالياً"
        }
        return defaults.get(key, default)
    
    setting = settings_col.find_one({"key": key})
    return setting["value"] if setting else default

def update_setting(key, value):
    """Update setting in database."""
    if settings_col is None:
        return True
    
    try:
        settings_col.update_one(
            {"key": key},
            {"$set": {"value": value, "updated_at": datetime.datetime.now()}},
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error updating setting {key}: {e}")
        return False

def create_transaction(user_id, trans_type, amount, description=""):
    """Create transaction record."""
    if transactions_col is None:
        return True
    
    try:
        user = get_user(user_id)
        if not user:
            return False
        
        transaction = {
            "user_id": user_id,
            "type": trans_type,
            "amount": amount,
            "description": description,
            "created_at": datetime.datetime.now()
        }
        transactions_col.insert_one(transaction)
        return True
    except Exception as e:
        logger.error(f"Error creating transaction: {e}")
        return False

def extract_text_from_pdf(pdf_bytes):
    """Extract text from PDF."""
    try:
        with io.BytesIO(pdf_bytes) as file:
            reader = PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            return text
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return ""

def create_summary_pdf(text, filename):
    """Create PDF with summarized text."""
    buffer = io.BytesIO()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    styles = getSampleStyleSheet()
    
    # Create Arabic style
    arabic_style = ParagraphStyle(
        'Arabic',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_RIGHT,
        spaceAfter=12
    )
    
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Title'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=24
    )
    
    content = []
    
    # Title
    title = Paragraph(f"ملخص: {filename}", title_style)
    content.append(title)
    
    # Date
    date_text = f"تاريخ التلخيص: {datetime.datetime.now().strftime('%Y/%m/%d %H:%M')}"
    date_para = Paragraph(date_text, arabic_style)
    content.append(date_para)
    
    content.append(Spacer(1, 20))
    
    # Summary text
    if isinstance(text, str):
        # Reshape Arabic text
        reshaped_text = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped_text)
        summary_para = Paragraph(bidi_text, arabic_style)
        content.append(summary_para)
    
    # Footer
    content.append(Spacer(1, 40))
    footer_text = "تم التلخيص بواسطة بوت يلا نتعلم - @FC4Xbot"
    footer_para = Paragraph(footer_text, arabic_style)
    content.append(footer_para)
    
    doc.build(content)
    buffer.seek(0)
    return buffer

# ==================== Keyboard Builders ====================
class KeyboardBuilder:
    @staticmethod
    def main_menu(user_id):
        """Build main menu keyboard."""
        user = get_user(user_id)
        is_vip = user and user.get("vip_until") and user["vip_until"] > datetime.datetime.now()
        is_admin = user_id == ADMIN_ID
        
        keyboard = []
        
        # Row 1
        if get_setting("exemption_enabled", True):
            keyboard.append([InlineKeyboardButton("📊 حساب درجة الاعفاء", callback_data="service_exemption")])
        
        if get_setting("summary_enabled", True):
            keyboard.append([InlineKeyboardButton("📚 تلخيص الملازم", callback_data="service_summary")])
        
        # Row 2
        if get_setting("qa_enabled", True):
            keyboard.append([InlineKeyboardButton("❓ سؤال وجواب بالذكاء", callback_data="service_qa")])
        
        if get_setting("help_enabled", True):
            keyboard.append([InlineKeyboardButton("🆘 ساعدوني طالب", callback_data="service_help")])
        
        # Row 3
        if get_setting("materials_enabled", True):
            keyboard.append([InlineKeyboardButton("📖 ملازمي ومرشحاتي", callback_data="materials")])
        
        if get_setting("vip_enabled", True):
            if is_vip:
                keyboard.append([InlineKeyboardButton("🎓 محاضرات VIP", callback_data="vip_lectures")])
            else:
                keyboard.append([InlineKeyboardButton("⭐ اشتراك VIP", callback_data="vip_subscribe")])
        
        # Row 4
        keyboard.append([
            InlineKeyboardButton("💰 رصيدي", callback_data="balance"),
            InlineKeyboardButton("👥 دعوة صديق", callback_data="invite")
        ])
        
        # Row 5
        keyboard.append([
            InlineKeyboardButton("📢 قناة البوت", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"),
            InlineKeyboardButton("🛟 الدعم الفني", url=f"https://t.me/{SUPPORT_USERNAME.replace('@', '')}")
        ])
        
        if is_admin:
            keyboard.append([InlineKeyboardButton("👑 لوحة التحكم", callback_data="admin_panel")])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def admin_panel():
        """Build admin panel keyboard."""
        keyboard = [
            [InlineKeyboardButton("📊 الاحصائيات", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 ادارة المستخدمين", callback_data="admin_users")],
            [InlineKeyboardButton("💰 الشحن والخصم", callback_data="admin_finance")],
            [InlineKeyboardButton("🚫 ادارة الحظر", callback_data="admin_ban")],
            [InlineKeyboardButton("⚙️ ادارة الخدمات", callback_data="admin_services")],
            [InlineKeyboardButton("💳 ادارة الاسعار", callback_data="admin_prices")],
            [InlineKeyboardButton("🎓 ادارة VIP", callback_data="admin_vip")],
            [InlineKeyboardButton("📹 ادارة المحاضرات", callback_data="admin_lectures")],
            [InlineKeyboardButton("📢 الاذاعة", callback_data="admin_broadcast")],
            [InlineKeyboardButton("📁 ادارة المواد", callback_data="admin_materials")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def admin_users():
        """Build admin users keyboard."""
        keyboard = [
            [InlineKeyboardButton("📋 قائمة المستخدمين", callback_data="admin_users_list")],
            [InlineKeyboardButton("🔍 بحث مستخدم", callback_data="admin_search_user")],
            [InlineKeyboardButton("💰 شحن رصيد", callback_data="admin_charge")],
            [InlineKeyboardButton("💸 خصم رصيد", callback_data="admin_deduct")],
            [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban_user")],
            [InlineKeyboardButton("✅ فك حظر مستخدم", callback_data="admin_unban_user")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def admin_finance():
        """Build admin finance keyboard."""
        keyboard = [
            [InlineKeyboardButton("💰 شحن رصيد", callback_data="admin_charge")],
            [InlineKeyboardButton("💸 خصم رصيد", callback_data="admin_deduct")],
            [InlineKeyboardButton("💳 سحب ارباح VIP", callback_data="admin_withdraw_vip")],
            [InlineKeyboardButton("📊 حركات الحسابات", callback_data="admin_transactions")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def admin_services():
        """Build admin services keyboard."""
        services = [
            ("exemption", "حساب درجة الاعفاء"),
            ("summary", "تلخيص الملازم"),
            ("qa", "سؤال وجواب"),
            ("help", "ساعدوني طالب"),
            ("vip", "خدمة VIP"),
            ("materials", "المواد التعليمية")
        ]
        
        keyboard = []
        for key, name in services:
            status = "✅" if get_setting(f"{key}_enabled", True) else "❌"
            keyboard.append([InlineKeyboardButton(f"{status} {name}", callback_data=f"toggle_{key}")])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def admin_prices():
        """Build admin prices keyboard."""
        keyboard = [
            [InlineKeyboardButton("💰 سعر الخدمات العامة", callback_data="price_service")],
            [InlineKeyboardButton("⭐ سعر اشتراك VIP", callback_data="price_vip")],
            [InlineKeyboardButton("🎁 مكافأة الدعوة", callback_data="price_invite")],
            [InlineKeyboardButton("💵 الحد الأدنى للسحب", callback_data="price_min_withdraw")],
            [InlineKeyboardButton("📊 عمولة المدرس (%)", callback_data="price_teacher_commission")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def admin_vip():
        """Build admin VIP keyboard."""
        keyboard = [
            [InlineKeyboardButton("👥 مشتركين VIP", callback_data="admin_vip_users")],
            [InlineKeyboardButton("📊 احصائيات VIP", callback_data="admin_vip_stats")],
            [InlineKeyboardButton("🔄 تجديد اشتراك", callback_data="admin_vip_renew")],
            [InlineKeyboardButton("❌ الغاء اشتراك", callback_data="admin_vip_cancel")],
            [InlineKeyboardButton("📋 طلبات السحب", callback_data="admin_withdrawals")],
            [InlineKeyboardButton("💰 رصيد الأرباح", callback_data="admin_vip_balances")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def admin_lectures():
        """Build admin lectures keyboard."""
        keyboard = [
            [InlineKeyboardButton("📋 المحاضرات المعلقة", callback_data="admin_pending_lectures")],
            [InlineKeyboardButton("✅ المحاضرات المقبولة", callback_data="admin_approved_lectures")],
            [InlineKeyboardButton("❌ المحاضرات المرفوضة", callback_data="admin_rejected_lectures")],
            [InlineKeyboardButton("📊 احصائيات المحاضرات", callback_data="admin_lecture_stats")],
            [InlineKeyboardButton("⭐ تقييمات المحاضرات", callback_data="admin_lecture_ratings")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def admin_materials():
        """Build admin materials keyboard."""
        keyboard = [
            [InlineKeyboardButton("➕ اضافة مادة", callback_data="admin_add_material")],
            [InlineKeyboardButton("📋 قائمة المواد", callback_data="admin_list_materials")],
            [InlineKeyboardButton("✏️ تعديل مادة", callback_data="admin_edit_material")],
            [InlineKeyboardButton("🗑️ حذف مادة", callback_data="admin_delete_material")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def back_button(target="admin_panel"):
        """Build back button."""
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data=target)]])
    
    @staticmethod
    def confirm_cancel(target="admin_panel"):
        """Build confirm/cancel buttons."""
        keyboard = [
            [
                InlineKeyboardButton("✅ تأكيد", callback_data="confirm_action"),
                InlineKeyboardButton("❌ الغاء", callback_data=target)
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

# ==================== Message Builders ====================
class MessageBuilder:
    @staticmethod
    def welcome_message(user):
        """Build welcome message."""
        return f"""
        🎉 *أهلاً وسهلاً بك {user.first_name}!*
        
        *في بوت "يلا نتعلم" - رفيقك الدراسي الذكي*
        
        🎁 *هدية ترحيبية:* 1,000 دينار عراقي
        💰 *لشحن الرصيد:* تواصل مع الدعم الفني @{SUPPORT_USERNAME.replace('@', '')}
        
        *الخدمات المتاحة:*
        📊 حساب درجة الاعفاء
        📚 تلخيص الملازم بالذكاء الاصطناعي
        ❓ سؤال وجواب علمي
        🆘 ساعدوني طالب
        📖 ملازم ومرشحات
        ⭐ محاضرات VIP
        
        *📢 قناتنا:* @{CHANNEL_USERNAME.replace('@', '')}
        *🛟 الدعم الفني:* @{SUPPORT_USERNAME.replace('@', '')}
        
        اختر الخدمة التي تريدها من القائمة:
        """
    
    @staticmethod
    def balance_message(user_data):
        """Build balance message."""
        message = f"""
        💰 *حسابك المالي*
        
        *الرصيد الرئيسي:* {format_currency(user_data.get('balance', 0))}
        *رصيد الأرباح (VIP):* {format_currency(user_data.get('vip_balance', 0))}
        """
        
        if user_data.get("vip_until") and user_data["vip_until"] > datetime.datetime.now():
            remaining = user_data["vip_until"] - datetime.datetime.now()
            days = remaining.days
            message += f"\n*⭐ اشتراك VIP:* {days} يوم متبقي"
        
        message += f"\n\n*عدد الدعوات:* {user_data.get('invited_count', 0)}"
        
        return message
    
    @staticmethod
    def vip_subscription_info():
        """Build VIP subscription info."""
        vip_price = get_setting("vip_subscription_price", 5000)
        teacher_commission = get_setting("teacher_commission", 60)
        
        return f"""
        ⭐ *اشتراك VIP - المميزات والحزمة*
        
        *المميزات:*
        ✅ رفع محاضرات فيديو (حتى 100 ميجابايت)
        ✅ تحصيل {teacher_commission}% من أرباح المحاضرات
        ✅ قسم خاص لمحاضراتك
        ✅ دعم فني أولوية
        
        *الخطة الشهرية:*
        💳 السعر: {format_currency(vip_price)}
        📅 مدة الاشتراك: 30 يوم
        
        *طريقة الربح:*
        📊 60% من سعر المحاضرة لك
        📊 40% لإدارة البوت
        💳 السحب متاح عند وصول الرصيد للحد الأدنى
        
        *للاشتراك:* اضغط على زر "اشترك الآن"
        *للتواصل:* @{SUPPORT_USERNAME.replace('@', '')}
        """
    
    @staticmethod
    def admin_stats():
        """Build admin statistics message."""
        if users_col is None:
            return "❌ قاعدة البيانات غير متوفرة"
        
        total_users = users_col.count_documents({})
        active_today = users_col.count_documents({
            "last_active": {"$gte": datetime.datetime.now() - datetime.timedelta(days=1)}
        })
        vip_users = users_col.count_documents({
            "vip_until": {"$gt": datetime.datetime.now()}
        })
        banned_users = users_col.count_documents({"banned": True})
        
        # Calculate revenue
        total_balance = 0
        for user in users_col.find({}, {"balance": 1}):
            total_balance += user.get("balance", 0)
        
        return f"""
        📊 *إحصائيات البوت*
        
        *👥 المستخدمين:*
        • الإجمالي: {total_users}
        • النشطون اليوم: {active_today}
        • VIP النشط: {vip_users}
        • المحظورين: {banned_users}
        
        *💰 الأرصدة:*
        • إجمالي الأرصدة: {format_currency(total_balance)}
        
        *⚙️ الخدمات:*
        • النشطة: {sum([1 for s in ['exemption', 'summary', 'qa', 'help', 'vip', 'materials'] if get_setting(f'{s}_enabled', True)])}/6
        • الصيانة: {"مفعلة 🔴" if get_setting('maintenance_mode', False) else "غير مفعلة 🟢"}
        
        *⏰ آخر تحديث:* {format_date(datetime.datetime.now())}
        """

# ==================== Command Handlers ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    user_id = user.id
    
    # Check maintenance mode
    if get_setting("maintenance_mode", False) and user_id != ADMIN_ID:
        maintenance_msg = get_setting("maintenance_message", "البوت تحت الصيانة حالياً")
        await update.message.reply_text(f"🔧 {maintenance_msg}")
        return
    
    # Get or create user
    user_data = get_user(user_id)
    
    # Check if banned
    if user_data.get("banned"):
        ban_reason = user_data.get("ban_reason", "لم يتم تحديد سبب")
        ban_until = user_data.get("ban_until")
        
        if ban_until and ban_until > datetime.datetime.now():
            remaining = ban_until - datetime.datetime.now()
            message = f"❌ *تم حظرك من استخدام البوت*\n\nالسبب: {ban_reason}\nالمتبقي: {remaining.days} يوم"
        else:
            message = f"❌ *تم حظرك من استخدام البوت*\n\nالسبب: {ban_reason}"
        
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        return
    
    # Check for invite code
    if context.args:
        invite_code = context.args[0]
        await handle_invite(user_id, invite_code)
    
    # Send welcome message
    welcome_msg = MessageBuilder.welcome_message(user)
    
    await update.message.reply_text(
        welcome_msg,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.main_menu(user_id)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = f"""
    🆘 *مساعدة - بوت يلا نتعلم*
    
    *الخدمات المتاحة:*
    📊 حساب درجة الاعفاء
    📚 تلخيص الملازم (PDF)
    ❓ سؤال وجواب بالذكاء الاصطناعي
    🆘 ساعدوني طالب
    📖 ملازم ومرشحات
    ⭐ محاضرات VIP
    
    *💰 النظام المالي:*
    • العملة: الدينار العراقي
    • كل خدمة مدفوعة
    • شحن الرصيد: @{SUPPORT_USERNAME.replace('@', '')}
    • دعوة الأصدقاء: مكافأة لكل صديق
    
    *📞 الدعم الفني:*
    @{SUPPORT_USERNAME.replace('@', '')}
    
    *📢 قناة البوت:*
    @{CHANNEL_USERNAME.replace('@', '')}
    
    *🔄 الأوامر:*
    /start - إعادة تشغيل البوت
    /help - هذه الرسالة
    /balance - عرض الرصيد
    /invite - رابط الدعوة
    /cancel - إلغاء العملية الحالية
    """
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /balance command."""
    user_id = update.effective_user.id
    user_data = get_user(user_id)
    
    if user_data.get("banned"):
        await update.message.reply_text("❌ تم حظرك من استخدام البوت.")
        return
    
    balance_msg = MessageBuilder.balance_message(user_data)
    
    await update.message.reply_text(
        balance_msg,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.main_menu(user_id)
    )

async def invite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /invite command."""
    user_id = update.effective_user.id
    user_data = get_user(user_id)
    
    if user_data.get("banned"):
        await update.message.reply_text("❌ تم حظرك من استخدام البوت.")
        return
    
    invite_reward = get_setting("invite_reward", 500)
    invite_link = f"https://t.me/{BOT_USERNAME.replace('@', '')}?start={user_data['invite_code']}"
    
    # Special message for VIP users
    if user_data.get("vip_until") and user_data["vip_until"] > datetime.datetime.now():
        description = "🎓 انضم لأفضل بوت تعليمي مع محاضرات VIP حصرية!"
    else:
        description = "🎓 انضم لأفضل بوت تعليمي واحصل على هدية 1000 دينار مجاناً!"
    
    invite_text = f"""
    👥 *دعوة صديق*
    
    {description}
    
    *مكافأة الدعوة:* {format_currency(invite_reward)} لكل صديق
    *مدعووك حتى الآن:* {user_data.get('invited_count', 0)}
    
    *رابط الدعوة الخاص بك:*
    `{invite_link}`
    
    *طريقة المشاركة:*
    1. شارك الرابط مع أصدقائك
    2. عندما ينضم صديق يحصل على 1000 دينار هدية
    3. تحصل أنت على {format_currency(invite_reward)} دينار مكافأة
    """
    
    keyboard = [
        [InlineKeyboardButton("📤 مشاركة الرابط", url=f"https://t.me/share/url?url={invite_link}&text={description}")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
    ]
    
    await update.message.reply_text(
        invite_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command."""
    user_id = update.effective_user.id
    
    # Clear user state
    if 'state' in context.user_data:
        context.user_data.clear()
    
    await update.message.reply_text(
        "✅ تم إلغاء العملية الحالية.",
        reply_markup=KeyboardBuilder.main_menu(user_id)
    )
    
    return ConversationHandler.END

async def handle_invite(user_id, invite_code):
    """Handle invite code."""
    if users_col is None:
        return
    
    # Find inviter
    inviter = users_col.find_one({"invite_code": invite_code})
    
    if not inviter or inviter["user_id"] == user_id:
        return
    
    # Check if already invited
    existing_invite = invites_col.find_one({"invitee_id": user_id}) if invites_col else None
    if existing_invite:
        return
    
    # Record invite
    if invites_col:
        invites_col.insert_one({
            "inviter_id": inviter["user_id"],
            "invitee_id": user_id,
            "invite_code": invite_code,
            "created_at": datetime.datetime.now()
        })
    
    # Update inviter
    users_col.update_one(
        {"user_id": inviter["user_id"]},
        {"$inc": {"invited_count": 1}}
    )
    
    # Reward inviter
    invite_reward = get_setting("invite_reward", 500)
    current_balance = inviter.get("balance", 0)
    new_balance = current_balance + invite_reward
    
    users_col.update_one(
        {"user_id": inviter["user_id"]},
        {"$set": {"balance": new_balance}}
    )
    
    # Record transaction
    create_transaction(
        inviter["user_id"],
        "invite_reward",
        invite_reward,
        f"مكافأة دعوة للمستخدم {user_id}"
    )

# ==================== Callback Handlers ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all callback queries."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Check maintenance mode
    if get_setting("maintenance_mode", False) and data != "main_menu" and user_id != ADMIN_ID:
        maintenance_msg = get_setting("maintenance_message", "البوت تحت الصيانة حالياً")
        await query.edit_message_text(f"🔧 {maintenance_msg}")
        return
    
    # Check if user is banned
    user_data = get_user(user_id)
    if user_data.get("banned") and data != "main_menu" and user_id != ADMIN_ID:
        await query.edit_message_text("❌ تم حظرك من استخدام البوت.")
        return
    
    # Main menu
    if data == "main_menu":
        await query.edit_message_text(
            "🏠 *القائمة الرئيسية*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=KeyboardBuilder.main_menu(user_id)
        )
    
    # Service handlers
    elif data == "service_exemption":
        await handle_service_exemption(query, context)
    elif data == "service_summary":
        await handle_service_summary(query, context)
    elif data == "service_qa":
        await handle_service_qa(query, context)
    elif data == "service_help":
        await handle_service_help(query, context)
    elif data == "materials":
        await handle_materials(query, context)
    elif data == "vip_subscribe":
        await handle_vip_subscribe(query, context)
    elif data == "vip_lectures":
        await handle_vip_lectures(query, context)
    elif data == "balance":
        await handle_balance_callback(query, context)
    elif data == "invite":
        await handle_invite_callback(query, context)
    
    # Admin handlers
    elif data == "admin_panel":
        if user_id == ADMIN_ID:
            await query.edit_message_text(
                "👑 *لوحة تحكم المدير*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=KeyboardBuilder.admin_panel()
            )
        else:
            await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
    elif data == "admin_stats":
        await handle_admin_stats(query, context)
    elif data == "admin_users":
        await handle_admin_users(query, context)
    elif data == "admin_finance":
        await handle_admin_finance(query, context)
    elif data == "admin_ban":
        await handle_admin_ban_menu(query, context)
    elif data == "admin_services":
        await handle_admin_services(query, context)
    elif data == "admin_prices":
        await handle_admin_prices(query, context)
    elif data == "admin_vip":
        await handle_admin_vip(query, context)
    elif data == "admin_lectures":
        await handle_admin_lectures(query, context)
    elif data == "admin_broadcast":
        await handle_admin_broadcast_menu(query, context)
    elif data == "admin_materials":
        await handle_admin_materials(query, context)
    
    # Admin sub-menu handlers
    elif data == "admin_users_list":
        await handle_admin_users_list(query, context)
    elif data == "admin_search_user":
        await handle_admin_search_user(query, context)
    elif data == "admin_charge":
        await handle_admin_charge(query, context)
    elif data == "admin_deduct":
        await handle_admin_deduct(query, context)
    elif data == "admin_ban_user":
        await handle_admin_ban_user(query, context)
    elif data == "admin_unban_user":
        await handle_admin_unban_user(query, context)
    elif data.startswith("toggle_"):
        await handle_toggle_service(query, context, data.replace("toggle_", ""))
    elif data == "price_service":
        await handle_price_service(query, context)
    elif data == "price_vip":
        await handle_price_vip(query, context)
    elif data == "price_invite":
        await handle_price_invite(query, context)
    elif data == "price_min_withdraw":
        await handle_price_min_withdraw(query, context)
    elif data == "price_teacher_commission":
        await handle_price_teacher_commission(query, context)
    elif data == "admin_vip_users":
        await handle_admin_vip_users(query, context)
    elif data == "admin_withdraw_vip":
        await handle_admin_withdraw_vip(query, context)
    elif data == "admin_pending_lectures":
        await handle_admin_pending_lectures(query, context)
    elif data == "admin_broadcast_text":
        await handle_admin_broadcast_text(query, context)
    elif data == "admin_add_material":
        await handle_admin_add_material(query, context)
    elif data == "admin_list_materials":
        await handle_admin_list_materials(query, context)
    elif data == "admin_delete_material":
        await handle_admin_delete_material(query, context)
    
    # Lecture approval handlers
    elif data.startswith("approve_lecture_"):
        lecture_id = data.replace("approve_lecture_", "")
        await handle_approve_lecture(query, context, lecture_id)
    elif data.startswith("reject_lecture_"):
        lecture_id = data.replace("reject_lecture_", "")
        await handle_reject_lecture(query, context, lecture_id)
    
    # Material handlers
    elif data.startswith("material_"):
        material_id = data.replace("material_", "")
        await handle_material_view(query, context, material_id)
    elif data.startswith("delete_material_"):
        material_id = data.replace("delete_material_", "")
        await handle_delete_material_confirm(query, context, material_id)
    elif data == "confirm_delete_material":
        await handle_confirm_delete_material(query, context)
    
    # VIP subscription
    elif data == "confirm_vip_purchase":
        await handle_confirm_vip_purchase(query, context)
    
    # Lecture purchase
    elif data.startswith("purchase_lecture_"):
        lecture_id = data.replace("purchase_lecture_", "")
        await handle_purchase_lecture(query, context, lecture_id)
    
    # Question approval
    elif data.startswith("approve_question_"):
        question_id = data.replace("approve_question_", "")
        await handle_approve_question(query, context, question_id)
    elif data.startswith("reject_question_"):
        question_id = data.replace("reject_question_", "")
        await handle_reject_question(query, context, question_id)

async def handle_service_exemption(query, context):
    """Handle exemption service."""
    user_id = query.from_user.id
    user_data = get_user(user_id)
    
    if not get_setting("exemption_enabled", True):
        await query.edit_message_text("❌ خدمة حساب درجة الاعفاء معطلة حالياً.")
        return
    
    service_price = get_setting("service_price", 1000)
    
    if user_data["balance"] < service_price:
        await query.edit_message_text(
            f"❌ رصيدك غير كافي!\n\n"
            f"💰 سعر الخدمة: {format_currency(service_price)}\n"
            f"💵 رصيدك الحالي: {format_currency(user_data['balance'])}\n\n"
            f"لشحن الرصيد تواصل مع: @{SUPPORT_USERNAME.replace('@', '')}"
        )
        return
    
    # Store service info
    context.user_data['service_type'] = 'exemption'
    context.user_data['service_price'] = service_price
    context.user_data['course_scores'] = {}
    
    await query.edit_message_text(
        "📊 *حساب درجة الاعفاء*\n\n"
        "أدخل درجة الكورس الأول (0-100):\n\n"
        "ملاحظة: سيتم خصم المبلغ بعد إكمال العملية",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['state'] = UserState.WAITING_COURSE1

async def handle_service_summary(query, context):
    """Handle PDF summary service."""
    user_id = query.from_user.id
    user_data = get_user(user_id)
    
    if not get_setting("summary_enabled", True):
        await query.edit_message_text("❌ خدمة تلخيص الملازم معطلة حالياً.")
        return
    
    service_price = get_setting("service_price", 1000)
    
    if user_data["balance"] < service_price:
        await query.edit_message_text(
            f"❌ رصيدك غير كافي!\n\n"
            f"💰 سعر الخدمة: {format_currency(service_price)}\n"
            f"💵 رصيدك الحالي: {format_currency(user_data['balance'])}"
        )
        return
    
    context.user_data['service_type'] = 'summary'
    context.user_data['service_price'] = service_price
    
    await query.edit_message_text(
        "📚 *تلخيص الملازم*\n\n"
        "أرسل ملف PDF الذي تريد تلخيصه:\n\n"
        "ملاحظات:\n"
        "• حجم الملف يجب أن لا يتجاوز 20 ميجابايت\n"
        "• النص العربي مدعوم بشكل كامل\n"
        "• سيتم خصم المبلغ بعد إكمال العملية\n\n"
        "لإلغاء العملية: /cancel",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['state'] = UserState.WAITING_PDF

async def handle_service_qa(query, context):
    """Handle Q&A service."""
    user_id = query.from_user.id
    user_data = get_user(user_id)
    
    if not get_setting("qa_enabled", True):
        await query.edit_message_text("❌ خدمة سؤال وجواب معطلة حالياً.")
        return
    
    service_price = get_setting("service_price", 1000)
    
    if user_data["balance"] < service_price:
        await query.edit_message_text(
            f"❌ رصيدك غير كافي!\n\n"
            f"💰 سعر الخدمة: {format_currency(service_price)}\n"
            f"💵 رصيدك الحالي: {format_currency(user_data['balance'])}"
        )
        return
    
    context.user_data['service_type'] = 'qa'
    context.user_data['service_price'] = service_price
    
    await query.edit_message_text(
        "❓ *سؤال وجواب بالذكاء الاصطناعي*\n\n"
        "أرسل سؤالك الآن (نص أو صورة):\n\n"
        "يمكنك إرسال:\n"
        "• سؤال نصي في أي مادة\n"
        "• صورة تحتوي على سؤال\n"
        "• مشكلة تحتاج حلاً\n\n"
        "ملاحظة: الإجابات تعتمد على المنهج العراقي\n\n"
        "لإلغاء العملية: /cancel",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['state'] = UserState.WAITING_QUESTION

async def handle_service_help(query, context):
    """Handle help service."""
    user_id = query.from_user.id
    user_data = get_user(user_id)
    
    if not get_setting("help_enabled", True):
        await query.edit_message_text("❌ خدمة ساعدوني طالب معطلة حالياً.")
        return
    
    service_price = get_setting("service_price", 1000)
    
    if user_data["balance"] < service_price:
        await query.edit_message_text(
            f"❌ رصيدك غير كافي!\n\n"
            f"💰 سعر الخدمة: {format_currency(service_price)}\n"
            f"💵 رصيدك الحالي: {format_currency(user_data['balance'])}"
        )
        return
    
    # Deduct payment immediately
    new_balance = user_data["balance"] - service_price
    update_user(user_id, {"balance": new_balance})
    create_transaction(user_id, "service_payment", -service_price, "خدمة ساعدوني طالب")
    
    context.user_data['service_type'] = 'help'
    
    await query.edit_message_text(
        "🆘 *ساعدوني طالب*\n\n"
        "أرسل سؤالك الآن:\n\n"
        "سيتم:\n"
        "1. مراجعة سؤالك من الإدارة\n"
        "2. الموافقة أو الرفض خلال 24 ساعة\n"
        "3. عرض السؤال في قسم المساعدة\n"
        "4. إرسال الإجابة لك عند الحصول عليها\n\n"
        "لإلغاء العملية: /cancel",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['state'] = UserState.WAITING_QUESTION

async def handle_materials(query, context):
    """Handle materials callback."""
    user_id = query.from_user.id
    
    if not get_setting("materials_enabled", True):
        await query.edit_message_text("❌ قسم المواد التعليمية معطل حالياً.")
        return
    
    if materials_col is None:
        await query.edit_message_text("📭 لا توجد مواد تعليمية حالياً.")
        return
    
    materials = list(materials_col.find({"status": "active"}).limit(20))
    
    if not materials:
        await query.edit_message_text(
            "📭 لا توجد مواد تعليمية حالياً.\n\n"
            "سيتم إضافة مواد قريباً من قبل الإدارة.",
            reply_markup=KeyboardBuilder.main_menu(user_id)
        )
        return
    
    message = "📖 *المواد التعليمية المتاحة*\n\n"
    keyboard = []
    
    for material in materials:
        name = material.get("name", "بدون اسم")
        stage = material.get("stage", "غير محدد")
        btn_text = f"{name} - {stage}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"material_{material['_id']}")])
    
    keyboard.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")])
    
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_vip_subscribe(query, context):
    """Handle VIP subscription."""
    user_id = query.from_user.id
    user_data = get_user(user_id)
    
    if not get_setting("vip_enabled", True):
        await query.edit_message_text("❌ خدمة VIP معطلة حالياً.")
        return
    
    # Check if already VIP
    if user_data.get("vip_until") and user_data["vip_until"] > datetime.datetime.now():
        remaining = user_data["vip_until"] - datetime.datetime.now()
        await query.edit_message_text(
            f"⭐ أنت مشترك VIP بالفعل!\n\n"
            f"المتبقي: {remaining.days} يوم\n"
            f"رصيد الأرباح: {format_currency(user_data.get('vip_balance', 0))}",
            reply_markup=KeyboardBuilder.main_menu(user_id)
        )
        return
    
    vip_info = MessageBuilder.vip_subscription_info()
    
    keyboard = [
        [InlineKeyboardButton("💳 اشترك الآن", callback_data="confirm_vip_purchase")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        vip_info,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_vip_lectures(query, context):
    """Handle VIP lectures."""
    user_id = query.from_user.id
    user_data = get_user(user_id)
    
    # Check VIP status
    if not user_data.get("vip_until") or user_data["vip_until"] < datetime.datetime.now():
        await query.edit_message_text(
            "❌ هذه الخدمة للمشتركين في VIP فقط.\n\n"
            "اشترك من زر ⭐ اشتراك VIP في القائمة الرئيسية",
            reply_markup=KeyboardBuilder.main_menu(user_id)
        )
        return
    
    if vip_lectures_col is None:
        await query.edit_message_text("📭 لا توجد محاضرات VIP حالياً.")
        return
    
    lectures = list(vip_lectures_col.find({
        "status": "approved"
    }).limit(20))
    
    if not lectures:
        await query.edit_message_text(
            "📭 لا توجد محاضرات VIP حالياً.\n\n"
            "كن أول من يضيف محاضرة!",
            reply_markup=KeyboardBuilder.main_menu(user_id)
        )
        return
    
    message = "🎓 *محاضرات VIP المتاحة*\n\n"
    keyboard = []
    
    for lecture in lectures:
        title = lecture.get("title", "بدون عنوان")
        price = lecture.get("price", 0)
        teacher_id = lecture.get("user_id")
        
        teacher = get_user(teacher_id)
        teacher_name = teacher.get("first_name", "مدرس")
        
        price_text = "مجاني" if price == 0 else f"{format_currency(price)}"
        btn_text = f"{title[:20]} ({price_text}) - {teacher_name}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"purchase_lecture_{lecture['_id']}")])
    
    # Add button for uploading lectures
    keyboard.append([InlineKeyboardButton("📤 رفع محاضرة جديدة", callback_data="upload_lecture")])
    keyboard.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")])
    
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_balance_callback(query, context):
    """Handle balance callback."""
    user_id = query.from_user.id
    user_data = get_user(user_id)
    
    balance_msg = MessageBuilder.balance_message(user_data)
    
    await query.edit_message_text(
        balance_msg,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.main_menu(user_id)
    )

async def handle_invite_callback(query, context):
    """Handle invite callback."""
    user_id = query.from_user.id
    user_data = get_user(user_id)
    
    invite_reward = get_setting("invite_reward", 500)
    invite_link = f"https://t.me/{BOT_USERNAME.replace('@', '')}?start={user_data['invite_code']}"
    
    if user_data.get("vip_until") and user_data["vip_until"] > datetime.datetime.now():
        description = "🎓 انضم لأفضل بوت تعليمي مع محاضرات VIP حصرية!"
    else:
        description = "🎓 انضم لأفضل بوت تعليمي واحصل على هدية مجانية!"
    
    invite_text = f"""
    👥 *دعوة صديق*
    
    {description}
    
    *مكافأة الدعوة:* {format_currency(invite_reward)} دينار لكل صديق
    
    *رابط الدعوة الخاص بك:*
    `{invite_link}`
    
    *عدد المدعوين:* {user_data.get('invited_count', 0)}
    """
    
    keyboard = [
        [InlineKeyboardButton("📤 مشاركة الرابط", url=f"https://t.me/share/url?url={invite_link}&text={description}")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        invite_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ==================== Admin Handlers ====================
async def handle_admin_stats(query, context):
    """Handle admin statistics."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    stats_msg = MessageBuilder.admin_stats()
    
    await query.edit_message_text(
        stats_msg,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.admin_panel()
    )

async def handle_admin_users(query, context):
    """Handle admin users menu."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    await query.edit_message_text(
        "👥 *إدارة المستخدمين*\n\n"
        "اختر الإجراء المطلوب:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.admin_users()
    )

async def handle_admin_finance(query, context):
    """Handle admin finance menu."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    await query.edit_message_text(
        "💰 *إدارة الشحن والخصم*\n\n"
        "اختر الإجراء المطلوب:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.admin_finance()
    )

async def handle_admin_ban_menu(query, context):
    """Handle admin ban menu."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    await query.edit_message_text(
        "🚫 *إدارة الحظر*\n\n"
        "اختر الإجراء المطلوب:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.admin_users()
    )

async def handle_admin_services(query, context):
    """Handle admin services menu."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    await query.edit_message_text(
        "⚙️ *إدارة الخدمات*\n\n"
        "تفعيل/تعطيل الخدمات:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.admin_services()
    )

async def handle_admin_prices(query, context):
    """Handle admin prices menu."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    await query.edit_message_text(
        "💳 *إدارة الأسعار*\n\n"
        "اختر السعر الذي تريد تعديله:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.admin_prices()
    )

async def handle_admin_vip(query, context):
    """Handle admin VIP menu."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    await query.edit_message_text(
        "🎓 *إدارة نظام VIP*\n\n"
        "اختر الإجراء المطلوب:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.admin_vip()
    )

async def handle_admin_lectures(query, context):
    """Handle admin lectures menu."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    await query.edit_message_text(
        "📹 *إدارة المحاضرات*\n\n"
        "اختر الإجراء المطلوب:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.admin_lectures()
    )

async def handle_admin_broadcast_menu(query, context):
    """Handle admin broadcast menu."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    await query.edit_message_text(
        "📢 *الإذاعة للمستخدمين*\n\n"
        "أرسل النص الذي تريد إذاعته:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.back_button()
    )
    context.user_data['admin_action'] = 'broadcast'
    context.user_data['state'] = UserState.WAITING_BROADCAST

async def handle_admin_materials(query, context):
    """Handle admin materials menu."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    await query.edit_message_text(
        "📁 *إدارة المواد التعليمية*\n\n"
        "اختر الإجراء المطلوب:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.admin_materials()
    )

async def handle_admin_users_list(query, context):
    """Handle admin users list."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    if users_col is None:
        await query.edit_message_text("❌ قاعدة البيانات غير متوفرة.")
        return
    
    users = list(users_col.find().sort("created_at", DESCENDING).limit(20))
    
    message = "👥 *آخر 20 مستخدم*\n\n"
    for i, user in enumerate(users, 1):
        user_id = user["user_id"]
        balance = user.get("balance", 0)
        vip_status = "⭐" if user.get("vip_until") and user["vip_until"] > datetime.datetime.now() else ""
        banned_status = "🚫" if user.get("banned") else ""
        message += f"{i}. {user_id} - {format_currency(balance)} {vip_status}{banned_status}\n"
    
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.back_button("admin_users")
    )

async def handle_admin_search_user(query, context):
    """Handle admin search user."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    await query.edit_message_text(
        "🔍 *بحث عن مستخدم*\n\n"
        "أرسل معرف المستخدم:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.back_button("admin_users")
    )
    context.user_data['admin_action'] = 'search_user'
    context.user_data['state'] = UserState.WAITING_CHARGE_USER  # Reuse state

async def handle_admin_charge(query, context):
    """Handle admin charge."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    await query.edit_message_text(
        "💰 *شحن رصيد*\n\n"
        "أرسل معرف المستخدم:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.back_button("admin_finance")
    )
    context.user_data['admin_action'] = 'charge'
    context.user_data['state'] = UserState.WAITING_CHARGE_USER

async def handle_admin_deduct(query, context):
    """Handle admin deduct."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    await query.edit_message_text(
        "💸 *خصم رصيد*\n\n"
        "أرسل معرف المستخدم:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.back_button("admin_finance")
    )
    context.user_data['admin_action'] = 'deduct'
    context.user_data['state'] = UserState.WAITING_DEDUCT_USER

async def handle_admin_ban_user(query, context):
    """Handle admin ban user."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    await query.edit_message_text(
        "🚫 *حظر مستخدم*\n\n"
        "أرسل معرف المستخدم:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.back_button("admin_users")
    )
    context.user_data['admin_action'] = 'ban'
    context.user_data['state'] = UserState.WAITING_BAN_USER

async def handle_admin_unban_user(query, context):
    """Handle admin unban user."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    await query.edit_message_text(
        "✅ *فك حظر مستخدم*\n\n"
        "أرسل معرف المستخدم:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.back_button("admin_users")
    )
    context.user_data['admin_action'] = 'unban'
    context.user_data['state'] = UserState.WAITING_UNBAN_USER

async def handle_toggle_service(query, context, service_key):
    """Toggle service status."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    current = get_setting(f"{service_key}_enabled", True)
    new_value = not current
    
    service_names = {
        "exemption": "حساب درجة الاعفاء",
        "summary": "تلخيص الملازم",
        "qa": "سؤال وجواب",
        "help": "ساعدوني طالب",
        "vip": "خدمة VIP",
        "materials": "المواد التعليمية"
    }
    
    update_setting(f"{service_key}_enabled", new_value)
    
    status = "تم تفعيل" if new_value else "تم تعطيل"
    await query.answer(f"✅ {status} خدمة {service_names.get(service_key, service_key)}")
    
    await query.edit_message_text(
        "⚙️ *إدارة الخدمات*\n\n"
        "تفعيل/تعطيل الخدمات:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.admin_services()
    )

async def handle_price_service(query, context):
    """Handle service price change."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    current_price = get_setting("service_price", 1000)
    
    await query.edit_message_text(
        f"💰 *تغيير سعر الخدمات*\n\n"
        f"السعر الحالي: {format_currency(current_price)}\n\n"
        f"أرسل السعر الجديد (بالدينار العراقي):",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.back_button("admin_prices")
    )
    context.user_data['admin_action'] = 'change_service_price'
    context.user_data['state'] = UserState.WAITING_SERVICE_PRICE

async def handle_price_vip(query, context):
    """Handle VIP price change."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    current_price = get_setting("vip_subscription_price", 5000)
    
    await query.edit_message_text(
        f"⭐ *تغيير سعر اشتراك VIP*\n\n"
        f"السعر الحالي: {format_currency(current_price)}\n\n"
        f"أرسل السعر الجديد (بالدينار العراقي):",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.back_button("admin_prices")
    )
    context.user_data['admin_action'] = 'change_vip_price'
    context.user_data['state'] = UserState.WAITING_VIP_PRICE

async def handle_price_invite(query, context):
    """Handle invite reward change."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    current_reward = get_setting("invite_reward", 500)
    
    await query.edit_message_text(
        f"🎁 *تغيير مكافأة الدعوة*\n\n"
        f"المكافأة الحالية: {format_currency(current_reward)}\n\n"
        f"أرسل المكافأة الجديدة (بالدينار العراقي):",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.back_button("admin_prices")
    )
    context.user_data['admin_action'] = 'change_invite_reward'
    context.user_data['state'] = UserState.WAITING_INVITE_REWARD

async def handle_price_min_withdraw(query, context):
    """Handle minimum withdrawal change."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    current_min = get_setting("min_withdraw", 1000)
    
    await query.edit_message_text(
        f"💵 *تغيير الحد الأدنى للسحب*\n\n"
        f"الحد الحالي: {format_currency(current_min)}\n\n"
        f"أرسل الحد الجديد (بالدينار العراقي):",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.back_button("admin_prices")
    )
    context.user_data['admin_action'] = 'change_min_withdraw'
    context.user_data['state'] = UserState.WAITING_SERVICE_PRICE  # Reuse

async def handle_price_teacher_commission(query, context):
    """Handle teacher commission change."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    current_commission = get_setting("teacher_commission", 60)
    
    await query.edit_message_text(
        f"📊 *تغيير عمولة المدرس*\n\n"
        f"العمولة الحالية: {current_commission}%\n\n"
        f"أرسل النسبة الجديدة (0-100):",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.back_button("admin_prices")
    )
    context.user_data['admin_action'] = 'change_teacher_commission'
    context.user_data['state'] = UserState.WAITING_SERVICE_PRICE  # Reuse

async def handle_admin_vip_users(query, context):
    """Show VIP users."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    if users_col is None:
        await query.edit_message_text("❌ قاعدة البيانات غير متوفرة.")
        return
    
    vip_users = list(users_col.find({
        "vip_until": {"$gt": datetime.datetime.now()}
    }).limit(20))
    
    if not vip_users:
        await query.edit_message_text(
            "📭 لا يوجد مشتركين VIP حالياً.",
            reply_markup=KeyboardBuilder.back_button("admin_vip")
        )
        return
    
    message = "⭐ *قائمة مشتركين VIP*\n\n"
    for i, user in enumerate(vip_users, 1):
        user_id = user["user_id"]
        vip_until = user.get("vip_until")
        days_left = (vip_until - datetime.datetime.now()).days if vip_until else 0
        vip_balance = user.get("vip_balance", 0)
        message += f"{i}. {user_id} - {days_left} يوم - {format_currency(vip_balance)}\n"
    
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.back_button("admin_vip")
    )

async def handle_admin_withdraw_vip(query, context):
    """Handle VIP withdrawal."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    await query.edit_message_text(
        "💸 *سحب أرباح VIP*\n\n"
        "أرسل معرف المستخدم:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.back_button("admin_finance")
    )
    context.user_data['admin_action'] = 'withdraw_vip'
    context.user_data['state'] = UserState.WAITING_CHARGE_USER  # Reuse

async def handle_admin_pending_lectures(query, context):
    """Show pending lectures."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    if vip_lectures_col is None:
        await query.edit_message_text("❌ قاعدة البيانات غير متوفرة.")
        return
    
    lectures = list(vip_lectures_col.find({
        "status": "pending"
    }).limit(10))
    
    if not lectures:
        await query.edit_message_text(
            "📭 لا توجد محاضرات معلقة حالياً.",
            reply_markup=KeyboardBuilder.back_button("admin_lectures")
        )
        return
    
    message = "📋 *المحاضرات المعلقة*\n\n"
    keyboard = []
    
    for lecture in lectures:
        title = lecture.get("title", "بدون عنوان")
        user_id = lecture.get("user_id")
        price = lecture.get("price", 0)
        
        btn_text = f"{title[:20]} - {format_currency(price)} - {user_id}"
        keyboard.append([
            InlineKeyboardButton(btn_text, callback_data=f"view_lecture_{lecture['_id']}")
        ])
        keyboard.append([
            InlineKeyboardButton("✅ قبول", callback_data=f"approve_lecture_{lecture['_id']}"),
            InlineKeyboardButton("❌ رفض", callback_data=f"reject_lecture_{lecture['_id']}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_lectures")])
    
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_admin_broadcast_text(query, context):
    """Handle text broadcast."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    await query.edit_message_text(
        "📢 *الإذاعة للمستخدمين*\n\n"
        "أرسل النص الذي تريد إذاعته:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.back_button()
    )
    context.user_data['admin_action'] = 'broadcast'
    context.user_data['state'] = UserState.WAITING_BROADCAST

async def handle_admin_add_material(query, context):
    """Handle add material."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    await query.edit_message_text(
        "📁 *إضافة مادة جديدة*\n\n"
        "أرسل اسم المادة:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.back_button("admin_materials")
    )
    context.user_data['admin_action'] = 'add_material'
    context.user_data['state'] = UserState.WAITING_MATERIAL_NAME

async def handle_admin_list_materials(query, context):
    """List all materials."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    if materials_col is None:
        await query.edit_message_text("❌ قاعدة البيانات غير متوفرة.")
        return
    
    materials = list(materials_col.find().limit(20))
    
    if not materials:
        await query.edit_message_text(
            "📭 لا توجد مواد حالياً.",
            reply_markup=KeyboardBuilder.back_button("admin_materials")
        )
        return
    
    message = "📖 *قائمة المواد*\n\n"
    keyboard = []
    
    for material in materials:
        name = material.get("name", "بدون اسم")
        stage = material.get("stage", "غير محدد")
        btn_text = f"{name} - {stage}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"admin_view_material_{material['_id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_materials")])
    
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_admin_delete_material(query, context):
    """Handle delete material."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    if materials_col is None:
        await query.edit_message_text("❌ قاعدة البيانات غير متوفرة.")
        return
    
    materials = list(materials_col.find().limit(20))
    
    if not materials:
        await query.edit_message_text(
            "📭 لا توجد مواد حالياً.",
            reply_markup=KeyboardBuilder.back_button("admin_materials")
        )
        return
    
    message = "🗑️ *اختر المادة للحذف*\n\n"
    keyboard = []
    
    for material in materials:
        name = material.get("name", "بدون اسم")
        stage = material.get("stage", "غير محدد")
        btn_text = f"حذف: {name} - {stage}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"delete_material_{material['_id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_materials")])
    
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_approve_lecture(query, context, lecture_id):
    """Approve a lecture."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    if vip_lectures_col is None:
        await query.answer("❌ قاعدة البيانات غير متوفرة!", show_alert=True)
        return
    
    # Update lecture status
    vip_lectures_col.update_one(
        {"_id": lecture_id},
        {"$set": {"status": "approved", "approved_at": datetime.datetime.now()}}
    )
    
    # Get lecture info
    lecture = vip_lectures_col.find_one({"_id": lecture_id})
    if lecture:
        # Notify lecturer
        lecturer_id = lecture.get("user_id")
        try:
            await context.bot.send_message(
                chat_id=lecturer_id,
                text=f"✅ تمت الموافقة على محاضرتك: {lecture.get('title', '')}\n\n"
                     f"يمكنك مشاهدتها الآن في قسم محاضرات VIP."
            )
        except:
            pass
    
    await query.answer("✅ تمت الموافقة على المحاضرة!")
    await handle_admin_pending_lectures(query, context)

async def handle_reject_lecture(query, context, lecture_id):
    """Reject a lecture."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    if vip_lectures_col is None:
        await query.answer("❌ قاعدة البيانات غير متوفرة!", show_alert=True)
        return
    
    # Update lecture status
    vip_lectures_col.update_one(
        {"_id": lecture_id},
        {"$set": {"status": "rejected", "rejected_at": datetime.datetime.now()}}
    )
    
    # Get lecture info
    lecture = vip_lectures_col.find_one({"_id": lecture_id})
    if lecture:
        # Notify lecturer
        lecturer_id = lecture.get("user_id")
        try:
            await context.bot.send_message(
                chat_id=lecturer_id,
                text=f"❌ تم رفض محاضرتك: {lecture.get('title', '')}\n\n"
                     f"يمكنك التواصل مع الدعم الفني للاستفسار."
            )
        except:
            pass
    
    await query.answer("❌ تم رفض المحاضرة!")
    await handle_admin_pending_lectures(query, context)

async def handle_material_view(query, context, material_id):
    """View material."""
    user_id = query.from_user.id
    
    if materials_col is None:
        await query.answer("❌ قاعدة البيانات غير متوفرة!", show_alert=True)
        return
    
    material = materials_col.find_one({"_id": material_id})
    
    if not material:
        await query.answer("❌ المادة غير موجودة!", show_alert=True)
        return
    
    name = material.get("name", "بدون اسم")
    description = material.get("description", "بدون وصف")
    stage = material.get("stage", "غير محدد")
    file_id = material.get("file_id")
    
    message = f"""
    📖 *{name}*
    
    *الوصف:* {description}
    *المرحلة:* {stage}
    """
    
    keyboard = [[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]]
    
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    # Send file if available
    if file_id and context.user_data.get('send_file', True):
        try:
            await context.bot.send_document(
                chat_id=user_id,
                document=file_id,
                caption=f"📖 {name}"
            )
        except:
            await query.edit_message_text(
                "❌ حدث خطأ في إرسال الملف.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

async def handle_delete_material_confirm(query, context, material_id):
    """Confirm material deletion."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    if materials_col is None:
        await query.answer("❌ قاعدة البيانات غير متوفرة!", show_alert=True)
        return
    
    material = materials_col.find_one({"_id": material_id})
    
    if not material:
        await query.answer("❌ المادة غير موجودة!", show_alert=True)
        return
    
    name = material.get("name", "بدون اسم")
    
    context.user_data['delete_material_id'] = material_id
    
    await query.edit_message_text(
        f"⚠️ *تأكيد الحذف*\n\n"
        f"هل أنت متأكد من حذف المادة:\n"
        f"*{name}*\n\n"
        f"هذا الإجراء لا يمكن التراجع عنه.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.confirm_cancel("admin_materials")
    )

async def handle_confirm_delete_material(query, context):
    """Confirm and delete material."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    material_id = context.user_data.get('delete_material_id')
    
    if not material_id:
        await query.answer("❌ لم يتم تحديد مادة!", show_alert=True)
        return
    
    if materials_col is None:
        await query.edit_message_text("❌ قاعدة البيانات غير متوفرة.")
        return
    
    # Delete material
    result = materials_col.delete_one({"_id": material_id})
    
    if result.deleted_count > 0:
        await query.edit_message_text(
            "✅ تم حذف المادة بنجاح!",
            reply_markup=KeyboardBuilder.back_button("admin_materials")
        )
    else:
        await query.edit_message_text(
            "❌ فشل حذف المادة!",
            reply_markup=KeyboardBuilder.back_button("admin_materials")
        )
    
    # Clear temp data
    if 'delete_material_id' in context.user_data:
        del context.user_data['delete_material_id']

async def handle_confirm_vip_purchase(query, context):
    """Confirm VIP purchase."""
    user_id = query.from_user.id
    user_data = get_user(user_id)
    
    vip_price = get_setting("vip_subscription_price", 5000)
    
    if user_data["balance"] < vip_price:
        await query.edit_message_text(
            f"❌ رصيدك غير كافي!\n\n"
            f"💰 سعر الاشتراك: {format_currency(vip_price)}\n"
            f"💵 رصيدك الحالي: {format_currency(user_data['balance'])}\n\n"
            f"لشحن الرصيد تواصل مع: @{SUPPORT_USERNAME.replace('@', '')}",
            reply_markup=KeyboardBuilder.main_menu(user_id)
        )
        return
    
    # Deduct balance
    new_balance = user_data["balance"] - vip_price
    update_user(user_id, {"balance": new_balance})
    
    # Set VIP expiration
    vip_until = datetime.datetime.now() + datetime.timedelta(days=30)
    update_user(user_id, {
        "vip_until": vip_until,
        "vip_balance": 0
    })
    
    # Record transaction
    create_transaction(user_id, "vip_subscription", -vip_price, "اشتراك VIP شهري")
    
    await query.edit_message_text(
        f"""
        ✅ *تم الاشتراك في VIP بنجاح!*
        
        ⭐ اشتراكك ساري لمدة 30 يوم
        📅 تاريخ الانتهاء: {format_date(vip_until)}
        💰 رصيدك الجديد: {format_currency(new_balance)}
        
        *يمكنك الآن:*
        📤 رفع محاضرات فيديو
        💸 كسب 60% من أرباح المحاضرات
        📊 متابعة إحصائيات محاضراتك
        
        *لرفع أول محاضرة:* اضغط على زر "رفع محاضرة" في قسم محاضرات VIP
        """,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.main_menu(user_id)
    )

async def handle_purchase_lecture(query, context, lecture_id):
    """Purchase a lecture."""
    user_id = query.from_user.id
    user_data = get_user(user_id)
    
    if vip_lectures_col is None:
        await query.answer("❌ قاعدة البيانات غير متوفرة!", show_alert=True)
        return
    
    lecture = vip_lectures_col.find_one({"_id": lecture_id})
    
    if not lecture:
        await query.answer("❌ المحاضرة غير موجودة!", show_alert=True)
        return
    
    price = lecture.get("price", 0)
    
    if price > 0 and user_data["balance"] < price:
        await query.edit_message_text(
            f"❌ رصيدك غير كافي!\n\n"
            f"💰 سعر المحاضرة: {format_currency(price)}\n"
            f"💵 رصيدك الحالي: {format_currency(user_data['balance'])}",
            reply_markup=KeyboardBuilder.main_menu(user_id)
        )
        return
    
    if price > 0:
        # Deduct payment
        new_balance = user_data["balance"] - price
        update_user(user_id, {"balance": new_balance})
        create_transaction(user_id, "lecture_purchase", -price, f"شراء محاضرة: {lecture.get('title', '')}")
        
        # Calculate earnings (60% to teacher, 40% to admin)
        teacher_earnings = int(price * 0.6)
        admin_earnings = price - teacher_earnings
        
        # Update teacher's VIP balance
        teacher_id = lecture.get("user_id")
        teacher = get_user(teacher_id)
        teacher_vip_balance = teacher.get("vip_balance", 0) + teacher_earnings
        update_user(teacher_id, {"vip_balance": teacher_vip_balance})
        
        # Update lecture stats
        vip_lectures_col.update_one(
            {"_id": lecture_id},
            {
                "$inc": {
                    "purchases": 1,
                    "revenue": price
                }
            }
        )
        
        # Record teacher transaction
        create_transaction(teacher_id, "lecture_earning", teacher_earnings, f"ربح من محاضرة: {lecture.get('title', '')}")
    
    # Send video
    video_file_id = lecture.get("video_file_id")
    
    if video_file_id:
        try:
            await context.bot.send_video(
                chat_id=user_id,
                video=video_file_id,
                caption=f"🎓 {lecture.get('title', '')}\n\n{lecture.get('description', '')}"
            )
            
            if price > 0:
                await query.edit_message_text(
                    f"✅ تم شراء المحاضرة بنجاح!\n\n"
                    f"السعر: {format_currency(price)}\n"
                    f"رصيدك الجديد: {format_currency(new_balance)}",
                    reply_markup=KeyboardBuilder.main_menu(user_id)
                )
            else:
                await query.edit_message_text(
                    "✅ تم إرسال المحاضرة المجانية!",
                    reply_markup=KeyboardBuilder.main_menu(user_id)
                )
        except:
            await query.edit_message_text(
                "❌ حدث خطأ في إرسال المحاضرة.",
                reply_markup=KeyboardBuilder.main_menu(user_id)
            )
    else:
        await query.edit_message_text(
            "❌ المحاضرة غير متوفرة.",
            reply_markup=KeyboardBuilder.main_menu(user_id)
        )

async def handle_approve_question(query, context, question_id):
    """Approve a question."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    if questions_col is None:
        await query.answer("❌ قاعدة البيانات غير متوفرة!", show_alert=True)
        return
    
    # Update question status
    questions_col.update_one(
        {"_id": question_id},
        {"$set": {"status": "approved", "approved_at": datetime.datetime.now()}}
    )
    
    await query.answer("✅ تمت الموافقة على السؤال!")
    # You can add logic to post the question to a help channel here

async def handle_reject_question(query, context, question_id):
    """Reject a question."""
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("❌ ليس لديك صلاحية الوصول!", show_alert=True)
        return
    
    if questions_col is None:
        await query.answer("❌ قاعدة البيانات غير متوفرة!", show_alert=True)
        return
    
    # Update question status
    questions_col.update_one(
        {"_id": question_id},
        {"$set": {"status": "rejected", "rejected_at": datetime.datetime.now()}}
    )
    
    await query.answer("❌ تم رفض السؤال!")

# ==================== Message Handlers ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all messages."""
    user_id = update.effective_user.id
    message = update.message
    
    # Check maintenance mode
    if get_setting("maintenance_mode", False) and user_id != ADMIN_ID:
        maintenance_msg = get_setting("maintenance_message", "البوت تحت الصيانة حالياً")
        await message.reply_text(f"🔧 {maintenance_msg}")
        return
    
    # Get user
    user_data = get_user(user_id)
    
    # Check if banned
    if user_data.get("banned") and user_id != ADMIN_ID:
        await message.reply_text("❌ تم حظرك من استخدام البوت.")
        return
    
    # Check user state
    state = context.user_data.get('state')
    
    # Handle based on state
    if state == UserState.WAITING_COURSE1:
        await handle_course_score(update, context, 1)
    elif state == UserState.WAITING_COURSE2:
        await handle_course_score(update, context, 2)
    elif state == UserState.WAITING_COURSE3:
        await handle_course_score(update, context, 3)
    elif state == UserState.WAITING_PDF:
        await handle_pdf_upload(update, context)
    elif state == UserState.WAITING_QUESTION:
        await handle_question_input(update, context)
    elif state == UserState.WAITING_CHARGE_USER:
        await handle_admin_charge_user(update, context)
    elif state == UserState.WAITING_CHARGE_AMOUNT:
        await handle_admin_charge_amount(update, context)
    elif state == UserState.WAITING_DEDUCT_USER:
        await handle_admin_deduct_user(update, context)
    elif state == UserState.WAITING_DEDUCT_AMOUNT:
        await handle_admin_deduct_amount(update, context)
    elif state == UserState.WAITING_BAN_USER:
        await handle_admin_ban_user_input(update, context)
    elif state == UserState.WAITING_UNBAN_USER:
        await handle_admin_unban_user_input(update, context)
    elif state == UserState.WAITING_BROADCAST:
        await handle_admin_broadcast_input(update, context)
    elif state == UserState.WAITING_VIP_PRICE:
        await handle_admin_vip_price_input(update, context)
    elif state == UserState.WAITING_SERVICE_PRICE:
        await handle_admin_service_price_input(update, context)
    elif state == UserState.WAITING_INVITE_REWARD:
        await handle_admin_invite_reward_input(update, context)
    elif state == UserState.WAITING_MATERIAL_NAME:
        await handle_admin_material_name(update, context)
    elif state == UserState.WAITING_MATERIAL_DESC:
        await handle_admin_material_desc(update, context)
    elif state == UserState.WAITING_MATERIAL_STAGE:
        await handle_admin_material_stage(update, context)
    elif state == UserState.WAITING_MATERIAL_FILE:
        await handle_admin_material_file(update, context)
    else:
        # Default: show main menu
        await message.reply_text(
            "🏠 *القائمة الرئيسية*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=KeyboardBuilder.main_menu(user_id)
        )

async def handle_course_score(update: Update, context: ContextTypes.DEFAULT_TYPE, course_num: int):
    """Handle course score input."""
    user_id = update.effective_user.id
    message = update.message
    
    try:
        score = float(message.text)
        if not (0 <= score <= 100):
            raise ValueError
        
        # Store score
        if 'course_scores' not in context.user_data:
            context.user_data['course_scores'] = {}
        context.user_data['course_scores'][f'course{course_num}'] = score
        
        if course_num == 1:
            await message.reply_text("أدخل درجة الكورس الثاني (0-100):")
            context.user_data['state'] = UserState.WAITING_COURSE2
        elif course_num == 2:
            await message.reply_text("أدخل درجة الكورس الثالث (0-100):")
            context.user_data['state'] = UserState.WAITING_COURSE3
        elif course_num == 3:
            # Calculate average
            scores = context.user_data['course_scores']
            avg = (scores['course1'] + scores['course2'] + scores['course3']) / 3
            
            # Deduct payment
            service_price = context.user_data.get('service_price', 1000)
            user_data = get_user(user_id)
            
            if user_data["balance"] >= service_price:
                new_balance = user_data["balance"] - service_price
                update_user(user_id, {"balance": new_balance})
                create_transaction(user_id, "service_payment", -service_price, "خدمة حساب درجة الاعفاء")
                
                if avg >= 90:
                    result_msg = f"""
                    🎉 *مبروك!*
                    
                    • معدلك النهائي: {avg:.2f}
                    • أنت معفي من المادة!
                    
                    💰 تم خصم {format_currency(service_price)}
                    📊 رصيدك الجديد: {format_currency(new_balance)}
                    """
                else:
                    result_msg = f"""
                    📊 *نتيجتك*
                    
                    • معدلك النهائي: {avg:.2f}
                    • للأسف أنت غير معفي من المادة
                    
                    💰 تم خصم {format_currency(service_price)}
                    📊 رصيدك الجديد: {format_currency(new_balance)}
                    """
            else:
                result_msg = f"""
                ❌ *رصيد غير كافي*
                
                • المعدل المحسوب: {avg:.2f}
                • الرصيد المطلوب: {format_currency(service_price)}
                • رصيدك الحالي: {format_currency(user_data['balance'])}
                
                لشحن الرصيد: @{SUPPORT_USERNAME.replace('@', '')}
                """
            
            await message.reply_text(
                result_msg,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=KeyboardBuilder.main_menu(user_id)
            )
            
            # Clear state
            context.user_data.clear()
        
    except ValueError:
        await message.reply_text("❌ الرجاء إدخال درجة صحيحة بين 0 و 100:")

async def handle_pdf_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle PDF upload for summarization."""
    user_id = update.effective_user.id
    message = update.message
    
    if not message.document:
        await message.reply_text("❌ الرجاء إرسال ملف PDF:")
        return
    
    document = message.document
    if not document.file_name.lower().endswith('.pdf'):
        await message.reply_text("❌ الرجاء إرسال ملف PDF فقط:")
        return
    
    await message.reply_text("⏳ جاري تحليل الملف وتلخيصه...")
    
    try:
        # Download file
        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()
        
        # Extract text
        text = extract_text_from_pdf(file_bytes)
        
        if not text or len(text.strip()) < 50:
            await message.reply_text("❌ لا يمكن قراءة النص من الملف أو الملف فارغ.")
            return
        
        # Summarize using AI
        if model:
            prompt = f"لخص النص التالي بشكل احترافي باللغة العربية:\n\n{text[:3000]}"
            response = model.generate_content(prompt)
            summary = response.text
        else:
            summary = "عذراً، خدمة الذكاء الاصطناعي غير متوفرة حالياً."
        
        # Create PDF with summary
        summary_pdf = create_summary_pdf(summary, document.file_name)
        
        # Deduct payment
        service_price = context.user_data.get('service_price', 1000)
        user_data = get_user(user_id)
        
        if user_data["balance"] >= service_price:
            new_balance = user_data["balance"] - service_price
            update_user(user_id, {"balance": new_balance})
            create_transaction(user_id, "service_payment", -service_price, "خدمة تلخيص الملازم")
            
            # Send summarized PDF
            await message.reply_document(
                document=InputFile(summary_pdf, filename=f"ملخص_{document.file_name}"),
                caption=f"""
                ✅ *تم تلخيص الملف بنجاح!*
                
                📄 الملف الأصلي: {document.file_name}
                📝 التلخيص: {len(summary)} حرف
                
                💰 تم خصم {format_currency(service_price)}
                📊 رصيدك الجديد: {format_currency(new_balance)}
                """,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await message.reply_text(
                f"""
                ❌ *رصيد غير كافي*
                
                📄 الملف: {document.file_name}
                💰 الرصيد المطلوب: {format_currency(service_price)}
                📊 رصيدك الحالي: {format_currency(user_data['balance'])}
                
                لشحن الرصيد: @{SUPPORT_USERNAME.replace('@', '')}
                """,
                parse_mode=ParseMode.MARKDOWN
            )
        
        # Clear state
        context.user_data.clear()
        
        # Show main menu
        await message.reply_text(
            "🏠 *القائمة الرئيسية*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=KeyboardBuilder.main_menu(user_id)
        )
        
    except Exception as e:
        logger.error(f"PDF summarization error: {e}")
        await message.reply_text("❌ حدث خطأ في معالجة الملف. يرجى المحاولة لاحقاً.")
        context.user_data.clear()

async def handle_question_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle question input."""
    user_id = update.effective_user.id
    message = update.message
    service_type = context.user_data.get('service_type')
    
    question_text = ""
    
    if message.text:
        question_text = message.text
    elif message.caption:
        question_text = message.caption
    elif message.photo:
        question_text = "سؤال مصور"
    
    if service_type == 'qa':
        # AI Q&A service
        await message.reply_text("⏳ جاري البحث عن الإجابة...")
        
        try:
            if model:
                prompt = f"أجب على السؤال التالي بشكل علمي ومنهجي:\n\n{question_text}"
                response = model.generate_content(prompt)
                answer = response.text
            else:
                answer = "عذراً، خدمة الذكاء الاصطناعي غير متوفرة حالياً."
            
            # Deduct payment
            service_price = context.user_data.get('service_price', 1000)
            user_data = get_user(user_id)
            
            if user_data["balance"] >= service_price:
                new_balance = user_data["balance"] - service_price
                update_user(user_id, {"balance": new_balance})
                create_transaction(user_id, "service_payment", -service_price, "خدمة سؤال وجواب")
                
                await message.reply_text(
                    f"""
                    🤖 *الإجابة:*
                    
                    {answer}
                    
                    ---
                    💰 تم خصم {format_currency(service_price)}
                    📊 رصيدك الجديد: {format_currency(new_balance)}
                    """,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await message.reply_text(
                    f"""
                    ❌ *رصيد غير كافي*
                    
                    💰 الرصيد المطلوب: {format_currency(service_price)}
                    📊 رصيدك الحالي: {format_currency(user_data['balance'])}
                    
                    لشحن الرصيد: @{SUPPORT_USERNAME.replace('@', '')}
                    """,
                    parse_mode=ParseMode.MARKDOWN
                )
            
        except Exception as e:
            logger.error(f"AI Q&A error: {e}")
            await message.reply_text("❌ حدث خطأ في معالجة سؤالك. يرجى المحاولة لاحقاً.")
    
    elif service_type == 'help':
        # Help service - store question
        question_data = {
            "user_id": user_id,
            "question": question_text,
            "type": "text",
            "status": "pending",
            "created_at": datetime.datetime.now()
        }
        
        if questions_col:
            questions_col.insert_one(question_data)
        
        # Notify admin
        admin_message = f"""
        🆘 *سؤال جديد يحتاج موافقة*
        
        • المستخدم: {user_id}
        • السؤال: {question_text[:200]}...
        • الوقت: {format_date(datetime.datetime.now())}
        """
        
        await message.reply_text(
            """
            ✅ *تم إرسال سؤالك بنجاح*
            
            سيتم:
            1. مراجعة سؤالك من الإدارة
            2. الموافقة أو الرفض خلال 24 ساعة
            3. عرضه في قسم المساعدة للإجابة عليه
            
            ستتلقى إشعاراً عند الرد على سؤالك.
            """,
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Clear state
    context.user_data.clear()
    
    # Show main menu
    await message.reply_text(
        "🏠 *القائمة الرئيسية*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.main_menu(user_id)
    )

async def handle_admin_charge_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin charge - get user ID."""
    user_id = update.effective_user.id
    message = update.message
    
    if user_id != ADMIN_ID:
        await message.reply_text("❌ ليس لديك صلاحية الوصول!")
        return
    
    try:
        target_user_id = int(message.text)
        target_user = get_user(target_user_id, create_if_missing=False)
        
        if not target_user:
            await message.reply_text("❌ المستخدم غير موجود!")
            return
        
        context.user_data['charge_user_id'] = target_user_id
        context.user_data['state'] = UserState.WAITING_CHARGE_AMOUNT
        
        await message.reply_text(
            f"👤 المستخدم: {target_user_id}\n\n"
            f"أرسل المبلغ المراد شحنه (بالدينار العراقي):",
            reply_markup=KeyboardBuilder.back_button("admin_finance")
        )
        
    except ValueError:
        await message.reply_text("❌ الرجاء إرسال معرف مستخدم صحيح:")

async def handle_admin_charge_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin charge - get amount."""
    user_id = update.effective_user.id
    message = update.message
    
    if user_id != ADMIN_ID:
        await message.reply_text("❌ ليس لديك صلاحية الوصول!")
        return
    
    try:
        amount = int(message.text)
        if amount <= 0:
            raise ValueError
        
        target_user_id = context.user_data.get('charge_user_id')
        
        if not target_user_id:
            await message.reply_text("❌ حدث خطأ في العملية!")
            return
        
        # Charge user
        target_user = get_user(target_user_id)
        current_balance = target_user.get("balance", 0)
        new_balance = current_balance + amount
        
        update_user(target_user_id, {"balance": new_balance})
        create_transaction(target_user_id, "admin_charge", amount, f"شحن من المدير {user_id}")
        
        # Notify target user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"""
                💰 *تم شحن رصيدك*
                
                • المبلغ: {format_currency(amount)}
                • الرصيد السابق: {format_currency(current_balance)}
                • الرصيد الجديد: {format_currency(new_balance)}
                • التاريخ: {format_date(datetime.datetime.now())}
                
                🔧 العملية: شحن من الإدارة
                """
            )
        except:
            pass
        
        await message.reply_text(
            f"""
            ✅ *تم شحن الرصيد بنجاح*
            
            • المستخدم: {target_user_id}
            • المبلغ: {format_currency(amount)}
            • الرصيد الجديد: {format_currency(new_balance)}
            """,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=KeyboardBuilder.admin_panel()
        )
        
        # Clear state
        context.user_data.clear()
        
    except ValueError:
        await message.reply_text("❌ الرجاء إرسال مبلغ صحيح أكبر من صفر:")

async def handle_admin_deduct_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin deduct - get user ID."""
    user_id = update.effective_user.id
    message = update.message
    
    if user_id != ADMIN_ID:
        await message.reply_text("❌ ليس لديك صلاحية الوصول!")
        return
    
    try:
        target_user_id = int(message.text)
        target_user = get_user(target_user_id, create_if_missing=False)
        
        if not target_user:
            await message.reply_text("❌ المستخدم غير موجود!")
            return
        
        context.user_data['deduct_user_id'] = target_user_id
        context.user_data['state'] = UserState.WAITING_DEDUCT_AMOUNT
        
        current_balance = target_user.get("balance", 0)
        
        await message.reply_text(
            f"👤 المستخدم: {target_user_id}\n"
            f"💰 الرصيد الحالي: {format_currency(current_balance)}\n\n"
            f"أرسل المبلغ المراد خصمه (بالدينار العراقي):",
            reply_markup=KeyboardBuilder.back_button("admin_finance")
        )
        
    except ValueError:
        await message.reply_text("❌ الرجاء إرسال معرف مستخدم صحيح:")

async def handle_admin_deduct_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin deduct - get amount."""
    user_id = update.effective_user.id
    message = update.message
    
    if user_id != ADMIN_ID:
        await message.reply_text("❌ ليس لديك صلاحية الوصول!")
        return
    
    try:
        amount = int(message.text)
        if amount <= 0:
            raise ValueError
        
        target_user_id = context.user_data.get('deduct_user_id')
        
        if not target_user_id:
            await message.reply_text("❌ حدث خطأ في العملية!")
            return
        
        # Check if user has enough balance
        target_user = get_user(target_user_id)
        current_balance = target_user.get("balance", 0)
        
        if current_balance < amount:
            await message.reply_text(
                f"❌ رصيد المستخدم غير كافي!\n"
                f"💰 الرصيد الحالي: {format_currency(current_balance)}\n"
                f"💸 المبلغ المطلوب: {format_currency(amount)}",
                reply_markup=KeyboardBuilder.admin_panel()
            )
            context.user_data.clear()
            return
        
        new_balance = current_balance - amount
        
        update_user(target_user_id, {"balance": new_balance})
        create_transaction(target_user_id, "admin_deduct", -amount, f"خصم من المدير {user_id}")
        
        await message.reply_text(
            f"""
            ✅ *تم خصم الرصيد بنجاح*
            
            • المستخدم: {target_user_id}
            • المبلغ: {format_currency(amount)}
            • الرصيد الجديد: {format_currency(new_balance)}
            """,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=KeyboardBuilder.admin_panel()
        )
        
        # Clear state
        context.user_data.clear()
        
    except ValueError:
        await message.reply_text("❌ الرجاء إرسال مبلغ صحيح أكبر من صفر:")

async def handle_admin_ban_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin ban - get user ID."""
    user_id = update.effective_user.id
    message = update.message
    
    if user_id != ADMIN_ID:
        await message.reply_text("❌ ليس لديك صلاحية الوصول!")
        return
    
    try:
        target_user_id = int(message.text)
        target_user = get_user(target_user_id, create_if_missing=False)
        
        if not target_user:
            await message.reply_text("❌ المستخدم غير موجود!")
            return
        
        if target_user.get("banned"):
            await message.reply_text("⚠️ هذا المستخدم محظور بالفعل!")
            return
        
        # Ban user
        update_user(target_user_id, {
            "banned": True,
            "ban_reason": "حظر من المدير",
            "ban_until": datetime.datetime.now() + datetime.timedelta(days=30)
        })
        
        # Notify target user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"""
                🚫 *تم حظر حسابك*
                
                • السبب: حظر من الإدارة
                • المدة: 30 يوم
                • التاريخ: {format_date(datetime.datetime.now())}
                
                للاستئناف: @{SUPPORT_USERNAME.replace('@', '')}
                """
            )
        except:
            pass
        
        await message.reply_text(
            f"""
            ✅ *تم حظر المستخدم بنجاح*
            
            • المستخدم: {target_user_id}
            • المدة: 30 يوم
            • التاريخ: {format_date(datetime.datetime.now())}
            """,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=KeyboardBuilder.admin_panel()
        )
        
        # Clear state
        context.user_data.clear()
        
    except ValueError:
        await message.reply_text("❌ الرجاء إرسال معرف مستخدم صحيح:")

async def handle_admin_unban_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin unban - get user ID."""
    user_id = update.effective_user.id
    message = update.message
    
    if user_id != ADMIN_ID:
        await message.reply_text("❌ ليس لديك صلاحية الوصول!")
        return
    
    try:
        target_user_id = int(message.text)
        target_user = get_user(target_user_id, create_if_missing=False)
        
        if not target_user:
            await message.reply_text("❌ المستخدم غير موجود!")
            return
        
        if not target_user.get("banned"):
            await message.reply_text("⚠️ هذا المستخدم غير محظور!")
            return
        
        # Unban user
        update_user(target_user_id, {
            "banned": False,
            "ban_reason": None,
            "ban_until": None
        })
        
        # Notify target user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"""
                ✅ *تم فك حظر حسابك*
                
                • التاريخ: {format_date(datetime.datetime.now())}
                • يمكنك الآن استخدام البوت بشكل طبيعي
                
                نرحب بعودتك! 🎉
                """
            )
        except:
            pass
        
        await message.reply_text(
            f"""
            ✅ *تم فك حظر المستخدم بنجاح*
            
            • المستخدم: {target_user_id}
            • التاريخ: {format_date(datetime.datetime.now())}
            """,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=KeyboardBuilder.admin_panel()
        )
        
        # Clear state
        context.user_data.clear()
        
    except ValueError:
        await message.reply_text("❌ الرجاء إرسال معرف مستخدم صحيح:")

async def handle_admin_broadcast_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin broadcast text input."""
    user_id = update.effective_user.id
    message = update.message
    
    if user_id != ADMIN_ID:
        await message.reply_text("❌ ليس لديك صلاحية الوصول!")
        return
    
    broadcast_text = message.text
    
    await message.reply_text("⏳ جاري إرسال الإذاعة للمستخدمين...")
    
    # Get all active users (not banned)
    if users_col is None:
        await message.reply_text("❌ قاعدة البيانات غير متوفرة!")
        return
    
    users = users_col.find({"banned": False})
    
    success = 0
    failed = 0
    
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user["user_id"],
                text=broadcast_text,
                parse_mode=ParseMode.MARKDOWN
            )
            success += 1
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.05)
            
        except Exception as e:
            failed += 1
            logger.error(f"Failed to send broadcast to {user['user_id']}: {e}")
    
    await message.reply_text(
        f"""
        📢 *تم إرسال الإذاعة بنجاح*
        
        • الناجح: {success}
        • الفاشل: {failed}
        • التاريخ: {format_date(datetime.datetime.now())}
        """,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.admin_panel()
    )
    
    # Clear state
    context.user_data.clear()

async def handle_admin_vip_price_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle VIP price change."""
    user_id = update.effective_user.id
    message = update.message
    
    if user_id != ADMIN_ID:
        await message.reply_text("❌ ليس لديك صلاحية الوصول!")
        return
    
    try:
        new_price = int(message.text)
        if new_price < 1000:
            await message.reply_text("❌ السعر يجب أن يكون 1000 دينار على الأقل!")
            return
        
        old_price = get_setting("vip_subscription_price", 5000)
        update_setting("vip_subscription_price", new_price)
        
        await message.reply_text(
            f"""
            ✅ *تم تغيير سعر اشتراك VIP*
            
            • السعر القديم: {format_currency(old_price)}
            • السعر الجديد: {format_currency(new_price)}
            • التاريخ: {format_date(datetime.datetime.now())}
            """,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=KeyboardBuilder.admin_panel()
        )
        
        # Clear state
        context.user_data.clear()
        
    except ValueError:
        await message.reply_text("❌ الرجاء إرسال سعر صحيح:")

async def handle_admin_service_price_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle service price change."""
    user_id = update.effective_user.id
    message = update.message
    
    if user_id != ADMIN_ID:
        await message.reply_text("❌ ليس لديك صلاحية الوصول!")
        return
    
    try:
        new_price = int(message.text)
        if new_price < 100:
            await message.reply_text("❌ السعر يجب أن يكون 100 دينار على الأقل!")
            return
        
        old_price = get_setting("service_price", 1000)
        update_setting("service_price", new_price)
        
        await message.reply_text(
            f"""
            ✅ *تم تغيير سعر الخدمات*
            
            • السعر القديم: {format_currency(old_price)}
            • السعر الجديد: {format_currency(new_price)}
            • التاريخ: {format_date(datetime.datetime.now())}
            """,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=KeyboardBuilder.admin_panel()
        )
        
        # Clear state
        context.user_data.clear()
        
    except ValueError:
        await message.reply_text("❌ الرجاء إرسال سعر صحيح:")

async def handle_admin_invite_reward_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle invite reward change."""
    user_id = update.effective_user.id
    message = update.message
    
    if user_id != ADMIN_ID:
        await message.reply_text("❌ ليس لديك صلاحية الوصول!")
        return
    
    try:
        new_reward = int(message.text)
        if new_reward < 0:
            await message.reply_text("❌ المكافأة يجب أن تكون صفر أو أكثر!")
            return
        
        old_reward = get_setting("invite_reward", 500)
        update_setting("invite_reward", new_reward)
        
        await message.reply_text(
            f"""
            ✅ *تم تغيير مكافأة الدعوة*
            
            • المكافأة القديمة: {format_currency(old_reward)}
            • المكافأة الجديدة: {format_currency(new_reward)}
            • التاريخ: {format_date(datetime.datetime.now())}
            """,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=KeyboardBuilder.admin_panel()
        )
        
        # Clear state
        context.user_data.clear()
        
    except ValueError:
        await message.reply_text("❌ الرجاء إرسال مكافأة صحيحة:")

async def handle_admin_material_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle material name input."""
    user_id = update.effective_user.id
    message = update.message
    
    if user_id != ADMIN_ID:
        await message.reply_text("❌ ليس لديك صلاحية الوصول!")
        return
    
    material_name = message.text.strip()
    if len(material_name) < 2:
        await message.reply_text("❌ اسم المادة قصير جداً!")
        return
    
    context.user_data['material_name'] = material_name
    context.user_data['state'] = UserState.WAITING_MATERIAL_DESC
    
    await message.reply_text(
        "📝 *الخطوة 2/4*\n\n"
        "أرسل وصف المادة:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.back_button("admin_materials")
    )

async def handle_admin_material_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle material description input."""
    user_id = update.effective_user.id
    message = update.message
    
    if user_id != ADMIN_ID:
        await message.reply_text("❌ ليس لديك صلاحية الوصول!")
        return
    
    material_desc = message.text.strip()
    
    context.user_data['material_desc'] = material_desc
    context.user_data['state'] = UserState.WAITING_MATERIAL_STAGE
    
    await message.reply_text(
        "🎓 *الخطوة 3/4*\n\n"
        "أرسل المرحلة الدراسية (مثال: الصف السادس, المرحلة المتوسطة):",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.back_button("admin_materials")
    )

async def handle_admin_material_stage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle material stage input."""
    user_id = update.effective_user.id
    message = update.message
    
    if user_id != ADMIN_ID:
        await message.reply_text("❌ ليس لديك صلاحية الوصول!")
        return
    
    material_stage = message.text.strip()
    
    context.user_data['material_stage'] = material_stage
    context.user_data['state'] = UserState.WAITING_MATERIAL_FILE
    
    await message.reply_text(
        "📁 *الخطوة 4/4*\n\n"
        "أرسل ملف المادة (PDF, Word, أو صورة):",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.back_button("admin_materials")
    )

async def handle_admin_material_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle material file upload."""
    user_id = update.effective_user.id
    message = update.message
    
    if user_id != ADMIN_ID:
        await message.reply_text("❌ ليس لديك صلاحية الوصول!")
        return
    
    if not message.document and not message.photo:
        await message.reply_text("❌ الرجاء إرسال ملف أو صورة!")
        return
    
    file_id = None
    file_name = ""
    
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name or "ملف"
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_name = "صورة"
    
    if materials_col is None:
        await message.reply_text("❌ قاعدة البيانات غير متوفرة!")
        return
    
    # Save material to database
    material_data = {
        "name": context.user_data.get('material_name'),
        "description": context.user_data.get('material_desc'),
        "stage": context.user_data.get('material_stage'),
        "file_id": file_id,
        "file_name": file_name,
        "status": "active",
        "created_at": datetime.datetime.now(),
        "created_by": user_id
    }
    
    materials_col.insert_one(material_data)
    
    await message.reply_text(
        f"""
        ✅ *تم إضافة المادة بنجاح!*
        
        *اسم المادة:* {material_data['name']}
        *المرحلة:* {material_data['stage']}
        *نوع الملف:* {material_data['file_name']}
        
        يمكن للمستخدمين الآن الوصول إلى هذه المادة من قسم "ملازمي ومرشحاتي".
        """,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=KeyboardBuilder.admin_panel()
    )
    
    # Clear state
    context.user_data.clear()

# ==================== Main Function ====================
def main():
    """Main function to run the bot."""
    # Create application
    persistence = PicklePersistence(filepath=DATA_DIR / "bot_persistence.pickle")
    
    application = ApplicationBuilder() \
        .token(TOKEN) \
        .persistence(persistence) \
        .build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("invite", invite_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Add message handler (must be last)
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    # Set bot commands
    async def set_commands():
        commands = [
            BotCommand("start", "تشغيل البوت"),
            BotCommand("help", "المساعدة"),
            BotCommand("balance", "عرض الرصيد"),
            BotCommand("invite", "دعوة صديق"),
            BotCommand("cancel", "إلغاء العملية الحالية")
        ]
        await application.bot.set_my_commands(commands)
    
    application.run_polling()

if __name__ == "__main__":
    main()
