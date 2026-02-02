#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت تليجرام متكامل للتعليم - "يلا نتعلم"
تم التطوير بواسطة: Allawi
الدعم الفني: @Allawi04
أيدي المشرف: 6130994941
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
from enum import Enum

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
import google.generativeai as genai
from PyPDF2 import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4, letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image as ReportLabImage
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

# مكتبات إضافية
import requests
from bs4 import BeautifulSoup
import aiohttp
import qrcode
from io import BytesIO
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================
# إعدادات التكوين الأساسية
# ============================================

# توكن البوت
TELEGRAM_BOT_TOKEN = "8481569753:AAHTdbWwu0BHmoo_iHPsye8RkTptWzfiQWU"

# مفتاح API لـ Gemini AI
GEMINI_API_KEY = "AIzaSyAqlug21bw_eI60ocUtc1Z76NhEUc-zuzY"

# إعدادات المطور
ADMIN_USER_ID = 6130994941
ADMIN_USERNAME = "@Allawi04"

# إعدادات البوت
BOT_USERNAME = "@FC4Xbot"
BOT_NAME = "يلا نتعلم"
BOT_DESCRIPTION = "بوت تعليمي ذكي للطلاب العراقيين"

# إعدادات العملة
CURRENCY_NAME = "دينار عراقي"
CURRENCY_SYMBOL = "د.ع"
MINIMUM_SERVICE_PRICE = 1000
WELCOME_BONUS_AMOUNT = 1000

# إعدادات قاعدة البيانات
DATABASE_NAME = "learning_bot.db"
BACKUP_INTERVAL = 3600

# إعدادات الملفات
MAX_FILE_SIZE = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.txt'}
TEMP_DIR = "temp_files"
LOG_DIR = "logs"

# حالات المحادثة
(
    COURSE1, COURSE2, COURSE3,
    WAITING_PDF, WAITING_QUESTION,
    ADMIN_SEARCH_USER, ADMIN_CHARGE_AMOUNT,
    ADMIN_SET_PRICE, ADMIN_BROADCAST,
    WAITING_MATERIAL_NAME, WAITING_MATERIAL_DESC,
    WAITING_MATERIAL_FILE, WAITING_BROADCAST_CONFIRM
) = range(14)

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
# نظام قاعدة البيانات
# ============================================

