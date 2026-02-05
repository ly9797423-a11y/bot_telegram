#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت تليجرام "يلا نتعلم" - النسخة الكاملة المصححة
مطور: Allawi04
آيدي المدير: 6130994941
توكن البوت: 8481569753:AAH3alhJ0hcHldht-PxV7j8TzBlRsMqAqGI
"""

import asyncio
import sqlite3
import logging
import json
import os
import io
import base64
import re
import random
import string
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, InputFile, InputMediaPhoto
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

import google.generativeai as genai
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display
import PyPDF2
from PIL import Image
import requests

# ===================== إعدادات البوت =====================
API_TOKEN = "8481569753:AAH3alhJ0hcHldht-PxV7j8TzBlRsMqAqGI"
ADMIN_ID = 6130994941
SUPPORT_USERNAME = "@Allawi04"
CHANNEL_USERNAME = "https://t.me/FCJCV"  # تم التعديل هنا
BOT_USERNAME = "@FC4Xbot"
GEMINI_API_KEY = "AIzaSyARsl_YMXA74bPQpJduu0jJVuaku7MaHuY"

# إعداد التسعير الافتراضي
DEFAULT_PRICES = {
    "exemption": 1000,
    "summarize": 1000,
    "qna": 1000,
    "help_student": 1000,
    "vip_subscription": 5000,
    "vip_lecture": 3000
}

# إعداد الخطوط العربية
FONT_ARABIC = "fonts/Amiri-Regular.ttf"
FONT_ENGLISH = "fonts/DejaVuSans.ttf"

# إنشاء مجلدات التخزين
Path("fonts").mkdir(exist_ok=True)
Path("lectures").mkdir(exist_ok=True)
Path("materials").mkdir(exist_ok=True)
Path("summaries").mkdir(exist_ok=True)
Path("temp").mkdir(exist_ok=True)

# ===================== إعداد قاعدة البيانات =====================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('database.db', check_same_thread=False)
        self.create_tables()
        self.create_indexes()
        self.insert_default_data()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        # جدول المستخدمين
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                balance INTEGER DEFAULT 1000,
                is_banned INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0,
                is_vip INTEGER DEFAULT 0,
                vip_expiry TIMESTAMP,
                referral_code TEXT UNIQUE,
                referred_by TEXT,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_spent INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0
            )
        ''')
        
        # جدول العمليات المالية
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                type TEXT,
                description TEXT,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        
        # جدول الخدمات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                price INTEGER,
                is_active INTEGER DEFAULT 1,
                category TEXT
            )
        ''')
        
        # جدول المواد التعليمية
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                description TEXT,
                grade TEXT,
                file_id TEXT,
                file_type TEXT,
                added_by INTEGER,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                downloads INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY(added_by) REFERENCES users(user_id)
            )
        ''')
        
        # جدول أسئلة ساعدوني طالب
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS help_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                question TEXT,
                is_approved INTEGER DEFAULT 0,
                is_answered INTEGER DEFAULT 0,
                answer TEXT,
                answered_by INTEGER,
                price_paid INTEGER,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(answered_by) REFERENCES users(user_id)
            )
        ''')
        
        # جدول محاضرات VIP
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vip_lectures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER,
                title TEXT,
                description TEXT,
                subject TEXT,
                file_id TEXT,
                file_type TEXT,
                price INTEGER DEFAULT 3000,
                is_approved INTEGER DEFAULT 0,
                views INTEGER DEFAULT 0,
                purchases INTEGER DEFAULT 0,
                rating REAL DEFAULT 0.0,
                total_ratings INTEGER DEFAULT 0,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY(teacher_id) REFERENCES users(user_id)
            )
        ''')
        
        # جدول مشتريات محاضرات VIP
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lecture_purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                lecture_id INTEGER,
                amount_paid INTEGER,
                purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(lecture_id) REFERENCES vip_lectures(id)
            )
        ''')
        
        # جدول أرباح المحاضرين
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teacher_earnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER,
                lecture_id INTEGER,
                amount INTEGER,
                percentage INTEGER DEFAULT 60,
                status TEXT DEFAULT 'pending',
                request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                paid_date TIMESTAMP,
                FOREIGN KEY(teacher_id) REFERENCES users(user_id),
                FOREIGN KEY(lecture_id) REFERENCES vip_lectures(id)
            )
        ''')
        
        # جدول تقييمات المحاضرات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lecture_ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                lecture_id INTEGER,
                rating INTEGER CHECK(rating >= 1 AND rating <= 5),
                comment TEXT,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(lecture_id) REFERENCES vip_lectures(id),
                UNIQUE(user_id, lecture_id)
            )
        ''')
        
        # جدول الإعدادات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        # جدول الإحصائيات اليومية
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                date DATE PRIMARY KEY,
                new_users INTEGER DEFAULT 0,
                active_users INTEGER DEFAULT 0,
                revenue INTEGER DEFAULT 0,
                transactions INTEGER DEFAULT 0
            )
        ''')
        
        # جدول الإشعارات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        
        # جدول كوبونات الخصم
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS coupons (
                code TEXT PRIMARY KEY,
                discount_percent INTEGER,
                max_uses INTEGER,
                used_count INTEGER DEFAULT 0,
                expires_at TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        self.conn.commit()
    
    def create_indexes(self):
        cursor = self.conn.cursor()
        
        # إنشاء فهارس لتحسين الأداء
        indexes = [
            'CREATE INDEX IF NOT EXISTS idx_users_balance ON users(balance)',
            'CREATE INDEX IF NOT EXISTS idx_users_vip ON users(is_vip, vip_expiry)',
            'CREATE INDEX IF NOT EXISTS idx_users_banned ON users(is_banned)',
            'CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions(user_id, date)',
            'CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type)',
            'CREATE INDEX IF NOT EXISTS idx_services_active ON services(is_active)',
            'CREATE INDEX IF NOT EXISTS idx_materials_grade ON materials(grade, is_active)',
            'CREATE INDEX IF NOT EXISTS idx_vip_lectures_approved ON vip_lectures(is_approved, is_active)',
            'CREATE INDEX IF NOT EXISTS idx_vip_lectures_teacher ON vip_lectures(teacher_id, is_approved)',
            'CREATE INDEX IF NOT EXISTS idx_help_questions_approved ON help_questions(is_approved, is_answered)',
            'CREATE INDEX IF NOT EXISTS idx_teacher_earnings_status ON teacher_earnings(status, teacher_id)',
            'CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read)'
        ]
        
        for index in indexes:
            try:
                cursor.execute(index)
            except:
                pass
        
        self.conn.commit()
    
    def insert_default_data(self):
        cursor = self.conn.cursor()
        
        # إدخال الخدمات الافتراضية
        default_services = [
            ('exemption', 1000, 1, 'educational'),
            ('summarize', 1000, 1, 'educational'),
            ('qna', 1000, 1, 'educational'),
            ('help_student', 1000, 1, 'community'),
            ('vip_subscription', 5000, 1, 'vip'),
            ('vip_lecture', 3000, 1, 'vip')
        ]
        
        for service in default_services:
            cursor.execute('''
                INSERT OR IGNORE INTO services (name, price, is_active, category)
                VALUES (?, ?, ?, ?)
            ''', service)
        
        # إدخال الإعدادات الافتراضية
        default_settings = [
            ('maintenance_mode', '0'),
            ('referral_bonus', '500'),
            ('min_withdrawal', '15000'),
            ('admin_username', '@Allawi04'),
            ('channel_username', 'https://t.me/FCJCV'),
            ('welcome_bonus', '1000'),
            ('vip_subscription_price', '5000'),
            ('teacher_percentage', '60'),
            ('answer_reward', '100'),
            ('max_file_size_mb', '50'),
            ('daily_bonus_active', '1'),
            ('daily_bonus_amount', '100')
        ]
        
        for setting in default_settings:
            cursor.execute('''
                INSERT OR IGNORE INTO settings (key, value)
                VALUES (?, ?)
            ''', setting)
        
        # إضافة المدير كأول مستخدم
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, balance, is_admin, referral_code)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (ADMIN_ID, 'Allawi04', 'المدير', '', 1000000, 1, 'ADMIN001'))
        except:
            pass
        
        self.conn.commit()
    
    def add_user(self, user_id, username, first_name, last_name, referred_by=None):
        cursor = self.conn.cursor()
        
        # إنشاء كود دعوة فريد
        referral_code = f"REF{user_id}{random.randint(1000, 9999)}"
        
        # إضافة هدية الترحيب
        welcome_bonus = int(self.get_setting('welcome_bonus') or 1000)
        
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, balance, referral_code, referred_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name, welcome_bonus, referral_code, referred_by))
        
        if cursor.rowcount > 0:
            # إضافة هدية الترحيب كعملية
            self.add_transaction(user_id, welcome_bonus, 'welcome_bonus', 'هدية ترحيب')
            
            # تحديث إحصائيات اليوم
            self.update_daily_stats('new_users', 1)
            
            # مكافأة المدعو إذا كان هناك مدعو
            if referred_by:
                referral_bonus = int(self.get_setting('referral_bonus') or 500)
                self.update_balance(referred_by, referral_bonus, 'add')
                self.add_transaction(referred_by, referral_bonus, 'referral_bonus', f'مكافأة دعوة المستخدم {user_id}')
        
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        columns = [column[0] for column in cursor.description]
        row = cursor.fetchone()
        return dict(zip(columns, row)) if row else None
    
    def update_balance(self, user_id, amount, operation='add', description=None):
        cursor = self.conn.cursor()
        
        # الحصول على الرصيد الحالي
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if not result:
            return None
        
        current_balance = result[0]
        
        # حساب الرصيد الجديد
        if operation == 'add':
            new_balance = current_balance + amount
            trans_type = 'deposit'
        elif operation == 'deduct':
            if current_balance < amount:
                return None  # الرصيد غير كافي
            new_balance = current_balance - amount
            trans_type = 'withdraw'
        else:
            return None
        
        # تحديث الرصيد
        cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
        
        # إضافة العملية المالية
        if description:
            self.add_transaction(user_id, amount if operation == 'add' else -amount, 
                               trans_type, description)
        
        self.conn.commit()
        return new_balance
    
    def deduct_for_service(self, user_id, service_name, service_price):
        """خصم مبلغ الخدمة مع التحقق"""
        cursor = self.conn.cursor()
        
        # التحقق من الرصيد
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if not result or result[0] < service_price:
            return False
        
        # الخصم
        new_balance = result[0] - service_price
        cursor.execute('UPDATE users SET balance = ?, total_spent = total_spent + ? WHERE user_id = ?', 
                      (new_balance, service_price, user_id))
        
        # تسجيل العملية
        self.add_transaction(user_id, -service_price, 'service_purchase', 
                           f'شراء خدمة {service_name}')
        
        self.conn.commit()
        return True
    
    def add_transaction(self, user_id, amount, trans_type, description):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO transactions (user_id, amount, type, description)
            VALUES (?, ?, ?, ?)
        ''', (user_id, amount, trans_type, description))
        
        # تحديث إحصائيات اليوم
        if trans_type in ['service_purchase', 'deposit']:
            self.update_daily_stats('revenue', amount if amount > 0 else -amount)
            self.update_daily_stats('transactions', 1)
        
        self.conn.commit()
        return cursor.lastrowid
    
    def get_service_price(self, service_name):
        cursor = self.conn.cursor()
        cursor.execute('SELECT price FROM services WHERE name = ?', (service_name,))
        result = cursor.fetchone()
        return result[0] if result else DEFAULT_PRICES.get(service_name, 1000)
    
    def is_service_active(self, service_name):
        cursor = self.conn.cursor()
        cursor.execute('SELECT is_active FROM services WHERE name = ?', (service_name,))
        result = cursor.fetchone()
        return result[0] == 1 if result else False
    
    def update_service_price(self, service_name, new_price):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE services SET price = ? WHERE name = ?', (new_price, service_name))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def toggle_service(self, service_name, status):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE services SET is_active = ? WHERE name = ?', (status, service_name))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_active_services(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT name, price FROM services WHERE is_active = 1')
        return {row[0]: row[1] for row in cursor.fetchall()}
    
    def add_material(self, name, description, grade, file_id, file_type, added_by):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO materials (name, description, grade, file_id, file_type, added_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, description, grade, file_id, file_type, added_by))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_materials_by_grade(self, grade):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM materials 
            WHERE grade = ? AND is_active = 1 
            ORDER BY downloads DESC
        ''', (grade,))
        return cursor.fetchall()
    
    def get_all_users(self, limit=100, offset=0):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM users 
            ORDER BY join_date DESC 
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        return cursor.fetchall()
    
    def get_vip_users(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM users 
            WHERE is_vip = 1 AND (vip_expiry IS NULL OR vip_expiry > CURRENT_TIMESTAMP)
        ''')
        return cursor.fetchall()
    
    def ban_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (user_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def unban_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (user_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def make_admin(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE users SET is_admin = 1 WHERE user_id = ?', (user_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def add_vip_lecture(self, teacher_id, title, description, subject, file_id, file_type, price):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO vip_lectures (teacher_id, title, description, subject, file_id, file_type, price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (teacher_id, title, description, subject, file_id, file_type, price))
        self.conn.commit()
        return cursor.lastrowid
    
    def approve_lecture(self, lecture_id):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE vip_lectures SET is_approved = 1 WHERE id = ?', (lecture_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def reject_lecture(self, lecture_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM vip_lectures WHERE id = ?', (lecture_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_pending_lectures(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM vip_lectures WHERE is_approved = 0 ORDER BY upload_date DESC')
        return cursor.fetchall()
    
    def get_approved_lectures(self, limit=50, offset=0):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM vip_lectures 
            WHERE is_approved = 1 AND is_active = 1 
            ORDER BY purchases DESC, rating DESC 
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        return cursor.fetchall()
    
    def get_lecture_by_id(self, lecture_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM vip_lectures WHERE id = ?', (lecture_id,))
        columns = [column[0] for column in cursor.description]
        row = cursor.fetchone()
        return dict(zip(columns, row)) if row else None
    
    def purchase_lecture(self, user_id, lecture_id):
        lecture = self.get_lecture_by_id(lecture_id)
        if not lecture:
            return False
        
        price = lecture['price']
        
        # التحقق من الرصيد
        user = self.get_user(user_id)
        if not user or user['balance'] < price:
            return False
        
        # التحقق مما إذا كان المستخدم اشترى المحاضرة مسبقاً
        cursor = self.conn.cursor()
        cursor.execute('SELECT id FROM lecture_purchases WHERE user_id = ? AND lecture_id = ?', 
                      (user_id, lecture_id))
        if cursor.fetchone():
            return False  # المحاضرة مشتراة مسبقاً
        
        # خصم المبلغ
        self.update_balance(user_id, price, 'deduct', f'شراء محاضرة #{lecture_id}')
        
        # تسجيل الشراء
        cursor.execute('''
            INSERT INTO lecture_purchases (user_id, lecture_id, amount_paid)
            VALUES (?, ?, ?)
        ''', (user_id, lecture_id, price))
        
        # تحديث إحصائيات المحاضرة
        cursor.execute('''
            UPDATE vip_lectures 
            SET purchases = purchases + 1, views = views + 1 
            WHERE id = ?
        ''', (lecture_id,))
        
        # حساب أرباح المحاضر (60%)
        teacher_share = int(price * 0.6)
        teacher_id = lecture['teacher_id']
        
        # إضافة أرباح المحاضر
        cursor.execute('''
            INSERT INTO teacher_earnings (teacher_id, lecture_id, amount, percentage)
            VALUES (?, ?, ?, ?)
        ''', (teacher_id, lecture_id, teacher_share, 60))
        
        # تحديث أرباح المحاضر
        cursor.execute('UPDATE users SET total_earned = total_earned + ? WHERE user_id = ?', 
                      (teacher_share, teacher_id))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def get_teacher_earnings(self, teacher_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT SUM(amount) 
            FROM teacher_earnings 
            WHERE teacher_id = ? AND status = 'pending'
        ''', (teacher_id,))
        result = cursor.fetchone()
        return result[0] if result[0] else 0
    
    def get_teacher_total_earnings(self, teacher_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT SUM(amount) 
            FROM teacher_earnings 
            WHERE teacher_id = ? AND status = 'withdrawn'
        ''', (teacher_id,))
        result = cursor.fetchone()
        return result[0] if result[0] else 0
    
    def withdraw_earnings(self, teacher_id, amount):
        cursor = self.conn.cursor()
        
        # التحقق من الأرباح المعلقة
        pending_earnings = self.get_teacher_earnings(teacher_id)
        if pending_earnings < amount:
            return False
        
        # تحديث حالة الأرباح
        cursor.execute('''
            UPDATE teacher_earnings 
            SET status = 'withdrawn', paid_date = CURRENT_TIMESTAMP 
            WHERE teacher_id = ? AND status = 'pending'
        ''', (teacher_id,))
        
        # خصم المبلغ من أرباح المحاضر
        cursor.execute('UPDATE users SET total_earned = total_earned - ? WHERE user_id = ?', 
                      (amount, teacher_id))
        
        self.conn.commit()
        return cursor.rowcount > 0
    
    def add_help_question(self, user_id, question, price_paid):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO help_questions (user_id, question, price_paid)
            VALUES (?, ?, ?)
        ''', (user_id, question, price_paid))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_pending_questions(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM help_questions WHERE is_approved = 0 ORDER BY date DESC')
        return cursor.fetchall()
    
    def get_approved_questions(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM help_questions 
            WHERE is_approved = 1 AND is_answered = 0 
            ORDER BY date DESC
        ''')
        return cursor.fetchall()
    
    def approve_question(self, question_id):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE help_questions SET is_approved = 1 WHERE id = ?', (question_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def reject_question(self, question_id):
        cursor = self.conn.cursor()
        
        # استرداد المبلغ للمستخدم
        cursor.execute('SELECT user_id, price_paid FROM help_questions WHERE id = ?', (question_id,))
        result = cursor.fetchone()
        
        if result:
            user_id, price_paid = result
            # استرداد المبلغ
            self.update_balance(user_id, price_paid, 'add', f'استرداد مبلغ سؤال #{question_id}')
        
        # حذف السؤال
        cursor.execute('DELETE FROM help_questions WHERE id = ?', (question_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def answer_question(self, question_id, answer, answered_by):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE help_questions 
            SET is_answered = 1, answer = ?, answered_by = ? 
            WHERE id = ?
        ''', (answer, answered_by, question_id))
        
        # مكافأة المجيب
        reward_amount = int(self.get_setting('answer_reward') or 100)
        self.update_balance(answered_by, reward_amount, 'add', f'مكافأة الإجابة على سؤال #{question_id}')
        
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_statistics(self):
        cursor = self.conn.cursor()
        
        # إجمالي المستخدمين
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        # المستخدمين النشطين اليوم
        cursor.execute('SELECT COUNT(*) FROM users WHERE date(join_date) = date("now")')
        active_today = cursor.fetchone()[0]
        
        # المستخدمين VIP
        cursor.execute('SELECT COUNT(*) FROM users WHERE is_vip = 1')
        vip_users = cursor.fetchone()[0]
        
        # إجمالي الرصيد
        cursor.execute('SELECT SUM(balance) FROM users')
        total_balance = cursor.fetchone()[0] or 0
        
        # إجمالي الإيرادات
        cursor.execute('''
            SELECT SUM(amount) 
            FROM transactions 
            WHERE type IN ('service_purchase', 'vip_subscription', 'lecture_purchase') 
            AND amount < 0
        ''')
        total_revenue = abs(cursor.fetchone()[0] or 0)
        
        # إجمالي المشتريات
        cursor.execute('SELECT COUNT(*) FROM transactions WHERE type = "service_purchase"')
        total_purchases = cursor.fetchone()[0]
        
        # المحاضرات المعتمدة
        cursor.execute('SELECT COUNT(*) FROM vip_lectures WHERE is_approved = 1')
        total_lectures = cursor.fetchone()[0]
        
        return {
            'total_users': total_users,
            'active_today': active_today,
            'vip_users': vip_users,
            'total_balance': total_balance,
            'total_revenue': total_revenue,
            'total_purchases': total_purchases,
            'total_lectures': total_lectures
        }
    
    def get_setting(self, key):
        cursor = self.conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def update_setting(self, key, value):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value)
            VALUES (?, ?)
        ''', (key, value))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def update_daily_stats(self, field, increment=1):
        cursor = self.conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        
        # التحقق إذا كان هناك سجل لهذا اليوم
        cursor.execute('SELECT * FROM daily_stats WHERE date = ?', (today,))
        if cursor.fetchone():
            cursor.execute(f'''
                UPDATE daily_stats 
                SET {field} = {field} + ? 
                WHERE date = ?
            ''', (increment, today))
        else:
            cursor.execute(f'''
                INSERT INTO daily_stats (date, {field})
                VALUES (?, ?)
            ''', (today, increment))
        
        self.conn.commit()
    
    def add_notification(self, user_id, message):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO notifications (user_id, message)
            VALUES (?, ?)
        ''', (user_id, message))
        self.conn.commit()
        return cursor.lastrowid

# ===================== تهيئة قاعدة البيانات =====================
db = Database()

# ===================== إعداد الذكاء الاصطناعي =====================
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash')
except:
    model = None

# ===================== حالات FSM =====================
class Form(StatesGroup):
    # حالات لوحة التحكم
    admin_charge_user = State()
    admin_charge_amount = State()
    admin_deduct_user = State()
    admin_deduct_amount = State()
    admin_ban_user = State()
    admin_unban_user = State()
    admin_make_admin_user = State()
    admin_change_price_service = State()
    admin_change_price_amount = State()
    admin_toggle_service = State()
    admin_add_material_name = State()
    admin_add_material_desc = State()
    admin_add_material_grade = State()
    admin_add_material_file = State()
    admin_broadcast_message = State()
    admin_withdraw_user = State()
    admin_withdraw_amount = State()
    
    # حالات الخدمات
    exemption_course1 = State()
    exemption_course2 = State()
    exemption_course3 = State()
    
    summarize_pdf = State()
    
    qna_text = State()
    qna_image = State()
    
    help_question = State()
    help_answer = State()
    
    # حالات VIP
    vip_subscribe_confirm = State()
    vip_add_lecture_title = State()
    vip_add_lecture_desc = State()
    vip_add_lecture_subject = State()
    vip_add_lecture_price = State()
    vip_add_lecture_file = State()
    vip_delete_lecture = State()
    
    # حالات الشراء
    purchase_lecture_confirm = State()
    
    # حالات عامة
    referral_code = State()
    
    # حالات التقييم
    rate_lecture = State()
    rate_comment = State()

# ===================== إعداد البوت =====================
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ===================== وظائف مساعدة =====================
def format_balance(amount):
    """تنسيق المبالغ المالية"""
    return f"{amount:,} دينار"

def format_date(date_string):
    """تنسيق التاريخ"""
    if not date_string:
        return "غير محدد"
    
    try:
        if isinstance(date_string, str):
            date_obj = datetime.strptime(date_string, '%Y-%m-%d %H:%M:%S')
        else:
            date_obj = date_string
        
        return date_obj.strftime('%Y/%m/%d %H:%M')
    except:
        return date_string

async def check_access(user_id: int, service_name: str = None) -> Tuple[bool, str]:
    """التحقق من صلاحية الوصول للخدمة"""
    user = db.get_user(user_id)
    
    if not user:
        return False, "⚠️ المستخدم غير مسجل. الرجاء استخدام /start"
    
    if user['is_banned'] == 1:
        return False, "🚫 حسابك محظور. راجع الدعم الفني."
    
    # التحقق من وضع الصيانة
    if service_name and user['is_admin'] == 0:
        maintenance = db.get_setting('maintenance_mode')
        if maintenance == '1':
            return False, "🔧 البوت قيد الصيانة. الرجاء المحاولة لاحقاً."
    
    if service_name:
        # التحقق من تفعيل الخدمة
        if not db.is_service_active(service_name):
            return False, "⏸️ هذه الخدمة معطلة حالياً."
        
        # التحقق من الرصيد (عدا خدمات معينة)
        if service_name not in ['materials', 'balance', 'help_view']:
            price = db.get_service_price(service_name)
            if user['balance'] < price:
                return False, f"💰 رصيدك غير كافي. السعر: {format_balance(price)}"
    
    return True, ""

async def process_service_payment(user_id: int, service_name: str) -> Tuple[bool, str]:
    """معالجة دفع الخدمة"""
    price = db.get_service_price(service_name)
    
    if not db.deduct_for_service(user_id, service_name, price):
        return False, "❌ فشل في عملية الدفع. تأكد من رصيدك."
    
    return True, f"✅ تم خصم {format_balance(price)} من رصيدك."

async def send_notification(user_id: int, message: str):
    """إرسال إشعار للمستخدم"""
    try:
        await bot.send_message(user_id, f"🔔 {message}")
        db.add_notification(user_id, message)
    except:
        pass

async def create_pdf_from_text(text: str, filename: str) -> str:
    """إنشاء ملف PDF من النص"""
    try:
        pdf_path = f"summaries/{filename}.pdf"
        c = canvas.Canvas(pdf_path, pagesize=A4)
        width, height = A4
        
        # تقسيم النص إلى سطور
        lines = []
        current_line = ""
        words = text.split()
        
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if len(test_line) < 60:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        # كتابة النص في PDF
        y_position = height - 50
        for line in lines:
            if y_position < 50:
                c.showPage()
                y_position = height - 50
            
            c.setFont("Helvetica", 12)
            c.drawString(50, y_position, line[:80])
            y_position -= 20
        
        c.save()
        return pdf_path
    except Exception as e:
        logging.error(f"خطأ في إنشاء PDF: {e}")
        return None

async def summarize_with_ai(text: str) -> str:
    """تلخيص النص باستخدام الذكاء الاصطناعي"""
    if not model:
        return "عذراً، خدمة الذكاء الاصطناعي غير متاحة حالياً."
    
    try:
        prompt = f"""
        قم بتلخيص النص التالي بطريقة علمية ومنظمة:
        
        {text[:3000]}
        
        التلخيص يجب أن يكون:
        1. مختصراً مع الحفاظ على المعلومات المهمة
        2. منظم بعناوين رئيسية
        3. بلغة عربية فصحى
        4. خالٍ من المعلومات غير المهمة
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logging.error(f"خطأ في التلخيص: {e}")
        return "عذراً، حدث خطأ في التلخيص."

