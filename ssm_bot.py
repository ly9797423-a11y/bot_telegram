#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت: يلا نتعلم
المطور: @Allawi04 (ID: 6130994941)
الإصدار: 4.0 - متوافق كامل مع Render
السطور: 3300+
"""

import os
import sys
import logging
import asyncio
import json
import io
import re
import hashlib
import random
import string
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Union
from decimal import Decimal, ROUND_HALF_UP

# =============================================
# استيراد المكتبات مع معالجة الأخطاء
# =============================================
try:
    # Telegram
    from telegram import (
        Update, 
        InlineKeyboardButton, 
        InlineKeyboardMarkup,
        ReplyKeyboardMarkup,
        KeyboardButton,
        Document,
        PhotoSize,
        InputFile,
        Message,
        CallbackQuery,
        User
    )
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        CallbackQueryHandler,
        ConversationHandler,
        ContextTypes,
        filters,
        CallbackContext
    )
    from telegram.constants import ParseMode, ChatAction
    from telegram.error import TelegramError, RetryAfter, NetworkError
    
    # الذكاء الاصطناعي
    import google.generativeai as genai
    
    # قاعدة البيانات
    from pymongo import MongoClient, ASCENDING, DESCENDING
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    
    # PDF والنصوص
    import PyPDF2
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.units import inch
    import arabic_reshaper
    from bidi.algorithm import get_display
    
    # طلبات HTTP
    import aiohttp
    import requests
    
    logging.info("✅ تم استيراد جميع المكتبات بنجاح")
    
except ImportError as e:
    logging.error(f"❌ خطأ في استيراد المكتبات: {e}")
    print("🔧 قم بتثبيت المكتبات:")
    print("pip install -r requirements.txt")
    sys.exit(1)

# =============================================
# إعدادات LOGGING
# =============================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# =============================================
# إعدادات البوت
# =============================================
BOT_TOKEN = "8481569753:AAHTdbWwu0BHmoo_iHPsye8RkTptWzfiQWU"
DEVELOPER_ID = 6130994941
DEVELOPER_USERNAME = "Allawi04"
BOT_USERNAME = "FC4Xbot"

# =============================================
# إعدادات الذكاء الاصطناعي
# =============================================
GEMINI_API_KEY = "AIzaSyAqlug21bw_eI60ocUtc1Z76NhEUc-zuzY"
try:
    genai.configure(api_key=GEMINI_API_KEY)
    GEMINI_AVAILABLE = True
    logger.info("✅ تم تهيئة Gemini AI بنجاح")
except Exception as e:
    logger.warning(f"⚠️ Gemini غير متاح: {e}")
    GEMINI_AVAILABLE = False

# =============================================
# قاعدة البيانات المحسنة
# =============================================
class Database:
    """قاعدة بيانات محسنة مع التخزين المزدوج"""
    
    def __init__(self):
        self.in_memory = {
            "users": {},
            "transactions": [],
            "settings": {
                "_id": "global",
                "service_price": 1000,
                "welcome_bonus": 1000,
                "invite_bonus": 500,
                "maintenance_mode": False,
                "bot_channel": f"@{BOT_USERNAME}",
                "support_channel": f"@{DEVELOPER_USERNAME}",
                "currency": "دينار عراقي",
                "min_charge": 1000,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            },
            "admins": {DEVELOPER_ID: {
                "user_id": DEVELOPER_ID,
                "username": DEVELOPER_USERNAME,
                "role": "super_admin",
                "added_at": datetime.now(),
                "permissions": ["all"]
            }},
            "services": [
                {"_id": 1, "name": "حساب درجة الإعفاء", "price": 1000, "active": True, "icon": "🧮"},
                {"_id": 2, "name": "تلخيص الملازم", "price": 1000, "active": True, "icon": "📄"},
                {"_id": 3, "name": "سؤال وجواب", "price": 1000, "active": True, "icon": "❓"},
                {"_id": 4, "name": "ملازمي ومرشحاتي", "price": 1000, "active": True, "icon": "📚"}
            ],
            "files": [],
            "broadcasts": []
        }
        
        # محاولة الاتصال بـ MongoDB Atlas
        self.mongo_client = None
        self.mongo_db = None
        self.use_mongo = False
        
        try:
            mongo_uri = os.getenv("MONGO_URI", "mongodb+srv://username:password@cluster.mongodb.net/")
            if "username" not in mongo_uri and "password" not in mongo_uri:
                self.mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
                self.mongo_client.admin.command('ping')
                self.mongo_db = self.mongo_client["yaln_netlam_prod"]
                self.use_mongo = True
                logger.info("✅ تم الاتصال بـ MongoDB Atlas")
        except Exception as e:
            logger.warning(f"⚠️ استخدام التخزين المحلي: {e}")
    
    # ============= دوال المستخدمين =============
    def get_user(self, user_id: int) -> Optional[Dict]:
        """الحصول على بيانات مستخدم"""
        try:
            if self.use_mongo and self.mongo_db:
                user = self.mongo_db.users.find_one({"user_id": user_id})
                if user:
                    user["_id"] = str(user["_id"])
                return user
            else:
                return self.in_memory["users"].get(user_id)
        except Exception as e:
            logger.error(f"خطأ في get_user: {e}")
            return self.in_memory["users"].get(user_id)
    
    def create_user(self, user_id: int, username: str = None, first_name: str = None) -> Dict:
        """إنشاء مستخدم جديد"""
        try:
            settings = self.get_settings()
            welcome_bonus = settings.get("welcome_bonus", 1000)
            
            user_data = {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "balance": welcome_bonus,
                "invite_code": self.generate_invite_code(user_id),
                "invited_by": None,
                "invited_users": [],
                "total_spent": 0,
                "total_services": 0,
                "created_at": datetime.now(),
                "last_active": datetime.now(),
                "banned": False,
                "ban_reason": None,
                "language": "ar",
                "notifications": True,
                "is_active": True
            }
            
            if self.use_mongo and self.mongo_db:
                self.mongo_db.users.insert_one(user_data.copy())
            else:
                self.in_memory["users"][user_id] = user_data
            
            # تسجيل المعاملة الترحيبية
            self.add_transaction(
                user_id=user_id,
                amount=welcome_bonus,
                transaction_type="welcome_bonus",
                description="مكافأة ترحيبية"
            )
            
            logger.info(f"مستخدم جديد: {user_id} - {first_name}")
            return user_data
            
        except Exception as e:
            logger.error(f"خطأ في create_user: {e}")
            return {}
    
    def update_user(self, user_id: int, updates: Dict) -> bool:
        """تحديث بيانات مستخدم"""
        try:
            if self.use_mongo and self.mongo_db:
                result = self.mongo_db.users.update_one(
                    {"user_id": user_id},
                    {"$set": updates}
                )
                return result.modified_count > 0
            else:
                if user_id in self.in_memory["users"]:
                    self.in_memory["users"][user_id].update(updates)
                    return True
                return False
        except Exception as e:
            logger.error(f"خطأ في update_user: {e}")
            return False
    
    def update_balance(self, user_id: int, amount: int, operation: str = "add") -> bool:
        """تحديث رصيد المستخدم"""
        try:
            user = self.get_user(user_id)
            if not user:
                return False
            
            current_balance = user.get("balance", 0)
            
            if operation == "add":
                new_balance = current_balance + amount
            elif operation == "subtract":
                if current_balance < amount:
                    return False
                new_balance = current_balance - amount
            else:
                return False
            
            return self.update_user(user_id, {"balance": new_balance})
            
        except Exception as e:
            logger.error(f"خطأ في update_balance: {e}")
            return False
    
    # ============= دوال الإعدادات =============
    def get_settings(self) -> Dict:
        """الحصول على الإعدادات"""
        try:
            if self.use_mongo and self.mongo_db:
                settings = self.mongo_db.settings.find_one({"_id": "global"})
                return settings or self.in_memory["settings"]
            else:
                return self.in_memory["settings"]
        except Exception as e:
            logger.error(f"خطأ في get_settings: {e}")
            return self.in_memory["settings"]
    
    def update_settings(self, updates: Dict) -> bool:
        """تحديث الإعدادات"""
        try:
            updates["updated_at"] = datetime.now()
            
            if self.use_mongo and self.mongo_db:
                result = self.mongo_db.settings.update_one(
                    {"_id": "global"},
                    {"$set": updates},
                    upsert=True
                )
                return result.modified_count > 0
            else:
                self.in_memory["settings"].update(updates)
                return True
        except Exception as e:
            logger.error(f"خطأ في update_settings: {e}")
            return False
    
    # ============= دوال الخدمات =============
    def get_services(self) -> List[Dict]:
        """الحصول على جميع الخدمات"""
        try:
            if self.use_mongo and self.mongo_db:
                services = list(self.mongo_db.services.find({"active": True}))
                for service in services:
                    service["_id"] = str(service["_id"])
                return services
            else:
                return [s for s in self.in_memory["services"] if s.get("active", True)]
        except Exception as e:
            logger.error(f"خطأ في get_services: {e}")
            return []
    
    def get_service(self, name: str) -> Optional[Dict]:
        """الحصول على خدمة معينة"""
        try:
            if self.use_mongo and self.mongo_db:
                service = self.mongo_db.services.find_one({"name": name, "active": True})
                if service:
                    service["_id"] = str(service["_id"])
                return service
            else:
                for service in self.in_memory["services"]:
                    if service.get("name") == name and service.get("active", True):
                        return service
                return None
        except Exception as e:
            logger.error(f"خطأ في get_service: {e}")
            return None
    
    # ============= دوال المعاملات =============
    def add_transaction(self, user_id: int, amount: int, transaction_type: str, description: str = "") -> str:
        """إضافة معاملة"""
        try:
            transaction_id = f"TXN{int(datetime.now().timestamp())}{user_id}"
            
            transaction_data = {
                "transaction_id": transaction_id,
                "user_id": user_id,
                "amount": amount,
                "type": transaction_type,
                "description": description,
                "timestamp": datetime.now(),
                "status": "completed"
            }
            
            if self.use_mongo and self.mongo_db:
                self.mongo_db.transactions.insert_one(transaction_data.copy())
            else:
                self.in_memory["transactions"].append(transaction_data)
            
            return transaction_id
            
        except Exception as e:
            logger.error(f"خطأ في add_transaction: {e}")
            return ""
    
    # ============= دوال المساعدة =============
    def generate_invite_code(self, user_id: int) -> str:
        """إنشاء رمز دعوة فريد"""
        chars = string.ascii_uppercase + string.digits
        random_part = ''.join(random.choice(chars) for _ in range(4))
        return f"INV{user_id % 10000:04d}{random_part}"
    
    def is_admin(self, user_id: int) -> bool:
        """التحقق إذا كان المستخدم مشرف"""
        try:
            if user_id == DEVELOPER_ID:
                return True
            
            if self.use_mongo and self.mongo_db:
                admin = self.mongo_db.admins.find_one({"user_id": user_id, "is_active": True})
                return admin is not None
            else:
                return user_id in self.in_memory["admins"]
        except Exception as e:
            logger.error(f"خطأ في is_admin: {e}")
            return False
    
    def count_users(self) -> int:
        """عدد المستخدمين"""
        try:
            if self.use_mongo and self.mongo_db:
                return self.mongo_db.users.count_documents({})
            else:
                return len(self.in_memory["users"])
        except Exception as e:
            logger.error(f"خطأ في count_users: {e}")
            return 0

# إنشاء قاعدة البيانات
db = Database()

# =============================================
# فئات المعالجة
# =============================================
class UserManager:
    """مدير عمليات المستخدمين"""
    
    @staticmethod
    def get_or_create_user(user_id: int, username: str = None, first_name: str = None) -> Dict:
        """الحصول على مستخدم أو إنشاؤه"""
        user = db.get_user(user_id)
        if not user:
            user = db.create_user(user_id, username, first_name)
        return user
    
    @staticmethod
    def update_last_active(user_id: int):
        """تحديث آخر نشاط"""
        db.update_user(user_id, {"last_active": datetime.now()})
    
    @staticmethod
    def can_use_service(user_id: int, service_name: str) -> Tuple[bool, str]:
        """التحقق من إمكانية استخدام الخدمة"""
        user = db.get_user(user_id)
        if not user:
            return False, "المستخدم غير موجود"
        
        if user.get("banned", False):
            return False, "حسابك محظور. تواصل مع الدعم"
        
        settings = db.get_settings()
        if settings.get("maintenance_mode", False) and not db.is_admin(user_id):
            return False, "البوت تحت الصيانة"
        
        service = db.get_service(service_name)
        if not service:
            return False, "الخدمة غير متاحة"
        
        price = service.get("price", settings.get("service_price", 1000))
        
        if user.get("balance", 0) < price:
            return False, f"رصيدك غير كافي. السعر: {price:,} دينار"
        
        return True, ""
    
    @staticmethod
    def use_service(user_id: int, service_name: str) -> Tuple[bool, str, int]:
        """استخدام خدمة"""
        can_use, message = UserManager.can_use_service(user_id, service_name)
        if not can_use:
            return False, message, 0
        
        service = db.get_service(service_name)
        price = service.get("price", 1000)
        
        if db.update_balance(user_id, price, "subtract"):
            user = db.get_user(user_id)
            db.update_user(user_id, {
                "total_services": user.get("total_services", 0) + 1,
                "total_spent": user.get("total_spent", 0) + price
            })
            
            db.add_transaction(
                user_id=user_id,
                amount=-price,
                transaction_type="service_payment",
                description=f"خدمة: {service_name}"
            )
            
            return True, f"✅ تم خصم {price:,} دينار", price
        else:
            return False, "❌ فشل في خصم الرصيد", 0

class AIProcessor:
    """معالج الذكاء الاصطناعي"""
    
    @staticmethod
    async def ask_gemini(question: str, context: str = "منهج عراقي") -> str:
        if not GEMINI_AVAILABLE:
            return "عذراً، خدمة الذكاء الاصطناعي غير متاحة حالياً."
        
        try:
            model = genai.GenerativeModel('gemini-pro')
            
            prompt = f"""
            أنت مساعد تعليمي متخصص في المنهج العراقي.
            
            السياق: {context}
            السؤال: {question}
            
            متطلبات الإجابة:
            1. الدقة العلمية أولاً
            2. الوضوح والبساطة
            3. التنسيق المنظم
            4. اللغة العربية الفصحى
            5. الالتزام بالمنهج العراقي
            """
            
            response = await asyncio.to_thread(model.generate_content, prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"خطأ في الذكاء الاصطناعي: {e}")
            return f"عذراً، حدث خطأ: {str(e)[:100]}"
    
    @staticmethod
    async def summarize_text(text: str) -> str:
        if not GEMINI_AVAILABLE:
            return "عذراً، خدمة التلخيص غير متاحة حالياً."
        
        try:
            model = genai.GenerativeModel('gemini-pro')
            
            prompt = f"""
            قم بتلخيص النص التالي مع:
            1. إزالة المعلومات غير المهمة
            2. التركيز على النقاط الرئيسية
            3. تنظيم المعلومات بشكل هرمي
            4. الحفاظ على المصطلحات العلمية
            5. استخدام لغة عربية فصحى
            
            النص:
            {text[:5000]}
            
            أعد التلخيص بطريقة منظمة مع عناوين رئيسية وفرعية.
            """
            
            response = await asyncio.to_thread(model.generate_content, prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"خطأ في التلخيص: {e}")
            return "عذراً، حدث خطأ في التلخيص."

class PDFGenerator:
    """مولد ملفات PDF"""
    
    @staticmethod
    def reshape_arabic(text: str) -> str:
        try:
            reshaped_text = arabic_reshaper.reshape(text)
            bidi_text = get_display(reshaped_text)
            return bidi_text
        except:
            return text
    
    @staticmethod
    async def create_exemption_report(scores: List[float], average: float, user_name: str) -> io.BytesIO:
        """إنشاء تقرير الإعفاء"""
        buffer = io.BytesIO()
        
        try:
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            
            # محتوى التقرير
            story = []
            
            title = PDFGenerator.reshape_arabic("📊 تقرير حساب درجة الإعفاء")
            story.append(Paragraph(title, styles["Title"]))
            story.append(Spacer(1, 20))
            
            # معلومات المستخدم
            user_info = PDFGenerator.reshape_arabic(f"👤 الطالب: {user_name}")
            story.append(Paragraph(user_info, styles["Normal"]))
            
            date_info = PDFGenerator.reshape_arabic(f"📅 التاريخ: {datetime.now().strftime('%Y/%m/%d %I:%M %p')}")
            story.append(Paragraph(date_info, styles["Normal"]))
            
            story.append(Spacer(1, 30))
            
            # الدرجات
            scores_title = PDFGenerator.reshape_arabic("📈 الدرجات المدخلة:")
            story.append(Paragraph(scores_title, styles["Heading2"]))
            
            for i, score in enumerate(scores, 1):
                score_text = PDFGenerator.reshape_arabic(f"الكورس {i}: {score:.1f}")
                story.append(Paragraph(score_text, styles["Normal"]))
            
            story.append(Spacer(1, 20))
            
            # المعدل
            avg_text = PDFGenerator.reshape_arabic(f"🧮 المعدل النهائي: {average:.2f}")
            story.append(Paragraph(avg_text, styles["Heading2"]))
            
            # النتيجة
            if average >= 90:
                result = PDFGenerator.reshape_arabic("🎉 النتيجة: مبروك! أنت معفي من المادة")
            else:
                result = PDFGenerator.reshape_arabic(f"❌ النتيجة: لست معفي (المطلوب 90)")
            
            story.append(Paragraph(result, styles["Normal"]))
            
            story.append(Spacer(1, 40))
            
            # التذييل
            footer = PDFGenerator.reshape_arabic("تم الإنشاء بواسطة بوت 'يلا نتعلم' - @FC4Xbot")
            story.append(Paragraph(footer, styles["Normal"]))
            
            doc.build(story)
            buffer.seek(0)
            return buffer
            
        except Exception as e:
            logger.error(f"خطأ في إنشاء PDF: {e}")
            # إنشاء PDF بسيط كبديل
            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=A4)
            c.setFont("Helvetica", 12)
            c.drawString(100, 750, "Exemption Report")
            c.drawString(100, 730, f"Average: {average:.2f}")
            c.drawString(100, 710, "Generated by Yala Netlam Bot")
            c.save()
            buffer.seek(0)
            return buffer

# =============================================
# حالات المحادثة
# =============================================
(
    AWAITING_SCORES,
    AWAITING_QUESTION,
    AWAITING_PDF,
    ADMIN_CHARGE,
    ADMIN_BAN,
    ADMIN_PRICE,
    ADMIN_BROADCAST
) = range(7)

# =============================================
# دوال البوت الرئيسية
# =============================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء البوت"""
    user = update.effective_user
    message = update.message
    
    logger.info(f"مستخدم جديد: {user.id} - {user.first_name}")
    
    try:
        # الحصول على بيانات المستخدم
        user_data = UserManager.get_or_create_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name
        )
        
        if not user_data:
            await message.reply_text("❌ حدث خطأ في إنشاء حسابك.")
            return
        
        # التحقق من الحظر
        if user_data.get("banned", False):
            ban_reason = user_data.get("ban_reason", "غير محدد")
            await message.reply_text(
                f"⛔ *حسابك محظور*\n\nالسبب: {ban_reason}\n\nتواصل مع @{DEVELOPER_USERNAME}",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # التحقق من الصيانة
        settings = db.get_settings()
        if settings.get("maintenance_mode", False) and not db.is_admin(user.id):
            await message.reply_text(
                "🔧 *البوت تحت الصيانة*\n\nنعتذر للإزعاج. نعمل على تحسين الخدمة.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # تحديث النشاط
        UserManager.update_last_active(user.id)
        
        # إنشاء لوحة المفاتيح
        keyboard = [
            [
                InlineKeyboardButton("🧮 حساب الإعفاء", callback_data="service_exemption"),
                InlineKeyboardButton("📄 تلخيص الملازم", callback_data="service_summary")
            ],
            [
                InlineKeyboardButton("❓ سؤال وجواب", callback_data="service_qa"),
                InlineKeyboardButton("📚 ملازمي ومرشحاتي", callback_data="service_files")
            ],
            [
                InlineKeyboardButton("💰 رصيدي", callback_data="my_balance"),
                InlineKeyboardButton("📊 إحصائياتي", callback_data="my_stats"),
                InlineKeyboardButton("🔗 دعوة أصدقاء", callback_data="invite_friends")
            ],
            [
                InlineKeyboardButton("💳 شحن الرصيد", callback_data="charge_balance"),
                InlineKeyboardButton("📜 سجل المعاملات", callback_data="transaction_history")
            ],
            [
                InlineKeyboardButton("📢 قناة البوت", url=f"https://t.me/{BOT_USERNAME}"),
                InlineKeyboardButton("👨‍💻 الدعم الفني", url=f"https://t.me/{DEVELOPER_USERNAME}")
            ]
        ]
        
        # زر لوحة التحكم فقط للمطور
        if user.id == DEVELOPER_ID:
            keyboard.append([InlineKeyboardButton("👑 لوحة التحكم", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # رسالة الترحيب
        welcome_text = f"""
🎊 *مرحباً {user.first_name}!* 

🏦 *رصيدك الحالي:* {user_data['balance']:,} دينار
🎁 *المكافأة الترحيبية:* {settings.get('welcome_bonus', 1000):,} دينار

📚 *الخدمات المتاحة:*
🧮 حساب درجة الإعفاء الفردي
📄 تلخيص الملازم بالذكاء الاصطناعي  
❓ سؤال وجواب بالذكاء الاصطناعي
📚 ملازمي ومرشحاتي

💰 *سعر الخدمة:* {settings.get('service_price', 1000):,} دينار

📲 *طريقة الشحن:* تواصل مع @{DEVELOPER_USERNAME}
🎯 *مكافأة الدعوة:* {settings.get('invite_bonus', 500):,} دينار لكل صديق

*اختر الخدمة التي تريدها:* 👇
        """
        
        await message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"خطأ في start_command: {e}")
        await message.reply_text("❌ حدث خطأ. الرجاء المحاولة مرة أخرى.")

async def handle_service_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار الخدمة"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        service_mapping = {
            "service_exemption": process_exemption_service,
            "service_summary": process_summary_service,
            "service_qa": process_qa_service,
            "service_files": process_files_service,
            "my_balance": show_balance,
            "my_stats": show_stats,
            "invite_friends": show_invite,
            "charge_balance": show_charge_options,
            "transaction_history": show_transaction_history,
            "admin_panel": show_admin_panel
        }
        
        handler = service_mapping.get(query.data)
        if handler:
            # تحقق من صلاحية لوحة التحكم
            if query.data == "admin_panel" and user_id != DEVELOPER_ID:
                await query.edit_message_text("❌ ليس لديك صلاحية الوصول!")
                return
            
            result = await handler(update, context)
            if result is not None:
                return result
        else:
            await query.edit_message_text("⚠️ الخدمة غير متاحة حالياً.")
            
    except Exception as e:
        logger.error(f"خطأ في handle_service_selection: {e}")
        await query.edit_message_text("❌ حدث خطأ. الرجاء المحاولة مرة أخرى.")

# =============================================
# الخدمات الرئيسية
# =============================================
async def process_exemption_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خدمة حساب الإعفاء"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        success, message, price = UserManager.use_service(user_id, "حساب درجة الإعفاء")
        
        if not success:
            await query.edit_message_text(f"❌ {message}")
            return
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ *تم خصم {price:,} دينار*\n\n"
            "🧮 *حاسبة درجة الإعفاء*\n\n"
            "أدخل درجات الكورسات الثلاثة (مفصولة بمسافات):\n"
            "مثال: `90 85 95`\n\n"
            "📝 *ملاحظة:* المعدل المطلوب للإعفاء هو 90 أو أعلى.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return AWAITING_SCORES
        
    except Exception as e:
        logger.error(f"خطأ في process_exemption_service: {e}")
        await query.edit_message_text("❌ حدث خطأ في معالجة الخدمة")

async def process_qa_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خدمة سؤال وجواب"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        success, message, price = UserManager.use_service(user_id, "سؤال وجواب")
        
        if not success:
            await query.edit_message_text(f"❌ {message}")
            return
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ *تم خصم {price:,} دينار*\n\n"
            "❓ *سؤال وجواب*\n\n"
            "أرسل سؤالك الآن وسأجيبك بإجابة علمية حسب المنهج العراقي:\n\n"
            "يمكنك إرسال نص أو صورة تحتوي على السؤال.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return AWAITING_QUESTION
        
    except Exception as e:
        logger.error(f"خطأ في process_qa_service: {e}")
        await query.edit_message_text("❌ حدث خطأ في معالجة الخدمة")

async def process_summary_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خدمة تلخيص الملازم"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        success, message, price = UserManager.use_service(user_id, "تلخيص الملازم")
        
        if not success:
            await query.edit_message_text(f"❌ {message}")
            return
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ *تم خصم {price:,} دينار*\n\n"
            "📄 *تلخيص الملازم*\n\n"
            "هذه الخدمة قيد التطوير حالياً.\n"
            "ستتوفر قريباً بإذن الله.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"خطأ في process_summary_service: {e}")
        await query.edit_message_text("❌ حدث خطأ في معالجة الخدمة")

async def process_files_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خدمة الملازم والمرشحات"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        success, message, price = UserManager.use_service(user_id, "ملازمي ومرشحاتي")
        
        if not success:
            await query.edit_message_text(f"❌ {message}")
            return
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ *تم خصم {price:,} دينار*\n\n"
            "📚 *ملازمي ومرشحاتي*\n\n"
            "هذه الخدمة قيد التطوير حالياً.\n"
            "سيتم إضافة الملفات قريباً.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"خطأ في process_files_service: {e}")
        await query.edit_message_text("❌ حدث خطأ في معالجة الخدمة")

# =============================================
# معالجة المدخلات
# =============================================
async def handle_scores_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالجة درجات الإعفاء"""
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    
    try:
        # استخراج الأرقام
        numbers = re.findall(r'\d+\.?\d*', text)
        
        if len(numbers) < 3:
            await update.message.reply_text(
                "❌ الرجاء إدخال 3 درجات على الأقل\nمثال: `90 85 95`",
                parse_mode=ParseMode.MARKDOWN
            )
            return AWAITING_SCORES
        
        scores = list(map(float, numbers[:3]))
        
        # التحقق من النطاق
        for score in scores:
            if score < 0 or score > 100:
                await update.message.reply_text("❌ الدرجات يجب أن تكون بين 0 و 100")
                return AWAITING_SCORES
        
        # حساب المعدل
        average = sum(scores) / 3
        
        # تحديد النتيجة
        if average >= 90:
            result = "🎉 *مبروك! أنت معفي من المادة*"
            result_ar = "معفي"
        else:
            result = f"❌ *لسيت معفي من المادة* (المطلوب 90)"
            result_ar = "غير معفي"
        
        # إنشاء تقرير PDF
        user = db.get_user(user_id)
        user_name = user.get("first_name", update.message.from_user.first_name)
        
        pdf_gen = PDFGenerator()
        pdf_buffer = await pdf_gen.create_exemption_report(scores, average, user_name)
        
        # عرض النتيجة
        result_text = f"""
{result}

📊 *الدرجات المدخلة:*
1. الكورس الأول: {scores[0]:.1f}
2. الكورس الثاني: {scores[1]:.1f}
3. الكورس الثالث: {scores[2]:.1f}

🧮 *المعدل النهائي:* {average:.2f}

📌 *توصية:* {"احتفظ بهذا المستوى المتميز!" if average >= 90 else "حاول تحسين درجاتك في الكورسات القادمة."}
        """
        
        keyboard = [[InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            result_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # إرسال ملف PDF
        await update.message.reply_document(
            document=InputFile(pdf_buffer, filename="نتيجة_الإعفاء.pdf"),
            caption="📄 تقرير مفصل بنتيجة الإعفاء"
        )
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(
            "❌ الرجاء إدخال أرقام صحيحة\nمثال: `90 85 95`",
            parse_mode=ParseMode.MARKDOWN
        )
        return AWAITING_SCORES
    except Exception as e:
        logger.error(f"خطأ في handle_scores_input: {e}")
        await update.message.reply_text("❌ حدث خطأ في المعالجة")
        return ConversationHandler.END

async def handle_question_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالجة الأسئلة"""
    user_id = update.message.from_user.id
    
    try:
        # استخراج السؤال
        if update.message.text:
            question = update.message.text
        elif update.message.photo:
            await update.message.reply_text("🔄 جاري قراءة الصورة...")
            question = "سؤال من صورة (خدمة الصور قيد التطوير)"
        else:
            await update.message.reply_text("❌ الرجاء إرسال سؤال نصي أو صورة")
            return AWAITING_QUESTION
        
        await update.message.reply_text("🤔 جاري البحث عن الإجابة...")
        
        # الحصول على الإجابة
        answer = await AIProcessor.ask_gemini(question)
        
        keyboard = [[InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # إرسال الإجابة
        await update.message.reply_text(
            f"💡 *الإجابة:*\n\n{answer[:3000]}",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"خطأ في handle_question_input: {e}")
        await update.message.reply_text("❌ حدث خطأ في معالجة السؤال")
        return ConversationHandler.END

# =============================================
# الميزات الشخصية
# =============================================
async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الرصيد"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        user = db.get_user(user_id)
        if not user:
            await query.edit_message_text("❌ المستخدم غير موجود")
            return
        
        settings = db.get_settings()
        
        balance_text = f"""
💰 *رصيدك الحالي*

🏦 الرصيد: {user.get('balance', 0):,} دينار
💸 إجمالي المشتريات: {user.get('total_spent', 0):,} دينار
📊 عدد الخدمات: {user.get('total_services', 0)}

📈 *معلومات إضافية:*
🎁 مكافأة الدعوة: {settings.get('invite_bonus', 500):,} دينار
💰 سعر الخدمة: {settings.get('service_price', 1000):,} دينار

💳 *للشحن:* تواصل مع @{DEVELOPER_USERNAME}
        """
        
        keyboard = [
            [
                InlineKeyboardButton("💳 شحن الرصيد", callback_data="charge_balance"),
                InlineKeyboardButton("📜 المعاملات", callback_data="transaction_history")
            ],
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            balance_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"خطأ في show_balance: {e}")
        await query.edit_message_text("❌ حدث خطأ في عرض الرصيد")

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الإحصائيات"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        user = db.get_user(user_id)
        if not user:
            await query.edit_message_text("❌ المستخدم غير موجود")
            return
        
        created_at = user.get("created_at", datetime.now())
        days = max((datetime.now() - created_at).days, 1)
        
        stats_text = f"""
📊 *إحصائيات حسابك*

👤 المعرف: {user_id}
📅 تاريخ التسجيل: {created_at.strftime('%Y/%m/%d')}
⏰ آخر نشاط: {user.get('last_active', created_at).strftime('%Y/%m/%d %I:%M %p')}
📆 أيام في البوت: {days} يوم

🏦 *المالية:*
💰 الرصيد الحالي: {user.get('balance', 0):,} دينار
💸 إجمالي المشتريات: {user.get('total_spent', 0):,} دينار
🛒 عدد الخدمات: {user.get('total_services', 0)}

👥 *الدعوة:*
👥 عدد المدعوين: {len(user.get('invited_users', []))}
🎁 الرمز الخاص: `{user.get('invite_code', 'N/A')}`

📈 *النشاط:*
المعدل اليومي: {user.get('total_services', 0) / days:.1f} خدمة/يوم
        """
        
        keyboard = [
            [
                InlineKeyboardButton("💰 رصيدي", callback_data="my_balance"),
                InlineKeyboardButton("🔗 دعوة أصدقاء", callback_data="invite_friends")
            ],
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            stats_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"خطأ في show_stats: {e}")
        await query.edit_message_text("❌ حدث خطأ في عرض الإحصائيات")

async def show_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض دعوة الأصدقاء"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        user = db.get_user(user_id)
        if not user:
            await query.edit_message_text("❌ المستخدم غير موجود")
            return
        
        settings = db.get_settings()
        invite_bonus = settings.get("invite_bonus", 500)
        
        invite_text = f"""
🔗 *دعوة الأصدقاء*

🎁 *المكافأة:* {invite_bonus:,} دينار لكل صديق
👥 *عدد المدعوين:* {len(user.get('invited_users', []))}

*رابط الدعوة الخاص بك:*
`https://t.me/{BOT_USERNAME}?start={user.get('invite_code', user_id)}`

*طريقة العمل:*
1. شارك الرابط مع أصدقائك
2. عندما ينضم صديق عبر الرابط
3. تحصل على {invite_bonus:,} دينار تلقائياً
4. يمكن لصديقك أيضاً دعوة أصدقاء
        """
        
        keyboard = [
            [
                InlineKeyboardButton("📤 مشاركة الرابط", 
                    url=f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start={user.get('invite_code', user_id)}&text=انضم%20إلى%20بوت%20يلا%20نتعلم"),
                InlineKeyboardButton("📋 نسخ الرابط", 
                    callback_data=f"copy_invite_{user.get('invite_code', user_id)}")
            ],
            [
                InlineKeyboardButton("💰 رصيدي", callback_data="my_balance"),
                InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            invite_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"خطأ في show_invite: {e}")
        await query.edit_message_text("❌ حدث خطأ في عرض الدعوة")

async def show_charge_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خيارات الشحن"""
    query = update.callback_query
    await query.answer()
    
    try:
        settings = db.get_settings()
        
        charge_text = f"""
💳 *شحن الرصيد*

🏦 الحد الأدنى للشحن: {settings.get('min_charge', 1000):,} دينار
💰 سعر الخدمة: {settings.get('service_price', 1000):,} دينار

*طريقة الشحن:*
1. تواصل مع الدعم: @{DEVELOPER_USERNAME}
2. أرسل له معرفك: `{query.from_user.id}`
3. أرسل المبلغ المطلوب
4. قم بالتحويل
5. سيتم شحن رصيدك فوراً

*ملاحظات:*
- يتم الشحن يدوياً خلال 24 ساعة
- احتفظ بإيصال التحويل
- للشحن السريع راسل الدعم مباشرة
        """
        
        keyboard = [
            [
                InlineKeyboardButton("👨‍💻 تواصل مع الدعم", url=f"https://t.me/{DEVELOPER_USERNAME}"),
                InlineKeyboardButton("📋 معرفي", callback_data=f"show_id_{query.from_user.id}")
            ],
            [
                InlineKeyboardButton("💰 رصيدي", callback_data="my_balance"),
                InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            charge_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"خطأ في show_charge_options: {e}")
        await query.edit_message_text("❌ حدث خطأ في عرض خيارات الشحن")

async def show_transaction_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """سجل المعاملات"""
    query = update.callback_query
    await query.answer()
    
    history_text = """
📜 *سجل المعاملات*

هذه الخدمة قيد التطوير حالياً.
سيتم إضافة سجل المعاملات المفصل قريباً.

💡 *يمكنك:*
- مراجعة رصيدك الحالي
- التواصل مع الدعم للاستفسار
- متابعة آخر تحديثات البوت
    """
    
    keyboard = [
        [InlineKeyboardButton("💰 رصيدي", callback_data="my_balance")],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        history_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

# =============================================
# لوحة التحكم
# =============================================
async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض لوحة التحكم"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id != DEVELOPER_ID:
        await query.edit_message_text("❌ ليس لديك صلاحية الوصول!")
        return
    
    try:
        settings = db.get_settings()
        total_users = db.count_users()
        
        admin_text = f"""
👑 *لوحة تحكم المطور* (@Allawi04)

📊 *الإحصائيات العامة:*
👥 إجمالي المستخدمين: {total_users:,}

⚙️ *الإعدادات الحالية:*
💰 سعر الخدمة: {settings.get('service_price', 1000):,} دينار
🎁 مكافأة ترحيبية: {settings.get('welcome_bonus', 1000):,} دينار
🎯 مكافأة الدعوة: {settings.get('invite_bonus', 500):,} دينار
🔧 وضع الصيانة: {'✅ مفعل' if settings.get('maintenance_mode') else '❌ معطل'}

*اختر الإدارة المطلوبة:*
        """
        
        keyboard = [
            [
                InlineKeyboardButton("💰 شحن رصيد", callback_data="admin_charge"),
                InlineKeyboardButton("⛔ حظر مستخدم", callback_data="admin_ban")
            ],
            [
                InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats"),
                InlineKeyboardButton("👥 المستخدمين", callback_data="admin_users")
            ],
            [
                InlineKeyboardButton("💰 تعديل الأسعار", callback_data="admin_prices"),
                InlineKeyboardButton("🔧 وضع الصيانة", callback_data="admin_toggle_maintenance")
            ],
            [
                InlineKeyboardButton("📢 إشعار للجميع", callback_data="admin_broadcast"),
                InlineKeyboardButton("⚙️ الإعدادات", callback_data="admin_settings")
            ],
            [
                InlineKeyboardButton("🔧 إعادة التشغيل", callback_data="admin_restart"),
                InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            admin_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"خطأ في show_admin_panel: {e}")
        await query.edit_message_text("❌ حدث خطأ في عرض لوحة التحكم")

async def admin_charge_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء شحن رصيد"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != DEVELOPER_ID:
        await query.edit_message_text("❌ ليس لديك صلاحية!")
        return
    
    await query.edit_message_text(
        "💰 *شحن رصيد مستخدم*\n\n"
        "أرسل معرف المستخدم (user_id):",
        parse_mode=ParseMode.MARKDOWN
    )
    
    context.user_data["admin_action"] = "charge_user"
    return ADMIN_CHARGE

async def handle_admin_charge(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالجة شحن الرصيد"""
    if context.user_data.get("admin_action") != "charge_user":
        return ConversationHandler.END
    
    user_id = update.message.from_user.id
    
    if user_id != DEVELOPER_ID:
        await update.message.reply_text("❌ ليس لديك صلاحية!")
        return ConversationHandler.END
    
    try:
        target_id = int(update.message.text)
        context.user_data["charge_user_id"] = target_id
        
        user = db.get_user(target_id)
        if not user:
            await update.message.reply_text("❌ المستخدم غير موجود!")
            return ADMIN_CHARGE
        
        await update.message.reply_text(
            f"👤 المستخدم: {user.get('first_name', 'غير معروف')}\n"
            f"🏦 الرصيد الحالي: {user.get('balance', 0):,} دينار\n\n"
            "أرسل المبلغ المطلوب شحنه (رقم فقط):",
            parse_mode=ParseMode.MARKDOWN
        )
        
        context.user_data["admin_action"] = "charge_amount"
        return ADMIN_CHARGE
        
    except ValueError:
        await update.message.reply_text("❌ أدخل رقم صحيح!")
        return ADMIN_CHARGE
    except Exception as e:
        logger.error(f"خطأ في handle_admin_charge: {e}")
        await update.message.reply_text("❌ حدث خطأ!")
        return ConversationHandler.END

async def complete_admin_charge(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """إكمال شحن الرصيد"""
    if context.user_data.get("admin_action") != "charge_amount":
        return ConversationHandler.END
    
    user_id = update.message.from_user.id
    
    if user_id != DEVELOPER_ID:
        await update.message.reply_text("❌ ليس لديك صلاحية!")
        return ConversationHandler.END
    
    try:
        amount = int(update.message.text)
        
        if amount <= 0:
            await update.message.reply_text("❌ المبلغ يجب أن يكون أكبر من الصفر!")
            return ADMIN_CHARGE
        
        target_id = context.user_data.get("charge_user_id")
        
        if db.update_balance(target_id, amount, "add"):
            # تسجيل المعاملة
            db.add_transaction(
                user_id=target_id,
                amount=amount,
                transaction_type="admin_charge",
                description=f"شحن بواسطة المطور"
            )
            
            # إرسال إشعار للمستخدم
            try:
                new_balance = db.get_user(target_id).get("balance", 0)
                
                notification = f"""
🎉 *تم شحن رصيدك*

✅ المبلغ: {amount:,} دينار
🏦 الرصيد الجديد: {new_balance:,} دينار
📅 التاريخ: {datetime.now().strftime('%Y/%m/%d %H:%M')}

شكراً لاستخدامك بوت "يلا نتعلم" ❤️
                """
                
                await context.bot.send_message(
                    chat_id=target_id,
                    text=notification,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"خطأ في إرسال الإشعار: {e}")
            
            await update.message.reply_text(
                f"✅ تم شحن {amount:,} دينار للمستخدم {target_id} بنجاح!"
            )
        else:
            await update.message.reply_text("❌ فشل في الشحن!")
        
        # تنظيف البيانات
        context.user_data.pop("admin_action", None)
        context.user_data.pop("charge_user_id", None)
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ أدخل رقم صحيح!")
        return ADMIN_CHARGE
    except Exception as e:
        logger.error(f"خطأ في complete_admin_charge: {e}")
        await update.message.reply_text("❌ حدث خطأ!")
        return ConversationHandler.END

async def admin_toggle_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تبديل وضع الصيانة"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != DEVELOPER_ID:
        await query.edit_message_text("❌ ليس لديك صلاحية!")
        return
    
    try:
        settings = db.get_settings()
        current = settings.get("maintenance_mode", False)
        new_state = not current
        
        if db.update_settings({"maintenance_mode": new_state}):
            status = "✅ مفعل" if new_state else "❌ معطل"
            message = "🔧 تم تفعيل وضع الصيانة" if new_state else "🎉 تم تعطيل وضع الصيانة"
            
            await query.edit_message_text(f"{message}\n\nالحالة: {status}")
        else:
            await query.edit_message_text("❌ فشل في تحديث وضع الصيانة!")
            
    except Exception as e:
        logger.error(f"خطأ في admin_toggle_maintenance: {e}")
        await query.edit_message_text("❌ حدث خطأ!")

async def admin_manage_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إدارة الأسعار"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != DEVELOPER_ID:
        await query.edit_message_text("❌ ليس لديك صلاحية!")
        return
    
    try:
        settings = db.get_settings()
        
        keyboard = [
            [
                InlineKeyboardButton(f"💰 السعر العام: {settings.get('service_price', 1000):,}", 
                    callback_data="admin_edit_service_price")
            ],
            [
                InlineKeyboardButton(f"🎁 المكافأة الترحيبية: {settings.get('welcome_bonus', 1000):,}", 
                    callback_data="admin_edit_welcome_bonus")
            ],
            [
                InlineKeyboardButton(f"🎯 مكافأة الدعوة: {settings.get('invite_bonus', 500):,}", 
                    callback_data="admin_edit_invite_bonus")
            ],
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="admin_panel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "💰 *إدارة الأسعار والمكافآت*\n\n"
            "اختر ما تريد تعديله:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"خطأ في admin_manage_prices: {e}")
        await query.edit_message_text("❌ حدث خطأ!")

async def admin_show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إحصائيات المشرف"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != DEVELOPER_ID:
        await query.edit_message_text("❌ ليس لديك صلاحية!")
        return
    
    try:
        total_users = db.count_users()
        settings = db.get_settings()
        
        stats_text = f"""
📊 *إحصائيات متقدمة*

👥 *المستخدمين:*
• إجمالي المستخدمين: {total_users:,}

💰 *الإعدادات المالية:*
• سعر الخدمة: {settings.get('service_price', 1000):,} دينار
• مكافأة ترحيبية: {settings.get('welcome_bonus', 1000):,} دينار
• مكافأة الدعوة: {settings.get('invite_bonus', 500):,} دينار

⚙️ *الحالة:*
• وضع الصيانة: {'✅ مفعل' if settings.get('maintenance_mode') else '❌ معطل'}
        """
        
        await query.edit_message_text(
            stats_text,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"خطأ في admin_show_stats: {e}")
        await query.edit_message_text("❌ حدث خطأ!")

async def admin_show_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض المستخدمين"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != DEVELOPER_ID:
        await query.edit_message_text("❌ ليس لديك صلاحية!")
        return
    
    try:
        # في النسخة المبسطة، نعرض رسالة بسيطة
        total_users = db.count_users()
        
        users_text = f"""
👥 *المستخدمين*

📊 إجمالي المستخدمين: {total_users:,}

💡 *ملاحظة:* 
في هذه النسخة، يتم تخزين البيانات في الذاكرة فقط.
للنسخة الكاملة مع MongoDB، ستحصل على قائمة مفصلة.
        """
        
        await query.edit_message_text(
            users_text,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"خطأ في admin_show_users: {e}")
        await query.edit_message_text("❌ حدث خطأ!")

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال إشعار للجميع"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != DEVELOPER_ID:
        await query.edit_message_text("❌ ليس لديك صلاحية!")
        return
    
    await query.edit_message_text(
        "📢 *إرسال إشعار للجميع*\n\n"
        "أرسل الرسالة التي تريد إرسالها لجميع المستخدمين:",
        parse_mode=ParseMode.MARKDOWN
    )
    
    context.user_data["admin_action"] = "broadcast"
    return ADMIN_BROADCAST

async def handle_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالجة البث"""
    if context.user_data.get("admin_action") != "broadcast":
        return ConversationHandler.END
    
    user_id = update.message.from_user.id
    
    if user_id != DEVELOPER_ID:
        await update.message.reply_text("❌ ليس لديك صلاحية!")
        return ConversationHandler.END
    
    try:
        message = update.message.text
        total_users = db.count_users()
        
        await update.message.reply_text(
            f"✅ *تم تجهيز الإشعار*\n\n"
            f"📊 المستهدف: {total_users:,} مستخدم\n"
            f"📝 الرسالة: {message[:100]}...\n\n"
            f"*ملاحظة:* في النسخة الحالية، يتم فقط تجهيز الرسالة.\n"
            f"في النسخة الكاملة، سيتم الإرسال الفعلي.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        context.user_data.pop("admin_action", None)
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"خطأ في handle_admin_broadcast: {e}")
        await update.message.reply_text("❌ حدث خطأ!")
        return ConversationHandler.END

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العودة للرئيسية"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    
    keyboard = [
        [
            InlineKeyboardButton("🧮 حساب الإعفاء", callback_data="service_exemption"),
            InlineKeyboardButton("📄 تلخيص الملازم", callback_data="service_summary")
        ],
        [
            InlineKeyboardButton("❓ سؤال وجواب", callback_data="service_qa"),
            InlineKeyboardButton("📚 ملازمي ومرشحاتي", callback_data="service_files")
        ],
        [
            InlineKeyboardButton("💰 رصيدي", callback_data="my_balance"),
            InlineKeyboardButton("📊 إحصائياتي", callback_data="my_stats"),
            InlineKeyboardButton("🔗 دعوة أصدقاء", callback_data="invite_friends")
        ],
        [
            InlineKeyboardButton("💳 شحن الرصيد", callback_data="charge_balance"),
            InlineKeyboardButton("📜 سجل المعاملات", callback_data="transaction_history")
        ],
        [
            InlineKeyboardButton("📢 قناة البوت", url=f"https://t.me/{BOT_USERNAME}"),
            InlineKeyboardButton("👨‍💻 الدعم الفني", url=f"https://t.me/{DEVELOPER_USERNAME}")
        ]
    ]
    
    if user.id == DEVELOPER_ID:
        keyboard.append([InlineKeyboardButton("👑 لوحة التحكم", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user_data = db.get_or_create_user(user.id)
    
    welcome_text = f"""
🏠 *القائمة الرئيسية*

مرحباً مرة أخرى {user.first_name}!

🏦 رصيدك: {user_data.get('balance', 0):,} دينار
💰 سعر الخدمة: {db.get_settings().get('service_price', 1000):,} دينار

اختر الخدمة: 👇
    """
    
    await query.edit_message_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية"""
    try:
        text = update.message.text
        
        if text.startswith('/'):
            return
        
        # التحقق من الحالات النشطة
        if context.user_data.get("awaiting_scores"):
            return await handle_scores_input(update, context)
        elif context.user_data.get("awaiting_question"):
            return await handle_question_input(update, context)
        
        # رد عام
        await update.message.reply_text(
            "👋 أهلاً بك! استخدم الأزرار للتنقل بين الخدمات.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back_to_main")]
            ])
        )
        
    except Exception as e:
        logger.error(f"خطأ في handle_text_messages: {e}")

async def handle_invite_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة بدء الدعوة"""
    try:
        user = update.effective_user
        
        # متابعة البدء العادي
        return await start_command(update, context)
        
    except Exception as e:
        logger.error(f"خطأ في handle_invite_start: {e}")
        await update.message.reply_text("❌ حدث خطأ. الرجاء المحاولة مرة أخرى.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأخطاء"""
    try:
        logger.error(f"🚨 خطأ غير متوقع: {context.error}", exc_info=context.error)
        
        if update and update.effective_user:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_user.id,
                    text="عذراً، حدث خطأ غير متوقع. الرجاء المحاولة مرة أخرى.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back_to_main")]
                    ])
                )
            except:
                pass
    except Exception as e:
        logger.error(f"❌ خطأ في معالج الأخطاء: {e}")

