#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت تليجرام متكامل للتعليم - "يلا نتعلم"
الإصدار النهائي المتوافق مع Render.com
"""

# ============================================
# المكتبات الأساسية
# ============================================
import os
import sys
import logging
import json
import asyncio
import sqlite3
import threading
import time
import random
import string
import hashlib
import re
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path
from functools import wraps
from collections import defaultdict
import base64
import io
import urllib.parse
import csv

# مكتبات تليجرام
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup, 
    KeyboardButton,
    ReplyKeyboardRemove,
    WebAppInfo,
    InputFile,
    Document,
    PhotoSize,
    InputMediaDocument,
    InputMediaPhoto,
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChatAdministrators,
    ChatPermissions
)
from telegram.constants import ParseMode, ChatAction
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
    PicklePersistence,
    JobQueue
)
from telegram.error import TelegramError, BadRequest, NetworkError

# مكتبات الذكاء الاصطناعي وPDF
try:
    import google.generativeai as genai
    from PyPDF2 import PdfReader, PdfWriter
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.pdfgen import canvas
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
    from reportlab.lib.units import inch, cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
    import arabic_reshaper
    from bidi.algorithm import get_display
    from PIL import Image, ImageDraw, ImageFont
    import pytesseract
    from deep_translator import GoogleTranslator
    IMPORT_SUCCESS = True
except ImportError as e:
    print(f"تحذير: بعض المكتبات غير مثبتة: {e}")
    IMPORT_SUCCESS = False

# مكتبات إضافية
import requests
import aiohttp
from io import BytesIO

# ============================================
# إعدادات التكوين
# ============================================

# التوكنات - قم بتغييرها حسب حاجتك
TELEGRAM_BOT_TOKEN = "8481569753:AAHTdbWwu0BHmoo_iHPsye8RkTptWzfiQWU"
GEMINI_API_KEY = "AIzaSyAqlug21bw_eI60ocUtc1Z76NhEUc-zuzY"

# إعدادات المطور
ADMIN_USER_ID = 6130994941
ADMIN_USERNAME = "@Allawi04"

# إعدادات البوت
BOT_USERNAME = "@FC4Xbot"
BOT_NAME = "يلا نتعلم"

# إعدادات العملة
CURRENCY_NAME = "دينار عراقي"
CURRENCY_SYMBOL = "د.ع"
MINIMUM_SERVICE_PRICE = 1000
WELCOME_BONUS_AMOUNT = 1000

# إعدادات الملفات
MAX_FILE_SIZE = 20 * 1024 * 1024
TEMP_DIR = "temp_files"
LOG_DIR = "logs"

# حالات المحادثة
(
    COURSE1, COURSE2, COURSE3,
    WAITING_PDF, WAITING_QUESTION,
    ADMIN_SEARCH_USER, ADMIN_CHARGE_AMOUNT,
    ADMIN_SET_PRICE, ADMIN_BROADCAST
) = range(10)

# ============================================
# إعدادات التسجيل
# ============================================

def setup_logging():
    """إعداد نظام التسجيل"""
    os.makedirs(LOG_DIR, exist_ok=True)
    
    log_filename = os.path.join(LOG_DIR, f"bot_{datetime.now().strftime('%Y%m%d')}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)

logger = setup_logging()

# ============================================
# نظام قاعدة البيانات المبسط
# ============================================

class SimpleDatabase:
    """نظام قاعدة بيانات مبسط"""
    
    def __init__(self, db_name: str = "bot.db"):
        self.db_name = db_name
        self.connection = None
        self.cursor = None
        self.init_database()
    
    def init_database(self):
        """تهيئة قاعدة البيانات"""
        try:
            self.connection = sqlite3.connect(self.db_name, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            self.cursor = self.connection.cursor()
            
            # جدول المستخدمين
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    balance INTEGER DEFAULT 0,
                    invite_code TEXT UNIQUE,
                    referral_count INTEGER DEFAULT 0,
                    language_code TEXT DEFAULT 'ar',
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_banned INTEGER DEFAULT 0
                )
            ''')
            
            # جدول العمليات
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount INTEGER,
                    transaction_type TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # جدول الخدمات
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS service_usage (
                    usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    service_name TEXT,
                    service_type TEXT,
                    cost INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # جدول المواد
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS materials (
                    material_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    file_id TEXT,
                    stage TEXT,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    download_count INTEGER DEFAULT 0
                )
            ''')
            
            # إضافة مستخدم المشرف
            self.cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, username, first_name, balance)
                VALUES (?, ?, ?, ?)
            ''', (ADMIN_USER_ID, ADMIN_USERNAME.replace("@", ""), "المشرف", 1000000))
            
            self.connection.commit()
            logger.info("✅ تم تهيئة قاعدة البيانات")
        except Exception as e:
            logger.error(f"❌ خطأ في تهيئة قاعدة البيانات: {e}")
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, 
                 last_name: str = None) -> dict:
        """إضافة مستخدم جديد"""
        try:
            invite_code = self._generate_invite_code()
            
            self.cursor.execute('''
                INSERT OR IGNORE INTO users 
                (user_id, username, first_name, last_name, invite_code, balance)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, invite_code, WELCOME_BONUS_AMOUNT))
            
            if self.cursor.rowcount > 0:
                self.add_transaction(user_id, WELCOME_BONUS_AMOUNT, 'welcome_bonus', 'مكافأة ترحيبية')
            
            return self.get_user(user_id)
        except Exception as e:
            logger.error(f"❌ خطأ في إضافة مستخدم: {e}")
            return None
    
    def get_user(self, user_id: int) -> dict:
        """الحصول على بيانات مستخدم"""
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = self.cursor.fetchone()
        return dict(user) if user else None
    
    def update_balance(self, user_id: int, amount: int, transaction_type: str, 
                      description: str = "") -> bool:
        """تحديث رصيد المستخدم"""
        try:
            self.cursor.execute(
                'UPDATE users SET balance = balance + ? WHERE user_id = ?',
                (amount, user_id)
            )
            
            self.add_transaction(user_id, amount, transaction_type, description)
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث الرصيد: {e}")
            return False
    
    def get_balance(self, user_id: int) -> int:
        """الحصول على رصيد المستخدم"""
        self.cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result else 0
    
    def add_transaction(self, user_id: int, amount: int, transaction_type: str, 
                       description: str = "") -> bool:
        """إضافة عملية"""
        try:
            self.cursor.execute('''
                INSERT INTO transactions (user_id, amount, transaction_type, description)
                VALUES (?, ?, ?, ?)
            ''', (user_id, amount, transaction_type, description))
            
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في إضافة عملية: {e}")
            return False
    
    def add_service_usage(self, user_id: int, service_name: str, service_type: str, 
                         cost: int) -> bool:
        """تسجيل استخدام خدمة"""
        try:
            self.cursor.execute('''
                INSERT INTO service_usage (user_id, service_name, service_type, cost)
                VALUES (?, ?, ?, ?)
            ''', (user_id, service_name, service_type, cost))
            
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في تسجيل استخدام الخدمة: {e}")
            return False
    
    def get_all_users(self, limit: int = 100) -> list:
        """الحصول على جميع المستخدمين"""
        self.cursor.execute('SELECT * FROM users ORDER BY join_date DESC LIMIT ?', (limit,))
        users = self.cursor.fetchall()
        return [dict(user) for user in users]
    
    def search_users(self, search_term: str) -> list:
        """بحث عن مستخدمين"""
        search_term = f"%{search_term}%"
        self.cursor.execute('''
            SELECT * FROM users 
            WHERE user_id LIKE ? OR username LIKE ? OR first_name LIKE ? OR last_name LIKE ?
            LIMIT 20
        ''', (search_term, search_term, search_term, search_term))
        
        users = self.cursor.fetchall()
        return [dict(user) for user in users]
    
    def ban_user(self, user_id: int) -> bool:
        """حظر مستخدم"""
        try:
            self.cursor.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (user_id,))
            self.connection.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            logger.error(f"❌ خطأ في حظر مستخدم: {e}")
            return False
    
    def unban_user(self, user_id: int) -> bool:
        """إلغاء حظر مستخدم"""
        try:
            self.cursor.execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (user_id,))
            self.connection.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            logger.error(f"❌ خطأ في إلغاء حظر مستخدم: {e}")
            return False
    
    def add_material(self, title: str, description: str, file_id: str, stage: str) -> int:
        """إضافة مادة"""
        try:
            self.cursor.execute('''
                INSERT INTO materials (title, description, file_id, stage)
                VALUES (?, ?, ?, ?)
            ''', (title, description, file_id, stage))
            
            material_id = self.cursor.lastrowid
            self.connection.commit()
            return material_id
        except Exception as e:
            logger.error(f"❌ خطأ في إضافة مادة: {e}")
            return None
    
    def get_materials(self, stage: str = None, limit: int = 20) -> list:
        """الحصول على المواد"""
        if stage:
            self.cursor.execute('SELECT * FROM materials WHERE stage = ? ORDER BY upload_date DESC LIMIT ?', 
                              (stage, limit))
        else:
            self.cursor.execute('SELECT * FROM materials ORDER BY upload_date DESC LIMIT ?', (limit,))
        
        materials = self.cursor.fetchall()
        return [dict(m) for m in materials]
    
    def increment_download_count(self, material_id: int) -> bool:
        """زيادة عداد التنزيلات"""
        try:
            self.cursor.execute('UPDATE materials SET download_count = download_count + 1 WHERE material_id = ?', 
                              (material_id,))
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في زيادة عداد التنزيلات: {e}")
            return False
    
    def _generate_invite_code(self) -> str:
        """إنشاء كود دعوة"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            self.cursor.execute('SELECT COUNT(*) FROM users WHERE invite_code = ?', (code,))
            if self.cursor.fetchone()[0] == 0:
                return code
    
    def get_user_count(self) -> int:
        """عدد المستخدمين"""
        self.cursor.execute('SELECT COUNT(*) FROM users')
        return self.cursor.fetchone()[0]
    
    def close(self):
        """إغلاق قاعدة البيانات"""
        if self.connection:
            self.connection.close()