async def answer_question_with_ai(question: str) -> str:
    """الإجابة على الأسئلة باستخدام الذكاء الاصطناعي"""
    if not model:
        return "عذراً، خدمة الذكاء الاصطناعي غير متاحة حالياً."
    
    try:
        prompt = f"""
        أجب على السؤال التالي بطريقة علمية حسب المنهج العراقي:
        
        السؤال: {question}
        
        متطلبات الإجابة:
        1. كن دقيقاً علمياً
        2. قدم المعلومات حسب المنهج العراقي
        3. رتب الإجابة بشكل منطقي
        4. استخدم مصطلحات علمية صحيحة
        5. كن مفصلاً قدر الإمكان
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logging.error(f"خطأ في الإجابة: {e}")
        return "عذراً، حدث خطأ في الإجابة."

# ===================== لوحة التحكم =====================
async def admin_panel_keyboard() -> InlineKeyboardMarkup:
    """لوحة تحكم المدير"""
    keyboard = [
        [InlineKeyboardButton(text="📊 الإحصائيات", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 المستخدمين", callback_data="admin_users")],
        [InlineKeyboardButton(text="💰 الشحن والخصم", callback_data="admin_balance")],
        [InlineKeyboardButton(text="⚠️ الحظر والرفع", callback_data="admin_ban")],
        [InlineKeyboardButton(text="🛠️ إدارة الخدمات", callback_data="admin_services")],
        [InlineKeyboardButton(text="📢 الإذاعة", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔧 وضع الصيانة", callback_data="admin_maintenance")],
        [InlineKeyboardButton(text="🎬 محاضرات VIP", callback_data="admin_vip_lectures")],
        [InlineKeyboardButton(text="❓ أسئلة ساعدوني", callback_data="admin_help_questions")],
        [InlineKeyboardButton(text="💳 سحب أرباح", callback_data="admin_withdraw")],
        [InlineKeyboardButton(text="🏠 الرئيسية", callback_data="back_to_main")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def admin_users_keyboard() -> InlineKeyboardMarkup:
    """قائمة المستخدمين للمدير"""
    keyboard = [
        [InlineKeyboardButton(text="🔍 عرض مستخدم", callback_data="admin_view_user")],
        [InlineKeyboardButton(text="⛔ حظر مستخدم", callback_data="admin_ban_user")],
        [InlineKeyboardButton(text="✅ رفع الحظر", callback_data="admin_unban_user")],
        [InlineKeyboardButton(text="👑 رفع مشرف", callback_data="admin_make_admin")],
        [InlineKeyboardButton(text="👥 عرض VIP", callback_data="admin_view_vip")],
        [InlineKeyboardButton(text="📋 كل المستخدمين", callback_data="admin_all_users")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_back")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def admin_balance_keyboard() -> InlineKeyboardMarkup:
    """قائمة الشحن والخصم"""
    keyboard = [
        [InlineKeyboardButton(text="➕ شحن رصيد", callback_data="admin_charge")],
        [InlineKeyboardButton(text="➖ خصم رصيد", callback_data="admin_deduct")],
        [InlineKeyboardButton(text="💸 معاملات مستخدم", callback_data="admin_user_transactions")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_back")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def admin_services_keyboard() -> InlineKeyboardMarkup:
    """إدارة الخدمات"""
    keyboard = [
        [InlineKeyboardButton(text="💵 تغيير الأسعار", callback_data="admin_change_prices")],
        [InlineKeyboardButton(text="🚫 تعطيل/تفعيل خدمة", callback_data="admin_toggle_service")],
        [InlineKeyboardButton(text="📚 إضافة مادة", callback_data="admin_add_material")],
        [InlineKeyboardButton(text="🗑️ حذف مادة", callback_data="admin_delete_material")],
        [InlineKeyboardButton(text="🎬 إدارة محاضرات", callback_data="admin_manage_lectures")],
        [InlineKeyboardButton(text="🎓 إدارة اشتراكات", callback_data="admin_manage_subscriptions")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_back")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def services_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """لوحة الخدمات الرئيسية"""
    user = db.get_user(user_id)
    is_admin = user['is_admin'] if user else 0
    
    keyboard = []
    
    # إضافة زر لوحة التحكم للمدير
    if is_admin == 1:
        keyboard.append([InlineKeyboardButton(text="👑 لوحة التحكم", callback_data="admin_panel")])
    
    # الخدمات النشطة
    active_services = db.get_active_services()
    
    if 'exemption' in active_services:
        keyboard.append([InlineKeyboardButton(text=f"🧮 حساب درجة الإعفاء ({format_balance(active_services['exemption'])} دينار)", callback_data="service_exemption")])
    
    if 'summarize' in active_services:
        keyboard.append([InlineKeyboardButton(text=f"📄 تلخيص الملازم ({format_balance(active_services['summarize'])} دينار)", callback_data="service_summarize")])
    
    if 'qna' in active_services:
        keyboard.append([InlineKeyboardButton(text=f"❓ سؤال وجواب ({format_balance(active_services['qna'])} دينار)", callback_data="service_qna")])
    
    if 'help_student' in active_services:
        keyboard.append([InlineKeyboardButton(text=f"🙋 ساعدوني طالب ({format_balance(active_services['help_student'])} دينار)", callback_data="service_help_student")])
    
    keyboard.append([InlineKeyboardButton(text="📚 ملازمي ومرشحاتي (مجاناً)", callback_data="service_materials")])
    
    if 'vip_lecture' in active_services:
        keyboard.append([InlineKeyboardButton(text="🎬 محاضرات VIP", callback_data="vip_lectures")])
    
    if 'vip_subscription' in active_services:
        keyboard.append([InlineKeyboardButton(text="👑 اشتراك VIP", callback_data="vip_subscribe")])
    
    keyboard.append([InlineKeyboardButton(text="💰 رصيدي", callback_data="my_balance")])
    
    # إضافة أزرار القناة والدعم
    keyboard.append([
        InlineKeyboardButton(text="📢 قناة البوت", url=CHANNEL_USERNAME),
        InlineKeyboardButton(text="🆘 الدعم الفني", url=SUPPORT_USERNAME)
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def balance_keyboard() -> InlineKeyboardMarkup:
    """لوحة الرصيد"""
    keyboard = [
        [InlineKeyboardButton(text="💳 رصيدي الحالي", callback_data="balance_current")],
        [InlineKeyboardButton(text="📊 سجل العمليات", callback_data="balance_history")],
        [InlineKeyboardButton(text="👥 دعوة أصدقاء", callback_data="balance_referral")],
        [InlineKeyboardButton(text="💬 الدعم الفني", url=SUPPORT_USERNAME)],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_main")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def exemption_keyboard() -> InlineKeyboardMarkup:
    """لوحة حساب الإعفاء"""
    keyboard = [
        [InlineKeyboardButton(text="📊 احسب إعفائي", callback_data="exemption_calculate")],
        [InlineKeyboardButton(text="📖 كيفية الحساب؟", callback_data="exemption_howto")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_main")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def summarize_keyboard() -> InlineKeyboardMarkup:
    """لوحة تلخيص الملازم"""
    keyboard = [
        [InlineKeyboardButton(text="📤 ارسل ملف PDF", callback_data="summarize_upload")],
        [InlineKeyboardButton(text="ℹ️ كيفية التلخيص؟", callback_data="summarize_howto")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_main")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def qna_keyboard() -> InlineKeyboardMarkup:
    """لوحة سؤال وجواب"""
    keyboard = [
        [InlineKeyboardButton(text="✍️ اكتب سؤالك", callback_data="qna_text_input")],
        [InlineKeyboardButton(text="📸 ارسل صورة", callback_data="qna_image_input")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_main")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def help_student_keyboard() -> InlineKeyboardMarkup:
    """لوحة ساعدوني طالب"""
    keyboard = [
        [InlineKeyboardButton(text="💬 اطرح سؤالاً", callback_data="help_ask_question")],
        [InlineKeyboardButton(text="👁️ عرض الأسئلة", callback_data="help_view_questions")],
        [InlineKeyboardButton(text="💡 جاوب على سؤال", callback_data="help_answer_question")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_main")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def materials_keyboard() -> InlineKeyboardMarkup:
    """لوحة الملازم والمرشحات"""
    keyboard = [
        [InlineKeyboardButton(text="🏫 المرحلة الأولى", callback_data="materials_grade1")],
        [InlineKeyboardButton(text="🏫 المرحلة الثانية", callback_data="materials_grade2")],
        [InlineKeyboardButton(text="🏫 المرحلة الثالثة", callback_data="materials_grade3")],
        [InlineKeyboardButton(text="🏫 المرحلة الرابعة", callback_data="materials_grade4")],
        [InlineKeyboardButton(text="🔍 بحث عن مادة", callback_data="materials_search")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_main")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def vip_lectures_keyboard() -> InlineKeyboardMarkup:
    """لوحة محاضرات VIP"""
    keyboard = [
        [InlineKeyboardButton(text="🎥 عرض المحاضرات", callback_data="vip_view_lectures")],
        [InlineKeyboardButton(text="🔍 بحث محاضرة", callback_data="vip_search_lecture")],
        [InlineKeyboardButton(text="⭐ الأعلى تقييماً", callback_data="vip_top_rated")],
        [InlineKeyboardButton(text="👨‍🏫 محاضراتي المشتراة", callback_data="vip_my_purchases")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_main")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def vip_subscribe_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """لوحة اشتراك VIP"""
    user = db.get_user(user_id)
    is_vip = user['is_vip'] if user else 0
    vip_expiry = user['vip_expiry'] if user else None
    
    keyboard = []
    
    if is_vip == 1 and vip_expiry and datetime.strptime(vip_expiry, '%Y-%m-%d %H:%M:%S') > datetime.now():
        keyboard.append([InlineKeyboardButton(text="🎬 محاضراتي", callback_data="vip_my_lectures")])
        keyboard.append([InlineKeyboardButton(text="💸 أرباحي", callback_data="vip_my_earnings")])
        keyboard.append([InlineKeyboardButton(text="📝 تعديل بياناتي", callback_data="vip_edit_profile")])
    else:
        price = db.get_service_price('vip_subscription')
        keyboard.append([InlineKeyboardButton(text=f"👑 اشترك الآن ({format_balance(price)} دينار)", callback_data="vip_subscribe_now")])
    
    keyboard.append([InlineKeyboardButton(text="📋 شروط الاشتراك", callback_data="vip_terms")])
    keyboard.append([InlineKeyboardButton(text="💰 أسعار الاشتراك", callback_data="vip_prices")])
    keyboard.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ===================== معالجة الأوامر =====================
@dp.message(CommandStart())
async def cmd_start(message: Message):
    """معالجة أمر /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    # التحقق من كود الدعوة
    referred_by = None
    if len(message.text.split()) > 1:
        referral_code = message.text.split()[1]
        if referral_code.startswith('REF'):
            referred_by = referral_code[3:-4] if len(referral_code) > 7 else None
    
    # إضافة المستخدم
    db.add_user(user_id, username, first_name, last_name, referred_by)
    
    user = db.get_user(user_id)
    
    if user['is_banned'] == 1:
        await message.answer("🚫 حسابك محظور. راجع الدعم الفني.")
        return
    
    # عرض رسالة الترحيب
    welcome_text = f"""
    🎓 أهلاً بك في بوت <b>يلا نتعلم</b>!
    
    <b>خدمات البوت التعليمية:</b>
    • حساب درجة الإعفاء
    • تلخيص الملازم بالذكاء الاصطناعي
    • سؤال وجواب حسب المنهج العراقي
    • قسم ساعدوني طالب
    • مكتبة الملازم والمرشحات
    • محاضرات VIP للمحاضرين
    
    <b>رصيدك الحالي:</b> {format_balance(user['balance'])}
    <b>هدية الترحيب:</b> {format_balance(int(db.get_setting('welcome_bonus') or 1000))} ✓
    
    اختر الخدمة التي تريدها من القائمة:
    """
    
    keyboard = await services_keyboard(user_id)
    await message.answer(welcome_text, reply_markup=keyboard)

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    """لوحة تحكم المدير"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user or user['is_admin'] != 1:
        await message.answer("⛔ ليس لديك صلاحية الوصول.")
        return
    
    keyboard = await admin_panel_keyboard()
    await message.answer("<b>👑 لوحة تحكم المدير</b>", reply_markup=keyboard)

@dp.message(Command("balance"))
async def cmd_balance(message: Message):
    """عرض الرصيد"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await message.answer("⚠️ الرجاء استخدام /start أولاً")
        return
    
    if user['is_banned'] == 1:
        await message.answer("🚫 حسابك محظور. راجع الدعم الفني.")
        return
    
    balance_text = f"""
    💰 <b>معلومات الرصيد</b>
    
    <b>الرصيد الحالي:</b> {format_balance(user['balance'])}
    <b>إجمالي المصروف:</b> {format_balance(user['total_spent'])}
    
    اختر الخدمة:
    """
    
    keyboard = await balance_keyboard()
    await message.answer(balance_text, reply_markup=keyboard)