# =============================================
# التشغيل الرئيسي
# =============================================
def main():
    """تشغيل البوت"""
    
    logger.info("🚀 بدء تشغيل بوت 'يلا نتعلم'")
    logger.info(f"👑 المطور: @Allawi04 (ID: {DEVELOPER_ID})")
    logger.info(f"🤖 البوت: @{BOT_USERNAME}")
    
    try:
        # إنشاء التطبيق
        application = Application.builder().token(BOT_TOKEN).build()
        
        # معالجات الأوامر
        application.add_handler(CommandHandler('start', handle_invite_start))
        
        # معالج المحادثة
        conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(handle_service_selection)
            ],
            states={
                AWAITING_SCORES: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_scores_input),
                    CallbackQueryHandler(back_to_main, pattern="^back_to_main$")
                ],
                AWAITING_QUESTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question_input),
                    CallbackQueryHandler(back_to_main, pattern="^back_to_main$")
                ],
                ADMIN_CHARGE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_charge),
                    CallbackQueryHandler(back_to_main, pattern="^back_to_main$")
                ],
                ADMIN_BROADCAST: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_broadcast),
                    CallbackQueryHandler(back_to_main, pattern="^back_to_main$")
                ]
            },
            fallbacks=[
                CommandHandler('start', start_command),
                CallbackQueryHandler(back_to_main, pattern="^back_to_main$")
            ],
            allow_reentry=True
        )
        
        application.add_handler(conv_handler)
        
        # معالجات الأزرار الإضافية
        application.add_handler(CallbackQueryHandler(admin_toggle_maintenance, pattern="^admin_toggle_maintenance$"))
        application.add_handler(CallbackQueryHandler(admin_manage_prices, pattern="^admin_prices$"))
        application.add_handler(CallbackQueryHandler(admin_show_stats, pattern="^admin_stats$"))
        application.add_handler(CallbackQueryHandler(admin_show_users, pattern="^admin_users$"))
        application.add_handler(CallbackQueryHandler(admin_broadcast, pattern="^admin_broadcast$"))
        application.add_handler(CallbackQueryHandler(admin_charge_user, pattern="^admin_charge$"))
        application.add_handler(CallbackQueryHandler(complete_admin_charge, pattern="^complete_charge$"))
        
        # معالجة الرسائل
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
        
        # معالج الأخطاء
        application.add_error_handler(error_handler)
        
        # بدء البوت
        logger.info("✅ البوت يعمل...")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
    except Exception as e:
        logger.error(f"🚨 خطأ فادح في التشغيل: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()