# إنشاء قاعدة البيانات
db = SimpleDatabase()

# ============================================
# أدوات مساعدة
# ============================================

def format_arabic_text(text: str) -> str:
    """تنسيق النص العربي"""
    try:
        if not text:
            return ""
        
        # إذا كانت المكتبات غير مثبتة، ارجع النص كما هو
        if not IMPORT_SUCCESS:
            return text
        
        reshaped_text = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped_text)
        return bidi_text
    except Exception as e:
        logger.warning(f"⚠️ خطأ في تنسيق النص العربي: {e}")
        return text

def format_currency(amount: int) -> str:
    """تنسيق المبلغ"""
    return f"{amount:,} {CURRENCY_SYMBOL}"

def format_number(number: int) -> str:
    """تنسيق الأرقام"""
    return f"{number:,}"

def is_admin(user_id: int) -> bool:
    """التحقق إذا كان مشرفاً"""
    return user_id == ADMIN_USER_ID

def admin_only(func):
    """ديكوراتور للمشرفين فقط"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        if not is_admin(user_id):
            if update.callback_query:
                await update.callback_query.answer("⛔ هذا الأمر للمشرفين فقط!", show_alert=True)
            else:
                await update.message.reply_text(
                    "⛔ هذا الأمر للمشرفين فقط!",
                    reply_markup=main_keyboard(user_id)
                )
            return
        
        return await func(update, context, *args, **kwargs)
    return wrapper

def check_balance(service_price: int):
    """ديكوراتور للتحقق من الرصيد"""
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            
            if is_admin(user_id):
                return await func(update, context, *args, **kwargs)
            
            user_balance = db.get_balance(user_id)
            
            if user_balance < service_price:
                await update.message.reply_text(
                    format_arabic_text(f"""
                    ⚠️ **رصيدك غير كاف!**
                    
                    **سعر الخدمة:** {format_currency(service_price)}
                    **رصيدك الحالي:** {format_currency(user_balance)}
                    
                    📥 **لشحن الرصيد تواصل مع الدعم الفني**
                    """),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=main_keyboard(user_id)
                )
                return
            
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator

# ============================================
# لوحات المفاتيح
# ============================================

def main_keyboard(user_id: int = None) -> ReplyKeyboardMarkup:
    """لوحة المفاتيح الرئيسية"""
    keyboard = [
        ["📊 حساب درجة العفوية", "📄 تلخيص الملازم"],
        ["❓ أسئلة وأجوبة", "📚 ملازمي ومرشحاتي"],
        ["💰 رصيدي", "📤 دعوة أصدقاء"],
        ["ℹ️ معلومات البوت", "👨‍💻 الدعم الفني"]
    ]
    
    # إضافة زر لوحة التحكم للمشرف
    if user_id and is_admin(user_id):
        keyboard.append(["👑 لوحة التحكم"])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, selective=True)

def back_keyboard() -> ReplyKeyboardMarkup:
    """زر الرجوع"""
    return ReplyKeyboardMarkup([["🏠 القائمة الرئيسية"]], resize_keyboard=True)

def stages_keyboard() -> ReplyKeyboardMarkup:
    """لوحة المراحل الدراسية"""
    keyboard = [
        ["المرحلة الأولى", "المرحلة الثانية"],
        ["المرحلة الثالثة", "المرحلة الرابعة"],
        ["🏠 القائمة الرئيسية"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ============================================
# معالجات الأوامر الأساسية
# ============================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /start"""
    user = update.effective_user
    user_id = user.id
    
    welcome_text = format_arabic_text(f"""
    🎓 **مرحباً بك في {BOT_NAME}!**
    
    **📚 البوت التعليمي الذكي للطلاب العراقيين**
    
    🎁 **مكافأة ترحيبية:** {format_currency(WELCOME_BONUS_AMOUNT)}
    
    **الخدمات المتاحة:**
    
    📊 **حساب درجة العفوية** - {format_currency(MINIMUM_SERVICE_PRICE)}
    📄 **تلخيص الملازم** - {format_currency(MINIMUM_SERVICE_PRICE)}
    ❓ **أسئلة وأجوبة** - {format_currency(MINIMUM_SERVICE_PRICE)}
    📚 **ملازمي ومرشحاتي** - {format_currency(MINIMUM_SERVICE_PRICE)}
    
    💰 **الرصيد الحالي:** {format_currency(db.get_balance(user_id))}
    
    📤 **دعوة أصدقاء:** احصل على {format_currency(500)} لكل صديق!
    
    👨‍💻 **الدعم الفني:** {ADMIN_USERNAME}
    """)
    
    db.add_user(user_id, user.username, user.first_name, user.last_name)
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(user_id)
    )

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الرصيد"""
    user_id = update.effective_user.id
    user_balance = db.get_balance(user_id)
    user_data = db.get_user(user_id)
    
    balance_text = format_arabic_text(f"""
    💰 **الرصيد والعمليات المالية**
    
    **💵 الرصيد الحالي:** {format_currency(user_balance)}
    
    **📤 برنامج الدعوة:**
    • مكافأة الدعوة: {format_currency(500)}
    • عدد الأصدقاء المدعوين: {user_data.get('referral_count', 0)}
    
    **💳 طرق شحن الرصيد:**
    1. التواصل مع الدعم الفني
    2. دعوة الأصدقاء
    
    👨‍💻 **الدعم الفني:** {ADMIN_USERNAME}
    """)
    
    await update.message.reply_text(
        balance_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(user_id)
    )

async def invite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معلومات الدعوة"""
    user_id = update.effective_user.id
    user_data = db.get_user(user_id)
    
    invite_code = user_data.get('invite_code', '')
    invite_link = f"https://t.me/{BOT_USERNAME.replace('@', '')}?start={invite_code}"
    
    invite_text = format_arabic_text(f"""
    📤 **برنامج دعوة الأصدقاء**
    
    **🎁 المكافأة:** {format_currency(500)} لكل صديق
    **👥 عدد الأصدقاء المدعوين:** {user_data.get('referral_count', 0)}
    
    **🔗 رابط دعوتك:**
    `{invite_link}`
    
    **📝 كيفية الاستخدام:**
    1. أرسل الرابط لصديقك
    2. ينقر صديقك على الرابط
    3. تحصل أنت وصديقك على المكافأة!
    
    **📞 الدعم الفني:** {ADMIN_USERNAME}
    """)
    
    await update.message.reply_text(
        invite_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(user_id)
    )

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معلومات البوت"""
    user_id = update.effective_user.id
    
    total_users = db.get_user_count()
    
    info_text = format_arabic_text(f"""
    ℹ️ **معلومات عن {BOT_NAME}**
    
    **🤖 وصف البوت:**
    بوت تعليمي ذكي مصمم للطلاب العراقيين.
    
    **📊 إحصائيات البوت:**
    • إجمالي المستخدمين: {format_number(total_users)}
    
    **💎 المميزات:**
    ✅ حساب درجة العفوية
    ✅ تلخيص الملازم
    ✅ أسئلة وأجوبة
    ✅ مكتبة المواد التعليمية
    ✅ نظام الدعوة والمكافآت
    
    **📞 قنوات التواصل:**
    • البوت: {BOT_USERNAME}
    • الدعم: {ADMIN_USERNAME}
    
    **👑 المطور:**
    • {ADMIN_USERNAME}
    
    **🔄 آخر تحديث:** {datetime.now().strftime('%Y-%m-%d')}
    """)
    
    await update.message.reply_text(
        info_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(user_id)
    )

async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الدعم الفني"""
    user_id = update.effective_user.id
    
    support_text = format_arabic_text(f"""
    👨‍💻 **الدعم الفني والاتصال**
    
    **📞 معلومات الاتصال:**
    • يوزر الدعم: {ADMIN_USERNAME}
    • أيدي المطور: `{ADMIN_USER_ID}`
    
    **⏰ ساعات العمل:**
    • الأحد - الخميس: 9:00 ص - 5:00 م
    • الجمعة - السبت: 10:00 ص - 2:00 م
    
    **📋 خدمات الدعم:**
    1. المساعدة الفنية
    2. حل المشاكل
    3. استفسارات الدفع
    4. اقتراحات التطوير
    
    **⏱️ وقت الاستجابة:** خلال 24 ساعة
    """)
    
    await update.message.reply_text(
        support_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(user_id)
    )