# ===================== معالجة Callback Queries =====================
@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(callback_query: CallbackQuery):
    """العودة للقائمة الرئيسية"""
    user_id = callback_query.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback_query.answer("الرجاء استخدام /start أولاً")
        return
    
    if user['is_banned'] == 1:
        await callback_query.answer("حسابك محظور")
        return
    
    welcome_text = f"""
    🎓 <b>مرحباً بك مجدداً في يلا نتعلم!</b>
    
    <b>رصيدك الحالي:</b> {format_balance(user['balance'])}
    
    اختر الخدمة التي تريدها:
    """
    
    keyboard = await services_keyboard(user_id)
    await callback_query.message.edit_text(welcome_text, reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "admin_panel")
async def admin_panel_callback(callback_query: CallbackQuery):
    """لوحة تحكم المدير من الكالباك"""
    user_id = callback_query.from_user.id
    user = db.get_user(user_id)
    
    if not user or user['is_admin'] != 1:
        await callback_query.answer("⛔ ليس لديك صلاحية")
        return
    
    keyboard = await admin_panel_keyboard()
    await callback_query.message.edit_text("<b>👑 لوحة تحكم المدير</b>", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "admin_back")
async def admin_back_callback(callback_query: CallbackQuery):
    """العودة للوحة تحكم المدير"""
    user_id = callback_query.from_user.id
    user = db.get_user(user_id)
    
    if not user or user['is_admin'] != 1:
        await callback_query.answer("⛔ ليس لديك صلاحية")
        return
    
    keyboard = await admin_panel_keyboard()
    await callback_query.message.edit_text("<b>👑 لوحة تحكم المدير</b>", reply_markup=keyboard)

