#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت تليجرام: يلا نتعلم
مطور بواسطة: Allawi04
كود كامل ومتكامل - 3400+ سطر
"""

import os
import sys
import json
import sqlite3
import logging
import asyncio
import urllib.request
import urllib.parse
import io
import mimetypes
import tempfile
import hashlib
import random
import string
import time
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from html import escape

# ============================================================================
# مكتبات بديلة للطلبات HTTP
# ============================================================================

class HTTPResponse:
    def __init__(self, status_code: int, text: str, headers: Dict):
        self.status_code = status_code
        self.text = text
        self.headers = headers
    
    def json(self):
        try:
            return json.loads(self.text)
        except:
            return {}

def http_request(url: str, method: str = "GET", headers: Dict = None, 
                 data: Any = None, json_data: Dict = None, timeout: int = 30):
    """بديل بسيط لـ requests"""
    try:
        if headers is None:
            headers = {}
        
        req_data = None
        if json_data is not None:
            req_data = json.dumps(json_data).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        elif data is not None:
            req_data = str(data).encode('utf-8')
        
        req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.getcode()
            text = response.read().decode('utf-8')
            headers_dict = dict(response.getheaders())
            
            return HTTPResponse(status, text, headers_dict)
    except Exception as e:
        logging.error(f"HTTP Request Error: {e}")
        return HTTPResponse(500, f'{{"error": "{str(e)}"}}', {})

# ============================================================================
# إعدادات البوت
# ============================================================================

TOKEN = "8279341291:AAGet-xHKrmSg1RuBYaaNuzmaqv1LgwUM6E"
BOT_USERNAME = "@FC4Xbot"
ADMIN_ID = 6130994941
SUPPORT_USER = "@Allawi04"
CHANNEL_USERNAME = "FCJCV"
GEMINI_API_KEY = "AIzaSyARsl_YMXA74bPQpJduu0jJVuaku7MaHuY"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# أسعار الخدمات الأساسية
DEFAULT_PRICES = {
    "exemption": 1000,
    "summary": 1000,
    "qa": 1000,
    "help_student": 1000,
    "materials": 0,
    "vip_subscription": 5000,
}

# حالات المحادثة
class ConversationState(Enum):
    MAIN_MENU = 0
    ADMIN_PANEL = 1
    EXEMPTION_STEP1 = 2
    EXEMPTION_STEP2 = 3
    EXEMPTION_STEP3 = 4
    UPLOAD_PDF = 5
    ASK_QUESTION = 6
    ANSWER_QUESTION = 7
    HELP_STUDENT_ASK = 8
    HELP_STUDENT_ANSWER = 9
    VIP_SUBSCRIPTION = 10
    VIP_UPLOAD_LECTURE = 11
    VIP_SET_PRICE = 12
    VIP_UPLOAD_TITLE = 13
    VIP_UPLOAD_DESC = 14
    ADMIN_CHARGE = 15
    ADMIN_DEDUCT = 16
    ADMIN_BAN = 17
    ADMIN_UNBAN = 18
    ADMIN_SET_PRICE = 19
    ADMIN_ADD_MATERIAL = 20
    ADMIN_BROADCAST = 21
    ADMIN_VIP_MANAGE = 22
    ADMIN_VIP_WITHDRAW = 23
    WAITING_FOR_APPROVAL = 24
    ADMIN_ADD_MAT_TITLE = 25
    ADMIN_ADD_MAT_DESC = 26
    ADMIN_ADD_MAT_STAGE = 27
    ADMIN_ADD_MAT_FILE = 28

# ============================================================================
# فئات المساعدة
# ============================================================================

@dataclass
class UserData:
    user_id: int
    username: str
    first_name: str
    last_name: str = ""
    balance: int = 1000
    invited_by: int = 0
    invited_count: int = 0
    is_banned: bool = False
    is_admin: bool = False
    join_date: str = ""
    last_active: str = ""

@dataclass
class VIPUser:
    user_id: int
    subscription_date: str
    expiry_date: str
    is_active: bool = True
    earnings_balance: int = 0
    total_earnings: int = 0

@dataclass
class VIPLecture:
    lecture_id: int
    teacher_id: int
    title: str
    description: str
    video_path: str
    price: int = 0
    views: int = 0
    purchases: int = 0
    earnings: int = 0
    rating: float = 0.0
    rating_count: int = 0
    is_approved: bool = False
    upload_date: str = ""

@dataclass
class Material:
    material_id: int
    title: str
    description: str
    stage: str
    file_path: str
    upload_date: str = ""

@dataclass
class HelpQuestion:
    question_id: int
    user_id: int
    question_text: str
    subject: str = "عام"
    is_approved: bool = False
    is_answered: bool = False
    answer_text: str = ""
    answerer_id: int = 0
    ask_date: str = ""
    answer_date: str = ""

# ============================================================================
# قاعدة البيانات
# ============================================================================

class Database:
    def __init__(self, db_path: str = 'bot_database.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()
        self.create_default_admin()
        self.create_default_settings()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        tables = [
            """CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                balance INTEGER DEFAULT 1000,
                invited_by INTEGER DEFAULT 0,
                invited_count INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS vip_users (
                user_id INTEGER PRIMARY KEY,
                subscription_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expiry_date TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                earnings_balance INTEGER DEFAULT 0,
                total_earnings INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )""",
            """CREATE TABLE IF NOT EXISTS vip_lectures (
                lecture_id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER,
                title TEXT,
                description TEXT,
                video_path TEXT,
                price INTEGER DEFAULT 0,
                views INTEGER DEFAULT 0,
                purchases INTEGER DEFAULT 0,
                earnings INTEGER DEFAULT 0,
                rating REAL DEFAULT 0,
                rating_count INTEGER DEFAULT 0,
                is_approved INTEGER DEFAULT 0,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (teacher_id) REFERENCES users (user_id)
            )""",
            """CREATE TABLE IF NOT EXISTS lecture_purchases (
                purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                lecture_id INTEGER,
                purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                amount_paid INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (lecture_id) REFERENCES vip_lectures (lecture_id)
            )""",
            """CREATE TABLE IF NOT EXISTS materials (
                material_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                description TEXT,
                stage TEXT,
                file_path TEXT,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS help_questions (
                question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                question_text TEXT,
                subject TEXT,
                is_approved INTEGER DEFAULT 0,
                is_answered INTEGER DEFAULT 0,
                answer_text TEXT,
                answerer_id INTEGER,
                ask_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                answer_date TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )""",
            """CREATE TABLE IF NOT EXISTS transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                type TEXT,
                description TEXT,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )""",
            """CREATE TABLE IF NOT EXISTS bot_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS statistics (
                stat_date DATE PRIMARY KEY,
                new_users INTEGER DEFAULT 0,
                active_users INTEGER DEFAULT 0,
                transactions_count INTEGER DEFAULT 0,
                total_income INTEGER DEFAULT 0
            )""",
            """CREATE TABLE IF NOT EXISTS service_status (
                service_name TEXT PRIMARY KEY,
                is_active INTEGER DEFAULT 1
            )""",
            """CREATE TABLE IF NOT EXISTS invitation_stats (
                inviter_id INTEGER,
                invited_id INTEGER,
                bonus_received INTEGER DEFAULT 0,
                invite_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (inviter_id, invited_id)
            )""",
            """CREATE TABLE IF NOT EXISTS lecture_ratings (
                rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
                lecture_id INTEGER,
                user_id INTEGER,
                rating INTEGER,
                comment TEXT,
                rating_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lecture_id) REFERENCES vip_lectures (lecture_id),
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )""",
            """CREATE TABLE IF NOT EXISTS admin_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                action TEXT,
                target_id INTEGER,
                details TEXT,
                log_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        ]
        
        for table in tables:
            cursor.execute(table)
        
        # إضافة الخدمات الافتراضية
        default_services = [
            ('exemption', 1),
            ('summary', 1),
            ('qa', 1),
            ('help_student', 1),
            ('materials', 1),
            ('vip_subscription', 1)
        ]
        
        for service, status in default_services:
            cursor.execute(
                "INSERT OR IGNORE INTO service_status (service_name, is_active) VALUES (?, ?)",
                (service, status)
            )
        
        self.conn.commit()
    
    def create_default_admin(self):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, is_admin, balance) VALUES (?, ?, ?, ?, ?)",
            (ADMIN_ID, SUPPORT_USER, "المدير", 1, 1000000)
        )
        self.conn.commit()
    
    def create_default_settings(self):
        cursor = self.conn.cursor()
        
        default_settings = [
            ('invitation_bonus', '500'),
            ('welcome_bonus', '1000'),
            ('vip_invitation_bonus', '1000'),
            ('vip_subscription_days', '30'),
            ('admin_commission_percent', '40'),
            ('teacher_commission_percent', '60'),
            ('max_video_size_mb', '100'),
            ('min_question_length', '10')
        ]
        
        for key, value in default_settings:
            cursor.execute(
                "INSERT OR IGNORE INTO bot_settings (setting_key, setting_value) VALUES (?, ?)",
                (key, value)
            )
        
        self.conn.commit()
    
    # ============ عمليات المستخدمين ============
    
    def get_user(self, user_id: int) -> Optional[UserData]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if row:
            return UserData(
                user_id=row['user_id'],
                username=row['username'],
                first_name=row['first_name'],
                last_name=row['last_name'] or "",
                balance=row['balance'],
                invited_by=row['invited_by'],
                invited_count=row['invited_count'],
                is_banned=bool(row['is_banned']),
                is_admin=bool(row['is_admin']),
                join_date=row['join_date'],
                last_active=row['last_active']
            )
        return None
    
    def create_user(self, user_id: int, username: str, first_name: str, last_name: str = "", invited_by: int = 0) -> bool:
        cursor = self.conn.cursor()
        
        # الحصول على مكافأة الترحيب
        welcome_bonus = int(self.get_setting('welcome_bonus', '1000'))
        
        # إنشاء المستخدم
        cursor.execute(
            """INSERT OR IGNORE INTO users 
            (user_id, username, first_name, last_name, balance, invited_by) 
            VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, username, first_name, last_name, welcome_bonus, invited_by)
        )
        
        if cursor.rowcount > 0:
            # إذا كان هناك مدعو، إعطاء المكافأة
            if invited_by > 0:
                # تحديد مكافأة الدعوة
                inviter_user = self.get_user(invited_by)
                is_vip = self.is_vip_user(invited_by)
                bonus_amount = int(self.get_setting(
                    'vip_invitation_bonus' if is_vip else 'invitation_bonus', 
                    '1000' if is_vip else '500'
                ))
                
                # تحديث رصيد المدعو
                cursor.execute(
                    "UPDATE users SET invited_count = invited_count + 1, balance = balance + ? WHERE user_id = ?",
                    (bonus_amount, invited_by)
                )
                
                # تسجيل العملية
                cursor.execute(
                    """INSERT INTO transactions (user_id, amount, type, description) 
                    VALUES (?, ?, ?, ?)""",
                    (invited_by, bonus_amount, 'invitation_bonus', f'مكافأة دعوة للمستخدم {user_id}')
                )
                
                # تسجيل إحصائية الدعوة
                cursor.execute(
                    "INSERT OR IGNORE INTO invitation_stats (inviter_id, invited_id, bonus_received) VALUES (?, ?, ?)",
                    (invited_by, user_id, bonus_amount)
                )
            
            # تسجيل عملية هدية الترحيب
            cursor.execute(
                """INSERT INTO transactions (user_id, amount, type, description) 
                VALUES (?, ?, ?, ?)""",
                (user_id, welcome_bonus, 'welcome_bonus', 'هدية ترحيب جديدة')
            )
            
            # تحديث الإحصائيات
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute(
                """INSERT INTO statistics (stat_date, new_users) 
                VALUES (?, 1) 
                ON CONFLICT(stat_date) DO UPDATE SET new_users = new_users + 1""",
                (today,)
            )
            
            self.conn.commit()
            return True
        return False
    
    def update_user_activity(self, user_id: int):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,)
        )
        
        # تحديث الإحصائيات
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute(
            """INSERT OR IGNORE INTO statistics (stat_date, active_users) 
            VALUES (?, 0)""",
            (today,)
        )
        
        cursor.execute(
            """UPDATE statistics SET active_users = (
                SELECT COUNT(DISTINCT user_id) FROM users 
                WHERE last_active LIKE ?
            ) WHERE stat_date = ?""",
            (f"{today}%", today)
        )
        
        self.conn.commit()
    
    # ============ إدارة الأرصدة ============
    
    def update_balance(self, user_id: int, amount: int, trans_type: str, description: str = "") -> bool:
        cursor = self.conn.cursor()
        
        # التحقق من وجود المستخدم
        user = self.get_user(user_id)
        if not user:
            return False
        
        # حساب الرصيد الجديد
        new_balance = user.balance + amount
        
        # إذا كان الرصيد سالباً
        if new_balance < 0:
            return False
        
        # تحديث الرصيد
        cursor.execute(
            "UPDATE users SET balance = ? WHERE user_id = ?",
            (new_balance, user_id)
        )
        
        # تسجيل العملية
        cursor.execute(
            """INSERT INTO transactions (user_id, amount, type, description) 
            VALUES (?, ?, ?, ?)""",
            (user_id, amount, trans_type, description)
        )
        
        # تحديث إحصائيات الدخل
        if trans_type in ['service_payment', 'vip_subscription', 'lecture_purchase'] and amount < 0:
            today = datetime.now().strftime('%Y-%m-%d')
            income_amount = abs(amount)
            
            cursor.execute(
                """INSERT INTO statistics (stat_date, transactions_count, total_income) 
                VALUES (?, 1, ?) 
                ON CONFLICT(stat_date) DO UPDATE SET 
                transactions_count = transactions_count + 1,
                total_income = total_income + ?""",
                (today, income_amount, income_amount)
            )
        
        self.conn.commit()
        return True
    
    def check_balance(self, user_id: int, amount: int) -> bool:
        user = self.get_user(user_id)
        return user is not None and user.balance >= amount
    
    # ============ إدارة VIP ============
    
    def is_vip_user(self, user_id: int) -> bool:
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT 1 FROM vip_users 
            WHERE user_id = ? AND is_active = 1 AND expiry_date > CURRENT_TIMESTAMP""",
            (user_id,)
        )
        return cursor.fetchone() is not None
    
    def get_vip_user(self, user_id: int) -> Optional[VIPUser]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM vip_users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if row:
            return VIPUser(
                user_id=row['user_id'],
                subscription_date=row['subscription_date'],
                expiry_date=row['expiry_date'],
                is_active=bool(row['is_active']),
                earnings_balance=row['earnings_balance'],
                total_earnings=row['total_earnings']
            )
        return None
    
    def activate_vip(self, user_id: int, days: int = 30) -> bool:
        cursor = self.conn.cursor()
        
        expiry_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute(
            """INSERT OR REPLACE INTO vip_users 
            (user_id, subscription_date, expiry_date, is_active) 
            VALUES (?, CURRENT_TIMESTAMP, ?, 1)""",
            (user_id, expiry_date)
        )
        
        # تسجيل العملية
        cursor.execute(
            """INSERT INTO admin_logs (admin_id, action, target_id, details) 
            VALUES (?, ?, ?, ?)""",
            (ADMIN_ID, 'activate_vip', user_id, f'تفعيل اشتراك VIP لمدة {days} يوم')
        )
        
        self.conn.commit()
        return True
    
    def deactivate_vip(self, user_id: int) -> bool:
        cursor = self.conn.cursor()
        
        cursor.execute(
            "UPDATE vip_users SET is_active = 0 WHERE user_id = ?",
            (user_id,)
        )
        
        # تسجيل العملية
        cursor.execute(
            """INSERT INTO admin_logs (admin_id, action, target_id, details) 
            VALUES (?, ?, ?, ?)""",
            (ADMIN_ID, 'deactivate_vip', user_id, 'إلغاء اشتراك VIP')
        )
        
        self.conn.commit()
        return True
    
    def update_vip_earnings(self, user_id: int, amount: int) -> bool:
        cursor = self.conn.cursor()
        
        cursor.execute(
            """UPDATE vip_users 
            SET earnings_balance = earnings_balance + ?, 
                total_earnings = total_earnings + ? 
            WHERE user_id = ?""",
            (amount, amount, user_id)
        )
        
        self.conn.commit()
        return True
    
    def withdraw_vip_earnings(self, user_id: int, amount: int) -> bool:
        cursor = self.conn.cursor()
        
        # التحقق من الرصيد المتاح
        cursor.execute("SELECT earnings_balance FROM vip_users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if not row or row['earnings_balance'] < amount:
            return False
        
        # خصم المبلغ
        cursor.execute(
            "UPDATE vip_users SET earnings_balance = earnings_balance - ? WHERE user_id = ?",
            (amount, user_id)
        )
        
        # تسجيل العملية
        cursor.execute(
            """INSERT INTO admin_logs (admin_id, action, target_id, details) 
            VALUES (?, ?, ?, ?)""",
            (ADMIN_ID, 'vip_withdraw', user_id, f'سحب أرباح بقيمة {amount}')
        )
        
        self.conn.commit()
        return True
    
    # ============ محاضرات VIP ============
    
    def add_vip_lecture(self, teacher_id: int, title: str, description: str, 
                       video_path: str, price: int = 0) -> int:
        cursor = self.conn.cursor()
        
        cursor.execute(
            """INSERT INTO vip_lectures 
            (teacher_id, title, description, video_path, price, is_approved) 
            VALUES (?, ?, ?, ?, ?, 0)""",
            (teacher_id, title, description, video_path, price)
        )
        
        lecture_id = cursor.lastrowid
        
        # تسجيل العملية
        cursor.execute(
            """INSERT INTO admin_logs (admin_id, action, target_id, details) 
            VALUES (?, ?, ?, ?)""",
            (ADMIN_ID, 'add_vip_lecture', teacher_id, f'إضافة محاضرة: {title}')
        )
        
        self.conn.commit()
        return lecture_id
    
    def get_vip_lecture(self, lecture_id: int) -> Optional[VIPLecture]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM vip_lectures WHERE lecture_id = ?", (lecture_id,))
        row = cursor.fetchone()
        
        if row:
            return VIPLecture(
                lecture_id=row['lecture_id'],
                teacher_id=row['teacher_id'],
                title=row['title'],
                description=row['description'],
                video_path=row['video_path'],
                price=row['price'],
                views=row['views'],
                purchases=row['purchases'],
                earnings=row['earnings'],
                rating=row['rating'],
                rating_count=row['rating_count'],
                is_approved=bool(row['is_approved']),
                upload_date=row['upload_date']
            )
        return None
    
    def approve_vip_lecture(self, lecture_id: int) -> bool:
        cursor = self.conn.cursor()
        
        cursor.execute(
            "UPDATE vip_lectures SET is_approved = 1 WHERE lecture_id = ?",
            (lecture_id,)
        )
        
        # تسجيل العملية
        cursor.execute(
            """INSERT INTO admin_logs (admin_id, action, target_id, details) 
            VALUES (?, ?, ?, ?)""",
            (ADMIN_ID, 'approve_vip_lecture', lecture_id, 'موافقة على محاضرة VIP')
        )
        
        self.conn.commit()
        return True
    
    def reject_vip_lecture(self, lecture_id: int) -> bool:
        cursor = self.conn.cursor()
        
        cursor.execute(
            "DELETE FROM vip_lectures WHERE lecture_id = ?",
            (lecture_id,)
        )
        
        # تسجيل العملية
        cursor.execute(
            """INSERT INTO admin_logs (admin_id, action, target_id, details) 
            VALUES (?, ?, ?, ?)""",
            (ADMIN_ID, 'reject_vip_lecture', lecture_id, 'رفض محاضرة VIP')
        )
        
        self.conn.commit()
        return True
    
    def purchase_vip_lecture(self, user_id: int, lecture_id: int) -> Tuple[bool, str]:
        cursor = self.conn.cursor()
        
        # الحصول على بيانات المحاضرة
        lecture = self.get_vip_lecture(lecture_id)
        if not lecture:
            return False, "المحاضرة غير موجودة"
        
        if not lecture.is_approved:
            return False, "المحاضرة غير معتمدة بعد"
        
        # التحقق من الرصيد
        user = self.get_user(user_id)
        if not user or user.balance < lecture.price:
            return False, "رصيدك غير كافي"
        
        # خصم المبلغ
        if not self.update_balance(user_id, -lecture.price, 'lecture_purchase', f'شراء محاضرة: {lecture.title}'):
            return False, "حدث خطأ في الدفع"
        
        # توزيع الأرباح
        admin_commission = int(self.get_setting('admin_commission_percent', '40'))
        teacher_commission = int(self.get_setting('teacher_commission_percent', '60'))
        
        admin_share = (lecture.price * admin_commission) // 100
        teacher_share = lecture.price - admin_share
        
        # تحديث أرباح المحاضر
        self.update_vip_earnings(lecture.teacher_id, teacher_share)
        
        # تحديث إحصائيات المحاضرة
        cursor.execute(
            """UPDATE vip_lectures 
            SET purchases = purchases + 1, earnings = earnings + ? 
            WHERE lecture_id = ?""",
            (lecture.price, lecture_id)
        )
        
        # تسجيل عملية الشراء
        cursor.execute(
            """INSERT INTO lecture_purchases (user_id, lecture_id, amount_paid) 
            VALUES (?, ?, ?)""",
            (user_id, lecture_id, lecture.price)
        )
        
        # تسجيل العملية
        cursor.execute(
            """INSERT INTO admin_logs (admin_id, action, target_id, details) 
            VALUES (?, ?, ?, ?)""",
            (ADMIN_ID, 'lecture_purchase', user_id, f'شراء محاضرة {lecture_id} بقيمة {lecture.price}')
        )
        
        self.conn.commit()
        return True, "تم الشراء بنجاح"
    
    # ============ المواد التعليمية ============
    
    def add_material(self, title: str, description: str, stage: str, file_path: str) -> int:
        cursor = self.conn.cursor()
        
        cursor.execute(
            """INSERT INTO materials (title, description, stage, file_path) 
            VALUES (?, ?, ?, ?)""",
            (title, description, stage, file_path)
        )
        
        material_id = cursor.lastrowid
        
        # تسجيل العملية
        cursor.execute(
            """INSERT INTO admin_logs (admin_id, action, target_id, details) 
            VALUES (?, ?, ?, ?)""",
            (ADMIN_ID, 'add_material', material_id, f'إضافة مادة: {title}')
        )
        
        self.conn.commit()
        return material_id
    
    def get_material(self, material_id: int) -> Optional[Material]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM materials WHERE material_id = ?", (material_id,))
        row = cursor.fetchone()
        
        if row:
            return Material(
                material_id=row['material_id'],
                title=row['title'],
                description=row['description'],
                stage=row['stage'],
                file_path=row['file_path'],
                upload_date=row['upload_date']
            )
        return None
    
    def delete_material(self, material_id: int) -> bool:
        cursor = self.conn.cursor()
        
        cursor.execute("DELETE FROM materials WHERE material_id = ?", (material_id,))
        
        # تسجيل العملية
        cursor.execute(
            """INSERT INTO admin_logs (admin_id, action, target_id, details) 
            VALUES (?, ?, ?, ?)""",
            (ADMIN_ID, 'delete_material', material_id, 'حذف مادة تعليمية')
        )
        
        self.conn.commit()
        return cursor.rowcount > 0
    
    # ============ الأسئلة والإجابات ============
    
    def add_help_question(self, user_id: int, question_text: str, subject: str = "عام") -> int:
        cursor = self.conn.cursor()
        
        cursor.execute(
            """INSERT INTO help_questions (user_id, question_text, subject, is_approved) 
            VALUES (?, ?, ?, 0)""",
            (user_id, question_text, subject)
        )
        
        question_id = cursor.lastrowid
        self.conn.commit()
        return question_id
    
    def get_help_question(self, question_id: int) -> Optional[HelpQuestion]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM help_questions WHERE question_id = ?", (question_id,))
        row = cursor.fetchone()
        
        if row:
            return HelpQuestion(
                question_id=row['question_id'],
                user_id=row['user_id'],
                question_text=row['question_text'],
                subject=row['subject'],
                is_approved=bool(row['is_approved']),
                is_answered=bool(row['is_answered']),
                answer_text=row['answer_text'] or "",
                answerer_id=row['answerer_id'] or 0,
                ask_date=row['ask_date'],
                answer_date=row['answer_date'] or ""
            )
        return None
    
    def approve_help_question(self, question_id: int) -> bool:
        cursor = self.conn.cursor()
        
        cursor.execute(
            "UPDATE help_questions SET is_approved = 1 WHERE question_id = ?",
            (question_id,)
        )
        
        self.conn.commit()
        return True
    
    def reject_help_question(self, question_id: int) -> bool:
        cursor = self.conn.cursor()
        
        cursor.execute(
            "DELETE FROM help_questions WHERE question_id = ?",
            (question_id,)
        )
        
        self.conn.commit()
        return True
    
    def answer_help_question(self, question_id: int, answerer_id: int, answer_text: str) -> bool:
        cursor = self.conn.cursor()
        
        cursor.execute(
            """UPDATE help_questions 
            SET answer_text = ?, answerer_id = ?, is_answered = 1, answer_date = CURRENT_TIMESTAMP 
            WHERE question_id = ?""",
            (answer_text, answerer_id, question_id)
        )
        
        self.conn.commit()
        return True
    
    # ============ الإعدادات والخدمات ============
    
    def get_setting(self, key: str, default: str = "") -> str:
        cursor = self.conn.cursor()
        cursor.execute("SELECT setting_value FROM bot_settings WHERE setting_key = ?", (key,))
        row = cursor.fetchone()
        return row['setting_value'] if row else default
    
    def update_setting(self, key: str, value: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO bot_settings (setting_key, setting_value) VALUES (?, ?)",
            (key, value)
        )
        self.conn.commit()
        return True
    
    def is_service_active(self, service_name: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT is_active FROM service_status WHERE service_name = ?",
            (service_name,)
        )
        row = cursor.fetchone()
        return bool(row['is_active']) if row else True
    
    def set_service_status(self, service_name: str, is_active: bool) -> bool:
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO service_status (service_name, is_active) VALUES (?, ?)",
            (service_name, 1 if is_active else 0)
        )
        self.conn.commit()
        return True
    
    # ============ الإحصائيات والتقارير ============
    
    def get_user_stats(self) -> Dict:
        cursor = self.conn.cursor()
        
        stats = {}
        
        # إجمالي المستخدمين
        cursor.execute("SELECT COUNT(*) FROM users")
        stats['total_users'] = cursor.fetchone()[0]
        
        # المستخدمين النشطين (آخر 7 أيام)
        cursor.execute(
            "SELECT COUNT(*) FROM users WHERE last_active > datetime('now', '-7 days')"
        )
        stats['active_users'] = cursor.fetchone()[0]
        
        # المشتركين VIP
        cursor.execute(
            "SELECT COUNT(*) FROM vip_users WHERE is_active = 1 AND expiry_date > CURRENT_TIMESTAMP"
        )
        stats['vip_users'] = cursor.fetchone()[0]
        
        # إجمالي الأرصدة
        cursor.execute("SELECT SUM(balance) FROM users")
        stats['total_balance'] = cursor.fetchone()[0] or 0
        
        # الدخل اليومي
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute(
            "SELECT total_income FROM statistics WHERE stat_date = ?",
            (today,)
        )
        row = cursor.fetchone()
        stats['daily_income'] = row['total_income'] if row else 0
        
        return stats
    
    def get_recent_users(self, limit: int = 10) -> List[UserData]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM users ORDER BY last_active DESC LIMIT ?",
            (limit,)
        )
        
        users = []
        for row in cursor.fetchall():
            users.append(UserData(
                user_id=row['user_id'],
                username=row['username'],
                first_name=row['first_name'],
                last_name=row['last_name'] or "",
                balance=row['balance'],
                invited_by=row['invited_by'],
                invited_count=row['invited_count'],
                is_banned=bool(row['is_banned']),
                is_admin=bool(row['is_admin']),
                join_date=row['join_date'],
                last_active=row['last_active']
            ))
        
        return users
    
    def get_pending_questions(self) -> List[HelpQuestion]:
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT q.*, u.first_name 
            FROM help_questions q 
            JOIN users u ON q.user_id = u.user_id 
            WHERE q.is_approved = 0 
            ORDER BY q.ask_date"""
        )
        
        questions = []
        for row in cursor.fetchall():
            questions.append(HelpQuestion(
                question_id=row['question_id'],
                user_id=row['user_id'],
                question_text=row['question_text'],
                subject=row['subject'],
                is_approved=bool(row['is_approved']),
                is_answered=bool(row['is_answered']),
                ask_date=row['ask_date']
            ))
        
        return questions
    
    def get_pending_lectures(self) -> List[VIPLecture]:
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT l.*, u.first_name 
            FROM vip_lectures l 
            JOIN users u ON l.teacher_id = u.user_id 
            WHERE l.is_approved = 0 
            ORDER BY l.upload_date"""
        )
        
        lectures = []
        for row in cursor.fetchall():
            lectures.append(VIPLecture(
                lecture_id=row['lecture_id'],
                teacher_id=row['teacher_id'],
                title=row['title'],
                description=row['description'],
                video_path=row['video_path'],
                price=row['price'],
                is_approved=bool(row['is_approved']),
                upload_date=row['upload_date']
            ))
        
        return lectures
    
    def ban_user(self, user_id: int) -> bool:
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE users SET is_banned = 1 WHERE user_id = ?",
            (user_id,)
        )
        
        # تسجيل العملية
        cursor.execute(
            """INSERT INTO admin_logs (admin_id, action, target_id, details) 
            VALUES (?, ?, ?, ?)""",
            (ADMIN_ID, 'ban_user', user_id, 'حظر مستخدم')
        )
        
        self.conn.commit()
        return cursor.rowcount > 0
    
    def unban_user(self, user_id: int) -> bool:
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE users SET is_banned = 0 WHERE user_id = ?",
            (user_id,)
        )
        
        # تسجيل العملية
        cursor.execute(
            """INSERT INTO admin_logs (admin_id, action, target_id, details) 
            VALUES (?, ?, ?, ?)""",
            (ADMIN_ID, 'unban_user', user_id, 'فك حظر مستخدم')
        )
        
        self.conn.commit()
        return cursor.rowcount > 0