class Database:
    """نظام قاعدة بيانات متقدم"""
    
    def __init__(self, db_name: str = DATABASE_NAME):
        self.db_name = db_name
        self.connection = None
        self.cursor = None
        self.lock = threading.Lock()
        self.init_database()
    
    def init_database(self):
        """تهيئة قاعدة البيانات"""
        with self.lock:
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
                    phone_number TEXT,
                    balance INTEGER DEFAULT 0,
                    total_spent INTEGER DEFAULT 0,
                    total_earned INTEGER DEFAULT 0,
                    invite_code TEXT UNIQUE,
                    invited_by INTEGER,
                    referral_count INTEGER DEFAULT 0,
                    language_code TEXT DEFAULT 'ar',
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_premium INTEGER DEFAULT 0,
                    is_banned INTEGER DEFAULT 0,
                    ban_reason TEXT,
                    settings TEXT DEFAULT '{}',
                    metadata TEXT DEFAULT '{}'
                )
            ''')
            
            # جدول العمليات المالية
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount INTEGER,
                    transaction_type TEXT,
                    description TEXT,
                    reference_id TEXT,
                    status TEXT DEFAULT 'completed',
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
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # جدول المواد التعليمية
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS educational_materials (
                    material_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    file_id TEXT,
                    file_type TEXT,
                    file_size INTEGER,
                    category TEXT,
                    subcategory TEXT,
                    stage TEXT,
                    subject TEXT,
                    uploaded_by INTEGER,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    download_count INTEGER DEFAULT 0,
                    rating REAL DEFAULT 0.0,
                    is_approved INTEGER DEFAULT 1,
                    tags TEXT,
                    metadata TEXT DEFAULT '{}'
                )
            ''')
            
            # جدول الإعدادات
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_by INTEGER
                )
            ''')
            
            # جدول أسعار الخدمات
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS service_prices (
                    service_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_name TEXT UNIQUE,
                    service_code TEXT UNIQUE,
                    base_price INTEGER,
                    current_price INTEGER,
                    is_active INTEGER DEFAULT 1,
                    min_price INTEGER,
                    max_price INTEGER,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # جدول الإشعارات
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    notification_type TEXT,
                    title TEXT,
                    message TEXT,
                    is_read INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    read_at TIMESTAMP
                )
            ''')
            
            # إضافة الفهارس
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_invite_code ON users(invite_code)')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_materials_stage ON educational_materials(stage)')
            
            # إضافة الإعدادات الافتراضية
            self.add_default_settings()
            self.add_default_service_prices()
            
            self.connection.commit()
            logger.info("✅ تم تهيئة قاعدة البيانات بنجاح")
    
    def add_default_settings(self):
        """إضافة الإعدادات الافتراضية"""
        default_settings = [
            ('bot_name', BOT_NAME, 'اسم البوت'),
            ('bot_username', BOT_USERNAME, 'يوزر البوت'),
            ('admin_user_id', str(ADMIN_USER_ID), 'أيدي المشرف'),
            ('admin_username', ADMIN_USERNAME, 'يوزر المشرف'),
            ('welcome_bonus', str(WELCOME_BONUS_AMOUNT), 'مكافأة ترحيبية'),
            ('invite_bonus', '500', 'مكافأة دعوة صديق'),
            ('min_service_price', str(MINIMUM_SERVICE_PRICE), 'أقل سعر للخدمة'),
            ('currency_name', CURRENCY_NAME, 'اسم العملة'),
            ('currency_symbol', CURRENCY_SYMBOL, 'رمز العملة'),
            ('maintenance_mode', '0', 'وضع الصيانة'),
            ('support_channel', 'https://t.me/+channel', 'رابط القناة'),
            ('support_username', ADMIN_USERNAME, 'يوزر الدعم'),
            ('max_file_size', str(MAX_FILE_SIZE), 'الحجم الأقصى للملف'),
            ('daily_limit', '10', 'الحد اليومي'),
            ('language', 'ar', 'اللغة الافتراضية'),
            ('timezone', 'Asia/Baghdad', 'المنطقة الزمنية')
        ]
        
        for key, value, description in default_settings:
            self.cursor.execute('''
                INSERT OR IGNORE INTO bot_settings (setting_key, setting_value, description)
                VALUES (?, ?, ?)
            ''', (key, value, description))
        
        self.connection.commit()
    
    def add_default_service_prices(self):
        """إضافة أسعار الخدمات الافتراضية"""
        default_services = [
            ('عفوية', 'exemption_calc', 1000, 1000, 500, 5000, 'حساب درجة العفوية'),
            ('تلخيص', 'pdf_summary', 1000, 1000, 500, 5000, 'تلخيص الملازم بالذكاء الاصطناعي'),
            ('أسئلة', 'qa_ai', 1000, 1000, 500, 5000, 'أسئلة وأجوبة بالذكاء الاصطناعي'),
            ('ملازم', 'materials', 1000, 1000, 500, 5000, 'ملازمي ومرشحاتي')
        ]
        
        for name, code, base_price, current_price, min_price, max_price, description in default_services:
            self.cursor.execute('''
                INSERT OR IGNORE INTO service_prices 
                (service_name, service_code, base_price, current_price, min_price, max_price, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, code, base_price, current_price, min_price, max_price, description))
        
        self.connection.commit()
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, 
                 last_name: str = None, language_code: str = 'ar') -> dict:
        """إضافة مستخدم جديد"""
        with self.lock:
            try:
                invite_code = self.generate_invite_code()
                
                self.cursor.execute('''
                    INSERT OR IGNORE INTO users 
                    (user_id, username, first_name, last_name, language_code, invite_code, balance)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, username, first_name, last_name, language_code, invite_code, WELCOME_BONUS_AMOUNT))
                
                if self.cursor.rowcount > 0:
                    self.add_transaction(
                        user_id=user_id,
                        amount=WELCOME_BONUS_AMOUNT,
                        transaction_type='welcome_bonus',
                        description='مكافأة ترحيبية'
                    )
                
                return self.get_user(user_id)
            except Exception as e:
                logger.error(f"❌ فشل في إضافة مستخدم: {e}")
                return None
    
    def get_user(self, user_id: int) -> dict:
        """الحصول على بيانات مستخدم"""
        with self.lock:
            self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            user = self.cursor.fetchone()
            return dict(user) if user else None
    
    def update_balance(self, user_id: int, amount: int, transaction_type: str, description: str = "") -> bool:
        """تحديث رصيد المستخدم"""
        with self.lock:
            try:
                if amount > 0:
                    self.cursor.execute(
                        'UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id = ?',
                        (amount, amount, user_id)
                    )
                else:
                    self.cursor.execute(
                        'UPDATE users SET balance = balance + ?, total_spent = total_spent + ABS(?) WHERE user_id = ?',
                        (amount, amount, user_id)
                    )
                
                self.add_transaction(user_id, amount, transaction_type, description)
                self.connection.commit()
                return True
            except Exception as e:
                logger.error(f"❌ فشل في تحديث الرصيد: {e}")
                return False
    
    def get_balance(self, user_id: int) -> int:
        """الحصول على رصيد المستخدم"""
        with self.lock:
            self.cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
            result = self.cursor.fetchone()
            return result[0] if result else 0
    
    def add_transaction(self, user_id: int, amount: int, transaction_type: str, 
                       description: str = "", reference_id: str = None) -> int:
        """إضافة عملية مالية"""
        with self.lock:
            try:
                reference_id = reference_id or self.generate_reference_id()
                
                self.cursor.execute('''
                    INSERT INTO transactions 
                    (user_id, amount, transaction_type, description, reference_id)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, amount, transaction_type, description, reference_id))
                
                transaction_id = self.cursor.lastrowid
                self.connection.commit()
                return transaction_id
            except Exception as e:
                logger.error(f"❌ فشل في إضافة عملية: {e}")
                return None
    
    def add_service_usage(self, user_id: int, service_name: str, service_type: str, 
                         cost: int, details: str = "") -> int:
        """تسجيل استخدام خدمة"""
        with self.lock:
            try:
                self.cursor.execute('''
                    INSERT INTO service_usage 
                    (user_id, service_name, service_type, cost, details)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, service_name, service_type, cost, details))
                
                usage_id = self.cursor.lastrowid
                self.connection.commit()
                return usage_id
            except Exception as e:
                logger.error(f"❌ فشل في تسجيل استخدام الخدمة: {e}")
                return None
    
    def get_service_price(self, service_code: str) -> int:
        """الحصول على سعر الخدمة"""
        with self.lock:
            self.cursor.execute('SELECT current_price FROM service_prices WHERE service_code = ?', (service_code,))
            result = self.cursor.fetchone()
            return result[0] if result else MINIMUM_SERVICE_PRICE
    
    def update_service_price(self, service_code: str, new_price: int) -> bool:
        """تحديث سعر الخدمة"""
        with self.lock:
            try:
                self.cursor.execute('''
                    UPDATE service_prices 
                    SET current_price = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE service_code = ? AND ? BETWEEN min_price AND max_price
                ''', (new_price, service_code, new_price))
                
                self.connection.commit()
                return self.cursor.rowcount > 0
            except Exception as e:
                logger.error(f"❌ فشل في تحديث سعر الخدمة: {e}")
                return False
    
    def get_all_users(self, limit: int = 100, offset: int = 0) -> list:
        """الحصول على جميع المستخدمين"""
        with self.lock:
            self.cursor.execute('SELECT * FROM users ORDER BY join_date DESC LIMIT ? OFFSET ?', (limit, offset))
            users = self.cursor.fetchall()
            return [dict(user) for user in users]
    
    def search_users(self, search_term: str) -> list:
        """بحث عن مستخدمين"""
        with self.lock:
            search_term = f"%{search_term}%"
            self.cursor.execute('''
                SELECT * FROM users 
                WHERE user_id LIKE ? OR username LIKE ? OR first_name LIKE ? OR last_name LIKE ?
                LIMIT 50
            ''', (search_term, search_term, search_term, search_term))
            
            users = self.cursor.fetchall()
            return [dict(user) for user in users]
    
    def ban_user(self, user_id: int, reason: str = "انتهاك القواعد") -> bool:
        """حظر مستخدم"""
        with self.lock:
            try:
                self.cursor.execute('''
                    UPDATE users SET is_banned = 1, ban_reason = ? WHERE user_id = ?
                ''', (reason, user_id))
                
                self.connection.commit()
                return self.cursor.rowcount > 0
            except Exception as e:
                logger.error(f"❌ فشل في حظر المستخدم: {e}")
                return False
    
    def unban_user(self, user_id: int) -> bool:
        """إلغاء حظر مستخدم"""
        with self.lock:
            try:
                self.cursor.execute('''
                    UPDATE users SET is_banned = 0, ban_reason = NULL WHERE user_id = ?
                ''', (user_id,))
                
                self.connection.commit()
                return self.cursor.rowcount > 0
            except Exception as e:
                logger.error(f"❌ فشل في إلغاء حظر المستخدم: {e}")
                return False
    
    def add_material(self, title: str, description: str, file_id: str, file_type: str,
                    category: str, stage: str, uploaded_by: int, **kwargs) -> int:
        """إضافة مادة تعليمية"""
        with self.lock:
            try:
                tags = kwargs.get('tags', '')
                metadata = json.dumps(kwargs.get('metadata', {}))
                
                self.cursor.execute('''
                    INSERT INTO educational_materials 
                    (title, description, file_id, file_type, category, stage, 
                     uploaded_by, tags, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (title, description, file_id, file_type, category, stage, 
                      uploaded_by, tags, metadata))
                
                material_id = self.cursor.lastrowid
                self.connection.commit()
                return material_id
            except Exception as e:
                logger.error(f"❌ فشل في إضافة مادة: {e}")
                return None
    
    def get_materials(self, filters: dict = None, limit: int = 20, offset: int = 0) -> list:
        """الحصول على المواد التعليمية"""
        with self.lock:
            query = "SELECT * FROM educational_materials WHERE is_approved = 1"
            params = []
            
            if filters:
                if 'stage' in filters:
                    query += " AND stage = ?"
                    params.append(filters['stage'])
            
            query += " ORDER BY upload_date DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            self.cursor.execute(query, params)
            materials = self.cursor.fetchall()
            return [dict(m) for m in materials]
    
    def increment_download_count(self, material_id: int) -> bool:
        """زيادة عداد التنزيلات"""
        with self.lock:
            try:
                self.cursor.execute('''
                    UPDATE educational_materials 
                    SET download_count = download_count + 1 
                    WHERE material_id = ?
                ''', (material_id,))
                
                self.connection.commit()
                return self.cursor.rowcount > 0
            except Exception as e:
                logger.error(f"❌ فشل في تحديث عداد التنزيلات: {e}")
                return False
    
    def get_setting(self, key: str) -> str:
        """الحصول على إعداد"""
        with self.lock:
            self.cursor.execute('SELECT setting_value FROM bot_settings WHERE setting_key = ?', (key,))
            result = self.cursor.fetchone()
            return result[0] if result else None
    
    def update_setting(self, key: str, value: str, updated_by: int = None) -> bool:
        """تحديث إعداد"""
        with self.lock:
            try:
                self.cursor.execute('''
                    UPDATE bot_settings 
                    SET setting_value = ?, updated_at = CURRENT_TIMESTAMP, updated_by = ?
                    WHERE setting_key = ?
                ''', (value, updated_by, key))
                
                self.connection.commit()
                return self.cursor.rowcount > 0
            except Exception as e:
                logger.error(f"❌ فشل في تحديث الإعداد: {e}")
                return False
    
    def generate_invite_code(self, length: int = 8) -> str:
        """إنشاء كود دعوة"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
            self.cursor.execute('SELECT COUNT(*) FROM users WHERE invite_code = ?', (code,))
            if self.cursor.fetchone()[0] == 0:
                return code
    
    def generate_reference_id(self, length: int = 12) -> str:
        """إنشاء رقم مرجعي"""
        timestamp = int(time.time())
        random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"REF{timestamp}{random_part}"
    
    def get_user_count(self) -> int:
        """الحصول على عدد المستخدمين"""
        with self.lock:
            self.cursor.execute('SELECT COUNT(*) FROM users')
            return self.cursor.fetchone()[0]
    
    def close(self):
        """إغلاق قاعدة البيانات"""
        if self.connection:
            self.connection.close()

# إنشاء قاعدة البيانات
db = Database()

# ============================================
# نظام الذكاء الاصطناعي
# ============================================

class AIAssistant:
    """مساعد الذكاء الاصطناعي"""
    
    def __init__(self, api_key: str = GEMINI_API_KEY):
        self.api_key = api_key
        self.model = None
        self.init_ai()
    
    def init_ai(self):
        """تهيئة الذكاء الاصطناعي"""
        try:
            genai.configure(api_key=self.api_key)
            
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
            
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]
            
            self.model = genai.GenerativeModel(
                model_name="gemini-pro",
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            logger.info("✅ تم تهيئة الذكاء الاصطناعي")
            return True
        except Exception as e:
            logger.error(f"❌ فشل في تهيئة الذكاء الاصطناعي: {e}")
            return False
    
    async def summarize_pdf(self, pdf_path: str, user_id: int) -> dict:
        """تلخيص ملف PDF"""
        try:
            text_content = ""
            with open(pdf_path, 'rb') as file:
                pdf_reader = PdfReader(file)
                
                for page_num in range(min(len(pdf_reader.pages), 50)):
                    page = pdf_reader.pages[page_num]
                    text_content += page.extract_text() + "\n\n"
            
            if not text_content.strip():
                return {
                    'success': False,
                    'error': 'لا يمكن قراءة النص من ملف PDF'
                }
            
            if len(text_content) > 15000:
                text_content = text_content[:15000] + "..."
            
            prompt = f"""
            أنت معلم عراقي متخصص.
            قم بتلخيص النص التعليمي التالي:
            
            {text_content}
            
            قدم التلخيص باللغة العربية بشكل منظم.
            """
            
            response = await self.generate_text(prompt)
            
            if not response['success']:
                return response
            
            return {
                'success': True,
                'summary': response['text'],
                'original_length': len(text_content),
                'summary_length': len(response['text'])
            }
            
        except Exception as e:
            logger.error(f"❌ خطأ في تلخيص PDF: {e}")
            return {
                'success': False,
                'error': f'خطأ في معالجة الملف: {str(e)}'
            }
    
    async def answer_question(self, question: str, context: str = "", user_id: int = None) -> dict:
        """الإجابة على الأسئلة"""
        try:
            prompt = f"""
            أنت مساعد تعليمي للطلاب العراقيين.
            أجب على السؤال التالي:
            
            السؤال: {question}
            
            {f'السياق: {context}' if context else ''}
            
            قدم الإجابة باللغة العربية بشكل مفصل.
            """
            
            response = await self.generate_text(prompt)
            
            if not response['success']:
                return response
            
            return {
                'success': True,
                'answer': response['text'],
                'confidence': 0.85
            }
            
        except Exception as e:
            logger.error(f"❌ خطأ في الإجابة على السؤال: {e}")
            return {
                'success': False,
                'error': f'خطأ في معالجة السؤال: {str(e)}'
            }
    
    async def analyze_image_question(self, image_path: str, question: str = None) -> dict:
        """تحليل صورة تحتوي على سؤال"""
        try:
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang='ara+eng')
            
            if not text.strip():
                return {
                    'success': False,
                    'error': 'لا يمكن قراءة النص من الصورة'
                }
            
            prompt = f"""
            هذا نص من صورة لسؤال تعليمي:
            
            {text}
            
            {'السؤال: ' + question if question else ''}
            
            قم بتحليل النص والإجابة.
            """
            
            response = await self.generate_text(prompt)
            
            if not response['success']:
                return response
            
            return {
                'success': True,
                'extracted_text': text,
                'answer': response['text']
            }
            
        except Exception as e:
            logger.error(f"❌ خطأ في تحليل صورة: {e}")
            return {
                'success': False,
                'error': f'خطأ في معالجة الصورة: {str(e)}'
            }
    
    async def generate_text(self, prompt: str, max_retries: int = 3) -> dict:
        """إنشاء نص"""
        for attempt in range(max_retries):
            try:
                if not self.model:
                    self.init_ai()
                    if not self.model:
                        return {
                            'success': False,
                            'error': 'نظام الذكاء الاصطناعي غير متاح'
                        }
                
                response = self.model.generate_content(prompt)
                
                if not response or not response.text:
                    return {
                        'success': False,
                        'error': 'لا توجد استجابة من الذكاء الاصطناعي'
                    }
                
                return {
                    'success': True,
                    'text': response.text,
                    'model': 'gemini-pro',
                    'attempt': attempt + 1
                }
                
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"❌ فشل في إنشاء النص: {e}")
                    return {
                        'success': False,
                        'error': f'فشل في الاتصال بالذكاء الاصطناعي: {str(e)}'
                    }
                
                await asyncio.sleep(1)
    
    def format_answer(self, answer: str) -> str:
        """تنسيق الإجابة"""
        formatted = answer.strip()
        formatted = re.sub(r'\n\s*\n\s*\n+', '\n\n', formatted)
        formatted = re.sub(r'^\d+[\.\)]\s*', '• ', formatted, flags=re.MULTILINE)
        return formatted

# إنشاء مساعد الذكاء الاصطناعي
ai_assistant = AIAssistant()

# ============================================
# نظام ملفات PDF
# ============================================

class PDFManager:
    """مدير ملفات PDF"""
    
    def __init__(self):
        self.temp_dir = TEMP_DIR
        os.makedirs(self.temp_dir, exist_ok=True)
        self.setup_fonts()
    
    def setup_fonts(self):
        """إعداد الخطوط"""
        try:
            # محاولة تسجيل خط عربي
            font_paths = [
                '/usr/share/fonts/truetype/arabic/arial.ttf',
                '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
                '/System/Library/Fonts/Supplemental/Arial.ttf',
                'C:/Windows/Fonts/arial.ttf'
            ]
            
            arabic_font_found = False
            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        pdfmetrics.registerFont(TTFont('Arabic', font_path))
                        arabic_font_found = True
                        break
                    except:
                        continue
            
            if not arabic_font_found:
                pdfmetrics.registerFont(TTFont('Arabic', 'Helvetica'))
            
            pdfmetrics.registerFont(TTFont('English', 'Helvetica'))
            
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في إعداد الخطوط: {e}")
            return False
    
    def create_summary_pdf(self, summary_text: str, original_filename: str, 
                          user_id: int, metadata: dict = None) -> str:
        """إنشاء ملف PDF مخرص"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = re.sub(r'[^\w\-_]', '', original_filename.replace('.pdf', ''))
            output_filename = f"ملخص_{safe_filename}_{timestamp}.pdf"
            output_path = os.path.join(self.temp_dir, output_filename)
            
            styles = getSampleStyleSheet()
            
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontName='Arabic',
                fontSize=16,
                textColor=colors.HexColor('#2C3E50'),
                spaceAfter=20,
                alignment=TA_CENTER
            )
            
            arabic_style = ParagraphStyle(
                'ArabicText',
                parent=styles['Normal'],
                fontName='Arabic',
                fontSize=12,
                textColor=colors.HexColor('#2C3E50'),
                spaceAfter=10,
                alignment=TA_RIGHT,
                leading=18
            )
            
            doc = SimpleDocTemplate(
                output_path,
                pagesize=A4,
                rightMargin=50,
                leftMargin=50,
                topMargin=50,
                bottomMargin=50
            )
            
            story = []
            
            title_text = f"<b>📚 ملخص: {original_filename}</b>"
            story.append(Paragraph(format_arabic_text(title_text), title_style))
            story.append(Spacer(1, 10))
            
            info_text = f"""
            <b>تاريخ التلخيص:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}<br/>
            <b>أداة التلخيص:</b> بوت {BOT_NAME}<br/>
            <b>رقم المرجع:</b> REF{timestamp}{user_id}
            """
            story.append(Paragraph(format_arabic_text(info_text), arabic_style))
            story.append(Spacer(1, 30))
            
            paragraphs = summary_text.split('\n\n')
            for para in paragraphs:
                if para.strip():
                    story.append(Paragraph(format_arabic_text(para.strip()), arabic_style))
                    story.append(Spacer(1, 8))
            
            story.append(Spacer(1, 40))
            
            footer_text = f"""
            <i>تم إنشاء هذا الملخص تلقائياً بواسطة بوت {BOT_NAME}<br/>
            للاستفسارات والدعم: {db.get_setting('support_username') or ADMIN_USERNAME}</i>
            """
            story.append(Paragraph(format_arabic_text(footer_text), arabic_style))
            
            doc.build(story)
            
            logger.info(f"✅ تم إنشاء ملف PDF: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء PDF: {e}")
            return None
    
    def cleanup_temp_files(self, hours_old: int = 24):
        """تنظيف الملفات المؤقتة"""
        try:
            cutoff_time = time.time() - (hours_old * 3600)
            
            for filename in os.listdir(self.temp_dir):
                file_path = os.path.join(self.temp_dir, filename)
                if os.path.isfile(file_path):
                    if os.path.getctime(file_path) < cutoff_time:
                        os.remove(file_path)
            
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في تنظيف الملفات: {e}")
            return False

# إنشاء مدير PDF
pdf_manager = PDFManager()

# ============================================
# أدوات مساعدة
# ============================================

def format_arabic_text(text: str) -> str:
    """تنسيق النص العربي"""
    try:
        if not text:
            return ""
        
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

def format_date(date_str: str, format_type: str = "full") -> str:
    """تنسيق التاريخ"""
    try:
        if isinstance(date_str, str):
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            dt = date_str
        
        if format_type == "full":
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        elif format_type == "date":
            return dt.strftime("%Y-%m-%d")
        elif format_type == "time":
            return dt.strftime("%H:%M")
        else:
            return str(dt)
    except Exception as e:
        logger.warning(f"⚠️ خطأ في تنسيق التاريخ: {e}")
        return date_str

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

def check_balance(service_code: str):
    """ديكوراتور للتحقق من الرصيد"""
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            
            if is_admin(user_id):
                return await func(update, context, *args, **kwargs)
            
            service_price = db.get_service_price(service_code)
            user_balance = db.get_balance(user_id)
            
            if user_balance < service_price:
                await update.message.reply_text(
                    format_arabic_text(f"""
                    ⚠️ **رصيدك غير كاف!**
                    
                    **سعر الخدمة:** {format_currency(service_price)}
                    **رصيدك الحالي:** {format_currency(user_balance)}
                    
                    📥 **لشحن الرصيد:**
                    تواصل مع الدعم الفني: {db.get_setting('support_username') or ADMIN_USERNAME}
                    """),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=main_keyboard(user_id)
                )
                return
            
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator

def check_maintenance(func):
    """ديكوراتور للتحقق من الصيانة"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        if is_admin(user_id):
            return await func(update, context, *args, **kwargs)
        
        maintenance_mode = db.get_setting('maintenance_mode')
        if maintenance_mode == '1':
            await update.message.reply_text(
                format_arabic_text("""
                🔧 **البوت قيد الصيانة حالياً**
                
                نعمل على تحسين الخدمة وتطويرها.
                سنعود قريباً بخدمات أفضل!
                """),
                reply_markup=ReplyKeyboardRemove()
            )
            return
        
        return await func(update, context, *args, **kwargs)
    return wrapper

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
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, selective=True)

def admin_keyboard() -> ReplyKeyboardMarkup:
    """لوحة مفاتيح المشرف"""
    keyboard = [
        ["📊 الإحصائيات", "👥 إدارة المستخدمين"],
        ["💰 الشحن والإيرادات", "⚙️ إعدادات الخدمات"],
        ["📚 إدارة المواد", "🎁 برنامج الدعوة"],
        ["🔧 إعدادات البوت", "📢 البث للمستخدمين"],
        ["🏠 القائمة الرئيسية"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def back_keyboard() -> ReplyKeyboardMarkup:
    """زر الرجوع"""
    return ReplyKeyboardMarkup([["🏠 القائمة الرئيسية"]], resize_keyboard=True)

def cancel_keyboard() -> ReplyKeyboardMarkup:
    """زر الإلغاء"""
    return ReplyKeyboardMarkup([["❌ إلغاء"]], resize_keyboard=True)

def stages_keyboard() -> ReplyKeyboardMarkup:
    """لوحة المراحل الدراسية"""
    keyboard = [
        ["المرحلة الأولى", "المرحلة الثانية"],
        ["المرحلة الثالثة", "المرحلة الرابعة"],
        ["🏠 القائمة الرئيسية"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def confirmation_keyboard() -> ReplyKeyboardMarkup:
    """لوحة التأكيد"""
    keyboard = [
        ["✅ نعم", "❌ لا"],
        ["🏠 القائمة الرئيسية"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ============================================
# معالجات الأوامر
# ============================================

@check_maintenance
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /start"""
    user = update.effective_user
    user_id = user.id
    
    welcome_text = format_arabic_text(f"""
    🎓 **مرحباً بك في {BOT_NAME}!**
    
    **📚 البوت التعليمي الذكي للطلاب العراقيين**
    
    🎁 **مكافأة ترحيبية:** {format_currency(WELCOME_BONUS_AMOUNT)}
    
    **الخدمات المتاحة:**
    
    📊 **حساب درجة العفوية** - {format_currency(db.get_service_price('exemption_calc'))}
    📄 **تلخيص الملازم** - {format_currency(db.get_service_price('pdf_summary'))}
    ❓ **أسئلة وأجوبة** - {format_currency(db.get_service_price('qa_ai'))}
    📚 **ملازمي ومرشحاتي** - {format_currency(db.get_service_price('materials'))}
    
    💰 **الرصيد الحالي:** {format_currency(db.get_balance(user_id))}
    
    📤 **دعوة أصدقاء:** احصل على {format_currency(int(db.get_setting('invite_bonus') or 500))} لكل صديق!
    
    👨‍💻 **الدعم الفني:** {db.get_setting('support_username') or ADMIN_USERNAME}
    """)
    
    user_data = db.add_user(
        user_id=user_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        language_code=user.language_code
    )
    
    if context.args:
        invite_code = context.args[0]
        db.cursor.execute('SELECT user_id FROM users WHERE invite_code = ?', (invite_code,))
        inviter = db.cursor.fetchone()
        
        if inviter and inviter['user_id'] != user_id:
            bonus = int(db.get_setting('invite_bonus') or 500)
            db.update_balance(user_id, bonus, 'referral_bonus', f'مكافأة دعوة من {inviter["user_id"]}')
            db.update_balance(inviter['user_id'], bonus, 'referral_bonus', f'مكافأة لدعوة {user_id}')
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(user_id)
    )
    
    logger.info(f"👋 مستخدم جديد: {user_id}")

@check_maintenance
async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الرصيد"""
    user_id = update.effective_user.id
    user_balance = db.get_balance(user_id)
    user_data = db.get_user(user_id)
    
    invite_code = user_data.get('invite_code', '')
    invite_link = f"https://t.me/{BOT_USERNAME.replace('@', '')}?start={invite_code}"
    
    balance_text = format_arabic_text(f"""
    💰 **الرصيد والعمليات المالية**
    
    **💵 الرصيد الحالي:** {format_currency(user_balance)}
    
    **📤 برنامج الدعوة:**
    • مكافأة الدعوة: {format_currency(int(db.get_setting('invite_bonus') or 500))}
    • عدد الأصدقاء المدعوين: {user_data.get('referral_count', 0)}
    
    **🔗 رابط دعوتك:**
    `{invite_link}`
    
    **💳 طرق شحن الرصيد:**
    1. التواصل مع الدعم الفني
    2. دعوة الأصدقاء عبر الرابط
    
    **📝 آخر العمليات:**
    """)
    
    transactions = db.cursor.execute('''
        SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT 5
    ''', (user_id,)).fetchall()
    
    if transactions:
        for i, trans in enumerate(transactions, 1):
            amount = trans['amount']
            amount_str = f"+{format_currency(amount)}" if amount > 0 else format_currency(amount)
            balance_text += f"\n{i}. {trans['description']}: {amount_str}"
    else:
        balance_text += "\n📭 لا توجد عمليات سابقة"
    
    await update.message.reply_text(
        balance_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(user_id)
    )

@check_maintenance
async def invite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معلومات الدعوة"""
    user_id = update.effective_user.id
    user_data = db.get_user(user_id)
    
    invite_code = user_data.get('invite_code', '')
    invite_link = f"https://t.me/{BOT_USERNAME.replace('@', '')}?start={invite_code}"
    invite_bonus = int(db.get_setting('invite_bonus') or 500)
    
    invite_text = format_arabic_text(f"""
    📤 **برنامج دعوة الأصدقاء**
    
    **🎁 المكافأة:** {format_currency(invite_bonus)} لكل صديق
    **👥 عدد الأصدقاء المدعوين:** {user_data.get('referral_count', 0)}
    
    **🔗 رابط دعوتك:**
    `{invite_link}`
    
    **📝 كيفية الاستخدام:**
    1. أرسل الرابط لصديقك
    2. ينقر صديقك على الرابط ويبدأ استخدام البوت
    3. تحصل أنت وصديقك على المكافأة تلقائياً!
    
    **📞 للاستفسارات:** {db.get_setting('support_username') or ADMIN_USERNAME}
    """)
    
    await update.message.reply_text(
        invite_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(user_id)
    )

@check_maintenance
async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معلومات البوت"""
    user_id = update.effective_user.id
    
    total_users = db.get_user_count()
    
    info_text = format_arabic_text(f"""
    ℹ️ **معلومات عن {BOT_NAME}**
    
    **🤖 وصف البوت:**
    بوت تعليمي ذكي مصمم خصيصاً للطلاب العراقيين.
    
    **📊 إحصائيات البوت:**
    • إجمالي المستخدمين: {format_number(total_users)}
    
    **💎 المميزات:**
    ✅ حساب درجة العفوية
    ✅ تلخيص الملازم بالذكاء الاصطناعي
    ✅ أسئلة وأجوبة ذكية
    ✅ مكتبة المواد التعليمية
    ✅ نظام الدعوة والمكافآت
    
    **📞 قنوات التواصل:**
    • البوت الرسمي: {BOT_USERNAME}
    • الدعم الفني: {db.get_setting('support_username') or ADMIN_USERNAME}
    
    **👑 فريق التطوير:**
    • المطور: {ADMIN_USERNAME}
    • أيدي المطور: {ADMIN_USER_ID}
    
    **🔄 آخر تحديث:** {datetime.now().strftime('%Y-%m-%d')}
    """)
    
    await update.message.reply_text(
        info_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(user_id)
    )

@check_maintenance
async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الدعم الفني"""
    user_id = update.effective_user.id
    
    support_text = format_arabic_text(f"""
    👨‍💻 **الدعم الفني والاتصال**
    
    **📞 معلومات الاتصال:**
    • يوزر الدعم: {db.get_setting('support_username') or ADMIN_USERNAME}
    • أيدي المطور: `{ADMIN_USER_ID}`
    
    **⏰ ساعات العمل:**
    • الأحد - الخميس: 9:00 ص - 5:00 م
    • الجمعة - السبت: 10:00 ص - 2:00 م
    • توقيت بغداد
    
    **📋 خدمات الدعم:**
    1. المساعدة الفنية
    2. حل المشاكل
    3. استفسارات الدفع
    4. اقتراحات التطوير
    
    **⏱️ وقت الاستجابة:** خلال 24 ساعة
    
    **شكراً لثقتك!** 🤝
    """)
    
    await update.message.reply_text(
        support_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard(user_id)
    )

@check_maintenance
@check_balance('exemption_calc')
async def exemption_calculation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حساب درجة العفوية"""
    user_id = update.effective_user.id
    
    service_price = db.get_service_price('exemption_calc')
    
    db.add_service_usage(
        user_id=user_id,
        service_name='حساب درجة العفوية',
        service_type='exemption_calc',
        cost=service_price,
        details='بدء عملية الحساب'
    )
    
    if not is_admin(user_id):
        db.update_balance(
            user_id=user_id,
            amount=-service_price,
            transaction_type='service_payment',
            description='حساب درجة العفوية'
        )
    
    await update.message.reply_text(
        format_arabic_text("""
        📊 **حساب درجة العفوية**
        
        **🎯 الشرط:** المعدل ≥ 90
        
        **أرسل درجة الكورس الأول:**
        """),
        reply_markup=back_keyboard()
    )
    
    context.user_data['exemption_stage'] = 'course1'
    context.user_data['exemption_data'] = {}
    
    return COURSE1

async def process_course1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة درجة الكورس الأول"""
    user_id = update.effective_user.id
    
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
            
            context.user_data['exemption_stage'] = 'course2'
            return COURSE2
        else:
            await update.message.reply_text(
                format_arabic_text("""
                ⚠️ **درجة غير صحيحة!**
                
                الرجاء إدخال درجة بين 0 و 100:
                """),
                reply_markup=back_keyboard()
            )
            return COURSE1
            
    except ValueError:
        await update.message.reply_text(
            format_arabic_text("""
            ⚠️ **قيمة غير صحيحة!**
            
            الرجاء إدخال رقم فقط:
            """),
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
            
            context.user_data['exemption_stage'] = 'course3'
            return COURSE3
        else:
            await update.message.reply_text(
                format_arabic_text("""
                ⚠️ **درجة غير صحيحة!**
                
                الرجاء إدخال درجة بين 0 و 100:
                """),
                reply_markup=back_keyboard()
            )
            return COURSE2
            
    except ValueError:
        await update.message.reply_text(
            format_arabic_text("""
            ⚠️ **قيمة غير صحيحة!**
            
            الرجاء إدخال رقم فقط:
            """),
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
                is_exempt = True
            else:
                result = "❌ **للأسف، أنت غير معفي من المادة**"
                result_emoji = "❌"
                is_exempt = False
            
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
                format_arabic_text("""
                ⚠️ **درجة غير صحيحة!**
                
                الرجاء إدخال درجة بين 0 و 100:
                """),
                reply_markup=back_keyboard()
            )
            return COURSE3
            
    except ValueError:
        await update.message.reply_text(
            format_arabic_text("""
            ⚠️ **قيمة غير صحيحة!**
            
            الرجاء إدخال رقم فقط:
            """),
            reply_markup=back_keyboard()
        )
        return COURSE3

@check_maintenance
@check_balance('pdf_summary')
async def pdf_summary_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء تلخيص PDF"""
    user_id = update.effective_user.id
    
    service_price = db.get_service_price('pdf_summary')
    
    db.add_service_usage(
        user_id=user_id,
        service_name='تلخيص الملازم',
        service_type='pdf_summary',
        cost=service_price,
        details='بدء عملية التلخيص'
    )
    
    if not is_admin(user_id):
        db.update_balance(
            user_id=user_id,
            amount=-service_price,
            transaction_type='service_payment',
            description='تلخيص الملازم'
        )
    
    await update.message.reply_text(
        format_arabic_text("""
        📄 **تلخيص الملازم بالذكاء الاصطناعي**
        
        **📝 التعليمات:**
        1. أرسل ملف PDF المراد تلخيصه
        2. انتظر قليلاً لمعالجة الملف
        3. ستحصل على ملف PDF مخرص
        
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
            format_arabic_text("""
            ⚠️ **لم يتم إرسال ملف!**
            
            الرجاء إرسال ملف PDF:
            """),
            reply_markup=back_keyboard()
        )
        return WAITING_PDF
    
    document = update.message.document
    
    if not document.file_name.lower().endswith('.pdf'):
        await update.message.reply_text(
            format_arabic_text("""
            ⚠️ **نوع ملف غير مدعوم!**
            
            الرجاء إرسال ملف PDF فقط:
            """),
            reply_markup=back_keyboard()
        )
        return WAITING_PDF
    
    if document.file_size > MAX_FILE_SIZE:
        await update.message.reply_text(
            format_arabic_text(f"""
            ⚠️ **حجم الملف كبير جداً!**
            
            الحجم الأقصى: {MAX_FILE_SIZE // (1024*1024)} ميجابايت
            
            الرجاء إرسال ملف أصغر:
            """),
            reply_markup=back_keyboard()
        )
        return WAITING_PDF
    
    processing_msg = await update.message.reply_text(
        format_arabic_text("""
        ⏳ **جاري معالجة الملف...**
        
        📥 تحميل الملف...
        """),
        reply_markup=back_keyboard()
    )
    
    try:
        file = await context.bot.get_file(document.file_id)
        
        temp_filename = f"pdf_{user_id}_{int(time.time())}.pdf"
        temp_path = os.path.join(TEMP_DIR, temp_filename)
        
        await processing_msg.edit_text(
            format_arabic_text("""
            ⏳ **جاري معالجة الملف...**
            
            ✅ تم التحميل
            🔍 قراءة المحتوى...
            """),
            reply_markup=back_keyboard()
        )
        
        await file.download_to_drive(temp_path)
        
        await processing_msg.edit_text(
            format_arabic_text("""
            ⏳ **جاري معالجة الملف...**
            
            ✅ تم التحميل
            ✅ تم قراءة المحتوى
            🤖 جاري التلخيص...
            """),
            reply_markup=back_keyboard()
        )
        
        result = await ai_assistant.summarize_pdf(temp_path, user_id)
        
        if not result['success']:
            await processing_msg.edit_text(
                format_arabic_text(f"""
                ❌ **فشل في معالجة الملف!**
                
                **الخطأ:** {result['error']}
                
                الرجاء إرسال ملف آخر:
                """),
                reply_markup=back_keyboard()
            )
            
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            return WAITING_PDF
        
        await processing_msg.edit_text(
            format_arabic_text("""
            ⏳ **جاري معالجة الملف...**
            
            ✅ تم التحميل
            ✅ تم قراءة المحتوى
            ✅ تم التلخيص
            📝 جاري إنشاء ملف PDF...
            """),
            reply_markup=back_keyboard()
        )
        
        summary_pdf_path = pdf_manager.create_summary_pdf(
            summary_text=result['summary'],
            original_filename=document.file_name,
            user_id=user_id
        )
        
        if not summary_pdf_path:
            await processing_msg.edit_text(
                format_arabic_text("""
                ❌ **فشل في إنشاء الملف!**
                
                الرجاء إرسال ملف آخر:
                """),
                reply_markup=back_keyboard()
            )
            return WAITING_PDF
        
        await processing_msg.edit_text(
            format_arabic_text("""
            ⏳ **جاري معالجة الملف...**
            
            ✅ تم التحميل
            ✅ تم قراءة المحتوى
            ✅ تم التلخيص
            ✅ تم إنشاء ملف PDF
            📤 جاري إرسال الملف...
            """),
            reply_markup=back_keyboard()
        )
        
        with open(summary_pdf_path, 'rb') as pdf_file:
            await update.message.reply_document(
                document=pdf_file,
                caption=format_arabic_text(f"""
                ✅ **تم تلخيص الملف بنجاح!**
                
                **📄 الملف الأصلي:** {document.file_name}
                **📊 الملف المخرص:** ملخص_{document.file_name}
                **📅 تاريخ الإنشاء:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
                
                **🤖 التقنية المستخدمة:** الذكاء الاصطناعي
                """),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_keyboard(user_id)
            )
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
        if os.path.exists(summary_pdf_path):
            os.remove(summary_pdf_path)
        
        await processing_msg.delete()
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة PDF: {e}")
        
        await processing_msg.edit_text(
            format_arabic_text(f"""
            ❌ **حدث خطأ!**
            
            **الخطأ:** {str(e)}
            
            الرجاء إرسال ملف آخر:
            """),
            reply_markup=back_keyboard()
        )
        
        return WAITING_PDF

@check_maintenance
@check_balance('qa_ai')
async def qa_ai_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء خدمة الأسئلة"""
    user_id = update.effective_user.id
    
    service_price = db.get_service_price('qa_ai')
    
    db.add_service_usage(
        user_id=user_id,
        service_name='أسئلة وأجوبة',
        service_type='qa_ai',
        cost=service_price,
        details='بدء خدمة الأسئلة'
    )
    
    if not is_admin(user_id):
        db.update_balance(
            user_id=user_id,
            amount=-service_price,
            transaction_type='service_payment',
            description='أسئلة وأجوبة'
        )
    
    await update.message.reply_text(
        format_arabic_text("""
        ❓ **أسئلة وأجوبة بالذكاء الاصطناعي**
        
        **🎯 كيفية الاستخدام:**
        1. أرسل سؤالك نصياً
        2. أو أرسل صورة تحتوي على سؤال
        3. انتظر قليلاً للإجابة
        
        **📝 أرسل سؤالك الآن:**
        """),
        reply_markup=back_keyboard()
    )
    
    return WAITING_QUESTION

async def process_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة السؤال"""
    user_id = update.effective_user.id
    
    processing_msg = await update.message.reply_text(
        format_arabic_text("""
        ⏳ **جاري البحث عن الإجابة...**
        
        🤖 تحليل السؤال...
        """),
        reply_markup=back_keyboard()
    )
    
    try:
        question_text = ""
        is_image = False
        
        if update.message.text:
            question_text = update.message.text
            
        elif update.message.photo:
            is_image = True
            
            await processing_msg.edit_text(
                format_arabic_text("""
                ⏳ **جاري البحث عن الإجابة...**
                
                🤖 تحليل السؤال...
                📷 قراءة الصورة...
                """),
                reply_markup=back_keyboard()
            )
            
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            
            temp_image = f"question_{user_id}_{int(time.time())}.jpg"
            temp_path = os.path.join(TEMP_DIR, temp_image)
            
            await file.download_to_drive(temp_path)
            
            result = await ai_assistant.analyze_image_question(temp_path)
            
            if not result['success']:
                await processing_msg.edit_text(
                    format_arabic_text(f"""
                    ❌ **فشل في قراءة الصورة!**
                    
                    **الخطأ:** {result['error']}
                    
                    الرجاء إعادة إرسال السؤال:
                    """),
                    reply_markup=back_keyboard()
                )
                
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                
                return WAITING_QUESTION
            
            question_text = result['extracted_text']
            
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        else:
            await processing_msg.edit_text(
                format_arabic_text("""
                ⚠️ **نوع محتوى غير مدعوم!**
                
                الرجاء إرسال سؤال نصي أو صورة:
                """),
                reply_markup=back_keyboard()
            )
            return WAITING_QUESTION
        
        await processing_msg.edit_text(
            format_arabic_text("""
            ⏳ **جاري البحث عن الإجابة...**
            
            ✅ تم تحليل السؤال
            🔍 جاري البحث...
            """),
            reply_markup=back_keyboard()
        )
        
        result = await ai_assistant.answer_question(question_text, user_id=user_id)
        
        if not result['success']:
            await processing_msg.edit_text(
                format_arabic_text(f"""
                ❌ **فشل في الحصول على إجابة!**
                
                **الخطأ:** {result['error']}
                
                الرجاء إعادة إرسال السؤال:
                """),
                reply_markup=back_keyboard()
            )
            return WAITING_QUESTION
        
        await processing_msg.edit_text(
            format_arabic_text("""
            ⏳ **جاري البحث عن الإجابة...**
            
            ✅ تم تحليل السؤال
            ✅ تم العثور على إجابة
            📝 جاري تحسين التنسيق...
            """),
            reply_markup=back_keyboard()
        )
        
        answer_text = format_arabic_text(f"""
        🤖 **إجابة على سؤالك:**
        
        **❓ السؤال:**
        {question_text[:500]}{'...' if len(question_text) > 500 else ''}
        
        **✅ الإجابة:**
        {result['answer']}
        
        **📝 ملاحظة:** تمت الإجابة باستخدام الذكاء الاصطناعي
        """)
        
        if len(answer_text) > 4000:
            parts = [answer_text[i:i+4000] for i in range(0, len(answer_text), 4000)]
            
            for i, part in enumerate(parts):
                if i == 0:
                    await processing_msg.edit_text(
                        part,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=main_keyboard(user_id)
                    )
                else:
                    await update.message.reply_text(
                        part,
                        parse_mode=ParseMode.MARKDOWN
                    )
        else:
            await processing_msg.edit_text(
                answer_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_keyboard(user_id)
            )
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة السؤال: {e}")
        
        await processing_msg.edit_text(
            format_arabic_text(f"""
            ❌ **حدث خطأ!**
            
            **الخطأ:** {str(e)}
            
            الرجاء إعادة إرسال السؤال:
            """),
            reply_markup=back_keyboard()
        )
        
        return WAITING_QUESTION

@check_maintenance
@check_balance('materials')
async def materials_library(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مكتبة المواد"""
    user_id = update.effective_user.id
    
    service_price = db.get_service_price('materials')
    
    db.add_service_usage(
        user_id=user_id,
        service_name='ملازمي ومرشحاتي',
        service_type='materials',
        cost=service_price,
        details='تصفح المكتبة'
    )
    
    if not is_admin(user_id):
        db.update_balance(
            user_id=user_id,
            amount=-service_price,
            transaction_type='service_payment',
            description='ملازمي ومرشحاتي'
        )
    
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
            format_arabic_text("""
            ⚠️ **مرحلة غير صحيحة!**
            
            اختر مرحلة صحيحة:
            """),
            reply_markup=stages_keyboard()
        )
        return
    
    materials = db.get_materials(filters={'stage': stage_code}, limit=10)
    
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
    
    db.cursor.execute('SELECT * FROM educational_materials WHERE material_id = ?', (material_id,))
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
    • تاريخ الإضافة: {format_date(material['upload_date'], 'date')}
    
    **📥 يمكنك تنزيل المادة الآن:**
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
    
    db.cursor.execute('SELECT * FROM educational_materials WHERE material_id = ?', (material_id,))
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
            
            **📊 المعلومات:**
            • المرحلة: {material['stage']}
            • تاريخ الإضافة: {format_date(material['upload_date'], 'date')}
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
        [InlineKeyboardButton("💰 الشحن والإيرادات", callback_data="admin_finance")],
        [InlineKeyboardButton("⚙️ إعدادات الخدمات", callback_data="admin_services")],
        [InlineKeyboardButton("📚 إدارة المواد", callback_data="admin_materials")],
        [InlineKeyboardButton("🔧 إعدادات البوت", callback_data="admin_settings")],
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
    
    db.cursor.execute('SELECT COUNT(*) FROM service_usage WHERE DATE(created_at) = DATE("now")')
    daily_services = db.cursor.fetchone()[0]
    
    db.cursor.execute('SELECT SUM(cost) FROM service_usage WHERE DATE(created_at) = DATE("now")')
    daily_revenue = db.cursor.fetchone()[0] or 0
    
    stats_text = format_arabic_text(f"""
    📊 **الإحصائيات**
    
    **👥 المستخدمين:**
    • إجمالي المستخدمين: {format_number(total_users)}
    
    **💰 المالية (اليوم):**
    • عدد الخدمات: {format_number(daily_services)}
    • الإيرادات: {format_currency(daily_revenue)}
    
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
            [InlineKeyboardButton("💰 شحن رصيد", callback_data="admin_charge")],
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
            📭 **لا توجد نتائج لـ "{search_term}"**
            
            **أرسل بحث جديد:**
            """),
            reply_markup=back_keyboard()
        )
        return ADMIN_SEARCH_USER
    
    results_text = format_arabic_text(f"""
    🔍 **نتائج البحث**
    
    **📊 عدد النتائج:** {len(users)}
    
    **📝 النتائج:**
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
    **📅 تاريخ التسجيل:** {format_date(user['join_date'], 'date')}
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
                format_arabic_text("""
                ⚠️ **انتهت الجلسة!**
                """),
                reply_markup=admin_keyboard()
            )
            return ConversationHandler.END
        
        user = db.get_user(user_id)
        old_balance = user['balance']
        
        db.update_balance(
            user_id=user_id,
            amount=amount,
            transaction_type='admin_charge',
            description=f'شحن بواسطة المشرف: {amount}'
        )
        
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
            reply_markup=admin_keyboard()
        )
        
        context.user_data.pop('charge_user_id', None)
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            format_arabic_text("""
            ⚠️ **قيمة غير صحيحة!**
            
            الرجاء إرسال رقم صحيح:
            """),
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
        
        user = db.get_user(user_id)
        
        await query.edit_message_text(
            text=format_arabic_text(f"""
            ✅ **تم حظر المستخدم**
            
            **👤 المستخدم:** {user['first_name'] or ''} {user['last_name'] or ''}
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
        
        user = db.get_user(user_id)
        
        await query.edit_message_text(
            text=format_arabic_text(f"""
            ✅ **تم إلغاء حظر المستخدم**
            
            **👤 المستخدم:** {user['first_name'] or ''} {user['last_name'] or ''}
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
async def admin_service_settings_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إعدادات الخدمات"""
    query = update.callback_query
    await query.answer()
    
    db.cursor.execute('SELECT * FROM service_prices')
    services = db.cursor.fetchall()
    
    services_text = format_arabic_text("""
    ⚙️ **إعدادات الخدمات**
    
    **📝 الخدمات:**
    """)
    
    keyboard = []
    
    for service in services:
        service = dict(service)
        services_text += f"\n• **{service['service_name']}**"
        services_text += f"\n  السعر: {format_currency(service['current_price'])}"
        
        keyboard.append([
            InlineKeyboardButton(
                f"💰 {service['service_name']}",
                callback_data=f"admin_service_{service['service_code']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")])
    
    await query.edit_message_text(
        text=services_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@admin_only
async def admin_edit_service_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تعديل سعر الخدمة"""
    query = update.callback_query
    await query.answer()
    
    service_code = query.data.split('_')[-1]
    context.user_data['edit_service_code'] = service_code
    
    await query.edit_message_text(
        text=format_arabic_text(f"""
        💰 **تغيير السعر**
        
        **🔤 الخدمة:** {service_code}
        
        **أرسل السعر الجديد:**
        """),
        reply_markup=back_keyboard()
    )
    
    return ADMIN_SET_PRICE

async def process_admin_set_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة تعيين السعر"""
    try:
        new_price = int(update.message.text)
        service_code = context.user_data.get('edit_service_code')
        
        if not service_code:
            await update.message.reply_text(
                format_arabic_text("""
                ⚠️ **انتهت الجلسة!**
                """),
                reply_markup=admin_keyboard()
            )
            return ConversationHandler.END
        
        if db.update_service_price(service_code, new_price):
            await update.message.reply_text(
                format_arabic_text(f"""
                ✅ **تم تحديث السعر!**
                
                **🔤 الخدمة:** {service_code}
                **💰 السعر الجديد:** {format_currency(new_price)}
                """),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=admin_keyboard()
            )
        else:
            await update.message.reply_text(
                format_arabic_text(f"""
                ❌ **فشل في التحديث!**
                
                **أرسل السعر الجديد:**
                """),
                reply_markup=back_keyboard()
            )
            return ADMIN_SET_PRICE
        
        context.user_data.pop('edit_service_code', None)
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            format_arabic_text("""
            ⚠️ **قيمة غير صحيحة!**
            
            الرجاء إرسال رقم صحيح:
            """),
            reply_markup=back_keyboard()
        )
        return ADMIN_SET_PRICE

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
        • فشل الإرسال: 0
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
        reply_markup=admin_keyboard()
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
    
    elif data == "admin_services":
        await admin_service_settings_panel(update, context)
    
    elif data.startswith("admin_service_"):
        await admin_edit_service_price(update, context)
    
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

@check_maintenance
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
# وظائف الخلفية
# ============================================

async def cleanup_job(context: ContextTypes.DEFAULT_TYPE):
    """تنظيف الملفات"""
    try:
        pdf_manager.cleanup_temp_files(hours_old=24)
        logger.info("✅ تم تنظيف الملفات")
    except Exception as e:
        logger.error(f"❌ خطأ في التنظيف: {e}")

# ============================================
# الدالة الرئيسية
# ============================================

def main():
    """الدالة الرئيسية"""
    
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ لم تقم بتعيين توكن البوت!")
        return
    
    if not GEMINI_API_KEY:
        logger.error("❌ لم تقم بتعيين مفتاح API!")
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
                MessageHandler(filters.TEXT | filters.PHOTO, process_question)
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
    
    # محادثة سعر الخدمة
    admin_price_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_edit_service_price, pattern="^admin_service_")],
        states={
            ADMIN_SET_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_set_price)]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            MessageHandler(filters.Regex("^🏠 القائمة الرئيسية$"), cancel_conversation)
        ]
    )
    application.add_handler(admin_price_conv)
    
    # محادثة البث
    admin_broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_broadcast_start, pattern="^admin_broadcast$")],
        states={
            ADMIN_BROADCAST: [
                MessageHandler(filters.TEXT | filters.PHOTO | filters.Document.ALL, process_admin_broadcast)
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
    
    # وظائف مجدولة
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(cleanup_job, interval=3600, first=10)
    
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