# ============================================
# الخدمة 1: حساب درجة العفوية
# ============================================

@check_balance(MINIMUM_SERVICE_PRICE)
async def exemption_calculation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حساب درجة العفوية"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        db.update_balance(user_id, -MINIMUM_SERVICE_PRICE, 'service_payment', 'حساب درجة العفوية')
        db.add_service_usage(user_id, 'حساب درجة العفوية', 'exemption', MINIMUM_SERVICE_PRICE)
    
    await update.message.reply_text(
        format_arabic_text("""
        📊 **حساب درجة العفوية**
        
        **🎯 الشرط:** المعدل ≥ 90
        
        **أرسل درجة الكورس الأول:**
        """),
        reply_markup=back_keyboard()
    )
    
    context.user_data['exemption_data'] = {}
    return COURSE1

async def process_course1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة درجة الكورس الأول"""
    try:
        grade = float(update.message.text.strip())
        
        if 0 <= grade <= 100:
            context.user_data['exemption_data']['course1'] = grade
            
            await update.message.reply_text(
                format_arabic_text(f"""
                ✅ **تم حفظ درجة الكورس الأول:** {grade:.2f}
                
                **أرسل درجة الكورس الثاني:**
                """),
                reply_markup=back_keyboard()
            )
            return COURSE2
        else:
            await update.message.reply_text(
                "⚠️ الرجاء إدخال درجة بين 0 و 100:",
                reply_markup=back_keyboard()
            )
            return COURSE1
    except ValueError:
        await update.message.reply_text(
            "⚠️ الرجاء إدخال رقم صحيح:",
            reply_markup=back_keyboard()
        )
        return COURSE1

async def process_course2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة درجة الكورس الثاني"""
    try:
        grade = float(update.message.text.strip())
        
        if 0 <= grade <= 100:
            context.user_data['exemption_data']['course2'] = grade
            
            await update.message.reply_text(
                format_arabic_text(f"""
                ✅ **تم حفظ درجة الكورس الثاني:** {grade:.2f}
                
                **أرسل درجة الكورس الثالث:**
                """),
                reply_markup=back_keyboard()
            )
            return COURSE3
        else:
            await update.message.reply_text(
                "⚠️ الرجاء إدخال درجة بين 0 و 100:",
                reply_markup=back_keyboard()
            )
            return COURSE2
    except ValueError:
        await update.message.reply_text(
            "⚠️ الرجاء إدخال رقم صحيح:",
            reply_markup=back_keyboard()
        )
        return COURSE2