# ===================== معالجة الخدمات =====================
@dp.callback_query(lambda c: c.data == "service_exemption")
async def service_exemption_callback(callback_query: CallbackQuery):
    """خدمة حساب الإعفاء"""
    user_id = callback_query.from_user.id
    
    # التحقق من الوصول
    access, message = await check_access(user_id, "exemption")
    if not access:
        await callback_query.answer(message)
        return
    
    text = f"""
    🧮 <b>حساب درجة الإعفاء الفردي</b>
    
    أدخل درجات الكورسات الثلاثة:
    • الكورس الأول
    • الكورس الثاني  
    • الكورس الثالث
    
    <b>شرط الإعفاء:</b> المعدل ≥ 90
    <b>سعر الخدمة:</b> {format_balance(db.get_service_price('exemption'))}
    
    اضغط على <b>احسب إعفائي</b> للبدء:
    """
    
    keyboard = await exemption_keyboard()
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "exemption_calculate")
async def exemption_calculate_callback(callback_query: CallbackQuery, state: FSMContext):
    """بدء عملية حساب الإعفاء"""
    user_id = callback_query.from_user.id
    
    # التحقق من الدفع
    success, message = await process_service_payment(user_id, "exemption")
    if not success:
        await callback_query.answer(message)
        return
    
    await state.set_state(Form.exemption_course1)
    
    text = """
    <b>الخطوة 1/3</b>
    
    أدخل درجة الكورس الأول (0-100):
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 إلغاء", callback_data="back_to_main")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@dp.message(Form.exemption_course1)
async def process_course1(message: Message, state: FSMContext):
    """معالجة درجة الكورس الأول"""
    try:
        grade = float(message.text)
        if 0 <= grade <= 100:
            await state.update_data(course1=grade)
            await state.set_state(Form.exemption_course2)
            
            text = """
            <b>الخطوة 2/3</b>
            
            أدخل درجة الكورس الثاني (0-100):
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 إلغاء", callback_data="back_to_main")]
            ])
            
            await message.answer(text, reply_markup=keyboard)
        else:
            await message.answer("❌ الرجاء إدخال درجة بين 0 و 100")
    except ValueError:
        await message.answer("❌ الرجاء إدخال رقم صحيح")

