#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت "يلا نتعلم" - Telegram Bot متكامل للطلاب
المطور: Allawi04@
ID المطور: 6130994941
قناة البوت: https://t.me/FCJCV
"""

import asyncio
import logging
import sqlite3
import json
import os
import re
import tempfile
import uuid
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import html

import aiohttp
import fitz  # PyMuPDF
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import simpleSplit
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    InputFile, InputMediaDocument, ReplyKeyboardMarkup,
    KeyboardButton, Message, User, Chat, Document
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters,
    ConversationHandler
)
from telegram.constants import ParseMode, ChatAction
import google.generativeai as genai
import arabic_reshaper
from bidi.algorithm import get_display

# ============== إعدادات البوت ==============
BOT_TOKEN = "8481569753:AAH3alhJ0hcHldht-PxV7j8TzBlRsMqAqGI"
BOT_USERNAME = "@FC4Xbot"
DEVELOPER_ID = 6130994941
DEVELOPER_USERNAME = "Allawi04@"
CHANNEL_LINK = "https://t.me/FCJCV"
GEMINI_API_KEY = "AIzaSyARsl_YMXA74bPQpJduu0jJVuaku7MaHuY"

# إعداد الذكاء الاصطناعي
genai.configure(api_key=GEMINI_API_KEY)
generation_config = {
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config=generation_config,
    safety_settings=safety_settings
)

# ============== حالات المحادثة ==============
WAITING_FOR_GRADES, WAITING_FOR_PDF, WAITING_FOR_QUESTION = range(3)
WAITING_FOR_STUDENT_QUESTION, WAITING_FOR_MATERIAL, WAITING_FOR_VIP_LECTURE = range(3, 6)
ADMIN_CHARGE, ADMIN_DEDUCT, ADMIN_BAN, ADMIN_UNBAN, ADMIN_ADD_ADMIN = range(6, 11)
ADMIN_SERVICE_PRICE, ADMIN_BROADCAST, ADMIN_MAINTENANCE = range(11, 14)
VIP_LECTURE_TITLE, VIP_LECTURE_DESC, VIP_LECTURE_FILE, VIP_LECTURE_PRICE = range(14, 18)
VIP_SUBSCRIPTION_PAYMENT, WITHDRAWAL_REQUEST = range(18, 20)

# ============== إعداد قواعد البيانات ==============
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('yalla_nt3lm.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.init_database()
    
    def init_database(self):
        # جدول المستخدمين
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                balance INTEGER DEFAULT 1000,
                invite_code TEXT UNIQUE,
                invited_by INTEGER DEFAULT 0,
                invited_count INTEGER DEFAULT 0,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_banned INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0,
                is_vip INTEGER DEFAULT 0,
                vip_expiry TIMESTAMP,
                free_trial_used INTEGER DEFAULT 0,
                total_spent INTEGER DEFAULT 0
            )
        ''')
        
        # جدول المعاملات
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                transaction_type TEXT,
                description TEXT,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # جدول الخدمات
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                display_name TEXT,
                price INTEGER DEFAULT 1000,
                is_active INTEGER DEFAULT 1,
                category TEXT
            )
        ''')
        
        # جدول الأسئلة والأجوبة
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                question TEXT,
                subject TEXT,
                status TEXT DEFAULT 'pending',
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                answer TEXT,
                answered_by INTEGER,
                answer_date TIMESTAMP,
                reward_paid INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (answered_by) REFERENCES users (user_id)
            )
        ''')
        
        # جدول المواد الدراسية
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS study_materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                description TEXT,
                stage TEXT,
                file_id TEXT,
                added_by INTEGER,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (added_by) REFERENCES users (user_id)
            )
        ''')
        
        # جدول محاضرات VIP
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS vip_lectures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER,
                title TEXT,
                description TEXT,
                file_id TEXT,
                file_type TEXT,
                price INTEGER DEFAULT 5000,
                approved INTEGER DEFAULT 0,
                rating REAL DEFAULT 0.0,
                rating_count INTEGER DEFAULT 0,
                views INTEGER DEFAULT 0,
                purchases INTEGER DEFAULT 0,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (teacher_id) REFERENCES users (user_id)
            )
        ''')
        
        # جدول مشتريات محاضرات VIP
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS vip_purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                lecture_id INTEGER,
                amount_paid INTEGER,
                purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (lecture_id) REFERENCES vip_lectures (id)
            )
        ''')
        
        # جدول أرباح المعلمين
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS teacher_earnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER,
                lecture_id INTEGER,
                amount INTEGER,
                status TEXT DEFAULT 'pending',
                transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (teacher_id) REFERENCES users (user_id),
                FOREIGN KEY (lecture_id) REFERENCES vip_lectures (id)
            )
        ''')
        
        # جدول تقييمات المحاضرات
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS lecture_ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                lecture_id INTEGER,
                rating INTEGER,
                comment TEXT,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (lecture_id) REFERENCES vip_lectures (id)
            )
        ''')
        
        # جدول إعدادات البوت
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        # جدول طلبات السحب
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS withdrawal_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                status TEXT DEFAULT 'pending',
                request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_date TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # إدخال الخدمات الأساسية
        services = [
            ('exemption_calculator', 'حساب درجة الإعفاء', 1000, 'main'),
            ('pdf_summary', 'تلخيص الملازم', 1000, 'main'),
            ('qna', 'سؤال وجواب', 1000, 'main'),
            ('help_student', 'ساعدوني طالب', 1000, 'main'),
            ('study_materials', 'ملازمي ومرشحاتي', 0, 'main'),
            ('vip_subscription', 'اشتراك VIP', 20000, 'vip'),
            ('vip_lecture_purchase', 'شراء محاضرة VIP', 5000, 'vip'),
            ('vip_lecture_upload', 'رفع محاضرة VIP', 0, 'vip')
        ]
        
        for service_id, display_name, price, category in services:
            self.cursor.execute('''
                INSERT OR IGNORE INTO services (name, display_name, price, category)
                VALUES (?, ?, ?, ?)
            ''', (service_id, display_name, price, category))
        
        # إدخال الإعدادات الأساسية
        settings = [
            ('invite_bonus', '1000'),
            ('min_withdrawal', '15000'),
            ('vip_monthly_price', '20000'),
            ('maintenance_mode', '0'),
            ('support_username', DEVELOPER_USERNAME),
            ('channel_link', CHANNEL_LINK),
            ('admin_ids', str(DEVELOPER_ID)),
            ('question_reward', '100'),
            ('teacher_percentage', '60'),
            ('admin_percentage', '40')
        ]
        
        for key, value in settings:
            self.cursor.execute('''
                INSERT OR IGNORE INTO bot_settings (key, value)
                VALUES (?, ?)
            ''', (key, value))
        
        # إضافة المستخدم المطور
        self.cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, balance, is_admin, is_vip)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (DEVELOPER_ID, DEVELOPER_USERNAME, 'المطور', 1000000, 1, 1))
        
        self.conn.commit()
    
    def get_user(self, user_id: int) -> Dict:
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        cols = [col[0] for col in self.cursor.description]
        row = self.cursor.fetchone()
        if row:
            return dict(zip(cols, row))
        return None
    
    def create_user(self, user: User, invite_code: str = None, invited_by: int = None):
        invite_bonus = int(self.get_setting('invite_bonus'))
        
        self.cursor.execute('''
            INSERT OR IGNORE INTO users 
            (user_id, username, first_name, last_name, invite_code, invited_by, balance)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            user.id, 
            user.username, 
            user.first_name, 
            user.last_name,
            invite_code or str(uuid.uuid4())[:8],
            invited_by,
            invite_bonus if not invited_by else 0
        ))
        
        if invited_by:
            # منح المكافأة للمدعو
            self.update_balance(user.id, invite_bonus, 'invite_bonus', 'مكافأة دعوة')
            # زيادة عدد الدعوات للمدعِي
            self.cursor.execute('''
                UPDATE users SET invited_count = invited_count + 1 
                WHERE user_id = ?
            ''', (invited_by,))
            # منح مكافأة للمدعِي
            self.update_balance(invited_by, 500, 'invite_reward', 'مكافأة لدعوة مستخدم جديد')
        
        self.conn.commit()
        return self.get_user(user.id)
    
    def update_balance(self, user_id: int, amount: int, trans_type: str, description: str):
        self.cursor.execute('''
            UPDATE users SET balance = balance + ? WHERE user_id = ?
        ''', (amount, user_id))
        
        self.cursor.execute('''
            INSERT INTO transactions (user_id, amount, transaction_type, description)
            VALUES (?, ?, ?, ?)
        ''', (user_id, amount, trans_type, description))
        
        if amount < 0:
            self.cursor.execute('''
                UPDATE users SET total_spent = total_spent + ? WHERE user_id = ?
            ''', (abs(amount), user_id))
        
        self.conn.commit()
    
    def get_setting(self, key: str) -> str:
        self.cursor.execute('SELECT value FROM bot_settings WHERE key = ?', (key,))
        result = self.cursor.fetchone()
        return result[0] if result else None
    
    def update_setting(self, key: str, value: str):
        self.cursor.execute('''
            INSERT OR REPLACE INTO bot_settings (key, value)
            VALUES (?, ?)
        ''', (key, value))
        self.conn.commit()
    
    def get_service_price(self, service_name: str) -> int:
        self.cursor.execute('SELECT price FROM services WHERE name = ?', (service_name,))
        result = self.cursor.fetchone()
        return int(result[0]) if result else 1000
    
    def update_service_price(self, service_name: str, price: int):
        self.cursor.execute('UPDATE services SET price = ? WHERE name = ?', (price, service_name))
        self.conn.commit()
    
    def toggle_service(self, service_name: str, status: int):
        self.cursor.execute('UPDATE services SET is_active = ? WHERE name = ?', (status, service_name))
        self.conn.commit()
    
    def get_active_services(self, category: str = None) -> List:
        if category:
            self.cursor.execute('SELECT * FROM services WHERE is_active = 1 AND category = ?', (category,))
        else:
            self.cursor.execute('SELECT * FROM services WHERE is_active = 1')
        return self.cursor.fetchall()
    
    def get_all_users(self, limit: int = None) -> List:
        if limit:
            self.cursor.execute('SELECT * FROM users ORDER BY joined_date DESC LIMIT ?', (limit,))
        else:
            self.cursor.execute('SELECT * FROM users ORDER BY joined_date DESC')
        return self.cursor.fetchall()
    
    def get_vip_users(self):
        self.cursor.execute('''
            SELECT * FROM users 
            WHERE is_vip = 1 AND vip_expiry > datetime('now')
            ORDER BY vip_expiry DESC
        ''')
        return self.cursor.fetchall()
    
    def get_user_transactions(self, user_id: int, limit: int = 10):
        self.cursor.execute('''
            SELECT * FROM transactions 
            WHERE user_id = ? 
            ORDER BY date DESC 
            LIMIT ?
        ''', (user_id, limit))
        return self.cursor.fetchall()
    
    def add_study_material(self, name: str, description: str, stage: str, file_id: str, added_by: int):
        self.cursor.execute('''
            INSERT INTO study_materials (name, description, stage, file_id, added_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, description, stage, file_id, added_by))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_study_materials(self, stage: str = None):
        if stage:
            self.cursor.execute('SELECT * FROM study_materials WHERE stage = ? AND is_active = 1', (stage,))
        else:
            self.cursor.execute('SELECT * FROM study_materials WHERE is_active = 1')
        return self.cursor.fetchall()
    
    def add_vip_lecture(self, teacher_id: int, title: str, description: str, file_id: str, file_type: str, price: int):
        self.cursor.execute('''
            INSERT INTO vip_lectures (teacher_id, title, description, file_id, file_type, price)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (teacher_id, title, description, file_id, file_type, price))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_vip_lectures(self, approved: bool = True, teacher_id: int = None):
        if teacher_id:
            self.cursor.execute('''
                SELECT * FROM vip_lectures 
                WHERE teacher_id = ? AND approved = ? AND is_active = 1
                ORDER BY added_date DESC
            ''', (teacher_id, 1 if approved else 0))
        else:
            self.cursor.execute('''
                SELECT * FROM vip_lectures 
                WHERE approved = ? AND is_active = 1
                ORDER BY added_date DESC
            ''', (1 if approved else 0))
        return self.cursor.fetchall()
    
    def get_vip_lecture(self, lecture_id: int):
        self.cursor.execute('SELECT * FROM vip_lectures WHERE id = ?', (lecture_id,))
        cols = [col[0] for col in self.cursor.description]
        row = self.cursor.fetchone()
        if row:
            return dict(zip(cols, row))
        return None
    
    def purchase_vip_lecture(self, user_id: int, lecture_id: int):
        lecture = self.get_vip_lecture(lecture_id)
        if not lecture:
            return False
        
        # تسجيل الشراء
        self.cursor.execute('''
            INSERT INTO vip_purchases (user_id, lecture_id, amount_paid)
            VALUES (?, ?, ?)
        ''', (user_id, lecture_id, lecture['price']))
        
        # تحديث إحصائيات المحاضرة
        self.cursor.execute('''
            UPDATE vip_lectures 
            SET purchases = purchases + 1 
            WHERE id = ?
        ''', (lecture_id,))
        
        # حساب الأرباح
        teacher_percentage = int(self.get_setting('teacher_percentage'))
        admin_percentage = int(self.get_setting('admin_percentage'))
        
        teacher_earning = int(lecture['price'] * teacher_percentage / 100)
        admin_earning = lecture['price'] - teacher_earning
        
        # إضافة أرباح المعلم
        self.cursor.execute('''
            INSERT INTO teacher_earnings (teacher_id, lecture_id, amount, status)
            VALUES (?, ?, ?, 'pending')
        ''', (lecture['teacher_id'], lecture_id, teacher_earning))
        
        # إضافة ربح الإدارة
        self.cursor.execute('''
            INSERT INTO teacher_earnings (teacher_id, lecture_id, amount, status)
            VALUES (?, ?, ?, 'admin_earning')
        ''', (0, lecture_id, admin_earning))
        
        self.conn.commit()
        return True
    
    def get_lecture_earnings(self, teacher_id: int, status: str = 'pending'):
        self.cursor.execute('''
            SELECT COALESCE(SUM(amount), 0) FROM teacher_earnings 
            WHERE teacher_id = ? AND status = ?
        ''', (teacher_id, status))
        result = self.cursor.fetchone()
        return int(result[0]) if result else 0
    
    def update_earnings_status(self, teacher_id: int, amount: int):
        # تحديث حالة الأرباح للسحب
        self.cursor.execute('''
            UPDATE teacher_earnings 
            SET status = 'withdrawn' 
            WHERE teacher_id = ? AND status = 'pending' 
            AND amount <= ?
        ''', (teacher_id, amount))
        
        self.cursor.execute('''
            INSERT INTO teacher_earnings (teacher_id, amount, status)
            VALUES (?, ?, 'withdrawn')
        ''', (teacher_id, -amount,))
        
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    def add_student_question(self, user_id: int, question: str, subject: str = ''):
        self.cursor.execute('''
            INSERT INTO student_questions (user_id, question, subject)
            VALUES (?, ?, ?)
        ''', (user_id, question, subject))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_pending_questions(self):
        self.cursor.execute('''
            SELECT sq.*, u.username, u.first_name 
            FROM student_questions sq
            JOIN users u ON sq.user_id = u.user_id
            WHERE sq.status = 'pending'
            ORDER BY sq.date ASC
        ''')
        return self.cursor.fetchall()
    
    def get_answered_questions(self):
        self.cursor.execute('''
            SELECT sq.*, u.username as asker_username, 
                   u2.username as answerer_username, u2.first_name as answerer_name
            FROM student_questions sq
            JOIN users u ON sq.user_id = u.user_id
            LEFT JOIN users u2 ON sq.answered_by = u2.user_id
            WHERE sq.status = 'answered'
            ORDER BY sq.answer_date DESC
            LIMIT 20
        ''')
        return self.cursor.fetchall()
    
    def answer_question(self, question_id: int, answer: str, answered_by: int):
        reward = int(self.get_setting('question_reward'))
        
        # تحديث السؤال
        self.cursor.execute('''
            UPDATE student_questions 
            SET answer = ?, answered_by = ?, answer_date = datetime('now'), status = 'answered'
            WHERE id = ?
        ''', (answer, answered_by, question_id))
        
        # منح المكافأة للمجيب
        self.update_balance(answered_by, reward, 'question_reward', f'مكافأة إجابة على سؤال #{question_id}')
        
        # تحديث السؤال بأن المكافأة دفعت
        self.cursor.execute('''
            UPDATE student_questions SET reward_paid = 1 WHERE id = ?
        ''', (question_id,))
        
        self.conn.commit()

# ============== تهيئة قاعدة البيانات ==============
db = Database()

# ============== وظائف مساعدة ==============
def format_arabic(text: str) -> str:
    """تهيئة النص العربي للعرض بشكل صحيح"""
    try:
        reshaped_text = arabic_reshaper.reshape(text)
        return get_display(reshaped_text)
    except:
        return text

def format_number(number: int) -> str:
    """تنسيق الأرقام بفواصل"""
    return f"{number:,}"

async def send_message(user_id: int, text: str, context: ContextTypes.DEFAULT_TYPE, 
                      reply_markup: InlineKeyboardMarkup = None, 
                      parse_mode: ParseMode = ParseMode.HTML):
    """إرسال رسالة مع معالجة الأخطاء"""
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=True
        )
        return True
    except Exception as e:
        logging.error(f"Error sending message to {user_id}: {e}")
        return False

async def is_admin(user_id: int) -> bool:
    """التحقق مما إذا كان المستخدم أدمن"""
    if user_id == DEVELOPER_ID:
        return True
    
    user = db.get_user(user_id)
    return user and user.get('is_admin', 0) == 1

async def check_balance(user_id: int, service_name: str) -> Tuple[bool, int, str]:
    """فحص رصيد المستخدم وتكلفة الخدمة"""
    user = db.get_user(user_id)
    price = db.get_service_price(service_name)
    
    if not user:
        return False, price, "المستخدم غير موجود"
    
    if user['is_banned'] == 1:
        return False, price, "حسابك محظور. الرجاء التواصل مع الدعم."
    
    if user['balance'] >= price:
        return True, price, ""
    return False, price, f"رصيدك غير كافي. السعر: {format_number(price)} دينار"

async def deduct_balance(user_id: int, service_name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """خصم تكلفة الخدمة من رصيد المستخدم"""
    user = db.get_user(user_id)
    price = db.get_service_price(service_name)
    
    if user and user['balance'] >= price:
        db.update_balance(user_id, -price, 'service_payment', f'دفع مقابل خدمة {service_name}')
        
        # إرسال إشعار بالدفع
        notification = f"""