async def process_course3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة درجة الكورس الثالث"""
    user_id = update.effective_user.id
    
    try:
        grade = float(update.message.text.strip())
        
        if 0 <= grade <= 100:
            course1 = context.user_data['exemption_data']['course1']
            course2 = context.user_data['exemption_data']['course2']
            course3 = grade
            
            average = (course1 + course2 + course3) / 3
            
            if average >= 90:
                result = "🎉 **مبروك! أنت معفي من المادة** 🎉"
                result_emoji = "✅"
            else:
                result = "❌ **للأسف، أنت غير معفي من المادة**"
                result_emoji = "❌"
            
            result_text = format_arabic_text(f"""
            {result_emoji} **نتيجة حساب درجة العفوية**
            
            **📊 الدرجات المدخلة:**
            • الكورس الأول: {course1:.2f}
            • الكورس الثاني: {course2:.2f}
            • الكورس الثالث: {course3:.2f}
            
            **🧮 المعدل النهائي:** **{average:.2f}**
            
            **📈 النتيجة:** {result}
            
            **🔄 ملاحظة:** الحد الأدنى للإعفاء هو 90 درجة
            """)
            
            await update.message.reply_text(
                result_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_keyboard(user_id)
            )
            
            context.user_data.clear()
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                "⚠️ الرجاء إدخال درجة بين 0 و 100:",
                reply_markup=back_keyboard()
            )
            return COURSE3
    except ValueError:
        await update.message.reply_text(
            "⚠️ الرجاء إدخال رقم صحيح:",
            reply_markup=back_keyboard()
        )
        return COURSE3

# ============================================
# الخدمة 2: تلخيص الملازم
# ============================================

@check_balance(MINIMUM_SERVICE_PRICE)
async def pdf_summary_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء تلخيص PDF"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        db.update_balance(user_id, -MINIMUM_SERVICE_PRICE, 'service_payment', 'تلخيص الملازم')
        db.add_service_usage(user_id, 'تلخيص الملازم', 'pdf_summary', MINIMUM_SERVICE_PRICE)
    
    await update.message.reply_text(
        format_arabic_text("""
        📄 **تلخيص الملازم**
        
        **📝 التعليمات:**
        1. أرسل ملف PDF المراد تلخيصه
        2. انتظر قليلاً لمعالجة الملف
        
        **📦 المتطلبات:**
        • الملف يجب أن يكون بصيغة PDF
        • الحجم الأقصى: 20 ميجابايت
        
        **📤 أرسل ملف PDF الآن:**
        """),
        reply_markup=back_keyboard()
    )
    
    return WAITING_PDF

async def process_pdf_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة ملف PDF"""
    user_id = update.effective_user.id
    
    if not update.message.document:
        await update.message.reply_text(
            "⚠️ الرجاء إرسال ملف PDF:",
            reply_markup=back_keyboard()
        )
        return WAITING_PDF
    
    document = update.message.document
    
    if not document.file_name.lower().endswith('.pdf'):
        await update.message.reply_text(
            "⚠️ الرجاء إرسال ملف PDF فقط:",
            reply_markup=back_keyboard()
        )
        return WAITING_PDF
    
    if document.file_size > MAX_FILE_SIZE:
        await update.message.reply_text(
            f"⚠️ حجم الملف كبير جداً! الحجم الأقصى: {MAX_FILE_SIZE // (1024*1024)} ميجابايت",
            reply_markup=back_keyboard()
        )
        return WAITING_PDF
    
    await update.message.reply_text(
        "⏳ جاري معالجة الملف...",
        reply_markup=back_keyboard()
    )
    
    try:
        file = await context.bot.get_file(document.file_id)
        
        # في هذا الإصنجاء المبسط، سنخبر المستخدم أن الخدمة تعمل
        await update.message.reply_text(
            format_arabic_text(f"""
            ✅ **تم استلام الملف بنجاح!**
            
            **📄 الملف:** {document.file_name}
            **📏 الحجم:** {document.file_size // 1024} كيلوبايت
            
            **📝 ملاحظة:** خدمة الذكاء الاصطناعي قيد التطوير.
            سيتم إضافة التلخيص التلقائي قريباً.
            
            **💰 تم خصم:** {format_currency(MINIMUM_SERVICE_PRICE)}
            """),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_keyboard(user_id)
        )
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة PDF: {e}")
        await update.message.reply_text(
            f"❌ حدث خطأ: {str(e)}",
            reply_markup=main_keyboard(user_id)
        )
        return ConversationHandler.END