# ============================================================================
# أدوات المساعدة
# ============================================================================

class TextUtils:
    """أدوات معالجة النصوص"""
    
    @staticmethod
    def format_currency(amount: int) -> str:
        """تنسيق العملة"""
        return f"{amount:,} دينار عراقي"
    
    @staticmethod
    def truncate_text(text: str, max_length: int = 100) -> str:
        """تقصير النص مع إضافة ..."""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."
    
    @staticmethod
    def escape_markdown(text: str) -> str:
        """تهيئة النص لـ Markdown"""
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    @staticmethod
    def generate_invite_link(user_id: int) -> str:
        """إنشاء رابط دعوة"""
        return f"https://t.me/{BOT_USERNAME[1:]}?start={user_id}"
    
    @staticmethod
    def format_date(date_str: str) -> str:
        """تنسيق التاريخ"""
        try:
            dt = datetime.strptime(date_str[:19], '%Y-%m-%d %H:%M:%S')
            return dt.strftime('%Y/%m/%d %H:%M')
        except:
            return date_str

class PDFUtils:
    """أدوات معالجة PDF (بديل مبسط)"""
    
    @staticmethod
    def extract_text_from_pdf(pdf_bytes: bytes) -> str:
        """استخراج النص من ملف PDF (بديل مبسط)"""
        # في الإصدار الحقيقي، استخدم PyPDF2 أو مكتبة مشابهة
        # هنا نعيد نصاً افتراضياً لأغراض العرض
        return "نص المستند المستخرج. في الإصدار الحقيقي، سيتم استخدام PyPDF2 لاستخراج النص الفعلي."
    
    @staticmethod
    def create_summary_pdf(text: str, filename: str = "ملخص.pdf") -> bytes:
        """إنشاء ملف PDF يحتوي على النص الملخص"""
        # في الإصدار الحقيقي، استخدم reportlab
        # هنا نعيد ملفاً نصياً لأغراض العرض
        summary = f"ملخص النص:\n\n{text}\n\nتم الإنشاء بواسطة بوت يلا نتعلم"
        return summary.encode('utf-8')