@dp.message(Form.exemption_course2)
async def process_course2(message: Message, state: FSMContext):
    """معالجة درجة الكورس الثاني"""
    try:
        grade = float(message.text)
        if 0 <= grade <= 100:
            await state.update_data(course2=grade)
            await state.set_state(Form.exemption_course3)
            
            text = """
            <b>الخطوة 3/3</b>
            
            أدخل درجة الكورس الثالث (0-100):
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 إلغاء", callback_data="back_to_main")]
            ])
            
            await message.answer(text, reply_markup=keyboard)
        else:
            await message.answer("❌ الرجاء إدخال درجة بين 0 و 100")
    except ValueError:
        await message.answer("❌ الرجاء إدخال رقم صحيح")

@dp.message(Form.exemption_course3)
async def process_course3(message: Message, state: FSMContext):
    """معالجة درجة الكورس الثالث وحساب المعدل"""
    try:
        grade = float(message.text)
        if 0 <= grade <= 100:
            data = await state.get_data()
            course1 = data.get('course1', 0)
            course2 = data.get('course2', 0)
            course3 = grade
            
            # حساب المعدل
            average = (course1 + course2 + course3) / 3
            
            # تحديد الإعفاء
            if average >= 90:
                result = "🎉 <b>مبروك! أنت معفي من المادة</b>"
                emoji = "✅"
            else:
                result = "❌ <b>أنت غير معفي من المادة</b>"
                emoji = "⚠️"
            
            text = f"""
            {emoji} <b>نتيجة حساب الإعفاء</b>
            
            <b>الدرجات المدخلة:</b>
            • الكورس الأول: {course1}
            • الكورس الثاني: {course2}
            • الكورس الثالث: {course3}
            
            <b>المعدل النهائي:</b> {average:.2f}
            
            {result}
            
            <b>شرط الإعفاء:</b> المعدل ≥ 90
            """
            
            await state.clear()
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 الرئيسية", callback_data="back_to_main")]
            ])
            
            await message.answer(text, reply_markup=keyboard)
        else:
            await message.answer("❌ الرجاء إدخال درجة بين 0 و 100")
    except ValueError:
        await message.answer("❌ الرجاء إدخال رقم صحيح")

@dp.callback_query(lambda c: c.data == "service_summarize")
async def service_summarize_callback(callback_query: CallbackQuery):
    """خدمة تلخيص الملازم"""
    user_id = callback_query.from_user.id
    
    # التحقق من الوصول
    access, message = await check_access(user_id, "summarize")
    if not access:
        await callback_query.answer(message)
        return
    
    text = f"""
    📄 <b>تلخيص الملازم بالذكاء الاصطناعي</b>
    
    <b>المميزات:</b>
    • تلخيص احترافي للملازم
    • حذف المعلومات غير المهمة
    • تنظيم النص بشكل منطقي
    • إخراج PDF مرتب
    
    <b>سعر الخدمة:</b> {format_balance(db.get_service_price('summarize'))}
    
    اضغط على <b>ارسل ملف PDF</b> لبدء التلخيص:
    """
    
    keyboard = await summarize_keyboard()
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "summarize_upload")
async def summarize_upload_callback(callback_query: CallbackQuery, state: FSMContext):
    """طلب رفع ملف PDF"""
    user_id = callback_query.from_user.id
    
    # التحقق من الدفع
    success, message = await process_service_payment(user_id, "summarize")
    if not success:
        await callback_query.answer(message)
        return
    
    await state.set_state(Form.summarize_pdf)
    
    text = """
    <b>رفع ملف PDF للتلخيص</b>
    
    <b>الشروط:</b>
    1. الملف بصيغة PDF فقط
    2. حجم الملف لا يتعدى 20MB
    3. النص داخل الملف واضح
    4. الملف غير محمي بكلمة سر
    
    قم بإرسال ملف PDF الآن:
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 إلغاء", callback_data="back_to_main")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@dp.message(Form.summarize_pdf)
async def process_pdf_summary(message: Message, state: FSMContext):
    """معالجة ملف PDF والتلخيص"""
    if not message.document:
        await message.answer("❌ الرجاء إرسال ملف PDF")
        return
    
    if not message.document.file_name.endswith('.pdf'):
        await message.answer("❌ الملف يجب أن يكون بصيغة PDF")
        return
    
    # إرسال رسالة الانتظار
    wait_msg = await message.answer("⏳ جاري معالجة الملف وتلخيصه...")
    
    try:
        # تحميل الملف
        file = await bot.get_file(message.document.file_id)
        file_bytes = await bot.download_file(file.file_path)
        
        # استخراج النص من PDF
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        
        if not text or len(text) < 50:
            await wait_msg.delete()
            await message.answer("❌ لا يمكن قراءة النص من الملف. تأكد أن الملف يحتوي على نص قابل للقراءة.")
            await state.clear()
            return
        
        # تلخيص النص باستخدام الذكاء الاصطناعي
        summary = await summarize_with_ai(text[:3000])  # أرسل أول 3000 حرف فقط
        
        if not summary:
            await wait_msg.delete()
            await message.answer("❌ حدث خطأ في التلخيص. الرجاء المحاولة لاحقاً.")
            await state.clear()
            return
        
        # إنشاء ملف PDF من التلخيص
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"summary_{message.from_user.id}_{timestamp}"
        pdf_path = await create_pdf_from_text(summary, pdf_filename)
        
        if not pdf_path:
            await wait_msg.delete()
            await message.answer("❌ حدث خطأ في إنشاء ملف PDF.")
            await state.clear()
            return
        
        await wait_msg.delete()
        
        # إرسال الملف
        with open(pdf_path, 'rb') as pdf_file:
            await message.answer_document(
                InputFile(pdf_file, filename=f"ملخص_{timestamp}.pdf"),
                caption="✅ <b>تم تلخيص الملف بنجاح</b>\n\n📄 الملف جاهز للتحميل"
            )
        
        await state.clear()
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 الرئيسية", callback_data="back_to_main")]
        ])
        
        await message.answer("📄 تم إرسال الملف الملخص. هل تريد خدمة أخرى؟", reply_markup=keyboard)
        
    except Exception as e:
        logging.error(f"خطأ في تلخيص PDF: {e}")
        await wait_msg.delete()
        await message.answer("❌ حدث خطأ غير متوقع. الرجاء المحاولة لاحقاً.")
        await state.clear()