# ============================================
# الخدمة 3: أسئلة وأجوبة
# ============================================

@check_balance(MINIMUM_SERVICE_PRICE)
async def qa_ai_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء خدمة الأسئلة"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        db.update_balance(user_id, -MINIMUM_SERVICE_PRICE, 'service_payment', 'أسئلة وأجوبة')
        db.add_service_usage(user_id, 'أسئلة وأجوبة', 'qa_ai', MINIMUM_SERVICE_PRICE)
    
    await update.message.reply_text(
        format_arabic_text("""
        ❓ **أسئلة وأجوبة**
        
        **🎯 كيفية الاستخدام:**
        1. أرسل سؤالك نصياً
        2. انتظر قليلاً للإجابة
        
        **📝 أرسل سؤالك الآن:**
        """),
        reply_markup=back_keyboard()
    )
    
    return WAITING_QUESTION

async def process_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة السؤال"""
    user_id = update.effective_user.id
    
    question_text = update.message.text
    
    await update.message.reply_text(
        format_arabic_text(f"""
        ⏳ **جاري البحث عن الإجابة...**
        
        **❓ سؤالك:** {question_text}
        
        **📝 ملاحظة:** خدمة الذكاء الاصطناعي قيد التطوير.
        سيتم إضافة الإجابات الذكية قريباً.
        
        **💰 تم خصم:** {format_currency(MINIMUM_SERVICE_PRICE)}
        """),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(user_id)
    )
    
    return ConversationHandler.END

# ============================================
# الخدمة 4: ملازمي ومرشحاتي
# ============================================

@check_balance(MINIMUM_SERVICE_PRICE)
async def materials_library(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مكتبة المواد"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        db.update_balance(user_id, -MINIMUM_SERVICE_PRICE, 'service_payment', 'ملازمي ومرشحاتي')
        db.add_service_usage(user_id, 'ملازمي ومرشحاتي', 'materials', MINIMUM_SERVICE_PRICE)
    
    await update.message.reply_text(
        format_arabic_text("""
        📚 **ملازمي ومرشحاتي**
        
        **اختر المرحلة الدراسية:**
        """),
        reply_markup=stages_keyboard()
    )

async def handle_stage_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار المرحلة"""
    user_id = update.effective_user.id
    stage = update.message.text
    
    stage_map = {
        "المرحلة الأولى": "first",
        "المرحلة الثانية": "second", 
        "المرحلة الثالثة": "third",
        "المرحلة الرابعة": "fourth"
    }
    
    stage_code = stage_map.get(stage)
    
    if not stage_code:
        await update.message.reply_text(
            "⚠️ اختر مرحلة صحيحة:",
            reply_markup=stages_keyboard()
        )
        return
    
    materials = db.get_materials(stage=stage_code, limit=10)
    
    if not materials:
        await update.message.reply_text(
            format_arabic_text(f"""
            📭 **لا توجد مواد للمرحلة {stage}**
            
            سيتم إضافة مواد قريباً.
            """),
            reply_markup=main_keyboard(user_id)
        )
        return
    
    materials_text = format_arabic_text(f"""
    📚 **المواد - {stage}:**
    
    **📊 عدد المواد:** {len(materials)}
    
    **📝 قائمة المواد:**
    """)
    
    keyboard = []
    
    for i, material in enumerate(materials, 1):
        title = material['title'][:30] + ('...' if len(material['title']) > 30 else '')
        materials_text += f"\n{i}. **{title}**"
        
        keyboard.append([
            InlineKeyboardButton(
                f"{i}. {title}",
                callback_data=f"material_{material['material_id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_stages")])
    
    await update.message.reply_text(
        materials_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_material_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض تفاصيل المادة"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_stages":
        await query.edit_message_text(
            text=format_arabic_text("""
            📚 **ملازمي ومرشحاتي**
            
            **اختر المرحلة الدراسية:**
            """),
            reply_markup=stages_keyboard()
        )
        return
    
    material_id = int(query.data.split('_')[1])
    
    db.cursor.execute('SELECT * FROM materials WHERE material_id = ?', (material_id,))
    material = db.cursor.fetchone()
    
    if not material:
        await query.answer("❌ المادة غير موجودة!", show_alert=True)
        return
    
    material = dict(material)
    
    details_text = format_arabic_text(f"""
    📄 **تفاصيل المادة**
    
    **📌 العنوان:** {material['title']}
    **📝 الوصف:** {material['description'] or 'لا يوجد وصف'}
    
    **📊 المعلومات:**
    • المرحلة: {material['stage'] or 'غير محدد'}
    • عدد التنزيلات: {material['download_count']}
    
    **📥 يمكنك تنزيل المادة:**
    """)
    
    await query.edit_message_text(
        text=details_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 تنزيل المادة", callback_data=f"download_{material_id}")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_stages")]
        ])
    )