💳 <b>تم خصم مبلغ من حسابك</b>
━━━━━━━━━━━━━━
💰 المبلغ: <code>{format_number(price)} دينار</code>
📝 السبب: خدمة {service_name}
📊 الرصيد الجديد: <code>{format_number(user['balance'] - price)} دينار</code>
        """
        await send_message(user_id, notification, context)
        return True
    
    return False

def create_arabic_pdf(text: str, filename: str = "ملخص.pdf"):
    """إنشاء ملف PDF مع دعم اللغة العربية"""
    temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    
    c = canvas.Canvas(temp_file.name, pagesize=A4)
    width, height = A4
    
    # إعداد الخط العربي
    try:
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfbase import pdfmetrics
        
        # محاولة تحميل خط عربي
        arabic_font_paths = [
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
            'arial.ttf'
        ]
        
        arabic_font = 'Helvetica'
        for font_path in arabic_font_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont('Arabic', font_path))
                    arabic_font = 'Arabic'
                    break
                except:
                    pass
    except:
        arabic_font = 'Helvetica'
    
    # كتابة العنوان
    c.setFont(arabic_font, 16)
    title = "ملخص المادة"
    title_width = c.stringWidth(title, arabic_font, 16)
    c.drawString((width - title_width) / 2, height - 50, title)
    
    # كتابة النص
    c.setFont(arabic_font, 12)
    y = height - 100
    margin = 50
    
    lines = text.split('\n')
    for line in lines:
        if not line.strip():
            y -= 20
            continue
        
        # تقسيم الخط الطويل
        if len(line) > 80:
            words = line.split()
            current_line = []
            current_length = 0
            
            for word in words:
                if current_length + len(word) + 1 <= 80:
                    current_line.append(word)
                    current_length += len(word) + 1
                else:
                    if current_line:
                        text_line = ' '.join(current_line)
                        c.drawString(margin, y, format_arabic(text_line))
                        y -= 20
                    
                    current_line = [word]
                    current_length = len(word)
                
                if y < 50:
                    c.showPage()
                    c.setFont(arabic_font, 12)
                    y = height - 50
                    
            if current_line:
                text_line = ' '.join(current_line)
                c.drawString(margin, y, format_arabic(text_line))
                y -= 20
        else:
            c.drawString(margin, y, format_arabic(line))
            y -= 20
        
        if y < 50:
            c.showPage()
            c.setFont(arabic_font, 12)
            y = height - 50
    
    c.save()
    return temp_file.name

# ============== الواجهة الرئيسية ==============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء البوت والترحيب بالمستخدم"""
    user = update.effective_user
    
    # التحقق من وضع الصيانة
    if db.get_setting('maintenance_mode') == '1' and not await is_admin(user.id):
        maintenance_msg = """
🔧 <b>البوت قيد الصيانة</b>
━━━━━━━━━━━━━━
البوت حالياً تحت الصيانة والتطوير.
الرجاء المحاولة لاحقاً.
        
📞 للدعم: {}
        """.format(db.get_setting('support_username') or DEVELOPER_USERNAME)
        
        await update.message.reply_text(maintenance_msg, parse_mode=ParseMode.HTML)
        return
    
    # إنشاء المستخدم إذا لم يكن موجوداً
    user_data = db.get_user(user.id)
    if not user_data:
        invite_code = None
        invited_by = None
        
        if context.args:
            invite_code = context.args[0]
            # البحث عن المستخدم الذي دعاه
            db.cursor.execute('SELECT user_id FROM users WHERE invite_code = ?', (invite_code,))
            inviter = db.cursor.fetchone()
            if inviter:
                invited_by = inviter[0]
        
        user_data = db.create_user(user, invite_code, invited_by)
    
    # منح الهدية الترحيبية
    welcome_bonus = 1000
    if not user_data.get('free_trial_used', 0) and user_data['balance'] < welcome_bonus:
        db.update_balance(user.id, welcome_bonus, 'welcome_bonus', 'هدية ترحيبية')
        db.cursor.execute('UPDATE users SET free_trial_used = 1 WHERE user_id = ?', (user.id,))
        db.conn.commit()
        user_data = db.get_user(user.id)
    
    await show_main_menu(update, context, user_data)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_data: Dict = None):
    """عرض القائمة الرئيسية"""
    if isinstance(update, Update) and update.callback_query:
        query = update.callback_query
        user = query.from_user
        await query.answer()
    else:
        user = update.effective_user
    
    if not user_data:
        user_data = db.get_user(user.id)
    
    # الحصول على الخدمات النشطة
    active_services = db.get_active_services('main')
    
    keyboard = []
    
    # إضافة الخدمات النشطة
    for service in active_services:
        service_dict = dict(zip(['id', 'name', 'display_name', 'price', 'is_active', 'category'], service))
        if service_dict['name'] != 'study_materials':  # سيتم إضافته لاحقاً
            keyboard.append([InlineKeyboardButton(
                f"{service_dict['display_name']} - {format_number(service_dict['price'])} دينار",
                callback_data=f'service_{service_dict["name"]}'
            )])
    
    # إضافة خدمات الدراسة
    keyboard.append([InlineKeyboardButton("📚 ملازمي ومرشحاتي", callback_data='service_study_materials')])
    keyboard.append([InlineKeyboardButton("👑 محاضرات VIP", callback_data='vip_lectures')])
    
    # إضافة أزرار المساعدة والرصيد
    keyboard.append([
        InlineKeyboardButton("💳 رصيدي", callback_data='my_balance'),
        InlineKeyboardButton("👥 دعوة أصدقاء", callback_data='invite_friends')
    ])
    
    keyboard.append([
        InlineKeyboardButton("📊 إحصائياتي", callback_data='my_stats'),
        InlineKeyboardButton("ℹ️ المساعدة", callback_data='help')
    ])
    
    # إضافة زر رفع محاضرة VIP إذا كان مشتركاً
    if user_data.get('is_vip') and user_data.get('vip_expiry'):
        expiry_date = datetime.strptime(user_data['vip_expiry'], '%Y-%m-%d %H:%M:%S')
        if expiry_date > datetime.now():
            keyboard.insert(4, [InlineKeyboardButton("👨‍🏫 رفع محاضرة VIP", callback_data='upload_vip_lecture')])
    
    # إضافة لوحة التحكم للأدمن
    if await is_admin(user.id):
        keyboard.append([InlineKeyboardButton("⚙️ لوحة التحكم", callback_data='admin_panel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = f"""
🎉 <b>مرحباً {user.first_name}!</b>
━━━━━━━━━━━━━━
<b>👤 معلومات حسابك:</b>
💰 الرصيد: <code>{format_number(user_data['balance'])} دينار</code>
👥 عدد الدعوات: <code>{user_data['invited_count']}</code>
📅 تاريخ الانضمام: {user_data['joined_date'][:10]}
    """
    
    # إضافة حالة VIP إذا كان مشتركاً
    if user_data.get('is_vip') and user_data.get('vip_expiry'):
        expiry = datetime.strptime(user_data['vip_expiry'], '%Y-%m-%d %H:%M:%S')
        if expiry > datetime.now():
            days_left = (expiry - datetime.now()).days
            welcome_message += f"\n👑 حالة VIP: <b>مفعل</b> ({days_left} يوم متبقي)"
        else:
            welcome_message += f"\n👑 حالة VIP: <b>منتهي</b>"
    
    welcome_message += f"""

📚 <b>الخدمات المتاحة:</b>
• حساب درجة الإعفاء
• تلخيص الملازم بالذكاء الاصطناعي
• سؤال وجواب لأي مادة
• مساعدة الطلاب والإجابة على أسئلتهم
• ملازم ومرشحات متنوعة
• محاضرات VIP حصرية
    """
    
    if isinstance(update, Update) and update.callback_query:
        await update.callback_query.edit_message_text(
            welcome_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            welcome_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

# ============== خدمات البوت ==============
async def handle_service_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار الخدمة"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == 'service_exemption_calculator':
        await exemption_calculator_service(update, context)
    elif data == 'service_pdf_summary':
        await pdf_summary_service(update, context)
    elif data == 'service_qna':
        await qna_service(update, context)
    elif data == 'service_help_student':
        await help_student_service(update, context)
    elif data == 'service_study_materials':
        await study_materials_service(update, context)
    else:
        await query.edit_message_text("⏳ هذه الخدمة قيد التطوير...")

async def exemption_calculator_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خدمة حساب درجة الإعفاء"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # التحقق من الرصيد
    can_use, price, message = await check_balance(user_id, 'exemption_calculator')
    
    if not can_use:
        await query.edit_message_text(
            f"❌ <b>لا يمكن استخدام الخدمة</b>\n"
            f"━━━━━━━━━━━━━━\n{message}\n\n"
            f"💰 سعر الخدمة: <code>{format_number(price)} دينار</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    # خصم المبلغ
    if await deduct_balance(user_id, 'exemption_calculator', context):
        instruction = """
🧮 <b>حساب درجة الإعفاء</b>
━━━━━━━━━━━━━━
<code>أدخل درجات الكورسات الثلاثة (من 100)</code>

<b>📝 مثال:</b>
<blockquote>90
85
95</blockquote>

<b>⚠️ ملاحظة:</b>
• يجب أن يكون المعدل 90 أو أكثر للإعفاء
• أدخل الأرقام فقط، كل درجة في سطر
        """
        
        await query.edit_message_text(instruction, parse_mode=ParseMode.HTML)
        
        context.user_data['waiting_for_grades'] = True
        return WAITING_FOR_GRADES

async def handle_grades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة درجات الإعفاء المدخلة"""
    if not context.user_data.get('waiting_for_grades'):
        return ConversationHandler.END
    
    text = update.message.text.strip()
    grades = []
    
    # استخراج الدرجات من النص
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if line:
            # استخراج الأرقام من السطر
            numbers = re.findall(r'\d+(?:\.\d+)?', line)
            if numbers:
                try:
                    grade = float(numbers[0])
                    if 0 <= grade <= 100:
                        grades.append(grade)
                except ValueError:
                    continue
    
    if len(grades) < 3:
        await update.message.reply_text(
            "❌ <b>الرجاء إدخال 3 درجات صحيحة</b>\n"
            "مثال:\n<code>90\n85\n95</code>",
            parse_mode=ParseMode.HTML
        )
        return WAITING_FOR_GRADES
    
    # أخذ أول 3 درجات
    grades = grades[:3]
    
    # حساب المعدل
    average = sum(grades) / 3
    
    if average >= 90:
        result = f"""
🎉 <b>مبروك! أنت معفي من المادة</b>
━━━━━━━━━━━━━━
📊 <b>الدرجات:</b>
الكورس الأول: <code>{grades[0]}</code>
الكورس الثاني: <code>{grades[1]}</code>
الكورس الثالث: <code>{grades[2]}</code>

📈 <b>المعدل:</b> <code>{average:.2f}</code>
✅ <b>الحالة:</b> <b>معفي</b> 🎊

🏆 تهانينا! لقد حققت المعدل المطلوب للإعفاء.
        """
    else:
        result = f"""
😔 <b>أنت غير معفي من المادة</b>
━━━━━━━━━━━━━━
📊 <b>الدرجات:</b>
الكورس الأول: <code>{grades[0]}</code>
الكورس الثاني: <code>{grades[1]}</code>
الكورس الثالث: <code>{grades[2]}</code>

📈 <b>المعدل:</b> <code>{average:.2f}</code>
❌ <b>الحالة:</b> <b>غير معفي</b>

💡 <b>نصيحة:</b>
• ركز على المادة وحاول تحسين درجاتك
• المعدل المطلوب للإعفاء هو 90
• تحتاج إلى تحسين بمقدار <code>{90 - average:.2f}</code> نقطة
        """
    
    keyboard = [
        [InlineKeyboardButton("🔙 العودة للرئيسية", callback_data='back_to_main')]
    ]
    
    await update.message.reply_text(
        result,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    
    context.user_data['waiting_for_grades'] = False
    return ConversationHandler.END

async def pdf_summary_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خدمة تلخيص الملازم"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # التحقق من الرصيد
    can_use, price, message = await check_balance(user_id, 'pdf_summary')
    
    if not can_use:
        await query.edit_message_text(
            f"❌ <b>لا يمكن استخدام الخدمة</b>\n"
            f"━━━━━━━━━━━━━━\n{message}\n\n"
            f"💰 سعر الخدمة: <code>{format_number(price)} دينار</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    # خصم المبلغ
    if await deduct_balance(user_id, 'pdf_summary', context):
        instruction = """
📚 <b>تلخيص الملازم</b>
━━━━━━━━━━━━━━
<code>أرسل ملف PDF ليتم تلخيصه</code>

<b>📋 الشروط:</b>
• الملف يجب أن يكون بصيغة PDF فقط
• الحد الأقصى للحجم: 20MB
• يجب أن يحتوي على نص قابل للقراءة
• النصوص العربية مدعومة بالكامل

<b>⚡ المميزات:</b>
• تلخيص ذكي باستخدام الذكاء الاصطناعي
• استخراج النقاط الرئيسية
• تنظيم المعلومات بشكل منهجي
• ملف PDF جديد بجودة عالية
        """
        
        await query.edit_message_text(instruction, parse_mode=ParseMode.HTML)
        
        context.user_data['waiting_for_pdf'] = True
        return WAITING_FOR_PDF

async def handle_pdf_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة ملف PDF"""
    if not context.user_data.get('waiting_for_pdf'):
        return ConversationHandler.END
    
    user_id = update.message.from_user.id
    
    if not update.message.document:
        await update.message.reply_text("❌ الرجاء إرسال ملف PDF فقط")
        return WAITING_FOR_PDF
    
    document = update.message.document
    if not document.file_name or not document.file_name.lower().endswith('.pdf'):
        await update.message.reply_text("❌ الملف يجب أن يكون بصيغة PDF")
        return WAITING_FOR_PDF
    
    # إشعار ببدء المعالجة
    processing_msg = await update.message.reply_text("⏳ جاري معالجة الملف وتلخيصه...")
    
    try:
        # تحميل الملف
        temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        file = await document.get_file()
        await file.download_to_drive(temp_file.name)
        
        # استخراج النصوص من PDF
        doc = fitz.open(temp_file.name)
        text = ""
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text += page.get_text()
        
        doc.close()
        
        if not text.strip():
            await processing_msg.edit_text("❌ لم أتمكن من استخراج النصوص من الملف")
            os.unlink(temp_file.name)
            return WAITING_FOR_PDF
        
        # تقليل حجم النص إذا كان كبيراً
        if len(text) > 10000:
            text = text[:10000] + "..."
        
        # استخدام الذكاء الاصطناعي للتلخيص
        prompt = f"""
        قم بتلخيص النص التعليمي التالي بشكل احترافي مع التركيز على:
        1. النقاط الرئيسية والمفاهيم الأساسية
        2. التعاريف المهمة
        3. القوانين والمعادلات إذا وجدت
        4. الأمثلة التوضيحية المهمة
        
        النص:
        {text}
        
        التلخيص يجب أن يكون:
        - باللغة العربية الفصحى
        - منظم مع عناوين فرعية
        - شامل للنقاط المهمة
        - مناسب للطلاب والمراجعة
        - بطول مناسب (حوالي 500-1000 كلمة)
        
        ابدأ التلخيص مباشرة.
        """
        
        response = model.generate_content(prompt)
        summary = response.text if response else "عذراً، لم أتمكن من تلخيص النص حالياً."
        
        # إنشاء ملف PDF جديد
        pdf_path = create_arabic_pdf(summary)
        
        # إرسال الملف للمستخدم
        with open(pdf_path, 'rb') as f:
            await update.message.reply_document(
                document=InputFile(f, filename=f"ملخص_{document.file_name}"),
                caption="✅ <b>تم تلخيص الملف بنجاح</b>\n"
                       "📄 هذا الملف يحتوي على الملخص المنظم للمادة\n\n"
                       f"📝 <b>ملاحظة:</b> تم دفع <code>{format_number(db.get_service_price('pdf_summary'))}</code> دينار مقابل هذه الخدمة",
                parse_mode=ParseMode.HTML
            )
        
        await processing_msg.delete()
        
        # تنظيف الملفات المؤقتة
        os.unlink(temp_file.name)
        os.unlink(pdf_path)
        
    except Exception as e:
        logging.error(f"PDF processing error: {e}")
        await processing_msg.edit_text("❌ حدث خطأ في معالجة الملف. الرجاء المحاولة مرة أخرى.")
    
    context.user_data['waiting_for_pdf'] = False
    
    keyboard = [[InlineKeyboardButton("🔙 العودة للرئيسية", callback_data='back_to_main')]]
    await update.message.reply_text(
        "✨ <b>تم الانتهاء من الخدمة بنجاح!</b>\n"
        "يمكنك العودة للقائمة الرئيسية لاستخدام خدمات أخرى.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    
    return ConversationHandler.END

async def qna_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خدمة سؤال وجواب"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # التحقق من الرصيد
    can_use, price, message = await check_balance(user_id, 'qna')
    
    if not can_use:
        await query.edit_message_text(
            f"❌ <b>لا يمكن استخدام الخدمة</b>\n"
            f"━━━━━━━━━━━━━━\n{message}\n\n"
            f"💰 سعر الخدمة: <code>{format_number(price)} دينار</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    # خصم المبلغ
    if await deduct_balance(user_id, 'qna', context):
        instruction = """
❓ <b>سؤال وجواب بالذكاء الاصطناعي</b>
━━━━━━━━━━━━━━
<code>أرسل سؤالك في أي مادة دراسية</code>

<b>📚 التخصصات المدعومة:</b>
• الرياضيات والعلوم
• الفيزياء والكيمياء
• اللغة العربية والإنجليزية
• التاريخ والجغرافيا
• العلوم الإسلامية
• جميع المواد الدراسية العراقية

<b>✨ المميزات:</b>
• إجابات دقيقة وعلمية
• مراعاة المنهج العراقي
• شرح مفصل ومبسط
• أمثلة توضيحية
• مراجع علمية
        """
        
        await query.edit_message_text(instruction, parse_mode=ParseMode.HTML)
        
        context.user_data['waiting_for_question'] = True
        return WAITING_FOR_QUESTION

async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأسئلة بالإجابة الذكية"""
    if not context.user_data.get('waiting_for_question'):
        return ConversationHandler.END
    
    user_id = update.message.from_user.id
    question = ""
    
    if update.message.text:
        question = update.message.text
    elif update.message.caption:
        question = update.message.caption
    
    if not question.strip():
        await update.message.reply_text("❌ الرجاء إدخال سؤال واضح")
        return WAITING_FOR_QUESTION
    
    if len(question) < 5:
        await update.message.reply_text("❌ السؤال قصير جداً. الرجاء كتابة سؤال مفصل.")
        return WAITING_FOR_QUESTION
    
    processing_msg = await update.message.reply_text("🤔 جاري البحث عن الإجابة...")
    
    try:
        # استخدام Gemini للإجابة
        prompt = f"""
        أنت مساعد تعليمي متخصص في المنهج العراقي.
        أجب على السؤال التالي بدقة ووضوح:
        
        السؤال: {question}
        
        اشتراطات الإجابة:
        1. كن دقيقاً وعلمياً
        2. استخدم اللغة العربية الفصحى
        3. ركز على المنهج العراقي
        4. قدم شرحاً مفصلاً إذا لزم الأمر
        5. أذكر القوانين أو المعادلات إذا كانت موجودة
        6. قدم أمثلة توضيحية
        7. إذا كان السؤال يحتاج إلى خطوات حل، قدمها
        8. ختم بإجابة واضحة ومباشرة
        
        إذا كان السؤال خارج نطاق التعليمي، قل ذلك بأدب.
        """
        
        response = model.generate_content(prompt)
        answer = response.text if response else """
        عذراً، لم أتمكن من معالجة سؤالك حالياً.
        الرجاء:
        1. التأكد من أن السؤال واضح
        2. إعادة صياغة السؤال
        3. المحاولة مرة أخرى
        """
        
        # تنسيق الإجابة
        formatted_answer = f"""
🧠 <b>إجابة على سؤالك:</b>
━━━━━━━━━━━━━━
<b>❓ السؤال:</b>
{question}

<b>💡 الإجابة:</b>
{answer}

<b>📚 ملاحظة:</b>
• هذه الإجابة مبنية على المنهج التعليمي العراقي
• تم إنشاؤها باستخدام الذكاء الاصطناعي
• للاستفسارات الإضافية، يمكنك استخدام الخدمة مرة أخرى
        """
        
        await update.message.reply_text(formatted_answer, parse_mode=ParseMode.HTML)
        await processing_msg.delete()
        
    except Exception as e:
        logging.error(f"Q&A error: {e}")
        await processing_msg.edit_text("❌ حدث خطأ في معالجة السؤال. الرجاء المحاولة مرة أخرى.")
    
    context.user_data['waiting_for_question'] = False
    
    keyboard = [[InlineKeyboardButton("🔙 العودة للرئيسية", callback_data='back_to_main')]]
    await update.message.reply_text(
        "✅ <b>تمت الإجابة على سؤالك</b>\n"
        "يمكنك العودة للقائمة الرئيسية لاستخدام خدمات أخرى.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    
    return ConversationHandler.END

async def help_student_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خدمة ساعدوني طالب"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # التحقق من الرصيد
    can_use, price, message = await check_balance(user_id, 'help_student')
    
    if not can_use:
        await query.edit_message_text(
            f"❌ <b>لا يمكن استخدام الخدمة</b>\n"
            f"━━━━━━━━━━━━━━\n{message}\n\n"
            f"💰 سعر الخدمة: <code>{format_number(price)} دينار</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    # عرض الأسئلة المتاحة للإجابة
    pending_questions = db.get_pending_questions()
    
    if pending_questions:
        # عرض قائمة الأسئلة المتاحة
        questions_text = "🙋‍♂️ <b>الأسئلة المتاحة للإجابة</b>\n━━━━━━━━━━━━━━\n"
        
        keyboard = []
        for i, q in enumerate(pending_questions[:10], 1):
            q_dict = dict(zip(['id', 'user_id', 'question', 'subject', 'status', 'date', 
                              'answer', 'answered_by', 'answer_date', 'reward_paid',
                              'username', 'first_name'], q))
            question_preview = q_dict['question'][:50] + "..." if len(q_dict['question']) > 50 else q_dict['question']
            questions_text += f"\n{i}. {question_preview}"
            keyboard.append([InlineKeyboardButton(
                f"سؤال #{q_dict['id']} - {q_dict['first_name']}",
                callback_data=f'answer_question_{q_dict["id"]}'
            )])
        
        keyboard.append([InlineKeyboardButton("➕ طرح سؤال جديد", callback_data='ask_new_question')])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='back_to_main')])
        
        await query.edit_message_text(
            questions_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    else:
        # لا توجد أسئلة، عرض خيار طرح سؤال جديد
        instruction = """
🙋‍♂️ <b>ساعدوني طالب</b>
━━━━━━━━━━━━━━
لا توجد أسئلة متاحة للإجابة حالياً.

<b>💡 يمكنك:</b>
1. طرح سؤال جديد
2. العودة لاحقاً
3. مشاركة البوت مع زملائك

<b>🎁 مكافأة:</b>
كل إجابة صحيحة تحصل على <code>100 دينار</code> مكافأة!
        """
        
        keyboard = [
            [InlineKeyboardButton("➕ طرح سؤال جديد", callback_data='ask_new_question')],
            [InlineKeyboardButton("🔙 رجوع", callback_data='back_to_main')]
        ]
        
        await query.edit_message_text(
            instruction,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )

async def ask_new_question_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة طلب طرح سؤال جديد"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # التحقق من الرصيد
    can_use, price, message = await check_balance(user_id, 'help_student')
    
    if not can_use:
        await query.answer(f"❌ {message}", show_alert=True)
        return
    
    # خصم المبلغ
    if await deduct_balance(user_id, 'help_student', context):
        instruction = """
❓ <b>طرح سؤال جديد</b>
━━━━━━━━━━━━━━
<code>أرسل سؤالك الآن</code>

<b>📝 إرشادات:</b>
• اكتب سؤالك بوضوح
• حدد المادة إذا أمكن
• يمكنك إرفاق صورة إذا لزم الأمر
• السؤال سينشر للطلاب الآخرين للإجابة

<b>💰 تم خصم:</b> <code>{}</code> دينار
<b>🎁 مكافأة المجيب:</b> <code>100</code> دينار
        """.format(format_number(price))
        
        await query.edit_message_text(instruction, parse_mode=ParseMode.HTML)
        
        context.user_data['waiting_for_student_question'] = True
        return WAITING_FOR_STUDENT_QUESTION

async def handle_new_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة السؤال الجديد"""
    if not context.user_data.get('waiting_for_student_question'):
        return ConversationHandler.END
    
    user_id = update.message.from_user.id
    question_text = ""
    has_photo = False
    
    if update.message.text:
        question_text = update.message.text
    elif update.message.caption:
        question_text = update.message.caption
        if update.message.photo:
            has_photo = True
    
    if not question_text.strip():
        await update.message.reply_text("❌ الرجاء كتابة سؤال واضح")
        return WAITING_FOR_STUDENT_QUESTION
    
    # حفظ السؤال في قاعدة البيانات
    question_id = db.add_student_question(user_id, question_text)
    
    # إعداد الرسالة للموافقة
    question_message = f"""
❓ <b>سؤال جديد يحتاج موافقة</b>
━━━━━━━━━━━━━━
<b>🆔 رقم السؤال:</b> {question_id}
<b>👤 الطالب:</b> {update.message.from_user.mention_html()}
<b>🆔 الايدي:</b> <code>{user_id}</code>
<b>⏰ الوقت:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

<b>📝 السؤال:</b>
{question_text}
    """
    
    keyboard = [
        [
            InlineKeyboardButton("✅ الموافقة", callback_data=f'admin_approve_question_{question_id}'),
            InlineKeyboardButton("❌ الرفض", callback_data=f'admin_reject_question_{question_id}')
        ]
    ]
    
    # إرسال للإداريين
    admin_ids = db.get_setting('admin_ids')
    if admin_ids:
        for admin_id in admin_ids.split(','):
            try:
                await send_message(int(admin_id.strip()), question_message, context, InlineKeyboardMarkup(keyboard))
            except:
                pass
    
    # إرسال للمطور
    await send_message(DEVELOPER_ID, question_message, context, InlineKeyboardMarkup(keyboard))
    
    await update.message.reply_text(
        "✅ <b>تم استلام سؤالك</b>\n"
        "━━━━━━━━━━━━━━\n"
        "سؤالك قيد المراجعة من قبل الإدارة.\n"
        "سيتم نشره قريباً للإجابة عليه.\n\n"
        f"<b>🆔 رقم سؤالك:</b> {question_id}",
        parse_mode=ParseMode.HTML
    )
    
    context.user_data['waiting_for_student_question'] = False
    
    keyboard = [[InlineKeyboardButton("🔙 العودة للرئيسية", callback_data='back_to_main')]]
    await update.message.reply_text(
        "يمكنك متابعة حالة سؤالك من خلال قسم 'ساعدوني طالب'",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return ConversationHandler.END

async def study_materials_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خدمة ملازمي ومرشحاتي"""
    query = update.callback_query
    await query.answer()
    
    # عرض المراحل الدراسية
    keyboard = [
        [InlineKeyboardButton("🏫 الابتدائية", callback_data='stage_primary')],
        [InlineKeyboardButton("🏫 المتوسطة", callback_data='stage_middle')],
        [InlineKeyboardButton("🏫 الإعدادية", callback_data='stage_preparatory')],
        [InlineKeyboardButton("🎓 الجامعية", callback_data='stage_university')],
        [InlineKeyboardButton("➕ إضافة مادة (للمشرفين)", callback_data='add_material_admin')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='back_to_main')]
    ]
    
    await query.edit_message_text(
        "📚 <b>ملازمي ومرشحاتي</b>\n"
        "━━━━━━━━━━━━━━\n"
        "اختر المرحلة الدراسية لعرض المواد المتاحة:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def show_stage_materials(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض مواد مرحلة معينة"""
    query = update.callback_query
    await query.answer()
    
    stage_map = {
        'stage_primary': 'ابتدائية',
        'stage_middle': 'متوسطة',
        'stage_preparatory': 'إعدادية',
        'stage_university': 'جامعية'
    }
    
    stage = stage_map.get(query.data)
    if not stage:
        return
    
    materials = db.get_study_materials(stage)
    
    if not materials:
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='service_study_materials')]]
        await query.edit_message_text(
            f"📭 <b>لا توجد مواد لمرحلة {stage}</b>\n"
            "يمكنك العودة لاحقاً أو اقتراح إضافة مواد.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        return
    
    # عرض المواد
    message = f"📚 <b>مواد مرحلة {stage}</b>\n━━━━━━━━━━━━━━\n"
    
    keyboard = []
    for mat in materials:
        mat_dict = dict(zip(['id', 'name', 'description', 'stage', 'file_id', 
                           'added_by', 'added_date', 'is_active'], mat))
        message += f"\n📖 <b>{mat_dict['name']}</b>\n{mat_dict['description']}\n"
        
        keyboard.append([InlineKeyboardButton(
            f"📥 تحميل {mat_dict['name']}",
            callback_data=f'download_material_{mat_dict["id"]}'
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='service_study_materials')])
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

# ============== نظام VIP المتكامل ==============
async def vip_lectures_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض محاضرات VIP"""
    query = update.callback_query
    await query.answer()
    
    lectures = db.get_vip_lectures(approved=True)
    
    if not lectures:
        keyboard = [
            [InlineKeyboardButton("👑 اشتراك VIP", callback_data='vip_subscription_info')],
            [InlineKeyboardButton("🔙 رجوع", callback_data='back_to_main')]
        ]
        
        await query.edit_message_text(
            "👑 <b>محاضرات VIP</b>\n"
            "━━━━━━━━━━━━━━\n"
            "لا توجد محاضرات VIP متاحة حالياً.\n\n"
            "💡 <b>كن أول من يضيف محاضرات!</b>\n"
            "اشترك في VIP لرفع محاضراتك وكسب الأرباح.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        return
    
    # عرض أول محاضرة
    cols = [col[0] for col in db.cursor.description]
    lecture = dict(zip(cols, lectures[0]))
    
    teacher = db.get_user(lecture['teacher_id'])
    teacher_name = teacher['first_name'] if teacher else "مجهول"
    
    message = f"""
👑 <b>محاضرة VIP</b>
━━━━━━━━━━━━━━
<b>📚 العنوان:</b> {lecture['title']}
<b>👨‍🏫 المعلم:</b> {teacher_name}
<b>📝 الوصف:</b> {lecture['description']}
<b>💰 السعر:</b> {format_number(lecture['price'])} دينار
<b>⭐ التقييم:</b> {lecture['rating']:.1f}/5 ({lecture['rating_count']} تقييم)
<b>👁️ المشاهدات:</b> {format_number(lecture['views'])}
<b>🛒 المشتريات:</b> {format_number(lecture['purchases'])}
    """
    
    keyboard = []
    
    # زر الشراء
    keyboard.append([InlineKeyboardButton("🛒 شراء المحاضرة", callback_data=f'buy_lecture_{lecture["id"]}')])
    
    # أزرار التنقل
    if len(lectures) > 1:
        nav_buttons = []
        if len(lectures) > 1:
            nav_buttons.append(InlineKeyboardButton("التالي →", callback_data='next_lecture_1'))
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("👑 اشتراك VIP", callback_data='vip_subscription_info')])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='back_to_main')])
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    
    # حفظ الفهرس للتنقل
    context.user_data['current_lecture_index'] = 0
    context.user_data['lectures_list'] = lectures

async def vip_subscription_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معلومات اشتراك VIP"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = db.get_user(user_id)
    monthly_price = int(db.get_setting('vip_monthly_price') or 20000)
    
    is_vip = False
    days_left = 0
    if user.get('is_vip') and user.get('vip_expiry'):
        expiry = datetime.strptime(user['vip_expiry'], '%Y-%m-%d %H:%M:%S')
        if expiry > datetime.now():
            is_vip = True
            days_left = (expiry - datetime.now()).days
    
    if is_vip:
        message = f"""
👑 <b>اشتراك VIP - مفعل</b>
━━━━━━━━━━━━━━
<b>✨ المميزات:</b>
• رفع محاضرات VIP غير محدود
• أرباح 60% من مبيعات محاضراتك
• لوحة تحكم خاصة للمعلمين
• سحب الأرباح عند وصولها 15,000 دينار
• أولوية في الدعم الفني
• إحصائيات مفصلة لمحاضراتك

<b>📅 معلومات اشتراكك:</b>
• تاريخ الانتهاء: {expiry.strftime('%Y-%m-%d')}
• الأيام المتبقية: {days_left} يوم
• أرباحك الحالية: {format_number(db.get_lecture_earnings(user_id))} دينار
• عدد محاضراتك: {len(db.get_vip_lectures(teacher_id=user_id))}
        """
        
        keyboard = [
            [InlineKeyboardButton("📤 رفع محاضرة جديدة", callback_data='upload_vip_lecture')],
            [InlineKeyboardButton("📊 إحصائياتي", callback_data='vip_stats')],
            [InlineKeyboardButton("💰 أرباحي وسحب", callback_data='vip_earnings')],
            [InlineKeyboardButton("🔄 تجديد الاشتراك", callback_data=f'renew_vip_{monthly_price}')],
            [InlineKeyboardButton("🔙 رجوع", callback_data='back_to_main')]
        ]
    else:
        message = f"""
👑 <b>اشتراك VIP للمعلمين</b>
━━━━━━━━━━━━━━
<b>✨ المميزات:</b>
• رفع محاضرات VIP غير محدود
• أرباح 60% من مبيعات محاضراتك
• لوحة تحكم خاصة للمعلمين
• سحب الأرباح عند وصولها 15,000 دينار
• أولوية في الدعم الفني
• إحصائيات مفصلة لمحاضراتك

<b>💰 السعر الشهري:</b> {format_number(monthly_price)} دينار

<b>📋 شروط الاشتراك:</b>
1. المحاضرات تخضع للمراجعة والموافقة
2. يجب أن تكون المحاضرات تعليمية وذات جودة
3. يحق للإدارة رفض أو حذف المحاضرات غير المناسبة
4. الأرباح تصل بعد 24 ساعة من عملية البيع
5. الحد الأدنى للسحب: 15,000 دينار

<b>💼 كيف تربح:</b>
لكل محاضرة تشتريها:
• أنت (المعلم): تحصل على 60% من السعر
• الإدارة: تحصل على 40% من السعر
        """
        
        keyboard = [
            [InlineKeyboardButton(f"💳 اشتراك بـ {format_number(monthly_price)} دينار", 
                                 callback_data=f'subscribe_vip_{monthly_price}')],
            [InlineKeyboardButton("👀 عرض محاضرات VIP", callback_data='vip_lectures')],
            [InlineKeyboardButton("🔙 رجوع", callback_data='back_to_main')]
        ]
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def upload_vip_lecture_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء عملية رفع محاضرة VIP"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    # التحقق من اشتراك VIP
    user = db.get_user(user_id)
    if not user.get('is_vip') or not user.get('vip_expiry'):
        await query.answer("❌ تحتاج إلى اشتراك VIP لرفع المحاضرات", show_alert=True)
        return
    
    expiry = datetime.strptime(user['vip_expiry'], '%Y-%m-%d %H:%M:%S')
    if expiry <= datetime.now():
        await query.answer("❌ اشتراك VIP منتهي. الرجاء التجديد", show_alert=True)
        return
    
    instruction = """
📤 <b>رفع محاضرة VIP</b>
━━━━━━━━━━━━━━
<code>الخطوة 1/4: أدخل عنوان المحاضرة</code>

<b>📝 إرشادات:</b>
• العنوان يجب أن يكون واضحاً ومعبراً
• مثال: "شرح الدرس الأول في الفيزياء"
• الحد الأقصى: 100 حرف

<b>أرسل العنوان الآن:</b>
    """
    
    await query.edit_message_text(instruction, parse_mode=ParseMode.HTML)
    return VIP_LECTURE_TITLE

async def handle_vip_lecture_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة عنوان المحاضرة"""
    title = update.message.text.strip()
    
    if len(title) > 100:
        await update.message.reply_text("❌ العنوان طويل جداً. الحد الأقصى 100 حرف")
        return VIP_LECTURE_TITLE
    
    if len(title) < 5:
        await update.message.reply_text("❌ العنوان قصير جداً. الرجاء كتابة عنوان واضح")
        return VIP_LECTURE_TITLE
    
    context.user_data['vip_lecture_title'] = title
    
    instruction = """
📝 <b>رفع محاضرة VIP</b>
━━━━━━━━━━━━━━
<code>الخطوة 2/4: أدخل وصف المحاضرة</code>

<b>📋 إرشادات:</b>
• اكتب وصفاً مفصلاً للمحاضرة
• اذكر المحتويات الرئيسية
• حدد الفئة المستهدفة
• الحد الأقصى: 500 حرف

<b>أرسل الوصف الآن:</b>
    """
    
    await update.message.reply_text(instruction, parse_mode=ParseMode.HTML)
    return VIP_LECTURE_DESC

async def handle_vip_lecture_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة وصف المحاضرة"""
    description = update.message.text.strip()
    
    if len(description) > 500:
        await update.message.reply_text("❌ الوصف طويل جداً. الحد الأقصى 500 حرف")
        return VIP_LECTURE_DESC
    
    if len(description) < 20:
        await update.message.reply_text("❌ الوصف قصير جداً. الرجاء كتابة وصف مفصل")
        return VIP_LECTURE_DESC
    
    context.user_data['vip_lecture_desc'] = description
    
    instruction = """
💰 <b>رفع محاضرة VIP</b>
━━━━━━━━━━━━━━
<code>الخطوة 3/4: حدد سعر المحاضرة</code>

<b>💵 إرشادات:</b>
• السعر بالدينار العراقي
• الحد الأدنى: 1000 دينار
• الحد الأقصى: 50000 دينار
• السعر المناسب: 5000-10000 دينار

<b>📊 تذكر:</b>
• أنت تحصل على 60% من السعر
• الإدارة تحصل على 40%

<b>أرسل السعر الآن (رقم فقط):</b>
    """
    
    await update.message.reply_text(instruction, parse_mode=ParseMode.HTML)
    return VIP_LECTURE_PRICE

async def handle_vip_lecture_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة سعر المحاضرة"""
    try:
        price = int(update.message.text.strip())
        
        if price < 1000:
            await update.message.reply_text("❌ السعر أقل من الحد الأدنى (1000 دينار)")
            return VIP_LECTURE_PRICE
        
        if price > 50000:
            await update.message.reply_text("❌ السعر أعلى من الحد الأقصى (50000 دينار)")
            return VIP_LECTURE_PRICE
        
        context.user_data['vip_lecture_price'] = price
        
        instruction = """
📎 <b>رفع محاضرة VIP</b>
━━━━━━━━━━━━━━
<code>الخطوة 4/4: أرسل ملف المحاضرة</code>

<b>📁 أنواع الملفات المقبولة:</b>
• فيديو (MP4, AVI, MOV)
• مستند (PDF, DOC, DOCX, PPT)
• صورة (JPG, PNG) - كملف مضغوط

<b>📏 الشروط:</b>
• الحد الأقصى: 50MB
• الملف يجب أن يكون تعليمياً
• لا ملفات محمية بحقوق نشر

<b>أرسل الملف الآن:</b>
    """
        
        await update.message.reply_text(instruction, parse_mode=ParseMode.HTML)
        return VIP_LECTURE_FILE
        
    except ValueError:
        await update.message.reply_text("❌ الرجاء إدخال رقم صحيح")
        return VIP_LECTURE_PRICE

async def handle_vip_lecture_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة ملف المحاضرة"""
    user_id = update.message.from_user_id
    
    if not update.message.document and not update.message.video:
        await update.message.reply_text("❌ الرجاء إرسال ملف فيديو أو مستند")
        return VIP_LECTURE_FILE
    
    # تحديد نوع الملف
    file_type = ""
    file_id = ""
    
    if update.message.document:
        file_type = "document"
        file_id = update.message.document.file_id
    elif update.message.video:
        file_type = "video"
        file_id = update.message.video.file_id
    
    # حفظ المحاضرة في قاعدة البيانات
    lecture_id = db.add_vip_lecture(
        teacher_id=user_id,
        title=context.user_data['vip_lecture_title'],
        description=context.user_data['vip_lecture_desc'],
        file_id=file_id,
        file_type=file_type,
        price=context.user_data['vip_lecture_price']
    )
    
    # إعداد رسالة للموافقة
    user = db.get_user(user_id)
    
    approval_msg = f"""
📤 <b>محاضرة VIP جديدة تحتاج موافقة</b>
━━━━━━━━━━━━━━
<b>🆔 رقم المحاضرة:</b> {lecture_id}
<b>👨‍🏫 المعلم:</b> {user['first_name']} (@{user['username'] or 'لا يوجد'})
<b>🆔 الايدي:</b> <code>{user_id}</code>
<b>💰 السعر:</b> {format_number(context.user_data['vip_lecture_price'])} دينار

<b>📚 العنوان:</b>
{context.user_data['vip_lecture_title']}

<b>📝 الوصف:</b>
{context.user_data['vip_lecture_desc']}

<b>📁 نوع الملف:</b> {file_type}
<b>⏰ الوقت:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    
    keyboard = [
        [
            InlineKeyboardButton("✅ الموافقة", callback_data=f'admin_approve_lecture_{lecture_id}'),
            InlineKeyboardButton("❌ الرفض", callback_data=f'admin_reject_lecture_{lecture_id}')
        ],
        [
            InlineKeyboardButton("👁️ معاينة الملف", callback_data=f'admin_preview_lecture_{lecture_id}')
        ]
    ]
    
    # إرسال للإداريين
    admin_ids = db.get_setting('admin_ids')
    if admin_ids:
        for admin_id in admin_ids.split(','):
            try:
                await send_message(int(admin_id.strip()), approval_msg, context, InlineKeyboardMarkup(keyboard))
            except:
                pass
    
    # إرسال للمطور
    await send_message(DEVELOPER_ID, approval_msg, context, InlineKeyboardMarkup(keyboard))
    
    # إشعار للمستخدم
    await update.message.reply_text(
        f"✅ <b>تم رفع المحاضرة بنجاح</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"<b>🆔 رقم المحاضرة:</b> {lecture_id}\n"
        f"<b>📚 العنوان:</b> {context.user_data['vip_lecture_title']}\n\n"
        f"📋 المحاضرة الآن قيد المراجعة من قبل الإدارة.\n"
        f"سيتم إعلامك عند الموافقة عليها.",
        parse_mode=ParseMode.HTML
    )
    
    # تنظيف بيانات المستخدم
    keys_to_remove = ['vip_lecture_title', 'vip_lecture_desc', 'vip_lecture_price']
    for key in keys_to_remove:
        context.user_data.pop(key, None)
    
    keyboard = [[InlineKeyboardButton("🔙 العودة للرئيسية", callback_data='back_to_main')]]
    await update.message.reply_text(
        "يمكنك متابعة حالة المحاضرة من خلال قسم VIP",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return ConversationHandler.END

# ============== لوحة التحكم المتكاملة ==============
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لوحة تحكم المطور"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not await is_admin(user_id):
        await query.answer("⛔ ليس لديك صلاحية الوصول", show_alert=True)
        return
    
    # إحصائيات البوت
    db.cursor.execute('SELECT COUNT(*) FROM users')
    total_users = db.cursor.fetchone()[0]
    
    db.cursor.execute('SELECT COUNT(*) FROM users WHERE is_vip = 1')
    vip_users = db.cursor.fetchone()[0]
    
    db.cursor.execute('SELECT COALESCE(SUM(balance), 0) FROM users')
    total_balance = db.cursor.fetchone()[0]
    
    db.cursor.execute('SELECT COUNT(*) FROM transactions')
    total_transactions = db.cursor.fetchone()[0]
    
    db.cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM teacher_earnings WHERE status = "pending"')
    pending_earnings = db.cursor.fetchone()[0]
    
    maintenance_mode = db.get_setting('maintenance_mode') == '1'
    
    message = f"""
⚙️ <b>لوحة التحكم - الإدارة</b>
━━━━━━━━━━━━━━
<b>📊 إحصائيات البوت:</b>
👥 المستخدمين: {format_number(total_users)}
👑 مستخدمين VIP: {format_number(vip_users)}
💰 إجمالي الرصيد: {format_number(total_balance)} دينار
💳 المعاملات: {format_number(total_transactions)}
💰 أرباح معلقة: {format_number(pending_earnings)} دينار

<b>🔧 حالة البوت:</b> {'🛑 تحت الصيانة' if maintenance_mode else '✅ يعمل بشكل طبيعي'}
    """
    
    keyboard = [
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data='admin_users')],
        [InlineKeyboardButton("💳 الشحن والخصم", callback_data='admin_balance')],
        [InlineKeyboardButton("🚫 الحظر والإلغاء", callback_data='admin_ban')],
        [InlineKeyboardButton("📊 الإحصائيات المفصلة", callback_data='admin_stats')],
        [InlineKeyboardButton("⚙️ إعدادات الخدمات", callback_data='admin_services')],
        [InlineKeyboardButton("👑 إدارة VIP", callback_data='admin_vip')],
        [InlineKeyboardButton("📣 إذاعة عامة", callback_data='admin_broadcast')],
        [InlineKeyboardButton("❓ إدارة الأسئلة", callback_data='admin_questions')],
        [InlineKeyboardButton("📚 إدارة المواد", callback_data='admin_materials')],
        [InlineKeyboardButton("🔧 وضع الصيانة", callback_data='toggle_maintenance')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='back_to_main')]
    ]
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def admin_users_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إدارة المستخدمين"""
    query = update.callback_query
    await query.answer()
    
    if not await is_admin(query.from_user.id):
        return
    
    users = db.get_all_users(limit=10)
    
    if not users:
        message = "📭 لا يوجد مستخدمين حالياً."
    else:
        cols = [col[0] for col in db.cursor.description]
        message = "👥 <b>آخر 10 مستخدمين</b>\n━━━━━━━━━━━━━━\n"
        
        for user in users:
            user_dict = dict(zip(cols, user))
            status = "👑 VIP" if user_dict['is_vip'] else ("🚫 محظور" if user_dict['is_banned'] else "✅ نشط")
            vip_status = ""
            
            if user_dict['is_vip'] and user_dict['vip_expiry']:
                expiry = datetime.strptime(user_dict['vip_expiry'], '%Y-%m-%d %H:%M:%S')
                if expiry > datetime.now():
                    days_left = (expiry - datetime.now()).days
                    vip_status = f" ({days_left} يوم)"
            
            message += f"\n👤 {user_dict['first_name']} (@{user_dict['username'] or 'لا يوجد'})"
            message += f"\n🆔: <code>{user_dict['user_id']}</code> | 💰: {format_number(user_dict['balance'])}"
            message += f"\n📅: {user_dict['joined_date'][:10]} | {status}{vip_status}"
            message += "\n" + "─" * 30
    
    keyboard = [
        [
            InlineKeyboardButton("🔍 بحث عن مستخدم", callback_data='admin_search_user'),
            InlineKeyboardButton("📋 تصدير البيانات", callback_data='admin_export_users')
        ],
        [
            InlineKeyboardButton("👑 إدارة VIP", callback_data='admin_vip'),
            InlineKeyboardButton("🛠️ رفع مشرف", callback_data='admin_add_admin')
        ],
        [InlineKeyboardButton("🔙 رجوع للوحة", callback_data='admin_panel')]
    ]
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def admin_balance_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إدارة الرصيد"""
    query = update.callback_query
    await query.answer()
    
    if not await is_admin(query.from_user.id):
        return
    
    message = """
💳 <b>إدارة الرصيد</b>
━━━━━━━━━━━━━━
<b>اختر العملية:</b>

• <b>الشحن:</b> إضافة رصيد لمستخدم
• <b>الخصم:</b> خصم رصيد من مستخدم
• <b>التحويل:</b> نقل رصيد بين مستخدمين

<b>📝 الأوامر:</b>
1. للشحن: <code>شحن ايدي_المستخدم المبلغ</code>
2. للخصم: <code>خصم ايدي_المستخدم المبلغ</code>
3. للتحويل: <code>تحويل من_ايدي الى_ايدي المبلغ</code>

<blockquote>أمثلة:
شحن 123456789 5000
خصم 123456789 3000
تحويل 123456789 987654321 2000</blockquote>

<b>أرسل الأمر الآن:</b>
    """
    
    keyboard = [
        [InlineKeyboardButton("📋 عرض المعاملات", callback_data='admin_transactions')],
        [InlineKeyboardButton("🔙 رجوع للوحة", callback_data='admin_panel')]
    ]
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    
    context.user_data['admin_action'] = 'balance_management'

async def handle_admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأوامر الإدارية"""
    user_id = update.message.from_user.id
    
    if not await is_admin(user_id):
        return
    
    text = update.message.text.strip()
    
    if context.user_data.get('admin_action') == 'balance_management':
        await process_balance_command(update, context, text)
    elif context.user_data.get('admin_action') == 'ban_management':
        await process_ban_command(update, context, text)
    
    context.user_data['admin_action'] = None

async def process_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """معالجة أوامر الرصيد"""
    try:
        if text.startswith('شحن '):
            parts = text[4:].split()
            if len(parts) != 2:
                await update.message.reply_text("❌ صيغة غير صحيحة. مثال: شحن 123456789 5000")
                return
            
            target_id = int(parts[0])
            amount = int(parts[1])
            
            if amount <= 0:
                await update.message.reply_text("❌ المبلغ يجب أن يكون أكبر من صفر")
                return
            
            target_user = db.get_user(target_id)
            if not target_user:
                await update.message.reply_text("❌ المستخدم غير موجود")
                return
            
            db.update_balance(target_id, amount, 'admin_charge', f'شحن إداري بواسطة {user_id}')
            
            # إشعار للمستخدم
            user_notification = f"""
🎉 <b>تم شحن حسابك</b>
━━━━━━━━━━━━━━
💰 المبلغ: <code>{format_number(amount)} دينار</code>
📝 السبب: شحن إداري
📊 الرصيد الجديد: <code>{format_number(target_user['balance'] + amount)} دينار</code>
⏰ الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            await send_message(target_id, user_notification, context)
            
            await update.message.reply_text(
                f"✅ تم شحن <code>{format_number(amount)}</code> دينار للمستخدم {target_id}",
                parse_mode=ParseMode.HTML
            )
            
        elif text.startswith('خصم '):
            parts = text[4:].split()
            if len(parts) != 2:
                await update.message.reply_text("❌ صيغة غير صحيحة. مثال: خصم 123456789 3000")
                return
            
            target_id = int(parts[0])
            amount = int(parts[1])
            
            if amount <= 0:
                await update.message.reply_text("❌ المبلغ يجب أن يكون أكبر من صفر")
                return
            
            target_user = db.get_user(target_id)
            if not target_user:
                await update.message.reply_text("❌ المستخدم غير موجود")
                return
            
            if target_user['balance'] < amount:
                await update.message.reply_text("❌ رصيد المستخدم غير كافي للخصم")
                return
            
            db.update_balance(target_id, -amount, 'admin_deduction', f'خصم إداري بواسطة {user_id}')
            
            # إشعار للمستخدم
            user_notification = f"""
⚠️ <b>تم خصم مبلغ من حسابك</b>
━━━━━━━━━━━━━━
💰 المبلغ: <code>{format_number(amount)} دينار</code>
📝 السبب: خصم إداري
📊 الرصيد الجديد: <code>{format_number(target_user['balance'] - amount)} دينار</code>
⏰ الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            await send_message(target_id, user_notification, context)
            
            await update.message.reply_text(
                f"✅ تم خصم <code>{format_number(amount)}</code> دينار من المستخدم {target_id}",
                parse_mode=ParseMode.HTML
            )
            
        elif text.startswith('تحويل '):
            parts = text[6:].split()
            if len(parts) != 3:
                await update.message.reply_text("❌ صيغة غير صحيحة. مثال: تحويل 123456789 987654321 2000")
                return
            
            from_id = int(parts[0])
            to_id = int(parts[1])
            amount = int(parts[2])
            
            if amount <= 0:
                await update.message.reply_text("❌ المبلغ يجب أن يكون أكبر من صفر")
                return
            
            from_user = db.get_user(from_id)
            to_user = db.get_user(to_id)
            
            if not from_user or not to_user:
                await update.message.reply_text("❌ أحد المستخدمين غير موجود")
                return
            
            if from_user['balance'] < amount:
                await update.message.reply_text("❌ رصيد المستخدم المرسل غير كافي")
                return
            
            # خصم من المرسل
            db.update_balance(from_id, -amount, 'transfer_out', f'تحويل إلى {to_id}')
            # إضافة للمستلم
            db.update_balance(to_id, amount, 'transfer_in', f'تحويل من {from_id}')
            
            # إشعارات للمستخدمين
            notification_from = f"""
💸 <b>تحويل مبلغ</b>
━━━━━━━━━━━━━━
💰 المبلغ المحول: <code>{format_number(amount)} دينار</code>
👤 إلى المستخدم: {to_id}
📊 رصيدك الجديد: <code>{format_number(from_user['balance'] - amount)} دينار</code>
            """
            
            notification_to = f"""
🎁 <b>استلام مبلغ</b>
━━━━━━━━━━━━━━
💰 المبلغ المستلم: <code>{format_number(amount)} دينار</code>
👤 من المستخدم: {from_id}
📊 رصيدك الجديد: <code>{format_number(to_user['balance'] + amount)} دينار</code>
            """
            
            await send_message(from_id, notification_from, context)
            await send_message(to_id, notification_to, context)
            
            await update.message.reply_text(
                f"✅ تم تحويل <code>{format_number(amount)}</code> دينار من {from_id} إلى {to_id}",
                parse_mode=ParseMode.HTML
            )
            
        else:
            await update.message.reply_text("❌ أمر غير معروف. استخدم: شحن، خصم، أو تحويل")
            
    except ValueError:
        await update.message.reply_text("❌ الرجاء إدخال أرقام صحيحة")
    except Exception as e:
        logging.error(f"Admin command error: {e}")
        await update.message.reply_text("❌ حدث خطأ في معالجة الأمر")

async def admin_broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الإذاعة"""
    query = update.callback_query
    await query.answer()
    
    if not await is_admin(query.from_user.id):
        return
    
    message = """
📣 <b>الإذاعة العامة</b>
━━━━━━━━━━━━━━
<code>أرسل الرسالة التي تريد إذاعتها لجميع المستخدمين</code>

<b>📝 ملاحظات:</b>
• يمكنك استخدام HTML للتنسيق
• الرسالة سترسل لجميع المستخدمين النشطين
• العملية قد تستغرق بعض الوقت
• لا يمكن التراجع عن الإذاعة

<b>🚨 تنبيه:</b>
تأكد من محتوى الرسالة قبل الإرسال.

<b>أرسل الرسالة الآن:</b>
    """
    
    await query.edit_message_text(message, parse_mode=ParseMode.HTML)
    context.user_data['admin_action'] = 'broadcast'

async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة رسالة الإذاعة"""
    user_id = update.message.from_user.id
    
    if not await is_admin(user_id):
        return
    
    if context.user_data.get('admin_action') != 'broadcast':
        return
    
    broadcast_text = update.message.text_html or update.message.text
    
    if not broadcast_text.strip():
        await update.message.reply_text("❌ الرسالة فارغة")
        return
    
    # حفظ نص الإذاعة
    context.user_data['broadcast_text'] = broadcast_text
    
    # عرض تأكيد
    preview = broadcast_text[:200] + ("..." if len(broadcast_text) > 200 else "")
    
    keyboard = [
        [
            InlineKeyboardButton("✅ نعم، قم بالإذاعة", callback_data='confirm_broadcast'),
            InlineKeyboardButton("❌ إلغاء", callback_data='admin_panel')
        ]
    ]
    
    await update.message.reply_text(
        f"📣 <b>تأكيد الإذاعة</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"<b>معاينة الرسالة:</b>\n{preview}\n\n"
        f"سيتم إرسال هذه الرسالة لجميع المستخدمين.\n"
        f"هل أنت متأكد؟",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    
    context.user_data['admin_action'] = None

async def confirm_broadcast_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنفيذ الإذاعة"""
    query = update.callback_query
    await query.answer()
    
    if not await is_admin(query.from_user.id):
        return
    
    broadcast_text = context.user_data.get('broadcast_text', '')
    if not broadcast_text:
        await query.answer("❌ لا توجد رسالة للإذاعة", show_alert=True)
        return
    
    # جلب جميع المستخدمين غير المحظورين
    db.cursor.execute('SELECT user_id FROM users WHERE is_banned = 0')
    all_users = db.cursor.fetchall()
    
    total_users = len(all_users)
    successful = 0
    failed = 0
    
    progress_msg = await query.edit_message_text(
        f"📤 <b>جاري الإذاعة...</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"✅ تم إرسال: 0\n"
        f"❌ فشل: 0\n"
        f"📊 الإجمالي: {total_users}\n"
        f"⏳ المتبقي: {total_users}",
        parse_mode=ParseMode.HTML
    )
    
    for index, (user_id,) in enumerate(all_users, 1):
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=broadcast_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            successful += 1
        except Exception as e:
            failed += 1
        
        # تحديث الرسالة كل 20 مستخدم
        if index % 20 == 0 or index == total_users:
            try:
                await progress_msg.edit_text(
                    f"📤 <b>جاري الإذاعة...</b>\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"✅ تم إرسال: {successful}\n"
                    f"❌ فشل: {failed}\n"
                    f"📊 الإجمالي: {total_users}\n"
                    f"⏳ المتبقي: {total_users - index}\n"
                    f"📈 النسبة: {(index/total_users)*100:.1f}%",
                    parse_mode=ParseMode.HTML
                )
            except:
                pass
    
    # نتيجة الإذاعة
    result_message = f"""
🎉 <b>تمت الإذاعة بنجاح</b>
━━━━━━━━━━━━━━
<b>📊 النتائج:</b>
✅ تم إرسال بنجاح: {successful}
❌ فشل في الإرسال: {failed}
📊 الإجمالي: {total_users}
📈 نسبة النجاح: {(successful/total_users)*100:.1f}%
    """
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع للوحة", callback_data='admin_panel')]]
    
    await progress_msg.edit_text(
        result_message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    
    # تنظيف البيانات
    context.user_data.pop('broadcast_text', None)

async def admin_services_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إدارة الخدمات"""
    query = update.callback_query
    await query.answer()
    
    if not await is_admin(query.from_user.id):
        return
    
    services = db.get_active_services()
    
    message = "⚙️ <b>إدارة الخدمات</b>\n━━━━━━━━━━━━━━\n"
    keyboard = []
    
    for service in services:
        service_dict = dict(zip(['id', 'name', 'display_name', 'price', 'is_active', 'category'], service))
        status = "✅ مفعل" if service_dict['is_active'] else "❌ معطل"
        message += f"\n<b>{service_dict['display_name']}</b>\n"
        message += f"💰 السعر: {format_number(service_dict['price'])} دينار | {status}\n"
        message += f"📂 القسم: {service_dict['category']}\n"
        message += "─" * 30 + "\n"
        
        # أزرار لكل خدمة
        row = []
        row.append(InlineKeyboardButton(
            f"🔄 {service_dict['display_name']}",
            callback_data=f'admin_toggle_service_{service_dict["name"]}'
        ))
        row.append(InlineKeyboardButton(
            "💰 تغيير السعر",
            callback_data=f'admin_change_price_{service_dict["name"]}'
        ))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع للوحة", callback_data='admin_panel')])
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def admin_toggle_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تفعيل/تعطيل خدمة"""
    query = update.callback_query
    await query.answer()
    
    if not await is_admin(query.from_user.id):
        return
    
    service_name = query.data.replace('admin_toggle_service_', '')
    
    # الحصول على حالة الخدمة الحالية
    db.cursor.execute('SELECT is_active FROM services WHERE name = ?', (service_name,))
    current_status = db.cursor.fetchone()
    
    if not current_status:
        await query.answer("❌ الخدمة غير موجودة", show_alert=True)
        return
    
    new_status = 0 if current_status[0] == 1 else 1
    db.toggle_service(service_name, new_status)
    
    status_text = "مفعلة" if new_status == 1 else "معطلة"
    await query.answer(f"✅ تم {status_text} الخدمة", show_alert=True)
    
    # تحديث العرض
    await admin_services_management(update, context)

# ============== معالجة الأزرار العامة ==============
async def handle_callback_queries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة جميع استدعاءات الأزرار"""
    query = update.callback_query
    data = query.data
    
    try:
        # معالجة أزرار الخدمات
        if data.startswith('service_'):
            await handle_service_selection(update, context)
        
        # معالجة أزرار العودة
        elif data == 'back_to_main':
            await show_main_menu(update, context)
        
        # معالجة أزرار الرصيد
        elif data == 'my_balance':
            await show_balance(update, context)
        
        # معالجة أزرار المساعدة
        elif data == 'help':
            await show_help(update, context)
        
        # معالجة أزرار VIP
        elif data == 'vip_lectures':
            await vip_lectures_handler(update, context)
        elif data == 'vip_subscription_info':
            await vip_subscription_info(update, context)
        elif data == 'upload_vip_lecture':
            await upload_vip_lecture_start(update, context)
        
        # معالجة أزرار لوحة التحكم
        elif data == 'admin_panel':
            await admin_panel(update, context)
        elif data == 'admin_users':
            await admin_users_management(update, context)
        elif data == 'admin_balance':
            await admin_balance_management(update, context)
        elif data == 'admin_broadcast':
            await admin_broadcast_handler(update, context)
        elif data == 'admin_services':
            await admin_services_management(update, context)
        elif data.startswith('admin_toggle_service_'):
            await admin_toggle_service(update, context)
        elif data == 'confirm_broadcast':
            await confirm_broadcast_execute(update, context)
        
        # معالجة أزرار المراحل الدراسية
        elif data.startswith('stage_'):
            await show_stage_materials(update, context)
        
        # معالجة أزرار الأسئلة
        elif data == 'ask_new_question':
            await ask_new_question_handler(update, context)
        
        else:
            await query.answer("⏳ هذه الميزة قيد التطوير...", show_alert=True)
            
    except Exception as e:
        logging.error(f"Callback error: {e}")
        await query.answer("❌ حدث خطأ. الرجاء المحاولة مرة أخرى", show_alert=True)

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض رصيد المستخدم"""
    query = update.callback_query
    user = query.from_user
    await query.answer()
    
    user_data = db.get_user(user.id)
    if not user_data:
        return
    
    # جلب آخر المعاملات
    transactions = db.get_user_transactions(user.id, limit=5)
    
    message = f"""
💰 <b>رصيدك الحالي</b>
━━━━━━━━━━━━━━
<b>💵 المبلغ:</b> <code>{format_number(user_data['balance'])} دينار عراقي</code>

<b>📨 رابط الدعوة:</b>
<code>https://t.me/{BOT_USERNAME[1:]}?start={user_data['invite_code']}</code>

<b>🎁 مكافأة الدعوة:</b> {format_number(int(db.get_setting('invite_bonus') or 1000))} دينار لكل صديق
<b>👥 عدد الدعوات:</b> {user_data['invited_count']}
<b>💸 إجمالي الإنفاق:</b> {format_number(user_data.get('total_spent', 0))} دينار
    """
    
    if transactions:
        cols = [col[0] for col in db.cursor.description]
        message += "\n\n<b>📝 آخر المعاملات:</b>\n"
        for trans in transactions:
            trans_dict = dict(zip(cols, trans))
            amount = trans_dict['amount']
            sign = "➕" if amount > 0 else "➖"
            amount_display = format_number(abs(amount))
            date = trans_dict['date'][:16]
            message += f"\n{sign} {amount_display} - {trans_dict['description']} - {date}"
    
    keyboard = [
        [
            InlineKeyboardButton("💳 شحن الرصيد", url=f"https://t.me/{DEVELOPER_USERNAME[1:]}"),
            InlineKeyboardButton("📤 مشاركة الرابط", callback_data='share_invite')
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data='back_to_main')]
    ]
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض رسالة المساعدة"""
    query = update.callback_query
    await query.answer()
    
    support_username = db.get_setting('support_username') or DEVELOPER_USERNAME
    channel_link = db.get_setting('channel_link') or CHANNEL_LINK
    
    message = f"""
ℹ️ <b>مركز المساعدة</b>
━━━━━━━━━━━━━━
<b>📞 الدعم الفني:</b> @{support_username[1:] if support_username.startswith('@') else support_username}
<b>📢 قناة البوت:</b> {channel_link}

<b>❓ الأسئلة الشائعة:</b>

<b>Q: كيف أشحن رصيدي؟</b>
A: تواصل مع الدعم الفني @{support_username[1:] if support_username.startswith('@') else support_username}

<b>Q: كيف أحصل على رصيد مجاني؟</b>
A: ادعُ أصدقائك عبر رابط الدعوة في قسم "رصيدي"

<b>Q: الخدمة لا تعمل، ماذا أفعل؟</b>
A: تأكد من أن رصيدك كافٍ، إذا استمرت المشكلة تواصل مع الدعم

<b>Q: كيف أصبح معلم VIP؟</b>
A: اشترك في خدمة VIP من قسم "محاضرات VIP"

<b>Q: كم سعر الخدمات؟</b>
A: أقل سعر خدمة هو 1000 دينار، ويمكنك تغيير الأسعار من لوحة التحكم

<b>⚠️ ملاحظة:</b>
جميع الخدمات مدفوعة، وأقل سعر للخدمة هو 1000 دينار عراقي.
    """
    
    keyboard = [
        [
            InlineKeyboardButton("📞 الدعم الفني", url=f"https://t.me/{support_username[1:] if support_username.startswith('@') else support_username}"),
            InlineKeyboardButton("📢 القناة", url=channel_link)
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data='back_to_main')]
    ]
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

# ============== الوظيفة الرئيسية ==============
def main():
    """تشغيل البوت"""
    # إعداد التسجيل
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    # إنشاء التطبيق
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة handlers للبدء والمساعدة
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", show_help))
    
    # إضافة Conversation Handlers للخدمات
    exemption_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(exemption_calculator_service, pattern='^service_exemption_calculator$')],
        states={
            WAITING_FOR_GRADES: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_grades)],
        },
        fallbacks=[CallbackQueryHandler(show_main_menu, pattern='^back_to_main$')],
        allow_reentry=True
    )
    
    pdf_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(pdf_summary_service, pattern='^service_pdf_summary$')],
        states={
            WAITING_FOR_PDF: [MessageHandler(filters.Document.PDF, handle_pdf_file)],
        },
        fallbacks=[CallbackQueryHandler(show_main_menu, pattern='^back_to_main$')],
        allow_reentry=True
    )
    
    qna_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(qna_service, pattern='^service_qna$')],
        states={
            WAITING_FOR_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question)],
        },
        fallbacks=[CallbackQueryHandler(show_main_menu, pattern='^back_to_main$')],
        allow_reentry=True
    )
    
    student_question_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(ask_new_question_handler, pattern='^ask_new_question$')],
        states={
            WAITING_FOR_STUDENT_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_question)],
        },
        fallbacks=[CallbackQueryHandler(show_main_menu, pattern='^back_to_main$')],
        allow_reentry=True
    )
    
    vip_lecture_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(upload_vip_lecture_start, pattern='^upload_vip_lecture$')],
        states={
            VIP_LECTURE_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_vip_lecture_title)],
            VIP_LECTURE_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_vip_lecture_desc)],
            VIP_LECTURE_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_vip_lecture_price)],
            VIP_LECTURE_FILE: [MessageHandler(filters.Document.ALL | filters.VIDEO, handle_vip_lecture_file)],
        },
        fallbacks=[CallbackQueryHandler(show_main_menu, pattern='^back_to_main$')],
        allow_reentry=True
    )
    
    # إضافة الـ Conversation Handlers
    application.add_handler(exemption_handler)
    application.add_handler(pdf_handler)
    application.add_handler(qna_handler)
    application.add_handler(student_question_handler)
    application.add_handler(vip_lecture_handler)
    
    # معالجة الأوامر الإدارية
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_commands))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast_message))
    
    # معالجة استدعاءات الأزرار
    application.add_handler(CallbackQueryHandler(handle_callback_queries))
    
    # بدء البوت
    print("=" * 50)
    print("✅ البوت يعمل بنجاح!")
    print(f"🤖 اسم البوت: {BOT_USERNAME}")
    print(f"👤 المطور: {DEVELOPER_USERNAME}")
    print(f"🆔 ايدي المطور: {DEVELOPER_ID}")
    print(f"📢 القناة: {CHANNEL_LINK}")
    print("=" * 50)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