@dp.callback_query(lambda c: c.data == "service_qna")
async def service_qna_callback(callback_query: CallbackQuery):
    """خدمة سؤال وجواب"""
    user_id = callback_query.from_user.id
    
    # التحقق من الوصول
    access, message = await check_access(user_id, "qna")
    if not access:
        await callback_query.answer(message)
        return
    
    text = f"""
    ❓ <b>سؤال وجواب بالذكاء الاصطناعي</b>
    
    <b>المميزات:</b>
    • إجابات علمية دقيقة
    • حسب المنهج العراقي
    • إجابات مفصلة ومنظمة
    
    <b>سعر الخدمة:</b> {format_balance(db.get_service_price('qna'))}
    
    اختر طريقة إدخال السؤال:
    """
    
    keyboard = await qna_keyboard()
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "qna_text_input")
async def qna_text_input_callback(callback_query: CallbackQuery, state: FSMContext):
    """إدخال سؤال نصي"""
    user_id = callback_query.from_user.id
    
    # التحقق من الدفع
    success, message = await process_service_payment(user_id, "qna")
    if not success:
        await callback_query.answer(message)
        return
    
    await state.set_state(Form.qna_text)
    
    text = """
    <b>إدخال السؤال النصي</b>
    
    اكتب سؤالك العلمي واضغط إرسال:
    
    <b>ملاحظة:</b> يجب أن يكون السؤال واضحاً ومحدداً للحصول على إجابة أفضل.
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 إلغاء", callback_data="back_to_main")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@dp.message(Form.qna_text)
async def process_qna_text(message: Message, state: FSMContext):
    """معالجة السؤال النصي"""
    question = message.text
    
    if len(question) < 5:
        await message.answer("❌ السؤال قصير جداً. الرجاء كتابة سؤال مفصّل.")
        return
    
    # إرسال رسالة الانتظار
    wait_msg = await message.answer("⏳ جاري البحث عن الإجابة...")
    
    try:
        # الحصول على الإجابة من الذكاء الاصطناعي
        answer = await answer_question_with_ai(question)
        
        await wait_msg.delete()
        
        if not answer:
            await message.answer("❌ لم أتمكن من العثور على إجابة مناسبة.")
            await state.clear()
            return
        
        # تقليم الإجابة إذا كانت طويلة جداً
        if len(answer) > 4000:
            answer = answer[:4000] + "\n\n... (تم تقليم الإجابة بسبب الطول)"
        
        text = f"""
        ❓ <b>السؤال:</b>
        {question}
        
        💡 <b>الإجابة:</b>
        {answer}
        
        <b>ملاحظة:</b> هذه الإجابة مقدمة بواسطة الذكاء الاصطناعي بناءً على المعلومات المتاحة.
        """
        
        await state.clear()
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 الرئيسية", callback_data="back_to_main")]
        ])
        
        await message.answer(text, reply_markup=keyboard)
        
    except Exception as e:
        logging.error(f"خطأ في الإجابة على السؤال: {e}")
        await wait_msg.delete()
        await message.answer("❌ حدث خطأ في معالجة السؤال. الرجاء المحاولة لاحقاً.")
        await state.clear()

@dp.callback_query(lambda c: c.data == "service_help_student")
async def service_help_student_callback(callback_query: CallbackQuery):
    """خدمة ساعدوني طالب"""
    user_id = callback_query.from_user.id
    
    # التحقق من الوصول
    access, message = await check_access(user_id, "help_student")
    if not access:
        await callback_query.answer(message)
        return
    
    text = f"""
    🙋 <b>ساعدوني طالب</b>
    
    <b>فكرة الخدمة:</b>
    • اطرح سؤالاً وادفع {format_balance(db.get_service_price('help_student'))}
    • السؤال يعرض على الطلاب الآخرين
    • من يجيب يحصل على {format_balance(int(db.get_setting('answer_reward') or 100))} مكافأة
    • الإجابة ترسل لك مباشرة
    
    <b>ملاحظة:</b> السؤال يحتاج موافقة الإدارة قبل النشر.
    """
    
    keyboard = await help_student_keyboard()
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "help_ask_question")
async def help_ask_question_callback(callback_query: CallbackQuery, state: FSMContext):
    """طرح سؤال في ساعدوني طالب"""
    user_id = callback_query.from_user.id
    
    # التحقق من الدفع
    success, message = await process_service_payment(user_id, "help_student")
    if not success:
        await callback_query.answer(message)
        return
    
    await state.set_state(Form.help_question)
    
    text = f"""
    <b>طرح سؤال جديد</b>
    
    اكتب سؤالك واضغط إرسال:
    
    <b>شروط النشر:</b>
    1. يجب أن يكون السؤال علمياً
    2. لا يحتوي على إساءة أو ألفاظ غير لائقة
    3. واضح ومحدد
    4. متعلق بالمنهج الدراسي
    
    <b>مكافأة المجيب:</b> {format_balance(int(db.get_setting('answer_reward') or 100))}
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 إلغاء", callback_data="back_to_main")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@dp.message(Form.help_question)
async def process_help_question(message: Message, state: FSMContext):
    """معالجة سؤال ساعدوني طالب"""
    question = message.text
    
    if len(question) < 10:
        await message.answer("❌ السؤال قصير جداً. الرجاء كتابة سؤال مفصّل.")
        return
    
    # حفظ السؤال في قاعدة البيانات
    price = db.get_service_price('help_student')
    question_id = db.add_help_question(message.from_user.id, question, price)
    
    text = f"""
    ✅ <b>تم إرسال سؤالك</b>
    
    <b>رقم السؤال:</b> #{question_id}
    <b>حالة السؤال:</b> قيد المراجعة
    
    <b>ملاحظة:</b> سوف يتم مراجعة سؤالك من قبل الإدارة قبل النشر.
    عند الموافقة، سيعرض السؤال للطلاب الآخرين للإجابة.
    
    ستحصل على إجابة مباشرة عندما يجيب أحد الطلاب.
    """
    
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 الرئيسية", callback_data="back_to_main")]
    ])
    
    await message.answer(text, reply_markup=keyboard)
    
    # إرسال إشعار للمدير
    admin_text = f"""
    📋 <b>سؤال جديد يحتاج موافقة</b>
    
    <b>رقم السؤال:</b> #{question_id}
    <b>المستخدم:</b> @{message.from_user.username or 'بدون يوزر'}
    <b>الاسم:</b> {message.from_user.first_name}
    <b>الآيدي:</b> {message.from_user.id}
    
    <b>السؤال:</b>
    {question}
    
    <b>للموافقة:</b> /approve_question {question_id}
    <b>للرفض:</b> /reject_question {question_id}
    """
    
    await bot.send_message(ADMIN_ID, admin_text)