async def download_material(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنزيل مادة"""
    query = update.callback_query
    await query.answer()
    
    material_id = int(query.data.split('_')[1])
    
    db.cursor.execute('SELECT * FROM materials WHERE material_id = ?', (material_id,))
    material = db.cursor.fetchone()
    
    if not material:
        await query.answer("❌ المادة غير موجودة!", show_alert=True)
        return
    
    material = dict(material)
    
    try:
        db.increment_download_count(material_id)
        
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=material['file_id'],
            caption=format_arabic_text(f"""
            📥 **تم تنزيل المادة!**
            
            **📌 العنوان:** {material['title']}
            **📝 الوصف:** {material['description'] or 'لا يوجد وصف'}
            """),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_keyboard(query.from_user.id)
        )
        
        await query.answer("✅ تم إرسال الملف!", show_alert=True)
        
    except Exception as e:
        logger.error(f"❌ خطأ في إرسال الملف: {e}")
        await query.answer("❌ فشل في إرسال الملف!", show_alert=True)

# ============================================
# لوحة التحكم
# ============================================

@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لوحة تحكم المشرف"""
    user_id = update.effective_user.id
    
    total_users = db.get_user_count()
    
    admin_text = format_arabic_text(f"""
    👑 **لوحة تحكم المشرف**
    
    **📊 نظرة سريعة:**
    • إجمالي المستخدمين: {format_number(total_users)}
    
    **⚡ اختر الإجراء:**
    """)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users")],
        [InlineKeyboardButton("💰 الشحن", callback_data="admin_charge")],
        [InlineKeyboardButton("📢 البث للمستخدمين", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
    ])
    
    if update.callback_query:
        await update.callback_query.message.reply_text(
            admin_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        await update.callback_query.answer()
    else:
        await update.message.reply_text(
            admin_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )

@admin_only
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إحصائيات المشرف"""
    query = update.callback_query
    await query.answer()
    
    total_users = db.get_user_count()
    
    db.cursor.execute('SELECT COUNT(*) FROM service_usage')
    total_services = db.cursor.fetchone()[0]
    
    db.cursor.execute('SELECT SUM(cost) FROM service_usage')
    total_revenue = db.cursor.fetchone()[0] or 0
    
    stats_text = format_arabic_text(f"""
    📊 **الإحصائيات**
    
    **👥 المستخدمين:**
    • إجمالي المستخدمين: {format_number(total_users)}
    
    **💰 المالية:**
    • إجمالي الخدمات: {format_number(total_services)}
    • إجمالي الإيرادات: {format_currency(total_revenue)}
    
    **📅 التاريخ:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
    """)
    
    await query.edit_message_text(
        text=stats_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 تحديث", callback_data="admin_stats")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")]
        ])
    )

@admin_only
async def admin_users_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إدارة المستخدمين"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        text=format_arabic_text("""
        👥 **إدارة المستخدمين**
        
        **اختر الإجراء:**
        """),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 بحث عن مستخدم", callback_data="admin_search_user")],
            [InlineKeyboardButton("📋 عرض جميع المستخدمين", callback_data="admin_list_users")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")]
        ])
    )

@admin_only
async def admin_search_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء بحث المشرف"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        text=format_arabic_text("""
        🔍 **بحث عن مستخدم**
        
        **أرسل كلمة البحث:**
        """),
        reply_markup=back_keyboard()
    )
    
    return ADMIN_SEARCH_USER

async def process_admin_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة بحث المشرف"""
    search_term = update.message.text
    
    users = db.search_users(search_term)
    
    if not users:
        await update.message.reply_text(
            format_arabic_text(f"""
            📭 **لا توجد نتائج**
            
            **أرسل بحث جديد:**
            """),
            reply_markup=back_keyboard()
        )
        return ADMIN_SEARCH_USER
    
    results_text = format_arabic_text(f"""
    🔍 **نتائج البحث**
    
    **📊 عدد النتائج:** {len(users)}
    """)
    
    keyboard = []
    
    for i, user in enumerate(users[:10], 1):
        name = f"{user['first_name'] or ''} {user['last_name'] or ''}".strip()
        if not name:
            name = f"المستخدم {user['user_id']}"
        
        results_text += f"\n{i}. **{name}**"
        results_text += f"\n   • الأيدي: `{user['user_id']}`"
        results_text += f"\n   • الرصيد: {format_currency(user['balance'])}"
        
        keyboard.append([
            InlineKeyboardButton(
                f"{i}. {name[:15]}...",
                callback_data=f"admin_view_user_{user['user_id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_users")])
    
    await update.message.reply_text(
        results_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return ConversationHandler.END

@admin_only
async def admin_view_user_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض تفاصيل مستخدم"""
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.split('_')[-1])
    user = db.get_user(user_id)
    
    if not user:
        await query.answer("❌ المستخدم غير موجود!", show_alert=True)
        return
    
    details_text = format_arabic_text(f"""
    👤 **تفاصيل المستخدم**
    
    **🆔 الأيدي:** `{user['user_id']}`
    **👤 الاسم:** {user['first_name'] or ''} {user['last_name'] or ''}
    **📧 اليوزر:** @{user['username'] or 'بدون'}
    
    **💰 الرصيد:** {format_currency(user['balance'])}
    **📅 تاريخ التسجيل:** {user['join_date'][:10]}
    **🚫 الحالة:** {"محظور" if user['is_banned'] else "نشط"}
    """)
    
    keyboard = []
    
    if user['is_banned']:
        keyboard.append([InlineKeyboardButton("✅ إلغاء حظر", callback_data=f"admin_unban_{user_id}")])
    else:
        keyboard.append([InlineKeyboardButton("🚫 حظر", callback_data=f"admin_ban_{user_id}")])
    
    keyboard.append([
        InlineKeyboardButton("💰 شحن رصيد", callback_data=f"admin_charge_{user_id}"),
        InlineKeyboardButton("🔙 رجوع", callback_data="admin_users")
    ])
    
    await query.edit_message_text(
        text=details_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@admin_only
async def admin_charge_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء شحن الرصيد"""
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.split('_')[-1])
    context.user_data['charge_user_id'] = user_id
    
    user = db.get_user(user_id)
    
    await query.edit_message_text(
        text=format_arabic_text(f"""
        💰 **شحن رصيد**
        
        **👤 المستخدم:** {user['first_name'] or ''} {user['last_name'] or ''}
        **💵 الرصيد الحالي:** {format_currency(user['balance'])}
        
        **أرسل المبلغ:**
        """),
        reply_markup=back_keyboard()
    )
    
    return ADMIN_CHARGE_AMOUNT

async def process_admin_charge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة شحن الرصيد"""
    try:
        amount = int(update.message.text)
        user_id = context.user_data.get('charge_user_id')
        
        if not user_id:
            await update.message.reply_text(
                "⚠️ انتهت الجلسة!",
                reply_markup=back_keyboard()
            )
            return ConversationHandler.END
        
        user = db.get_user(user_id)
        old_balance = user['balance']
        
        db.update_balance(user_id, amount, 'admin_charge', f'شحن بواسطة المشرف')
        
        new_balance = old_balance + amount
        
        await update.message.reply_text(
            format_arabic_text(f"""
            ✅ **تم الشحن بنجاح!**
            
            **👤 المستخدم:** {user['first_name'] or ''} {user['last_name'] or ''}
            **💰 المبلغ:** {format_currency(amount)}
            **💵 الرصيد السابق:** {format_currency(old_balance)}
            **💳 الرصيد الجديد:** {format_currency(new_balance)}
            """),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_keyboard()
        )
        
        context.user_data.pop('charge_user_id', None)
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "⚠️ الرجاء إرسال رقم صحيح:",
            reply_markup=back_keyboard()
        )
        return ADMIN_CHARGE_AMOUNT

@admin_only
async def admin_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حظر مستخدم"""
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.split('_')[-1])
    
    if db.ban_user(user_id):
        await query.answer("✅ تم حظر المستخدم!", show_alert=True)
        await query.edit_message_text(
            text=format_arabic_text(f"""
            ✅ **تم حظر المستخدم**
            
            **🆔 الأيدي:** `{user_id}`
            """),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ إلغاء حظر", callback_data=f"admin_unban_{user_id}")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="admin_users")]
            ])
        )
    else:
        await query.answer("❌ فشل في الحظر!", show_alert=True)