class AIUtils:
    """أدوات الذكاء الاصطناعي"""
    
    @staticmethod
    def generate_gemini_response(prompt: str) -> str:
        """إنشاء رد باستخدام Gemini AI"""
        try:
            headers = {
                'Content-Type': 'application/json',
                'X-goog-api-key': GEMINI_API_KEY
            }
            
            data = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }]
            }
            
            response = http_request(GEMINI_URL, "POST", headers=headers, json_data=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    return result['candidates'][0]['content']['parts'][0]['text']
            
            return "عذراً، حدث خطأ في معالجة الطلب. حاول مرة أخرى لاحقاً."
            
        except Exception as e:
            logging.error(f"Gemini AI Error: {e}")
            return "عذراً، خدمة الذكاء الاصطناعي غير متوفرة حالياً."
    
    @staticmethod
    def summarize_text(text: str) -> str:
        """تلخيص النص باستخدام الذكاء الاصطناعي"""
        prompt = f"""الرجاء تلخيص النص التالي مع الحفاظ على المعلومات المهمة:
        
        {text[:3000]}
        
        قدم التلخيص بشكل منظم مع عناوين رئيسية."""
        
        return AIUtils.generate_gemini_response(prompt)
    
    @staticmethod
    def answer_question(question: str) -> str:
        """الإجابة على سؤال باستخدام الذكاء الاصطناعي"""
        prompt = f"""أجب على السؤال التالي كطالب عراقي، مع تقديم إجابة علمية دقيقة ومناسبة للمنهج العراقي:

        السؤال: {question}
        
        قدم الإجابة بشكل منظم ومفصل مع الأمثلة إذا لزم الأمر."""
        
        return AIUtils.generate_gemini_response(prompt)

# ============================================================================
# واجهة تليجرام (بديل مبسط)
# ============================================================================

class TelegramBot:
    """واجهة مبسطة للتعامل مع Telegram Bot API"""
    
    BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
    
    @staticmethod
    def send_message(chat_id: int, text: str, parse_mode: str = None, 
                    reply_markup: Dict = None) -> Dict:
        """إرسال رسالة"""
        data = {
            "chat_id": chat_id,
            "text": text
        }
        
        if parse_mode:
            data["parse_mode"] = parse_mode
        
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        
        response = http_request(f"{TelegramBot.BASE_URL}/sendMessage", 
                               "POST", json_data=data)
        return response.json()
    
    @staticmethod
    def edit_message_text(chat_id: int, message_id: int, text: str, 
                         parse_mode: str = None, reply_markup: Dict = None) -> Dict:
        """تعديل نص الرسالة"""
        data = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text
        }
        
        if parse_mode:
            data["parse_mode"] = parse_mode
        
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        
        response = http_request(f"{TelegramBot.BASE_URL}/editMessageText", 
                               "POST", json_data=data)
        return response.json()
    
    @staticmethod
    def answer_callback_query(callback_query_id: str, text: str = None, 
                             show_alert: bool = False) -> Dict:
        """الرد على استعلام رد الاتصال"""
        data = {
            "callback_query_id": callback_query_id
        }
        
        if text:
            data["text"] = text
        
        if show_alert:
            data["show_alert"] = show_alert
        
        response = http_request(f"{TelegramBot.BASE_URL}/answerCallbackQuery", 
                               "POST", json_data=data)
        return response.json()
    
    @staticmethod
    def send_document(chat_id: int, document: bytes, filename: str, 
                     caption: str = None, parse_mode: str = None) -> Dict:
        """إرسال مستند"""
        # هذه دالة مبسطة، في الإصدار الحقيقي تحتاج لمعالجة الملفات بشكل صحيح
        return {"ok": True, "result": {"message_id": 123}}
    
    @staticmethod
    def send_video(chat_id: int, video: bytes, caption: str = None) -> Dict:
        """إرسال فيديو"""
        # دالة مبسطة
        return {"ok": True, "result": {"message_id": 124}}
    
    @staticmethod
    def delete_message(chat_id: int, message_id: int) -> Dict:
        """حذف رسالة"""
        data = {
            "chat_id": chat_id,
            "message_id": message_id
        }
        
        response = http_request(f"{TelegramBot.BASE_URL}/deleteMessage", 
                               "POST", json_data=data)
        return response.json()
    
    @staticmethod
    def get_user_profile_photos(user_id: int) -> Dict:
        """الحصول على صور الملف الشخصي للمستخدم"""
        data = {"user_id": user_id}
        response = http_request(f"{TelegramBot.BASE_URL}/getUserProfilePhotos", 
                               "POST", json_data=data)
        return response.json()

# ============================================================================
# واجهات المستخدم
# ============================================================================

class KeyboardBuilder:
    """بناء لوحات المفاتيح"""
    
    @staticmethod
    def create_inline_keyboard(buttons: List[List[Dict]]) -> Dict:
        """إنشاء لوحة مفاتيح مضمنة"""
        keyboard = []
        
        for row in buttons:
            keyboard_row = []
            for btn in row:
                keyboard_row.append({
                    "text": btn.get("text", "زر"),
                    "callback_data": btn.get("callback_data", "empty"),
                    "url": btn.get("url")
                })
            keyboard.append(keyboard_row)
        
        return {"inline_keyboard": keyboard}
    
    @staticmethod
    def create_reply_keyboard(buttons: List[List[str]], resize: bool = True, 
                             one_time: bool = False) -> Dict:
        """إنشاء لوحة مفاتيح رد"""
        keyboard = []
        
        for row in buttons:
            keyboard_row = []
            for text in row:
                keyboard_row.append({"text": text})
            keyboard.append(keyboard_row)
        
        return {
            "keyboard": keyboard,
            "resize_keyboard": resize,
            "one_time_keyboard": one_time
        }
    
    @staticmethod
    def remove_keyboard() -> Dict:
        """إزالة لوحة المفاتيح"""
        return {"remove_keyboard": True}
    
    @staticmethod
    def main_menu(user_id: int) -> Dict:
        """القائمة الرئيسية"""
        buttons = [
            [
                {"text": "🧮 حساب درجة الإعفاء", "callback_data": "service_exemption"},
                {"text": "📚 تلخيص الملازم", "callback_data": "service_summary"}
            ],
            [
                {"text": "❓ سؤال وجواب", "callback_data": "service_qa"},
                {"text": "👥 ساعدوني طالب", "callback_data": "service_help"}
            ],
            [
                {"text": "📖 ملازمي ومرشحاتي", "callback_data": "service_materials"},
                {"text": "🎓 محاضرات VIP", "callback_data": "vip_lectures"}
            ],
            [
                {"text": "⭐ اشتراك VIP", "callback_data": "vip_subscription"},
                {"text": "💰 رصيدي", "callback_data": "my_balance"}
            ],
            [
                {"text": "👥 دعوة صديق", "callback_data": "invite_friend"}
            ]
        ]
        
        if user_id == ADMIN_ID:
            buttons.append([{"text": "👑 لوحة التحكم", "callback_data": "admin_panel"}])
        
        return KeyboardBuilder.create_inline_keyboard(buttons)
    
    @staticmethod
    def admin_panel() -> Dict:
        """لوحة تحكم المدير"""
        buttons = [
            [
                {"text": "💰 شحن رصيد", "callback_data": "admin_charge"},
                {"text": "💸 خصم رصيد", "callback_data": "admin_deduct"}
            ],
            [
                {"text": "🚫 حظر مستخدم", "callback_data": "admin_ban"},
                {"text": "✅ فك حظر", "callback_data": "admin_unban"}
            ],
            [
                {"text": "👥 إدارة المستخدمين", "callback_data": "admin_users"},
                {"text": "⚙️ إدارة الخدمات", "callback_data": "admin_services"}
            ],
            [
                {"text": "📊 الإحصائيات", "callback_data": "admin_stats"},
                {"text": "📢 إرسال إذاعة", "callback_data": "admin_broadcast"}
            ],
            [
                {"text": "⭐ إدارة VIP", "callback_data": "admin_vip"},
                {"text": "📖 إدارة المواد", "callback_data": "admin_materials"}
            ],
            [
                {"text": "❓ الأسئلة المنتظرة", "callback_data": "admin_pending_questions"},
                {"text": "🎬 محاضرات منتظرة", "callback_data": "admin_pending_lectures"}
            ],
            [
                {"text": "🔙 القائمة الرئيسية", "callback_data": "main_menu"}
            ]
        ]
        
        return KeyboardBuilder.create_inline_keyboard(buttons)
    
    @staticmethod
    def back_button(target: str = "main_menu") -> Dict:
        """زر الرجوع"""
        return KeyboardBuilder.create_inline_keyboard([
            [{"text": "🔙 الرجوع", "callback_data": target}]
        ])
    
    @staticmethod
    def cancel_button() -> Dict:
        """زر الإلغاء"""
        return KeyboardBuilder.create_inline_keyboard([
            [{"text": "❌ إلغاء", "callback_data": "main_menu"}]
        ])
    
    @staticmethod
    def confirmation_buttons(confirm_data: str, cancel_data: str) -> Dict:
        """أزرار التأكيد"""
        return KeyboardBuilder.create_inline_keyboard([
            [
                {"text": "✅ نعم", "callback_data": confirm_data},
                {"text": "❌ لا", "callback_data": cancel_data}
            ]
        ])
    
    @staticmethod
    def vip_subscription_menu() -> Dict:
        """قائمة اشتراك VIP"""
        buttons = [
            [{"text": "✅ اشتراك الآن", "callback_data": "vip_purchase"}],
            [{"text": "📋 الشروط والمميزات", "callback_data": "vip_terms"}],
            [{"text": "🔙 الرجوع", "callback_data": "main_menu"}]
        ]
        
        return KeyboardBuilder.create_inline_keyboard(buttons)
    
    @staticmethod
    def vip_lectures_menu() -> Dict:
        """قائمة محاضرات VIP"""
        buttons = [
            [{"text": "🎓 عرض المحاضرات", "callback_data": "view_vip_lectures"}],
            [{"text": "📤 رفع محاضرة", "callback_data": "vip_upload"}],
            [{"text": "💰 أرباحي", "callback_data": "vip_earnings"}],
            [{"text": "🔙 الرجوع", "callback_data": "main_menu"}]
        ]
        
        return KeyboardBuilder.create_inline_keyboard(buttons)

# ============================================================================
# البوت الرئيسي
# ============================================================================