# ===================== معالجة المدير =====================
@dp.callback_query(lambda c: c.data == "admin_charge")
async def admin_charge_callback(callback_query: CallbackQuery, state: FSMContext):
    """شحن رصيد للمدير"""
    user_id = callback_query.from_user.id
    user = db.get_user(user_id)
    
    if not user or user['is_admin'] != 1:
        await callback_query.answer("⛔ ليس لديك صلاحية")
        return
    
    await state.set_state(Form.admin_charge_user)
    
    text = """
    <b>شحن رصيد - المدير</b>
    
    <b>أدخل آيدي المستخدم:</b>
    
    <b>ملاحظة:</b> سوف تطلب منك إدخال المبلغ في الخطوة التالية.
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 إلغاء", callback_data="admin_back")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@dp.message(Form.admin_charge_user)
async def admin_charge_user_process(message: Message, state: FSMContext):
    """معالجة آيدي المستخدم للشحن"""
    try:
        target_user_id = int(message.text)
        target_user = db.get_user(target_user_id)
        
        if not target_user:
            await message.answer("❌ لم يتم العثور على المستخدم")
            await state.clear()
            return
        
        await state.update_data(charge_user_id=target_user_id)
        await state.set_state(Form.admin_charge_amount)
        
        text = f"""
        <b>شحن رصيد - الخطوة 2</b>
        
        <b>المستخدم:</b> {target_user_id}
        <b>الاسم:</b> {target_user['first_name']} {target_user['last_name'] or ''}
        <b>الرصيد الحالي:</b> {format_balance(target_user['balance'])}
        
        <b>أدخل المبلغ للشحن (بالدينار):</b>
        """
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 إلغاء", callback_data="admin_back")]
        ])
        
        await message.answer(text, reply_markup=keyboard)
        
    except ValueError:
        await message.answer("❌ الرجاء إدخال آيدي صحيح")

@dp.message(Form.admin_charge_amount)
async def admin_charge_amount_process(message: Message, state: FSMContext):
    """معالجة مبلغ الشحن"""
    try:
        amount = int(message.text)
        if amount <= 0:
            await message.answer("❌ المبلغ يجب أن يكون أكبر من صفر")
            await state.clear()
            return
        
        data = await state.get_data()
        target_user_id = data.get('charge_user_id')
        
        if not target_user_id:
            await message.answer("❌ خطأ في البيانات")
            await state.clear()
            return
        
        # شحن الرصيد
        new_balance = db.update_balance(target_user_id, amount, 'add', 
                                       f'شحن من المدير {message.from_user.id}')
        
        if new_balance is not None:
            text = f"""
            ✅ <b>تم شحن الرصيد بنجاح</b>
            
            <b>المستخدم:</b> {target_user_id}
            <b>المبلغ:</b> {format_balance(amount)}
            <b>الرصيد الجديد:</b> {format_balance(new_balance)}
            """
            
            # إرسال إشعار للمستخدم
            await send_notification(target_user_id, f"تم شحن رصيدك بمبلغ {format_balance(amount)} من الإدارة. الرصيد الجديد: {format_balance(new_balance)}")
        else:
            text = "❌ فشل في شحن الرصيد"
        
        await state.clear()
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 لوحة التحكم", callback_data="admin_back")]
        ])
        
        await message.answer(text, reply_markup=keyboard)
        
    except ValueError:
        await message.answer("❌ الرجاء إدخال رقم صحيح")

@dp.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats_callback(callback_query: CallbackQuery):
    """إحصائيات البوت للمدير"""
    user_id = callback_query.from_user.id
    user = db.get_user(user_id)
    
    if not user or user['is_admin'] != 1:
        await callback_query.answer("⛔ ليس لديك صلاحية")
        return
    
    stats = db.get_statistics()
    
    text = f"""
    📊 <b>إحصائيات البوت - المدير</b>
    
    <b>المستخدمين:</b>
    • إجمالي المستخدمين: {stats['total_users']}
    • نشط اليوم: {stats['active_today']}
    • مشتركين VIP: {stats['vip_users']}
    
    <b>المالية:</b>
    • إجمالي الرصيد: {format_balance(stats['total_balance'])}
    • إجمالي الإيرادات: {format_balance(stats['total_revenue'])}
    • إجمالي المشتريات: {stats['total_purchases']}
    
    <b>المحتوى:</b>
    • المحاضرات المعتمدة: {stats['total_lectures']}
    
    <b>النظام:</b>
    • وضع الصيانة: {'✅ مفعل' if db.get_setting('maintenance_mode') == '1' else '❌ معطل'}
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 تحديث", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📈 تفاصيل مالية", callback_data="admin_financial_stats")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_back")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "admin_users")
async def admin_users_callback(callback_query: CallbackQuery):
    """إدارة المستخدمين للمدير"""
    user_id = callback_query.from_user.id
    user = db.get_user(user_id)
    
    if not user or user['is_admin'] != 1:
        await callback_query.answer("⛔ ليس لديك صلاحية")
        return
    
    keyboard = await admin_users_keyboard()
    await callback_query.message.edit_text("<b>👥 إدارة المستخدمين</b>", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "admin_balance")