@admin_only
async def admin_unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء حظر"""
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.split('_')[-1])
    
    if db.unban_user(user_id):
        await query.answer("✅ تم إلغاء الحظر!", show_alert=True)
        await query.edit_message_text(
            text=format_arabic_text(f"""
            ✅ **تم إلغاء حظر المستخدم**
            
            **🆔 الأيدي:** `{user_id}`
            """),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚫 حظر", callback_data=f"admin_ban_{user_id}")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="admin_users")]
            ])
        )
    else:
        await query.answer("❌ فشل في إلغاء الحظر!", show_alert=True)

@admin_only
async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء البث"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        text=format_arabic_text("""
        📢 **البث للمستخدمين**
        
        **أرسل الرسالة:**
        """),
        reply_markup=back_keyboard()
    )
    
    return ADMIN_BROADCAST

async def process_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة البث"""
    user_id = update.effective_user.id
    
    users = db.get_all_users()
    total_users = len(users)
    
    progress_msg = await update.message.reply_text(
        format_arabic_text(f"""
        📤 **جاري الإرسال...**
        
        **📊 الإحصائيات:**
        • إجمالي المستخدمين: {format_number(total_users)}
        • تم الإرسال: 0
        """),
        reply_markup=back_keyboard()
    )
    
    successful = 0
    failed = 0
    
    for i, user in enumerate(users):
        try:
            if update.message.text:
                await context.bot.send_message(
                    user['user_id'],
                    format_arabic_text(f"""
                    📢 **إشعار من إدارة البوت**
                    
                    {update.message.text}
                    """),
                    parse_mode=ParseMode.MARKDOWN
                )
            
            successful += 1
            
            if i % 10 == 0:
                await progress_msg.edit_text(
                    format_arabic_text(f"""
                    📤 **جاري الإرسال...**
                    
                    **📊 الإحصائيات:**
                    • إجمالي المستخدمين: {format_number(total_users)}
                    • تم الإرسال: {format_number(i + 1)}
                    • فشل الإرسال: {format_number(failed)}
                    """),
                    reply_markup=back_keyboard()
                )
            
            await asyncio.sleep(0.1)
            
        except Exception as e:
            failed += 1
            continue
    
    result_text = format_arabic_text(f"""
    ✅ **تم الانتهاء من البث!**
    
    **📊 النتائج:**
    • إجمالي المستخدمين: {format_number(total_users)}
    • تم الإرسال بنجاح: {format_number(successful)}
    • فشل الإرسال: {format_number(failed)}
    
    **📅 التاريخ:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
    """)
    
    await progress_msg.edit_text(
        result_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_keyboard()
    )
    
    return ConversationHandler.END

# ============================================
# معالجات الأزرار
# ============================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأزرار"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "main_menu":
        await query.edit_message_text(
            text=format_arabic_text("🏠 **القائمة الرئيسية**"),
            reply_markup=main_keyboard(query.from_user.id)
        )
    
    elif data == "admin_back":
        await admin_panel(update, context)
    
    elif data == "admin_stats":
        await admin_stats(update, context)
    
    elif data == "admin_users":
        await admin_users_management(update, context)
    
    elif data == "admin_search_user":
        await admin_search_user_start(update, context)
    
    elif data.startswith("admin_view_user_"):
        await admin_view_user_details(update, context)
    
    elif data.startswith("admin_charge_"):
        await admin_charge_user_start(update, context)
    
    elif data.startswith("admin_ban_"):
        await admin_ban_user(update, context)
    
    elif data.startswith("admin_unban_"):
        await admin_unban_user(update, context)
    
    elif data == "admin_broadcast":
        await admin_broadcast_start(update, context)
    
    elif data.startswith("material_"):
        await show_material_details(update, context)
    
    elif data.startswith("download_"):
        await download_material(update, context)
    
    else:
        await query.answer("❌ زر غير مدعوم!", show_alert=True)