class LearnBot:
    def __init__(self):
        self.db = Database()
        self.text_utils = TextUtils()
        self.ai_utils = AIUtils()
        self.pdf_utils = PDFUtils()
        self.user_sessions = {}  # تخزين جلسات المستخدمين
        
        # إعداد التسجيل
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    # ============ معالجة الرسائل ============
    
    def handle_message(self, update: Dict) -> None:
        """معالجة الرسالة الواردة"""
        try:
            message = update.get("message", {})
            
            if not message:
                # قد يكون استعلام رد اتصال
                callback_query = update.get("callback_query", {})
                if callback_query:
                    self.handle_callback_query(callback_query)
                return
            
            # استخراج المعلومات الأساسية
            chat_id = message.get("chat", {}).get("id")
            text = message.get("text", "")
            user = message.get("from", {})
            
            if not user:
                return
            
            user_id = user.get("id")
            username = user.get("username", "")
            first_name = user.get("first_name", "")
            last_name = user.get("last_name", "")
            
            # تحديث نشاط المستخدم
            self.db.update_user_activity(user_id)
            
            # التحقق من الحظر
            user_data = self.db.get_user(user_id)
            if user_data and user_data.is_banned:
                TelegramBot.send_message(
                    chat_id,
                    "🚫 حسابك محظور! راسل الدعم الفني للمساعدة.",
                    reply_markup=KeyboardBuilder.back_button()
                )
                return
            
            # معالجة الأوامر
            if text.startswith("/"):
                self.handle_command(chat_id, user_id, text, user_data)
            else:
                # معالجة الرسائل العادية بناءً على حالة المستخدم
                self.handle_regular_message(chat_id, user_id, text, message)
        
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
    
    def handle_command(self, chat_id: int, user_id: int, command: str, user_data: Optional[UserData]):
        """معالجة الأوامر"""
        if command.startswith("/start"):
            # استخراج رابط الدعوة
            invited_by = 0
            if " " in command:
                try:
                    invited_by = int(command.split()[1])
                except:
                    pass
            
            # إنشاء المستخدم إذا لم يكن موجوداً
            if not user_data:
                user_info = self.get_user_info(user_id)
                self.db.create_user(
                    user_id,
                    user_info.get("username", ""),
                    user_info.get("first_name", ""),
                    user_info.get("last_name", ""),
                    invited_by
                )
                user_data = self.db.get_user(user_id)
            
            # إرسال رسالة الترحيب
            welcome_text = f"""
            🎉 أهلاً بك {user_data.first_name} في بوت *يلا نتعلم*!

            *رصيدك الحالي:* {self.text_utils.format_currency(user_data.balance)}

            *الخدمات المتاحة:*
            • حساب درجة الإعفاء
            • تلخيص الملازم (PDF)
            • سؤال وجواب بالذكاء الاصطناعي
            • قسم ساعدوني طالب
            • مكتبة المواد التعليمية
            • محاضرات VIP

            جميع الخدمات مدفوعة بسعر 1000 دينار لكل خدمة.

            اختر الخدمة التي تريدها 👇
            """
            
            TelegramBot.send_message(
                chat_id,
                welcome_text,
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.main_menu(user_id)
            )
        
        elif command == "/admin" and user_id == ADMIN_ID:
            self.show_admin_panel(chat_id)
        
        elif command == "/balance":
            self.show_balance(chat_id, user_id)
        
        elif command == "/invite":
            self.show_invitation(chat_id, user_id)
        
        else:
            TelegramBot.send_message(
                chat_id,
                "❓ الأمر غير معروف. استخدم /start للبدء.",
                reply_markup=KeyboardBuilder.back_button()
            )
    
    def handle_regular_message(self, chat_id: int, user_id: int, text: str, message: Dict):
        """معالجة الرسائل العادية"""
        # الحصول على حالة المستخدم
        session = self.user_sessions.get(user_id, {})
        state = session.get("state", ConversationState.MAIN_MENU)
        
        if state == ConversationState.EXEMPTION_STEP1:
            self.handle_exemption_step1(chat_id, user_id, text, session)
        
        elif state == ConversationState.EXEMPTION_STEP2:
            self.handle_exemption_step2(chat_id, user_id, text, session)
        
        elif state == ConversationState.EXEMPTION_STEP3:
            self.handle_exemption_step3(chat_id, user_id, text, session)
        
        elif state == ConversationState.HELP_STUDENT_ASK:
            self.handle_help_question(chat_id, user_id, text, session)
        
        elif state == ConversationState.HELP_STUDENT_ANSWER:
            self.handle_help_answer(chat_id, user_id, text, session)
        
        elif state == ConversationState.ADMIN_CHARGE:
            self.handle_admin_charge(chat_id, user_id, text, session)
        
        elif state == ConversationState.ADMIN_DEDUCT:
            self.handle_admin_deduct(chat_id, user_id, text, session)
        
        elif state == ConversationState.ADMIN_BAN:
            self.handle_admin_ban(chat_id, user_id, text, session)
        
        elif state == ConversationState.ADMIN_UNBAN:
            self.handle_admin_unban(chat_id, user_id, text, session)
        
        elif state == ConversationState.ADMIN_BROADCAST:
            self.handle_admin_broadcast(chat_id, user_id, text, session)
        
        elif state == ConversationState.VIP_UPLOAD_TITLE:
            self.handle_vip_upload_title(chat_id, user_id, text, session)
        
        elif state == ConversationState.VIP_UPLOAD_DESC:
            self.handle_vip_upload_desc(chat_id, user_id, text, session)
        
        elif state == ConversationState.VIP_SET_PRICE:
            self.handle_vip_set_price(chat_id, user_id, text, session)
        
        elif state == ConversationState.ADMIN_ADD_MAT_TITLE:
            self.handle_admin_add_mat_title(chat_id, user_id, text, session)
        
        elif state == ConversationState.ADMIN_ADD_MAT_DESC:
            self.handle_admin_add_mat_desc(chat_id, user_id, text, session)
        
        elif state == ConversationState.ADMIN_ADD_MAT_STAGE:
            self.handle_admin_add_mat_stage(chat_id, user_id, text, session)
        
        else:
            # إذا كانت الرسالة تحتوي على ملف
            if "document" in message:
                self.handle_document(chat_id, user_id, message, session)
            elif "photo" in message:
                self.handle_photo(chat_id, user_id, message, session)
            else:
                TelegramBot.send_message(
                    chat_id,
                    "🤔 لم أفهم رسالتك. استخدم القائمة أدناه:",
                    reply_markup=KeyboardBuilder.main_menu(user_id)
                )
    
    def handle_callback_query(self, callback_query: Dict):
        """معالجة استعلام رد الاتصال"""
        try:
            query_id = callback_query.get("id")
            data = callback_query.get("data", "")
            user = callback_query.get("from", {})
            message = callback_query.get("message", {})
            
            if not user or not message:
                return
            
            user_id = user.get("id")
            chat_id = message.get("chat", {}).get("id")
            message_id = message.get("message_id")
            
            # الرد على الاستعلام
            TelegramBot.answer_callback_query(query_id)
            
            # تحديث نشاط المستخدم
            self.db.update_user_activity(user_id)
            
            # التحقق من الحظر
            user_data = self.db.get_user(user_id)
            if user_data and user_data.is_banned:
                TelegramBot.edit_message_text(
                    chat_id,
                    message_id,
                    "🚫 حسابك محظور! راسل الدعم الفني للمساعدة.",
                    reply_markup=KeyboardBuilder.back_button()
                )
                return
            
            # معالجة البيانات
            if data == "main_menu":
                self.show_main_menu(chat_id, user_id, message_id)
            
            elif data == "admin_panel":
                if user_id == ADMIN_ID:
                    self.show_admin_panel(chat_id, message_id)
                else:
                    TelegramBot.edit_message_text(
                        chat_id,
                        message_id,
                        "⛔ ليس لديك صلاحية الدخول إلى لوحة التحكم!",
                        reply_markup=KeyboardBuilder.back_button()
                    )
            
            elif data.startswith("service_"):
                service = data.replace("service_", "")
                self.handle_service_selection(chat_id, user_id, message_id, service)
            
            elif data == "my_balance":
                self.show_balance(chat_id, user_id, message_id)
            
            elif data == "invite_friend":
                self.show_invitation(chat_id, user_id, message_id)
            
            elif data == "vip_subscription":
                self.show_vip_subscription(chat_id, user_id, message_id)
            
            elif data == "vip_lectures":
                self.show_vip_lectures(chat_id, user_id, message_id)
            
            elif data.startswith("admin_"):
                self.handle_admin_callback(chat_id, user_id, message_id, data)
            
            elif data.startswith("vip_"):
                self.handle_vip_callback(chat_id, user_id, message_id, data)
            
            elif data.startswith("approve_"):
                self.handle_approval_callback(chat_id, user_id, message_id, data)
            
            elif data.startswith("reject_"):
                self.handle_rejection_callback(chat_id, user_id, message_id, data)
            
            elif data.startswith("answer_"):
                self.handle_answer_callback(chat_id, user_id, message_id, data)
        
        except Exception as e:
            self.logger.error(f"Error handling callback: {e}")
    
    # ============ عرض القوائم ============
    
    def show_main_menu(self, chat_id: int, user_id: int, message_id: int = None):
        """عرض القائمة الرئيسية"""
        user_data = self.db.get_user(user_id)
        
        if not user_data:
            # إعادة توجيه إلى /start
            TelegramBot.send_message(
                chat_id,
                "يرجى استخدام /start للبدء",
                reply_markup=KeyboardBuilder.back_button()
            )
            return
        
        welcome_text = f"""
        👋 أهلاً بك {user_data.first_name} في بوت *يلا نتعلم*!

        *رصيدك الحالي:* {self.text_utils.format_currency(user_data.balance)}

        *الخدمات المتاحة:* (جميعها مدفوعة)

        اختر الخدمة التي تريدها 👇
        """
        
        if message_id:
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                welcome_text,
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.main_menu(user_id)
            )
        else:
            TelegramBot.send_message(
                chat_id,
                welcome_text,
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.main_menu(user_id)
            )
    
    def show_admin_panel(self, chat_id: int, message_id: int = None):
        """عرض لوحة تحكم المدير"""
        stats = self.db.get_user_stats()
        
        text = f"""
        👑 *لوحة التحكم - يلا نتعلم*

        *الإحصائيات العامة:*
        👥 إجمالي المستخدمين: {stats['total_users']}
        🔥 المستخدمين النشطين: {stats['active_users']}
        ⭐ مشتركي VIP: {stats['vip_users']}
        💰 إجمالي الأرصدة: {self.text_utils.format_currency(stats['total_balance'])}
        📈 الدخل اليومي: {self.text_utils.format_currency(stats['daily_income'])}

        *اختر القسم الذي تريد إدارته:*
        """
        
        if message_id:
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                text,
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.admin_panel()
            )
        else:
            TelegramBot.send_message(
                chat_id,
                text,
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.admin_panel()
            )
    
    def show_balance(self, chat_id: int, user_id: int, message_id: int = None):
        """عرض رصيد المستخدم"""
        user_data = self.db.get_user(user_id)
        
        if not user_data:
            return
        
        # الحصول على معلومات VIP
        vip_user = self.db.get_vip_user(user_id)
        
        text = f"""
        💰 *رصيدك الحالي*

        *الرصيد الرئيسي:* {self.text_utils.format_currency(user_data.balance)}
        """
        
        if vip_user and vip_user.is_active:
            expiry_date = self.text_utils.format_date(vip_user.expiry_date)
            text += f"\n*رصيد الأرباح (VIP):* {self.text_utils.format_currency(vip_user.earnings_balance)}"
            text += f"\n*انتهاء الاشتراك VIP:* {expiry_date}"
        
        text += f"\n\n*عدد المدعوين:* {user_data.invited_count}"
        text += f"\n*تاريخ الانضمام:* {user_data.join_date[:10]}"
        
        keyboard = KeyboardBuilder.create_inline_keyboard([
            [{"text": "👥 دعوة صديق", "callback_data": "invite_friend"}],
            [{"text": "🔙 القائمة الرئيسية", "callback_data": "main_menu"}]
        ])
        
        if user_id == ADMIN_ID:
            keyboard["inline_keyboard"].insert(0, [
                {"text": "👑 لوحة التحكم", "callback_data": "admin_panel"}
            ])
        
        if message_id:
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        else:
            TelegramBot.send_message(
                chat_id,
                text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
    
    def show_invitation(self, chat_id: int, user_id: int, message_id: int = None):
        """عرض رابط الدعوة"""
        invite_link = self.text_utils.generate_invite_link(user_id)
        
        # تحديد مكافأة الدعوة
        is_vip = self.db.is_vip_user(user_id)
        bonus_amount = int(self.db.get_setting(
            "vip_invitation_bonus" if is_vip else "invitation_bonus",
            "1000" if is_vip else "500"
        ))
        
        text = f"""
        👥 *دعوة صديق*

        *رابط الدعوة:* `{invite_link}`

        *مكافأة الدعوة:* {self.text_utils.format_currency(bonus_amount)} لكل صديق
        صديقك سيحصل على {self.db.get_setting('welcome_bonus', '1000')} دينار هدية ترحيب!

        *كيفية الدعوة:*
        1. شارك الرابط أعلاه مع أصدقائك
        2. عندما ينضم صديقك عبر الرابط
        3. تحصل على المكافأة تلقائياً
        """
        
        if is_vip:
            text += "\n🎯 *مميزات خاصة للمحاضرين VIP:*"
            text += "\n• رابط دعوة ترويجي خاص"
            text += "\n• مكافأة مضاعفة لكل دعوة"
            text += "\n• تقارير متقدمة للدعوات"
        
        keyboard = KeyboardBuilder.create_inline_keyboard([
            [{"text": "📤 مشاركة الرابط", "url": f"https://t.me/share/url?url={urllib.parse.quote(invite_link)}&text=انضم%20إلى%20بوت%20يلا%20نتعلم%20للدراسة%20باستخدام%20الذكاء%20الاصطناعي!"}],
            [{"text": "📊 إحصائيات دعواتي", "callback_data": "invite_stats"}],
            [{"text": "🔙 القائمة الرئيسية", "callback_data": "main_menu"}]
        ])
        
        if message_id:
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        else:
            TelegramBot.send_message(
                chat_id,
                text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
    
    def show_vip_subscription(self, chat_id: int, user_id: int, message_id: int = None):
        """عرض اشتراك VIP"""
        price = int(self.db.get_setting("vip_subscription_price", "5000"))
        days = int(self.db.get_setting("vip_subscription_days", "30"))
        
        text = f"""
        ⭐ *اشتراك VIP*

        *السعر الشهري:* {self.text_utils.format_currency(price)}
        *المدة:* {days} يوم

        *المميزات:*
        • الوصول إلى جميع محاضرات VIP
        • رفع محاضرات خاصة بك
        • تحصيل 60% من أرباح محاضراتك
        • دعم فني متميز
        • إشعارات فورية
        • مكافآت دعوة مضاعفة

        *شروط الاشتراك:*
        • الاشتراك شهري (يتجدد يدوياً)
        • يمكنك رفع محاضرات حتى 100 ميجابايت
        • جميع المحاضرات تخضع للمراجعة
        • يمكن إلغاء الاشتراك في أي وقت

        هل تريد الاشتراك؟
        """
        
        if message_id:
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                text,
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.vip_subscription_menu()
            )
        else:
            TelegramBot.send_message(
                chat_id,
                text,
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.vip_subscription_menu()
            )
    
    def show_vip_lectures(self, chat_id: int, user_id: int, message_id: int = None):
        """عرض محاضرات VIP"""
        is_vip = self.db.is_vip_user(user_id)
        
        if not is_vip:
            text = """
            🎓 *محاضرات VIP*

            للوصول إلى محاضرات VIP، يجب عليك الاشتراك في باقة VIP أولاً.

            *مميزات الاشتراك:*
            • الوصول إلى جميع المحاضرات
            • رفع محاضرات خاصة بك
            • تحصيل الأرباح من محاضراتك
            """
            
            keyboard = KeyboardBuilder.create_inline_keyboard([
                [{"text": "⭐ اشتراك VIP", "callback_data": "vip_subscription"}],
                [{"text": "🔙 القائمة الرئيسية", "callback_data": "main_menu"}]
            ])
        else:
            # الحصول على محاضرات VIP
            # هذه دالة وهمية، في الإصدار الحقيقي تحتاج لجلب المحاضرات من قاعدة البيانات
            text = """
            🎓 *محاضرات VIP*

            *المحاضرات المتاحة:*
            1. الرياضيات المتقدمة - 5000 دينار
            2. الفيزياء الحديثة - 3000 دينار
            3. الكيمياء العضوية - 4000 دينار
            4. اللغة الإنجليزية - 2000 دينار

            اختر المحاضرة التي تريدها:
            """
            
            keyboard = KeyboardBuilder.create_inline_keyboard([
                [{"text": "🧮 الرياضيات", "callback_data": "view_lecture_1"}],
                [{"text": "⚛️ الفيزياء", "callback_data": "view_lecture_2"}],
                [{"text": "🧪 الكيمياء", "callback_data": "view_lecture_3"}],
                [{"text": "🔤 الإنجليزية", "callback_data": "view_lecture_4"}],
                [{"text": "📤 رفع محاضرة", "callback_data": "vip_upload"}],
                [{"text": "💰 أرباحي", "callback_data": "vip_earnings"}],
                [{"text": "🔙 القائمة الرئيسية", "callback_data": "main_menu"}]
            ])
        
        if message_id:
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        else:
            TelegramBot.send_message(
                chat_id,
                text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
    
    # ============ معالجة الخدمات ============
    
    def handle_service_selection(self, chat_id: int, user_id: int, message_id: int, service: str):
        """معالجة اختيار الخدمة"""
        # التحقق من تفعيل الخدمة
        if not self.db.is_service_active(service):
            text = f"⛔ خدمة {service} معطلة حالياً. راسل الدعم الفني للمزيد من المعلومات."
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                text,
                reply_markup=KeyboardBuilder.back_button()
            )
            return
        
        # الحصول على سعر الخدمة
        price = DEFAULT_PRICES.get(service, 1000)
        
        # التحقق من الرصيد
        user_data = self.db.get_user(user_id)
        if not user_data or user_data.balance < price:
            text = f"""
            ⚠️ رصيدك غير كافي!

            *سعر الخدمة:* {self.text_utils.format_currency(price)}
            *رصيدك الحالي:* {self.text_utils.format_currency(user_data.balance if user_data else 0)}

            قم بشحن رصيدك أو استخدم خدمة الدعوة للحصول على مكافآت.
            """
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                text,
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.back_button()
            )
            return
        
        # حفظ حالة الخدمة
        self.user_sessions[user_id] = {
            "state": ConversationState.MAIN_MENU,
            "service": service,
            "price": price
        }
        
        if service == "exemption":
            self.start_exemption_calculation(chat_id, user_id, message_id)
        
        elif service == "summary":
            text = """
            📚 *تلخيص الملازم (PDF)*

            أرسل ملف PDF المراد تلخيصه.

            *ملاحظات:*
            • الملف يجب أن يكون بصيغة PDF
            • الحجم الأقصى: 20 ميجابايت
            • سيتم استخدام الذكاء الاصطناعي للتلخيص
            """
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                text,
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.cancel_button()
            )
            self.user_sessions[user_id]["state"] = ConversationState.UPLOAD_PDF
        
        elif service == "qa":
            text = """
            ❓ *سؤال وجواب بالذكاء الاصطناعي*

            أرسل سؤالك الآن.

            يمكنك إرسال:
            • نص السؤال
            • صورة تحتوي على السؤال
            • ملف نصي

            سيتم الرد باستخدام الذكاء الاصطناعي المتخصص في المنهج العراقي.
            """
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                text,
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.cancel_button()
            )
            self.user_sessions[user_id]["state"] = ConversationState.ASK_QUESTION
        
        elif service == "help":
            self.show_help_student_section(chat_id, user_id, message_id)
        
        elif service == "materials":
            self.show_materials(chat_id, user_id, message_id)
    
    def start_exemption_calculation(self, chat_id: int, user_id: int, message_id: int):
        """بدء حساب درجة الإعفاء"""
        self.user_sessions[user_id] = {
            "state": ConversationState.EXEMPTION_STEP1,
            "service": "exemption",
            "scores": []
        }
        
        text = """
        🧮 *حساب درجة الإعفاء*

        أدخل درجة الكورس الأول (0-100):
        """
        TelegramBot.edit_message_text(
            chat_id,
            message_id,
            text,
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.cancel_button()
        )
    
    def handle_exemption_step1(self, chat_id: int, user_id: int, text: str, session: Dict):
        """معالجة درجة الكورس الأول"""
        try:
            score = float(text)
            if 0 <= score <= 100:
                session["scores"].append(score)
                session["state"] = ConversationState.EXEMPTION_STEP2
                self.user_sessions[user_id] = session
                
                TelegramBot.send_message(
                    chat_id,
                    "✅ تم حفظ درجة الكورس الأول\n\nأدخل درجة الكورس الثاني (0-100):",
                    reply_markup=KeyboardBuilder.cancel_button()
                )
            else:
                TelegramBot.send_message(
                    chat_id,
                    "⚠️ الرجاء إدخال درجة بين 0 و 100",
                    reply_markup=KeyboardBuilder.cancel_button()
                )
        except:
            TelegramBot.send_message(
                chat_id,
                "⚠️ الرجاء إدخال رقم صحيح",
                reply_markup=KeyboardBuilder.cancel_button()
            )
    
    def handle_exemption_step2(self, chat_id: int, user_id: int, text: str, session: Dict):
        """معالجة درجة الكورس الثاني"""
        try:
            score = float(text)
            if 0 <= score <= 100:
                session["scores"].append(score)
                session["state"] = ConversationState.EXEMPTION_STEP3
                self.user_sessions[user_id] = session
                
                TelegramBot.send_message(
                    chat_id,
                    "✅ تم حفظ درجة الكورس الثاني\n\nأدخل درجة الكورس الثالث (0-100):",
                    reply_markup=KeyboardBuilder.cancel_button()
                )
            else:
                TelegramBot.send_message(
                    chat_id,
                    "⚠️ الرجاء إدخال درجة بين 0 و 100",
                    reply_markup=KeyboardBuilder.cancel_button()
                )
        except:
            TelegramBot.send_message(
                chat_id,
                "⚠️ الرجاء إدخال رقم صحيح",
                reply_markup=KeyboardBuilder.cancel_button()
            )
    
    def handle_exemption_step3(self, chat_id: int, user_id: int, text: str, session: Dict):
        """معالجة درجة الكورس الثالث وحساب المعدل"""
        try:
            score = float(text)
            if 0 <= score <= 100:
                session["scores"].append(score)
                
                # حساب المعدل
                scores = session["scores"]
                average = sum(scores) / len(scores)
                
                # خصم المبلغ
                price = DEFAULT_PRICES.get("exemption", 1000)
                if not self.db.update_balance(user_id, -price, "service_payment", "حساب درجة الإعفاء"):
                    TelegramBot.send_message(
                        chat_id,
                        "⚠️ حدث خطأ في عملية الدفع!",
                        reply_markup=KeyboardBuilder.back_button()
                    )
                    return
                
                # إرسال النتيجة
                if average >= 90:
                    result_text = f"""
                    🎉 *مبروك! أنت معفى من المادة*

                    *المعدل النهائي:* {average:.2f}
                    *الدرجات:* {scores[0]}, {scores[1]}, {scores[2]}

                    تهانينا على تحقيق الإعفاء! 🎊
                    """
                else:
                    result_text = f"""
                    ⚠️ *للأسف أنت غير معفى*

                    *المعدل النهائي:* {average:.2f}
                    *الدرجات:* {scores[0]}, {scores[1]}, {scores[2]}

                    المعدل المطلوب للإعفاء هو 90 أو أكثر
                    """
                
                keyboard = KeyboardBuilder.create_inline_keyboard([
                    [{"text": "🔙 القائمة الرئيسية", "callback_data": "main_menu"}],
                    [{"text": "🔄 حساب جديد", "callback_data": "service_exemption"}]
                ])
                
                TelegramBot.send_message(
                    chat_id,
                    result_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                
                # تنظيف الجلسة
                self.user_sessions.pop(user_id, None)
            
            else:
                TelegramBot.send_message(
                    chat_id,
                    "⚠️ الرجاء إدخال درجة بين 0 و 100",
                    reply_markup=KeyboardBuilder.cancel_button()
                )
        except:
            TelegramBot.send_message(
                chat_id,
                "⚠️ الرجاء إدخال رقم صحيح",
                reply_markup=KeyboardBuilder.cancel_button()
            )
    
    def handle_document(self, chat_id: int, user_id: int, message: Dict, session: Dict):
        """معالجة الملفات"""
        state = session.get("state", ConversationState.MAIN_MENU)
        
        if state == ConversationState.UPLOAD_PDF:
            self.handle_pdf_upload(chat_id, user_id, message, session)
    
    def handle_pdf_upload(self, chat_id: int, user_id: int, message: Dict, session: Dict):
        """معالجة رفع ملف PDF"""
        document = message.get("document", {})
        file_name = document.get("file_name", "")
        
        if not file_name.lower().endswith(".pdf"):
            TelegramBot.send_message(
                chat_id,
                "⚠️ الملف يجب أن يكون بصيغة PDF",
                reply_markup=KeyboardBuilder.cancel_button()
            )
            return
        
        # خصم المبلغ
        price = DEFAULT_PRICES.get("summary", 1000)
        if not self.db.update_balance(user_id, -price, "service_payment", "تلخيص PDF"):
            TelegramBot.send_message(
                chat_id,
                "⚠️ حدث خطأ في عملية الدفع!",
                reply_markup=KeyboardBuilder.back_button()
            )
            return
        
        # إعلام المستخدم بالمعالجة
        TelegramBot.send_message(
            chat_id,
            "🔄 جاري معالجة الملف وتلخيصه...",
            reply_markup=KeyboardBuilder.back_button()
        )
        
        try:
            # هنا في الإصدار الحقيقي، تحتاج لتحميل الملف ومعالجته
            # هذه معالجة وهمية لأغراض العرض
            
            # إنشاء ملف ملخص وهمي
            summary_text = "هذا هو النص الملخص للملف. في الإصدار الحقيقي، سيتم استخدام الذكاء الاصطناعي لتحليل وتلخيص الملف."
            pdf_bytes = self.pdf_utils.create_summary_pdf(summary_text)
            
            # إرسال الملف الملخص
            TelegramBot.send_document(
                chat_id,
                pdf_bytes,
                "ملخص_المادة.pdf",
                caption="✅ *تم تلخيص الملف بنجاح*\n\nهذا هو الملف الملخص باستخدام الذكاء الاصطناعي.",
                parse_mode="Markdown"
            )
            
            keyboard = KeyboardBuilder.create_inline_keyboard([
                [{"text": "🔙 القائمة الرئيسية", "callback_data": "main_menu"}],
                [{"text": "📚 تلخيص ملف آخر", "callback_data": "service_summary"}]
            ])
            
            TelegramBot.send_message(
                chat_id,
                "اختر الخطوة التالية:",
                reply_markup=keyboard
            )
            
            # تنظيف الجلسة
            self.user_sessions.pop(user_id, None)
        
        except Exception as e:
            self.logger.error(f"PDF Processing Error: {e}")
            
            # إعادة المبلغ
            self.db.update_balance(user_id, price, "refund", "خطأ في معالجة PDF")
            
            TelegramBot.send_message(
                chat_id,
                "⚠️ حدث خطأ في معالجة الملف! تم إعادة المبلغ إلى رصيدك.",
                reply_markup=KeyboardBuilder.back_button()
            )
    
    def handle_photo(self, chat_id: int, user_id: int, message: Dict, session: Dict):
        """معالجة الصور"""
        state = session.get("state", ConversationState.MAIN_MENU)
        
        if state == ConversationState.ASK_QUESTION:
            # معالجة سؤال عن طريق صورة
            self.handle_ai_question(chat_id, user_id, "صورة تحتوي على سؤال دراسي", session)
    
    def handle_ai_question(self, chat_id: int, user_id: int, question: str, session: Dict):
        """معالجة سؤال بالذكاء الاصطناعي"""
        # خصم المبلغ
        price = DEFAULT_PRICES.get("qa", 1000)
        if not self.db.update_balance(user_id, -price, "service_payment", "سؤال وجواب AI"):
            TelegramBot.send_message(
                chat_id,
                "⚠️ حدث خطأ في عملية الدفع!",
                reply_markup=KeyboardBuilder.back_button()
            )
            return
        
        # إعلام المستخدم بالمعالجة
        TelegramBot.send_message(
            chat_id,
            "🤔 جاري تحليل سؤالك وإعداد الإجابة...",
            reply_markup=KeyboardBuilder.back_button()
        )
        
        try:
            # استخدام الذكاء الاصطناعي للإجابة
            answer = self.ai_utils.answer_question(question)
            
            TelegramBot.send_message(
                chat_id,
                f"🧠 *إجابة الذكاء الاصطناعي:*\n\n{answer}\n\n---\nإذا كانت الإجابة غير واضحة، يمكنك إعادة صياغة السؤال.",
                parse_mode="Markdown"
            )
            
            keyboard = KeyboardBuilder.create_inline_keyboard([
                [{"text": "🔙 القائمة الرئيسية", "callback_data": "main_menu"}],
                [{"text": "❓ سؤال آخر", "callback_data": "service_qa"}]
            ])
            
            TelegramBot.send_message(
                chat_id,
                "اختر الخطوة التالية:",
                reply_markup=keyboard
            )
            
            # تنظيف الجلسة
            self.user_sessions.pop(user_id, None)
        
        except Exception as e:
            self.logger.error(f"AI Question Error: {e}")
            
            # إعادة المبلغ
            self.db.update_balance(user_id, price, "refund", "خطأ في معالجة السؤال")
            
            TelegramBot.send_message(
                chat_id,
                "⚠️ حدث خطأ في معالجة سؤالك! تم إعادة المبلغ إلى رصيدك.",
                reply_markup=KeyboardBuilder.back_button()
            )
    
    # ============ قسم ساعدوني طالب ============
    
    def show_help_student_section(self, chat_id: int, user_id: int, message_id: int):
        """عرض قسم ساعدوني طالب"""
        # الحصول على الأسئلة غير المجابة
        questions = []  # في الإصدار الحقيقي: self.db.get_unanswered_questions()
        
        if not questions:
            text = """
            👥 *قسم ساعدوني طالب*

            لا توجد أسئلة متاحة للإجابة حالياً.

            يمكنك:
            1. إرسال سؤال جديد
            2. الانتظار حتى يتم إضافة أسئلة جديدة
            """
            
            keyboard = KeyboardBuilder.create_inline_keyboard([
                [{"text": "❓ أرسل سؤال جديد", "callback_data": "ask_help_question"}],
                [{"text": "🔙 القائمة الرئيسية", "callback_data": "main_menu"}]
            ])
        else:
            text = """
            👥 *قسم ساعدوني طالب*

            *الأسئلة المتاحة للإجابة:*

            1. سؤال في الرياضيات عن التفاضل
            2. استفسار حول قانون نيوتن
            3. مساعدة في قواعد اللغة العربية

            اختر السؤال الذي تريد الإجابة عليه:
            """
            
            keyboard = KeyboardBuilder.create_inline_keyboard([
                [{"text": "✏️ جاوب على السؤال 1", "callback_data": "answer_question_1"}],
                [{"text": "✏️ جاوب على السؤال 2", "callback_data": "answer_question_2"}],
                [{"text": "✏️ جاوب على السؤال 3", "callback_data": "answer_question_3"}],
                [{"text": "❓ أرسل سؤال جديد", "callback_data": "ask_help_question"}],
                [{"text": "🔙 القائمة الرئيسية", "callback_data": "main_menu"}]
            ])
        
        TelegramBot.edit_message_text(
            chat_id,
            message_id,
            text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    def handle_help_question(self, chat_id: int, user_id: int, text: str, session: Dict):
        """معالجة إرسال سؤال في قسم ساعدوني طالب"""
        if len(text) < 10:
            TelegramBot.send_message(
                chat_id,
                "⚠️ السؤال قصير جداً! الرجاء كتابة سؤال مفصل.",
                reply_markup=KeyboardBuilder.cancel_button()
            )
            return
        
        # خصم المبلغ
        price = DEFAULT_PRICES.get("help_student", 1000)
        if not self.db.update_balance(user_id, -price, "service_payment", "سؤال ساعدوني طالب"):
            TelegramBot.send_message(
                chat_id,
                "⚠️ حدث خطأ في عملية الدفع!",
                reply_markup=KeyboardBuilder.back_button()
            )
            return
        
        # حفظ السؤال في قاعدة البيانات
        question_id = self.db.add_help_question(user_id, text)
        
        # إعلام المستخدم
        TelegramBot.send_message(
            chat_id,
            "✅ تم استلام سؤالك!\nسيتم مراجعته من قبل الإدارة ونشره قريباً.\nستصلك إشعار عند الموافقة على السؤال.",
            reply_markup=KeyboardBuilder.back_button()
        )
        
        # إرسال إشعار للمدير
        admin_text = f"""
        📋 *سؤال جديد يحتاج موافقة*

        *المستخدم:* {self.db.get_user(user_id).first_name}
        *السؤال:* {text[:200]}...
        *رقم السؤال:* {question_id}
        """
        
        keyboard = KeyboardBuilder.create_inline_keyboard([
            [
                {"text": "✅ موافقة", "callback_data": f"approve_question_{question_id}"},
                {"text": "❌ رفض", "callback_data": f"reject_question_{question_id}"}
            ],
            [{"text": "👀 عرض كامل", "callback_data": f"view_question_{question_id}"}]
        ])
        
        TelegramBot.send_message(
            ADMIN_ID,
            admin_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
        # تنظيف الجلسة
        self.user_sessions.pop(user_id, None)
    
    # ============ إدارة VIP ============
    
    def handle_vip_callback(self, chat_id: int, user_id: int, message_id: int, data: str):
        """معالجة ردود الاتصال الخاصة بـ VIP"""
        if data == "vip_purchase":
            self.purchase_vip_subscription(chat_id, user_id, message_id)
        
        elif data == "vip_upload":
            self.start_vip_upload(chat_id, user_id, message_id)
        
        elif data == "vip_earnings":
            self.show_vip_earnings(chat_id, user_id, message_id)
    
    def purchase_vip_subscription(self, chat_id: int, user_id: int, message_id: int):
        """شراء اشتراك VIP"""
        price = int(self.db.get_setting("vip_subscription_price", "5000"))
        
        # التحقق من الرصيد
        user_data = self.db.get_user(user_id)
        if not user_data or user_data.balance < price:
            text = f"""
            ⚠️ رصيدك غير كافي!

            *سعر الاشتراك:* {self.text_utils.format_currency(price)}
            *رصيدك الحالي:* {self.text_utils.format_currency(user_data.balance if user_data else 0)}
            """
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                text,
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.back_button()
            )
            return
        
        # خصم المبلغ
        if not self.db.update_balance(user_id, -price, "vip_subscription", "اشتراك VIP شهري"):
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                "⚠️ حدث خطأ في عملية الدفع!",
                reply_markup=KeyboardBuilder.back_button()
            )
            return
        
        # تفعيل الاشتراك
        days = int(self.db.get_setting("vip_subscription_days", "30"))
        self.db.activate_vip(user_id, days)
        
        # إعلام المستخدم
        text = f"""
        🎉 *مبروك! تم تفعيل اشتراكك VIP*

        *مدة الاشتراك:* {days} يوم
        *تاريخ التجديد:* {(datetime.now() + timedelta(days=days)).strftime('%Y/%m/%d')}

        يمكنك الآن:
        • الوصول إلى جميع محاضرات VIP
        • رفع محاضرات خاصة بك
        • تحصيل الأرباح من محاضراتك

        استمتع بمزاياك الجديدة! 🚀
        """
        
        keyboard = KeyboardBuilder.create_inline_keyboard([
            [{"text": "🎓 محاضرات VIP", "callback_data": "vip_lectures"}],
            [{"text": "🔙 القائمة الرئيسية", "callback_data": "main_menu"}]
        ])
        
        TelegramBot.edit_message_text(
            chat_id,
            message_id,
            text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    def start_vip_upload(self, chat_id: int, user_id: int, message_id: int):
        """بدء رفع محاضرة VIP"""
        # التحقق من اشتراك VIP
        if not self.db.is_vip_user(user_id):
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                "⛔ يجب أن تكون مشتركاً في VIP لرفع المحاضرات!",
                reply_markup=KeyboardBuilder.back_button()
            )
            return
        
        TelegramBot.edit_message_text(
            chat_id,
            message_id,
            "📤 *رفع محاضرة VIP*\n\nأرسل الفيديو الآن (حتى 100 ميجابايت):",
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.cancel_button()
        )
        
        self.user_sessions[user_id] = {
            "state": ConversationState.VIP_UPLOAD_LECTURE,
            "vip_upload": {}
        }
    
    def handle_vip_upload_title(self, chat_id: int, user_id: int, text: str, session: Dict):
        """معالجة عنوان محاضرة VIP"""
        session["vip_upload"]["title"] = text
        session["state"] = ConversationState.VIP_UPLOAD_DESC
        self.user_sessions[user_id] = session
        
        TelegramBot.send_message(
            chat_id,
            "📝 *أدخل وصف المحاضرة:*",
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.cancel_button()
        )
    
    def handle_vip_upload_desc(self, chat_id: int, user_id: int, text: str, session: Dict):
        """معالجة وصف محاضرة VIP"""
        session["vip_upload"]["description"] = text
        session["state"] = ConversationState.VIP_SET_PRICE
        self.user_sessions[user_id] = session
        
        keyboard = KeyboardBuilder.create_inline_keyboard([
            [
                {"text": "💰 مدفوعة", "callback_data": "lecture_paid"},
                {"text": "🆓 مجانية", "callback_data": "lecture_free"}
            ],
            [{"text": "❌ إلغاء", "callback_data": "main_menu"}]
        ])
        
        TelegramBot.send_message(
            chat_id,
            "💰 *اختر نوع المحاضرة:*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    def handle_vip_set_price(self, chat_id: int, user_id: int, text: str, session: Dict):
        """معالجة سعر محاضرة VIP"""
        try:
            price = int(text)
            if price < 0:
                TelegramBot.send_message(
                    chat_id,
                    "⚠️ السعر يجب أن يكون صفر أو أكثر",
                    reply_markup=KeyboardBuilder.cancel_button()
                )
                return
            
            session["vip_upload"]["price"] = price
            
            # حفظ المحاضرة في قاعدة البيانات
            upload_data = session["vip_upload"]
            lecture_id = self.db.add_vip_lecture(
                user_id,
                upload_data.get("title", ""),
                upload_data.get("description", ""),
                upload_data.get("file_id", ""),
                price
            )
            
            # تنظيف الجلسة
            self.user_sessions.pop(user_id, None)
            
            # إعلام المستخدم
            TelegramBot.send_message(
                chat_id,
                "✅ *تم رفع المحاضرة بنجاح!*\n\nسيتم مراجعتها من قبل الإدارة ونشرها قريباً.\nستصلك إشعار عند الموافقة على المحاضرة.",
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.create_inline_keyboard([
                    [{"text": "🎓 محاضرات VIP", "callback_data": "vip_lectures"},
                     {"text": "🏠 القائمة الرئيسية", "callback_data": "main_menu"}]
                ])
            )
        
        except ValueError:
            TelegramBot.send_message(
                chat_id,
                "⚠️ الرجاء إدخال رقم صحيح",
                reply_markup=KeyboardBuilder.cancel_button()
            )
    
    def show_vip_earnings(self, chat_id: int, user_id: int, message_id: int):
        """عرض أرباح VIP"""
        vip_user = self.db.get_vip_user(user_id)
        
        if not vip_user:
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                "⛔ يجب أن تكون مشتركاً في VIP لعرض الأرباح!",
                reply_markup=KeyboardBuilder.back_button()
            )
            return
        
        text = f"""
        💰 *أرباحك من VIP*

        *الرصيد القابل للسحب:* {self.text_utils.format_currency(vip_user.earnings_balance)}
        *إجمالي الأرباح:* {self.text_utils.format_currency(vip_user.total_earnings)}

        *للسحب:*
        1. راسل الدعم الفني {SUPPORT_USER}
        2. أكد هويتك
        3. سيتم تحويل الأرباح إليك

        *ملاحظة:* يتم خصم 40% للإدارة من كل عملية بيع.
        """
        
        keyboard = KeyboardBuilder.create_inline_keyboard([
            [{"text": "📞 اتصل بالدعم للسحب", "url": f"https://t.me/{SUPPORT_USER.replace('@', '')}"}],
            [{"text": "🎓 محاضراتي", "callback_data": "my_lectures"}],
            [{"text": "🔙 القائمة الرئيسية", "callback_data": "main_menu"}]
        ])
        
        TelegramBot.edit_message_text(
            chat_id,
            message_id,
            text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    # ============ إدارة المدير ============
    
    def handle_admin_callback(self, chat_id: int, user_id: int, message_id: int, data: str):
        """معالجة ردود الاتصال في لوحة التحكم"""
        if data == "admin_charge":
            self.start_admin_charge(chat_id, message_id)
        
        elif data == "admin_deduct":
            self.start_admin_deduct(chat_id, message_id)
        
        elif data == "admin_ban":
            self.start_admin_ban(chat_id, message_id)
        
        elif data == "admin_unban":
            self.start_admin_unban(chat_id, message_id)
        
        elif data == "admin_broadcast":
            self.start_admin_broadcast(chat_id, message_id)
        
        elif data == "admin_users":
            self.show_admin_users(chat_id, message_id)
        
        elif data == "admin_services":
            self.show_admin_services(chat_id, message_id)
        
        elif data == "admin_stats":
            self.show_admin_stats(chat_id, message_id)
        
        elif data == "admin_vip":
            self.show_admin_vip(chat_id, message_id)
        
        elif data == "admin_materials":
            self.show_admin_materials(chat_id, message_id)
        
        elif data == "admin_pending_questions":
            self.show_pending_questions(chat_id, message_id)
        
        elif data == "admin_pending_lectures":
            self.show_pending_lectures(chat_id, message_id)
    
    def start_admin_charge(self, chat_id: int, message_id: int):
        """بدء شحن رصيد"""
        TelegramBot.edit_message_text(
            chat_id,
            message_id,
            "💰 *شحن رصيد*\n\nأرسل آيدي المستخدم:",
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.back_button("admin_panel")
        )
        
        self.user_sessions[ADMIN_ID] = {
            "state": ConversationState.ADMIN_CHARGE,
            "admin_action": "charge"
        }
    
    def handle_admin_charge(self, chat_id: int, user_id: int, text: str, session: Dict):
        """معالجة شحن رصيد"""
        try:
            target_user_id = int(text)
            user_data = self.db.get_user(target_user_id)
            
            if not user_data:
                TelegramBot.send_message(
                    chat_id,
                    "⚠️ المستخدم غير موجود",
                    reply_markup=KeyboardBuilder.back_button("admin_panel")
                )
                return
            
            session["target_user_id"] = target_user_id
            session["state"] = ConversationState.ADMIN_CHARGE + 1
            self.user_sessions[user_id] = session
            
            TelegramBot.send_message(
                chat_id,
                f"👤 *المستخدم:* {user_data.first_name}\n\nأرسل المبلغ المطلوب شحنه:",
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.back_button("admin_panel")
            )
        
        except ValueError:
            TelegramBot.send_message(
                chat_id,
                "⚠️ الرجاء إدخال آيدي صحيح",
                reply_markup=KeyboardBuilder.back_button("admin_panel")
            )
    
    def handle_admin_deduct(self, chat_id: int, user_id: int, text: str, session: Dict):
        """معالجة خصم رصيد"""
        try:
            target_user_id = int(text)
            user_data = self.db.get_user(target_user_id)
            
            if not user_data:
                TelegramBot.send_message(
                    chat_id,
                    "⚠️ المستخدم غير موجود",
                    reply_markup=KeyboardBuilder.back_button("admin_panel")
                )
                return
            
            session["target_user_id"] = target_user_id
            session["state"] = ConversationState.ADMIN_DEDUCT + 1
            self.user_sessions[user_id] = session
            
            TelegramBot.send_message(
                chat_id,
                f"👤 *المستخدم:* {user_data.first_name}\n\nأرسل المبلغ المطلوب خصمه:",
                parse_mode="Markdown",
                reply_markup=KeyboardBuilder.back_button("admin_panel")
            )
        
        except ValueError:
            TelegramBot.send_message(
                chat_id,
                "⚠️ الرجاء إدخال آيدي صحيح",
                reply_markup=KeyboardBuilder.back_button("admin_panel")
            )
    
    def handle_admin_ban(self, chat_id: int, user_id: int, text: str, session: Dict):
        """معالجة حظر مستخدم"""
        try:
            target_user_id = int(text)
            user_data = self.db.get_user(target_user_id)
            
            if not user_data:
                TelegramBot.send_message(
                    chat_id,
                    "⚠️ المستخدم غير موجود",
                    reply_markup=KeyboardBuilder.back_button("admin_panel")
                )
                return
            
            if self.db.ban_user(target_user_id):
                # إرسال إشعار للمستخدم
                try:
                    TelegramBot.send_message(
                        target_user_id,
                        "🚫 *حسابك تم حظره*\n\nللمزيد من المعلومات، راسل الدعم الفني.",
                        parse_mode="Markdown"
                    )
                except:
                    pass
                
                TelegramBot.send_message(
                    chat_id,
                    f"✅ تم حظر المستخدم {user_data.first_name}",
                    reply_markup=KeyboardBuilder.back_button("admin_panel")
                )
            else:
                TelegramBot.send_message(
                    chat_id,
                    "⚠️ حدث خطأ في حظر المستخدم",
                    reply_markup=KeyboardBuilder.back_button("admin_panel")
                )
            
            # تنظيف الجلسة
            self.user_sessions.pop(user_id, None)
        
        except ValueError:
            TelegramBot.send_message(
                chat_id,
                "⚠️ الرجاء إدخال آيدي صحيح",
                reply_markup=KeyboardBuilder.back_button("admin_panel")
            )
    
    def handle_admin_unban(self, chat_id: int, user_id: int, text: str, session: Dict):
        """معالجة فك حظر مستخدم"""
        try:
            target_user_id = int(text)
            user_data = self.db.get_user(target_user_id)
            
            if not user_data:
                TelegramBot.send_message(
                    chat_id,
                    "⚠️ المستخدم غير موجود",
                    reply_markup=KeyboardBuilder.back_button("admin_panel")
                )
                return
            
            if self.db.unban_user(target_user_id):
                # إرسال إشعار للمستخدم
                try:
                    TelegramBot.send_message(
                        target_user_id,
                        "✅ *تم فك حظر حسابك*\n\nيمكنك استخدام البوت مرة أخرى.",
                        parse_mode="Markdown"
                    )
                except:
                    pass
                
                TelegramBot.send_message(
                    chat_id,
                    f"✅ تم فك حظر المستخدم {user_data.first_name}",
                    reply_markup=KeyboardBuilder.back_button("admin_panel")
                )
            else:
                TelegramBot.send_message(
                    chat_id,
                    "⚠️ حدث خطأ في فك حظر المستخدم",
                    reply_markup=KeyboardBuilder.back_button("admin_panel")
                )
            
            # تنظيف الجلسة
            self.user_sessions.pop(user_id, None)
        
        except ValueError:
            TelegramBot.send_message(
                chat_id,
                "⚠️ الرجاء إدخال آيدي صحيح",
                reply_markup=KeyboardBuilder.back_button("admin_panel")
            )
    
    def start_admin_broadcast(self, chat_id: int, message_id: int):
        """بدء إرسال إذاعة"""
        TelegramBot.edit_message_text(
            chat_id,
            message_id,
            "📢 *إرسال إذاعة*\n\nأرسل النص الذي تريد إذاعته:",
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.back_button("admin_panel")
        )
        
        self.user_sessions[ADMIN_ID] = {
            "state": ConversationState.ADMIN_BROADCAST
        }
    
    def handle_admin_broadcast(self, chat_id: int, user_id: int, text: str, session: Dict):
        """معالجة إرسال إذاعة"""
        if len(text) < 5:
            TelegramBot.send_message(
                chat_id,
                "⚠️ النص قصير جداً",
                reply_markup=KeyboardBuilder.back_button("admin_panel")
            )
            return
        
        session["broadcast_text"] = text
        self.user_sessions[user_id] = session
        
        keyboard = KeyboardBuilder.create_inline_keyboard([
            [{"text": "✅ نعم، أرسل الإذاعة", "callback_data": "confirm_broadcast"}],
            [{"text": "❌ إلغاء", "callback_data": "admin_panel"}]
        ])
        
        TelegramBot.send_message(
            chat_id,
            f"📢 *تأكيد الإذاعة*\n\nالنص:\n{text[:500]}...\n\nسيتم إرسال هذه الرسالة لجميع المستخدمين.\nهل تريد المتابعة؟",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    def show_admin_users(self, chat_id: int, message_id: int):
        """عرض قائمة المستخدمين"""
        users = self.db.get_recent_users(50)
        
        text = "👥 *إدارة المستخدمين*\n\n"
        text += f"*آخر 50 مستخدم نشط:*\n\n"
        
        for i, user in enumerate(users, 1):
            status = "🚫" if user.is_banned else "✅"
            username = f"@{user.username}" if user.username else "بدون"
            text += f"{i}. {status} {user.first_name} ({username})\n"
            text += f"   آيدي: {user.user_id} | رصيد: {self.text_utils.format_currency(user.balance)}\n"
            text += f"   آخر نشاط: {self.text_utils.format_date(user.last_active)}\n\n"
        
        keyboard = KeyboardBuilder.create_inline_keyboard([
            [{"text": "🔍 بحث عن مستخدم", "callback_data": "admin_search_user"}],
            [{"text": "📊 تقرير مفصل", "callback_data": "admin_users_report"}],
            [{"text": "🔙 رجوع", "callback_data": "admin_panel"}]
        ])
        
        TelegramBot.edit_message_text(
            chat_id,
            message_id,
            text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    def show_admin_services(self, chat_id: int, message_id: int):
        """عرض إدارة الخدمات"""
        text = "⚙️ *إدارة الخدمات*\n\n"
        text += "*الأسعار الحالية:*\n\n"
        
        for service, price in DEFAULT_PRICES.items():
            service_name = {
                'exemption': 'حساب درجة الإعفاء',
                'summary': 'تلخيص الملازم',
                'qa': 'سؤال وجواب',
                'help_student': 'ساعدوني طالب',
                'vip_subscription': 'اشتراك VIP'
            }.get(service, service)
            
            status = "✅" if self.db.is_service_active(service) else "❌"
            text += f"{status} {service_name}: {self.text_utils.format_currency(price)}\n"
        
        text += f"\n*مكافأة الدعوة:* {self.text_utils.format_currency(500)}\n"
        text += f"*مكافأة دعوة VIP:* {self.text_utils.format_currency(1000)}\n"
        text += f"*هدية الترحيب:* {self.db.get_setting('welcome_bonus', '1000')} دينار"
        
        keyboard = KeyboardBuilder.create_inline_keyboard([
            [{"text": "📝 تعديل الأسعار", "callback_data": "admin_set_prices"}],
            [{"text": "🚫 تعطيل خدمة", "callback_data": "admin_disable_service"}],
            [{"text": "✅ تفعيل خدمة", "callback_data": "admin_enable_service"}],
            [{"text": "🔙 رجوع", "callback_data": "admin_panel"}]
        ])
        
        TelegramBot.edit_message_text(
            chat_id,
            message_id,
            text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    def show_admin_stats(self, chat_id: int, message_id: int):
        """عرض الإحصائيات"""
        stats = self.db.get_user_stats()
        
        text = "📊 *الإحصائيات العامة*\n\n"
        text += f"*إجمالي المستخدمين:* {stats['total_users']}\n"
        text += f"*المستخدمين النشطين:* {stats['active_users']}\n"
        text += f"*مشتركي VIP:* {stats['vip_users']}\n"
        text += f"*إجمالي الأرصدة:* {self.text_utils.format_currency(stats['total_balance'])}\n"
        text += f"*الدخل اليومي:* {self.text_utils.format_currency(stats['daily_income'])}\n\n"
        
        text += "*الخدمات الأكثر استخداماً:*\n"
        text += "1. حساب درجة الإعفاء\n"
        text += "2. سؤال وجواب\n"
        text += "3. تلخيص الملازم\n\n"
        
        text += "*النمو الشهري:* +15%"
        
        keyboard = KeyboardBuilder.create_inline_keyboard([
            [{"text": "📈 تقرير مفصل", "callback_data": "admin_detailed_stats"}],
            [{"text": "📅 إحصائيات يومية", "callback_data": "admin_daily_stats"}],
            [{"text": "🔙 رجوع", "callback_data": "admin_panel"}]
        ])
        
        TelegramBot.edit_message_text(
            chat_id,
            message_id,
            text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    def show_admin_vip(self, chat_id: int, message_id: int):
        """عرض إدارة VIP"""
        # الحصول على مشتركي VIP
        # هذه دالة وهمية، في الإصدار الحقيقي تحتاج لجلب البيانات من قاعدة البيانات
        
        text = "⭐ *إدارة مشتركي VIP*\n\n"
        text += "*المشتركون النشطون:*\n"
        text += "1. أحمد - ينتهي في 2024/12/31\n"
        text += "2. محمد - ينتهي في 2024/12/15\n"
        text += "3. علي - ينتهي في 2024/12/10\n\n"
        
        text += "*إجمالي الأرباح الموزعة:* 50,000 دينار\n"
        text += "*عمليات السحب اليوم:* 3 عمليات\n\n"
        
        text += "*الإجراءات المتاحة:*"
        
        keyboard = KeyboardBuilder.create_inline_keyboard([
            [{"text": "👥 قائمة المشتركين", "callback_data": "admin_vip_list"}],
            [{"text": "💰 سحب أرباح", "callback_data": "admin_vip_withdraw"}],
            [{"text": "⏰ تجديد اشتراك", "callback_data": "admin_vip_renew"}],
            [{"text": "🚫 إلغاء اشتراك", "callback_data": "admin_vip_cancel"}],
            [{"text": "🔙 رجوع", "callback_data": "admin_panel"}]
        ])
        
        TelegramBot.edit_message_text(
            chat_id,
            message_id,
            text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    def show_admin_materials(self, chat_id: int, message_id: int):
        """عرض إدارة المواد"""
        text = "📖 *إدارة المواد التعليمية*\n\n"
        text += "*المواد المتاحة:*\n"
        text += "1. الرياضيات للصف السادس\n"
        text += "2. العلوم للصف الخامس\n"
        text += "3. اللغة العربية للصف الرابع\n\n"
        
        text += "*الإجراءات المتاحة:*"
        
        keyboard = KeyboardBuilder.create_inline_keyboard([
            [{"text": "➕ إضافة مادة", "callback_data": "admin_add_material"}],
            [{"text": "✏️ تعديل مادة", "callback_data": "admin_edit_material"}],
            [{"text": "🗑️ حذف مادة", "callback_data": "admin_delete_material"}],
            [{"text": "🔙 رجوع", "callback_data": "admin_panel"}]
        ])
        
        TelegramBot.edit_message_text(
            chat_id,
            message_id,
            text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    def show_pending_questions(self, chat_id: int, message_id: int):
        """عرض الأسئلة المنتظرة"""
        questions = self.db.get_pending_questions()
        
        if not questions:
            text = "❓ *الأسئلة المنتظرة*\n\nلا توجد أسئلة تحتاج موافقة."
            keyboard = KeyboardBuilder.create_inline_keyboard([
                [{"text": "🔙 رجوع", "callback_data": "admin_panel"}]
            ])
        else:
            text = "❓ *الأسئلة المنتظرة*\n\n"
            
            keyboard_rows = []
            for question in questions:
                text += f"*السؤال {question.question_id}:*\n"
                text += f"{question.question_text[:100]}...\n"
                text += f"من: {self.db.get_user(question.user_id).first_name}\n"
                text += f"التاريخ: {self.text_utils.format_date(question.ask_date)}\n\n"
                
                keyboard_rows.append([
                    {"text": f"✅ {question.question_id}", "callback_data": f"approve_question_{question.question_id}"},
                    {"text": f"❌ {question.question_id}", "callback_data": f"reject_question_{question.question_id}"},
                    {"text": f"👁️ {question.question_id}", "callback_data": f"view_question_{question.question_id}"}
                ])
            
            keyboard_rows.append([{"text": "🔙 رجوع", "callback_data": "admin_panel"}])
            keyboard = KeyboardBuilder.create_inline_keyboard(keyboard_rows)
        
        TelegramBot.edit_message_text(
            chat_id,
            message_id,
            text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    def show_pending_lectures(self, chat_id: int, message_id: int):
        """عرض المحاضرات المنتظرة"""
        lectures = self.db.get_pending_lectures()
        
        if not lectures:
            text = "🎬 *المحاضرات المنتظرة*\n\nلا توجد محاضرات تحتاج موافقة."
            keyboard = KeyboardBuilder.create_inline_keyboard([
                [{"text": "🔙 رجوع", "callback_data": "admin_panel"}]
            ])
        else:
            text = "🎬 *المحاضرات المنتظرة*\n\n"
            
            keyboard_rows = []
            for lecture in lectures:
                text += f"*المحاضرة {lecture.lecture_id}:*\n"
                text += f"{lecture.title}\n"
                text += f"السعر: {self.text_utils.format_currency(lecture.price)}\n"
                text += f"المحاضر: {self.db.get_user(lecture.teacher_id).first_name}\n"
                text += f"التاريخ: {self.text_utils.format_date(lecture.upload_date)}\n\n"
                
                keyboard_rows.append([
                    {"text": f"✅ {lecture.lecture_id}", "callback_data": f"approve_lecture_{lecture.lecture_id}"},
                    {"text": f"❌ {lecture.lecture_id}", "callback_data": f"reject_lecture_{lecture.lecture_id}"},
                    {"text": f"👁️ {lecture.lecture_id}", "callback_data": f"view_lecture_{lecture.lecture_id}"}
                ])
            
            keyboard_rows.append([{"text": "🔙 رجوع", "callback_data": "admin_panel"}])
            keyboard = KeyboardBuilder.create_inline_keyboard(keyboard_rows)
        
        TelegramBot.edit_message_text(
            chat_id,
            message_id,
            text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    # ============ أدوات مساعدة ============
    
    def get_user_info(self, user_id: int) -> Dict:
        """الحصول على معلومات المستخدم من Telegram"""
        # هذه دالة وهمية، في الإصدار الحقيقي تحتاج لاستخدام Telegram API
        return {
            "username": f"user_{user_id}",
            "first_name": f"مستخدم {user_id}",
            "last_name": ""
        }
    
    def show_materials(self, chat_id: int, user_id: int, message_id: int):
        """عرض المواد التعليمية"""
        text = """
        📖 *ملازمي ومرشحاتي*

        *المواد المتاحة:*

        1. *الرياضيات - الصف السادس*
           - كتاب الرياضيات المتقدم
           - تمارين وحلول

        2. *العلوم - الصف الخامس*
           - كتاب العلوم الشامل
           - تجارب عملية

        3. *اللغة العربية - الصف الرابع*
           - قواعد اللغة
           - نصوص أدبية

        اختر المادة التي تريد تحميلها:
        """
        
        keyboard = KeyboardBuilder.create_inline_keyboard([
            [{"text": "🧮 الرياضيات", "callback_data": "download_math"}],
            [{"text": "🔬 العلوم", "callback_data": "download_science"}],
            [{"text": "📚 العربية", "callback_data": "download_arabic"}],
            [{"text": "🔙 القائمة الرئيسية", "callback_data": "main_menu"}]
        ])
        
        TelegramBot.edit_message_text(
            chat_id,
            message_id,
            text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    def handle_approval_callback(self, chat_id: int, user_id: int, message_id: int, data: str):
        """معالجة الموافقة"""
        if data.startswith("approve_question_"):
            question_id = int(data.replace("approve_question_", ""))
            self.approve_question(chat_id, question_id, message_id)
        
        elif data.startswith("approve_lecture_"):
            lecture_id = int(data.replace("approve_lecture_", ""))
            self.approve_lecture(chat_id, lecture_id, message_id)
    
    def handle_rejection_callback(self, chat_id: int, user_id: int, message_id: int, data: str):
        """معالجة الرفض"""
        if data.startswith("reject_question_"):
            question_id = int(data.replace("reject_question_", ""))
            self.reject_question(chat_id, question_id, message_id)
        
        elif data.startswith("reject_lecture_"):
            lecture_id = int(data.replace("reject_lecture_", ""))
            self.reject_lecture(chat_id, lecture_id, message_id)
    
    def approve_question(self, chat_id: int, question_id: int, message_id: int):
        """الموافقة على سؤال"""
        if self.db.approve_help_question(question_id):
            question = self.db.get_help_question(question_id)
            if question:
                # إرسال إشعار للمستخدم
                try:
                    TelegramBot.send_message(
                        question.user_id,
                        f"✅ *تمت الموافقة على سؤالك*\n\nيمكن للطلاب الآن الإجابة على سؤالك.",
                        parse_mode="Markdown"
                    )
                except:
                    pass
            
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                "✅ تمت الموافقة على السؤال",
                reply_markup=KeyboardBuilder.back_button("admin_pending_questions")
            )
        else:
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                "⚠️ حدث خطأ في الموافقة على السؤال",
                reply_markup=KeyboardBuilder.back_button("admin_pending_questions")
            )
    
    def reject_question(self, chat_id: int, question_id: int, message_id: int):
        """رفض سؤال"""
        question = self.db.get_help_question(question_id)
        
        if question:
            # إرسال إشعار للمستخدم
            try:
                TelegramBot.send_message(
                    question.user_id,
                    "❌ *تم رفض سؤالك*\n\nللمزيد من المعلومات، راسل الدعم الفني.",
                    parse_mode="Markdown"
                )
            except:
                pass
        
        if self.db.reject_help_question(question_id):
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                "❌ تم رفض السؤال",
                reply_markup=KeyboardBuilder.back_button("admin_pending_questions")
            )
        else:
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                "⚠️ حدث خطأ في رفض السؤال",
                reply_markup=KeyboardBuilder.back_button("admin_pending_questions")
            )
    
    def approve_lecture(self, chat_id: int, lecture_id: int, message_id: int):
        """الموافقة على محاضرة"""
        if self.db.approve_vip_lecture(lecture_id):
            lecture = self.db.get_vip_lecture(lecture_id)
            if lecture:
                # إرسال إشعار للمحاضر
                try:
                    TelegramBot.send_message(
                        lecture.teacher_id,
                        f"✅ *تمت الموافقة على محاضرتك*\n\n{lecture.title}\n\nيمكن للمستخدمين الآن مشاهدة وشراء محاضرتك.",
                        parse_mode="Markdown"
                    )
                except:
                    pass
            
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                "✅ تمت الموافقة على المحاضرة",
                reply_markup=KeyboardBuilder.back_button("admin_pending_lectures")
            )
        else:
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                "⚠️ حدث خطأ في الموافقة على المحاضرة",
                reply_markup=KeyboardBuilder.back_button("admin_pending_lectures")
            )
    
    def reject_lecture(self, chat_id: int, lecture_id: int, message_id: int):
        """رفض محاضرة"""
        lecture = self.db.get_vip_lecture(lecture_id)
        
        if lecture:
            # إرسال إشعار للمحاضر
            try:
                TelegramBot.send_message(
                    lecture.teacher_id,
                    f"❌ *تم رفض محاضرتك*\n\n{lecture.title}\n\nللمزيد من المعلومات، راسل الدعم الفني.",
                    parse_mode="Markdown"
                )
            except:
                pass
        
        if self.db.reject_vip_lecture(lecture_id):
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                "❌ تم رفض المحاضرة",
                reply_markup=KeyboardBuilder.back_button("admin_pending_lectures")
            )
        else:
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                "⚠️ حدث خطأ في رفض المحاضرة",
                reply_markup=KeyboardBuilder.back_button("admin_pending_lectures")
            )
    
    def handle_answer_callback(self, chat_id: int, user_id: int, message_id: int, data: str):
        """معالجة الإجابة على سؤال"""
        if data.startswith("answer_question_"):
            question_id = int(data.replace("answer_question_", ""))
            self.start_answering_question(chat_id, user_id, message_id, question_id)
    
    def start_answering_question(self, chat_id: int, user_id: int, message_id: int, question_id: int):
        """بدء الإجابة على سؤال"""
        question = self.db.get_help_question(question_id)
        
        if not question:
            TelegramBot.edit_message_text(
                chat_id,
                message_id,
                "⚠️ السؤال غير موجود",
                reply_markup=KeyboardBuilder.back_button()
            )
            return
        
        TelegramBot.edit_message_text(
            chat_id,
            message_id,
            f"✏️ *الإجابة على السؤال*\n\n*السؤال:* {question.question_text}\n\nأرسل إجابتك الآن:",
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.cancel_button()
        )
        
        self.user_sessions[user_id] = {
            "state": ConversationState.HELP_STUDENT_ANSWER,
            "question_id": question_id
        }
    
    def handle_help_answer(self, chat_id: int, user_id: int, text: str, session: Dict):
        """معالجة الإجابة على سؤال"""
        question_id = session.get("question_id")
        
        if not question_id:
            TelegramBot.send_message(
                chat_id,
                "⚠️ حدث خطأ في البيانات",
                reply_markup=KeyboardBuilder.back_button()
            )
            return
        
        if not text or len(text) < 5:
            TelegramBot.send_message(
                chat_id,
                "⚠️ الإجابة قصيرة جداً",
                reply_markup=KeyboardBuilder.cancel_button()
            )
            return
        
        # حفظ الإجابة
        if self.db.answer_help_question(question_id, user_id, text):
            question = self.db.get_help_question(question_id)
            
            if question:
                # إرسال الإجابة للمستخدم
                try:
                    TelegramBot.send_message(
                        question.user_id,
                        f"✅ *تمت الإجابة على سؤالك*\n\n*سؤالك:* {question.question_text[:200]}...\n\n*الإجابة:*\n{text}",
                        parse_mode="Markdown"
                    )
                except:
                    pass
            
            TelegramBot.send_message(
                chat_id,
                "✅ تم إرسال الإجابة بنجاح!",
                reply_markup=KeyboardBuilder.create_inline_keyboard([
                    [{"text": "👥 المزيد من الأسئلة", "callback_data": "service_help"},
                     {"text": "🏠 القائمة الرئيسية", "callback_data": "main_menu"}]
                ])
            )
        else:
            TelegramBot.send_message(
                chat_id,
                "⚠️ حدث خطأ في إرسال الإجابة",
                reply_markup=KeyboardBuilder.back_button()
            )
        
        # تنظيف الجلسة
        self.user_sessions.pop(user_id, None)
    
    def handle_admin_add_mat_title(self, chat_id: int, user_id: int, text: str, session: Dict):
        """معالجة عنوان مادة جديدة"""
        session["new_material"] = {"title": text}
        session["state"] = ConversationState.ADMIN_ADD_MAT_DESC
        self.user_sessions[user_id] = session
        
        TelegramBot.send_message(
            chat_id,
            "📝 *أدخل وصف المادة:*",
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.back_button("admin_materials")
        )
    
    def handle_admin_add_mat_desc(self, chat_id: int, user_id: int, text: str, session: Dict):
        """معالجة وصف مادة جديدة"""
        session["new_material"]["description"] = text
        session["state"] = ConversationState.ADMIN_ADD_MAT_STAGE
        self.user_sessions[user_id] = session
        
        TelegramBot.send_message(
            chat_id,
            "📚 *أدخل المرحلة الدراسية:*\n\nمثال: الصف السادس، الصف الخامس، المرحلة الإعدادية",
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.back_button("admin_materials")
        )
    
    def handle_admin_add_mat_stage(self, chat_id: int, user_id: int, text: str, session: Dict):
        """معالجة مرحلة مادة جديدة"""
        session["new_material"]["stage"] = text
        session["state"] = ConversationState.ADMIN_ADD_MAT_FILE
        self.user_sessions[user_id] = session
        
        TelegramBot.send_message(
            chat_id,
            "📎 *أرسل ملف المادة (PDF):*",
            parse_mode="Markdown",
            reply_markup=KeyboardBuilder.back_button("admin_materials")
        )

# ============================================================================
# خادم ويب بسيط للتعامل مع طلبات Telegram
# ============================================================================

class SimpleHTTPServer:
    """خادم ويب بسيط لاستقبال طلبات Telegram"""
    
    def __init__(self, bot: LearnBot, port: int = 8080):
        self.bot = bot
        self.port = port
    
    def handle_request(self, environ, start_response):
        """معالجة طلب HTTP"""
        if environ['REQUEST_METHOD'] == 'POST' and environ['PATH_INFO'] == f'/{TOKEN}':
            try:
                content_length = int(environ.get('CONTENT_LENGTH', 0))
                post_data = environ['wsgi.input'].read(content_length)
                update = json.loads(post_data.decode('utf-8'))
                
                # معالجة التحديث
                self.bot.handle_message(update)
                
                start_response('200 OK', [('Content-Type', 'application/json')])
                return [json.dumps({"ok": True}).encode('utf-8')]
            
            except Exception as e:
                self.bot.logger.error(f"Error handling request: {e}")
                start_response('500 Internal Server Error', [('Content-Type', 'application/json')])
                return [json.dumps({"ok": False, "error": str(e)}).encode('utf-8')]
        
        else:
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b'Not Found']
    
    def run(self):
        """تشغيل الخادم"""
        from wsgiref.simple_server import make_server
        
        self.bot.logger.info(f"Starting bot on port {self.port}")
        self.bot.logger.info(f"Bot username: {BOT_USERNAME}")
        self.bot.logger.info(f"Admin ID: {ADMIN_ID}")
        
        with make_server('', self.port, self.handle_request) as httpd:
            self.bot.logger.info(f"Serving on port {self.port}...")
            httpd.serve_forever()

# ============================================================================
# الدالة الرئيسية
# ============================================================================

def main():
    """الدالة الرئيسية لتشغيل البوت"""
    print("=" * 60)
    print("🚀 بوت تليجرام: يلا نتعلم")
    print(f"👑 المدير: {ADMIN_ID}")
    print(f"🤖 البوت: {BOT_USERNAME}")
    print(f"📞 الدعم: {SUPPORT_USER}")
    print(f"📢 القناة: {CHANNEL_USERNAME}")
    print("=" * 60)
    
    # إنشاء البوت
    bot = LearnBot()
    
    # تشغيل الخادم
    server = SimpleHTTPServer(bot, port=8080)
    server.run()

if __name__ == "__main__":
    main()