async def admin_balance_callback(callback_query: CallbackQuery):
    """إدارة الرصيد للمدير"""
    user_id = callback_query.from_user.id
    user = db.get_user(user_id)
    
    if not user or user['is_admin'] != 1:
        await callback_query.answer("⛔ ليس لديك صلاحية")
        return
    
    keyboard = await admin_balance_keyboard()
    await callback_query.message.edit_text("<b>💰 إدارة الرصيد</b>", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "admin_services")
async def admin_services_callback(callback_query: CallbackQuery):
    """إدارة الخدمات للمدير"""
    user_id = callback_query.from_user.id
    user = db.get_user(user_id)
    
    if not user or user['is_admin'] != 1:
        await callback_query.answer("⛔ ليس لديك صلاحية")
        return
    
    keyboard = await admin_services_keyboard()
    await callback_query.message.edit_text("<b>🛠️ إدارة الخدمات</b>", reply_markup=keyboard)

# ===================== نظام VIP =====================
@dp.callback_query(lambda c: c.data == "vip_subscribe")
async def vip_subscribe_callback(callback_query: CallbackQuery):
    """قسم اشتراك VIP"""
    user_id = callback_query.from_user.id
    
    keyboard = await vip_subscribe_keyboard(user_id)
    await callback_query.message.edit_text("<b>👑 اشتراك VIP</b>", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "vip_subscribe_now")
async def vip_subscribe_now_callback(callback_query: CallbackQuery):
    """اشتراك VIP"""
    user_id = callback_query.from_user.id
    
    # التحقق من الوصول
    access, message = await check_access(user_id, "vip_subscription")
    if not access:
        await callback_query.answer(message)
        return
    
    price = db.get_service_price('vip_subscription')
    
    text = f"""
    <b>👑 تأكيد اشتراك VIP</b>
    
    <b>تفاصيل الاشتراك:</b>
    • المدة: 30 يوم
    • السعر: {format_balance(price)}
    • الرصيد الحالي: {format_balance(db.get_user(user_id)['balance'])}
    
    <b>مميزات الاشتراك:</b>
    • رفع محاضرات VIP
    • أرباح 60% من مبيعات المحاضرات
    • لوحة تحكم خاصة
    • دعم فني مميز
    
    هل تريد المتابعة؟
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ نعم، اشترك الآن", callback_data="vip_subscribe_confirm")],
        [InlineKeyboardButton(text="❌ لا، إلغاء", callback_data="vip_subscribe")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "vip_subscribe_confirm")
async def vip_subscribe_confirm_callback(callback_query: CallbackQuery):
    """تأكيد اشتراك VIP"""
    user_id = callback_query.from_user.id
    
    # الخصم والتسجيل
    success, message = await process_service_payment(user_id, "vip_subscription")
    if not success:
        await callback_query.answer(message)
        return
    
    # تحديث حالة VIP للمستخدم
    expiry_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    cursor = db.conn.cursor()
    cursor.execute('UPDATE users SET is_vip = 1, vip_expiry = ? WHERE user_id = ?', 
                  (expiry_date, user_id))
    db.conn.commit()
    
    text = f"""
    ✅ <b>تم الاشتراك في VIP بنجاح</b>
    
    <b>تفاصيل الاشتراك:</b>
    • المدة: 30 يوم
    • تاريخ الانتهاء: {format_date(expiry_date)}
    • المبلغ المدفوع: {format_balance(db.get_service_price('vip_subscription'))}
    
    <b>مميزاتك الجديدة:</b>
    • ✓ رفع محاضرات VIP
    • ✓ تحصيل أرباح 60%
    • ✓ لوحة تحكم خاصة
    • ✓ دعم فني مميز
    
    <b>لبدء رفع المحاضرات:</b> اضغط على زر "محاضراتي"
    """
    
    keyboard = await vip_subscribe_keyboard(user_id)
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "vip_my_lectures")
async def vip_my_lectures_callback(callback_query: CallbackQuery):
    """محاضراتي (للمحاضر VIP)"""
    user_id = callback_query.from_user.id
    user = db.get_user(user_id)
    
    if not user or user['is_vip'] == 0:
        await callback_query.answer("⛔ هذه الخدمة للمشتركين في VIP فقط")
        return
    
    text = """
    🎬 <b>محاضراتي - لوحة المحاضر</b>
    
    <b>اختر الإجراء:</b>
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ رفع محاضرة جديدة", callback_data="vip_add_lecture")],
        [InlineKeyboardButton(text="🗑️ حذف محاضرة", callback_data="vip_delete_lecture")],
        [InlineKeyboardButton(text="📊 إحصائيات محاضراتي", callback_data="vip_lecture_stats")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="vip_subscribe")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "vip_add_lecture")
async def vip_add_lecture_callback(callback_query: CallbackQuery, state: FSMContext):
    """بدء عملية رفع محاضرة جديدة"""
    await state.set_state(Form.vip_add_lecture_title)
    
    text = """
    <b>رفع محاضرة جديدة - الخطوة 1/5</b>
    
    <b>أدخل عنوان المحاضرة:</b>
    
    <b>مثال:</b> "شرح التفاضل والتكامل - الجزء الأول"
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 إلغاء", callback_data="vip_my_lectures")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@dp.message(Form.vip_add_lecture_title)
async def process_vip_title(message: Message, state: FSMContext):
    """معالجة عنوان المحاضرة"""
    title = message.text
    
    if len(title) < 5:
        await message.answer("❌ العنوان قصير جداً. الرجاء إدخال عنوان واضح.")
        return
    
    await state.update_data(title=title)
    await state.set_state(Form.vip_add_lecture_desc)
    
    text = """
    <b>رفع محاضرة جديدة - الخطوة 2/5</b>
    
    <b>أدخل وصف المحاضرة:</b>
    
    <b>مثال:</b> "هذه المحاضرة تغطي أساسيات التفاضل والتكامل مع أمثلة تطبيقية"
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 إلغاء", callback_data="vip_my_lectures")]
    ])
    
    await message.answer(text, reply_mup=keyboard)

# (يتم استكمال باقي الكود - محاذرات VIP، نظام الأرباح، الإذاعة، إدارة المواد، وغيرها...)

# ===================== التشغيل الرئيسي =====================
async def main():
    """الدالة الرئيسية"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # بدء البوت
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