# ============================================
# معالجات الرسائل
# ============================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل"""
    if not update.message or not update.message.text:
        return
    
    user_id = update.effective_user.id
    message_text = update.message.text
    
    if message_text == "🏠 القائمة الرئيسية":
        await update.message.reply_text(
            format_arabic_text("🏠 **القائمة الرئيسية**"),
            reply_markup=main_keyboard(user_id)
        )
    
    elif message_text == "📊 حساب درجة العفوية":
        await exemption_calculation(update, context)
    
    elif message_text == "📄 تلخيص الملازم":
        await pdf_summary_start(update, context)
    
    elif message_text == "❓ أسئلة وأجوبة":
        await qa_ai_start(update, context)
    
    elif message_text == "📚 ملازمي ومرشحاتي":
        await materials_library(update, context)
    
    elif message_text == "💰 رصيدي":
        await balance_command(update, context)
    
    elif message_text == "📤 دعوة أصدقاء":
        await invite_command(update, context)
    
    elif message_text == "ℹ️ معلومات البوت":
        await info_command(update, context)
    
    elif message_text == "👨‍💻 الدعم الفني":
        await support_command(update, context)
    
    elif message_text in ["المرحلة الأولى", "المرحلة الثانية", "المرحلة الثالثة", "المرحلة الرابعة"]:
        await handle_stage_selection(update, context)
    
    elif message_text == "👑 لوحة التحكم":
        if is_admin(user_id):
            await admin_panel(update, context)
        else:
            await update.message.reply_text(
                "⛔ هذا الأمر للمشرفين فقط!",
                reply_markup=main_keyboard(user_id)
            )
    
    else:
        await update.message.reply_text(
            format_arabic_text("""
            🤔 **لم أفهم طلبك!**
            
            **📝 استخدم الأزرار في القائمة.**
            """),
            reply_markup=main_keyboard(user_id)
        )

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء المحادثة"""
    user_id = update.effective_user.id
    
    await update.message.reply_text(
        format_arabic_text("""
        ❌ **تم الإلغاء**
        
        **🏠 العودة للقائمة الرئيسية**
        """),
        reply_markup=main_keyboard(user_id)
    )
    
    context.user_data.clear()
    return ConversationHandler.END

# ============================================
# الدالة الرئيسية
# ============================================

def main():
    """الدالة الرئيسية"""
    
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ لم تقم بتعيين توكن البوت!")
        return
    
    application = ApplicationBuilder() \
        .token(TELEGRAM_BOT_TOKEN) \
        .concurrent_updates(True) \
        .build()
    
    # محادثة حساب العفوية
    exemption_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📊 حساب درجة العفوية$"), exemption_calculation)],
        states={
            COURSE1: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_course1)],
            COURSE2: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_course2)],
            COURSE3: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_course3)]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            MessageHandler(filters.Regex("^🏠 القائمة الرئيسية$"), cancel_conversation)
        ]
    )
    application.add_handler(exemption_conv)
    
    # محادثة تلخيص PDF
    pdf_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📄 تلخيص الملازم$"), pdf_summary_start)],
        states={
            WAITING_PDF: [
                MessageHandler(filters.Document.PDF, process_pdf_file),
                MessageHandler(filters.TEXT & ~filters.COMMAND, 
                             lambda u, c: u.message.reply_text("⚠️ أرسل ملف PDF!"))
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            MessageHandler(filters.Regex("^🏠 القائمة الرئيسية$"), cancel_conversation)
        ]
    )
    application.add_handler(pdf_conv)
    
    # محادثة الأسئلة
    qa_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^❓ أسئلة وأجوبة$"), qa_ai_start)],
        states={
            WAITING_QUESTION: [
                MessageHandler(filters.TEXT, process_question)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            MessageHandler(filters.Regex("^🏠 القائمة الرئيسية$"), cancel_conversation)
        ]
    )
    application.add_handler(qa_conv)
    
    # محادثة بحث المشرف
    admin_search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_search_user_start, pattern="^admin_search_user$")],
        states={
            ADMIN_SEARCH_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_search)]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            MessageHandler(filters.Regex("^🏠 القائمة الرئيسية$"), cancel_conversation)
        ]
    )
    application.add_handler(admin_search_conv)
    
    # محادثة شحن المشرف
    admin_charge_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_charge_user_start, pattern="^admin_charge_\\d+$")],
        states={
            ADMIN_CHARGE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_charge)]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            MessageHandler(filters.Regex("^🏠 القائمة الرئيسية$"), cancel_conversation)
        ]
    )
    application.add_handler(admin_charge_conv)
    
    # محادثة البث
    admin_broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_broadcast_start, pattern="^admin_broadcast$")],
        states={
            ADMIN_BROADCAST: [
                MessageHandler(filters.TEXT, process_admin_broadcast)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            MessageHandler(filters.Regex("^🏠 القائمة الرئيسية$"), cancel_conversation)
        ]
    )
    application.add_handler(admin_broadcast_conv)
    
    # الأوامر الأساسية
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("invite", invite_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("support", support_command))
    application.add_handler(CommandHandler("admin", admin_panel))
    
    # معالج الأزرار
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # معالج الرسائل
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # معلومات التشغيل
    logger.info("=" * 50)
    logger.info(f"🚀 بدأ تشغيل بوت {BOT_NAME}")
    logger.info(f"🤖 يوزر البوت: {BOT_USERNAME}")
    logger.info(f"👑 أيدي المشرف: {ADMIN_USER_ID}")
    logger.info(f"💰 العملة: {CURRENCY_NAME}")
    logger.info("=" * 50)
    
    # تشغيل البوت
    application.run_polling(
        poll_interval=1.0,
        timeout=30,
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == '__main__':
    # إنشاء المجلدات
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    
    try:
        main()
    except KeyboardInterrupt:
        logger.info("⏹️ تم إيقاف البوت")
    except Exception as e:
        logger.error(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
        logger.info("🔒 تم إغلاق الاتصالات")
