#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت "يلا نتعلم" - البوت التعليمي للطلاب العراقيين
المطور: Allawi04@
"""

import logging
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional
import PyPDF2
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters,
    ConversationHandler
)
from telegram.constants import ParseMode
import google.generativeai as genai

# ============= إعدادات البوت =============
TOKEN = "8481569753:AAH3alhJ0hcHldht-PxV7j8TzBlRsMqAqGI"
BOT_USERNAME = "@FC4Xbot"
ADMIN_ID = 6130994941
SUPPORT_USERNAME = "Allawi04"
GEMINI_API_KEY = "AIzaSyAqlug21bw_eI60ocUtc1Z76NhEUc-zuzY"

# ============= حالات المحادثة =============
ADMIN_MENU, CHARGE_USER, CHARGE_AMOUNT, PRICE_CHANGE, MATERIAL_ADD = range(5)

# ============= إعداد التسعير =============
SERVICE_PRICES = {
    "exemption": 1000,      # حساب درجة الإعفاء
    "summarize": 1000,      # تلخيص الملازم
    "qa": 1000,             # سؤال وجواب
    "materials": 1000       # ملازمي ومرشحاتي
}
WELCOME_BONUS = 1000        # هدية الترحيب
REFERRAL_BONUS = 500        # مكافأة الدعوة

# ============= إعداد الملفات =============
DATA_FILE = "users_data.json"
MATERIALS_FILE = "materials_data.json"
ADMIN_FILE = "admin_settings.json"

# ============= إعداد التسجيل =============
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============= إدارة البيانات =============
class DataManager:
    @staticmethod
    def load_data(filename: str, default=None):
        """تحميل البيانات من ملف JSON"""
        if default is None:
            default = {}
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return default
        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
            return default

    @staticmethod
    def save_data(filename: str, data):
        """حفظ البيانات إلى ملف JSON"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Error saving {filename}: {e}")

# ============= إدارة المستخدمين =============
class UserManager:
    def __init__(self):
        self.users = DataManager.load_data(DATA_FILE, {})
        
    def get_user(self, user_id: int) -> Dict:
        """الحصول على بيانات المستخدم أو إنشاء مستخدم جديد"""
        user_id_str = str(user_id)
        if user_id_str not in self.users:
            self.users[user_id_str] = {
                "balance": WELCOME_BONUS,
                "joined_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "referral_code": str(user_id),
                "invited_by": None,
                "invited_users": [],
                "transactions": [],
                "exemption_scores": [],
                "used_services": [],
                "pending_scores": []
            }
            self.save_users()
            logger.info(f"New user created: {user_id}")
        return self.users[user_id_str]
    
    def update_balance(self, user_id: int, amount: int, description: str = "") -> int:
        """تحديد رصيد المستخدم"""
        user = self.get_user(user_id)
        user["balance"] = user.get("balance", 0) + amount
        
        transaction = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "amount": amount,
            "description": description,
            "balance_after": user["balance"]
        }
        user.setdefault("transactions", []).append(transaction)
        self.save_users()
        
        logger.info(f"Updated balance for user {user_id}: +{amount} = {user['balance']}")
        return user["balance"]
    
    def can_afford(self, user_id: int, service: str) -> bool:
        """التحقق مما إذا كان المستخدم يمتلك رصيداً كافياً للخدمة"""
        user = self.get_user(user_id)
        price = SERVICE_PRICES.get(service, 1000)
        return user.get("balance", 0) >= price
    
    def charge_service(self, user_id: int, service: str) -> bool:
        """خصم تكلفة الخدمة من رصيد المستخدم"""
        if self.can_afford(user_id, service):
            price = SERVICE_PRICES.get(service, 1000)
            self.update_balance(user_id, -price, f"دفع لخدمة: {service}")
            user = self.get_user(user_id)
            user.setdefault("used_services", []).append({
                "service": service,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "cost": price
            })
            self.save_users()
            logger.info(f"Charged user {user_id} for {service}: {price}")
            return True
        return False
    
    def add_pending_score(self, user_id: int, score: float):
        """إضافة درجة مؤقتة للإعفاء"""
        user = self.get_user(user_id)
        user.setdefault("pending_scores", []).append(score)
        if len(user["pending_scores"]) > 3:
            user["pending_scores"] = user["pending_scores"][-3:]
        self.save_users()
    
    def clear_pending_scores(self, user_id: int):
        """مسح الدرجات المؤقتة"""
        user = self.get_user(user_id)
        user["pending_scores"] = []
        self.save_users()
    
    def save_users(self):
        """حفظ بيانات المستخدمين"""
        DataManager.save_data(DATA_FILE, self.users)

# ============= إدارة المواد التعليمية =============
class MaterialsManager:
    def __init__(self):
        self.materials = DataManager.load_data(MATERIALS_FILE, [])
    
    def get_materials_by_stage(self, stage: str) -> List[Dict]:
        """الحصول على المواد حسب المرحلة"""
        return [m for m in self.materials if m.get("stage") == stage]
    
    def get_all_stages(self) -> List[str]:
        """الحصول على جميع المراحل المتاحة"""
        stages = set(m.get("stage", "") for m in self.materials)
        return [s for s in stages if s]
    
    def add_material(self, material_data: Dict):
        """إضافة مادة جديدة"""
        material_data["id"] = len(self.materials) + 1
        material_data["added_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.materials.append(material_data)
        self.save_materials()
    
    def save_materials(self):
        """حفظ المواد"""
        DataManager.save_data(MATERIALS_FILE, self.materials)

# ============= إعداد الذكاء الاصطناعي =============
class AIService:
    def __init__(self):
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-pro')
            logger.info("Gemini AI configured successfully")
        except Exception as e:
            logger.error(f"Failed to configure Gemini AI: {e}")
            self.model = None
    
    def summarize_pdf(self, pdf_path: str) -> str:
        """تلخيص ملف PDF باستخدام الذكاء الاصطناعي"""
        try:
            if not self.model:
                return "❌ خدمة الذكاء الاصطناعي غير متاحة حالياً"
            
            text = self.extract_text_from_pdf(pdf_path)
            
            if len(text) < 50:
                return "❌ لم يتم العثور على نص كافي في الملف"
            
            prompt = f"""
            قم بتلخيص النص التعليمي التالي مع الحفاظ على المعلومات المهمة:
            - احذف المعلومات غير الأساسية
            - رتب النقاط الرئيسية
            - حافظ على التسلسل المنطقي
            - استخدم اللغة العربية الفصحى
            
            النص:
            {text[:3000]}
            """
            
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error summarizing PDF: {e}")
            return f"حدث خطأ في التلخيص: {str(e)[:100]}"
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """استخراج النص من ملف PDF"""
        text = ""
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
            text = f"خطأ في قراءة PDF: {str(e)}"
        return text
    
    def answer_question(self, question: str, context: str = "") -> str:
        """الإجابة على الأسئلة التعليمية"""
        try:
            if not self.model:
                return "❌ خدمة الذكاء الاصطناعي غير متاحة حالياً"
            
            prompt = f"""
            أنت مساعد تعليمي للطلاب العراقيين.
            أجب على السؤال التالي بطريقة علمية ومنهجية حسب المنهج العراقي:
            
            السؤال: {question}
            
            {f'السياق: {context}' if context else ''}
            
            قدم إجابة شاملة ومفيدة مع الأمثلة إذا لزم الأمر.
            """
            
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error answering question: {e}")
            return f"حدث خطأ في الإجابة: {str(e)[:100]}"
    
    def create_summary_pdf(self, original_text: str, summary: str, output_path: str) -> bool:
        """إنشاء ملف PDF منظم للتلخيص"""
        try:
            c = canvas.Canvas(output_path, pagesize=letter)
            width, height = letter
            
            c.setFont("Helvetica-Bold", 16)
            c.drawString(50, height - 50, "تلخيص الملزمة التعليمية")
            c.line(50, height - 60, width - 50, height - 60)
            
            c.setFont("Helvetica", 12)
            y_position = height - 100
            c.drawString(50, y_position, "النص الأصلي (مختصر):")
            y_position -= 20
            
            original_lines = original_text[:500].split('\n')
            for line in original_lines[:10]:
                if y_position < 100:
                    c.showPage()
                    y_position = height - 50
                    c.setFont("Helvetica", 12)
                c.drawString(50, y_position, line[:80])
                y_position -= 20
            
            y_position -= 30
            c.setFont("Helvetica-Bold", 14)
            c.drawString(50, y_position, "التلخيص:")
            y_position -= 20
            c.setFont("Helvetica", 12)
            
            summary_lines = summary.split('\n')
            for line in summary_lines:
                if y_position < 100:
                    c.showPage()
                    y_position = height - 50
                    c.setFont("Helvetica", 12)
                
                try:
                    reshaped_text = arabic_reshaper.reshape(line)
                    bidi_text = get_display(reshaped_text)
                    display_text = bidi_text[:80]
                except:
                    display_text = line[:80]
                
                c.drawString(50, y_position, display_text)
                y_position -= 20
            
            c.save()
            return True
        except Exception as e:
            logger.error(f"Error creating PDF: {e}")
            return False

# ============= الفئة الرئيسية للبوت =============
class YallaNataalamBot:
    def __init__(self):
        self.user_manager = UserManager()
        self.materials_manager = MaterialsManager()
        self.ai_service = AIService()
        self.settings = DataManager.load_data(ADMIN_FILE, {
            "maintenance": False,
            "prices": SERVICE_PRICES.copy(),
            "welcome_bonus": WELCOME_BONUS,
            "referral_bonus": REFERRAL_BONUS,
            "channel_link": "https://t.me/joinchat/AAAA",
            "support_link": f"https://t.me/{SUPPORT_USERNAME}"
        })
        logger.info("Bot initialized successfully")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """بدء البوت"""
        user = update.effective_user
        
        # التحقق من وضع الصيانة
        if self.settings.get("maintenance", False) and user.id != ADMIN_ID:
            await update.message.reply_text(
                "🔧 <b>البوت قيد الصيانة</b>\n\n"
                "نعمل على تحسين الخدمة. سيعود البوت قريباً.\n"
                f"📞 للاستفسار: @{SUPPORT_USERNAME}",
                parse_mode=ParseMode.HTML
            )
            return
        
        user_data = self.user_manager.get_user(user.id)
        
        welcome_message = f"""
🎓 <b>مرحباً {user.first_name}!</b>

أهلاً بك في بوت "يلا نتعلم" 🤖

💰 <b>رصيدك الحالي:</b> {user_data['balance']} دينار عراقي

🎁 <b>هدية ترحيبية:</b> {WELCOME_BONUS} دينار

اختر الخدمة التي تريدها:
"""
        
        keyboard = [
            [InlineKeyboardButton("🧮 حساب درجة الإعفاء", callback_data="service_exemption")],
            [InlineKeyboardButton("📚 تلخيص الملازم", callback_data="service_summarize")],
            [InlineKeyboardButton("❓ سؤال وجواب", callback_data="service_qa")],
            [InlineKeyboardButton("📖 ملازمي ومرشحاتي", callback_data="service_materials")],
            [InlineKeyboardButton("💰 رصيدي", callback_data="balance"),
             InlineKeyboardButton("📊 إحصائياتي", callback_data="stats")],
            [InlineKeyboardButton("👥 دعوة أصدقاء", callback_data="invite"),
             InlineKeyboardButton("🆘 الدعم الفني", url=f"https://t.me/{SUPPORT_USERNAME}")],
        ]
        
        if user.id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("👑 لوحة التحكم", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """فتح لوحة التحكم"""
        query = update.callback_query
        if query:
            await query.answer()
            user = query.from_user
            message = query
        else:
            user = update.effective_user
            message = update.message
        
        if user.id != ADMIN_ID:
            if query:
                await query.edit_message_text("⛔ <b>غير مسموح لك بالدخول!</b>", parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text("⛔ <b>غير مسموح لك بالدخول!</b>", parse_mode=ParseMode.HTML)
            return
        
        total_users = len(self.user_manager.users)
        total_balance = sum(user.get("balance", 0) for user in self.user_manager.users.values())
        
        panel_text = f"""
👑 <b>لوحة التحكم الإدارية</b>

📊 <b>إحصائيات البوت:</b>
- عدد المستخدمين: {total_users}
- إجمالي الرصيد: {total_balance:,} دينار
- حالة البوت: {"🟢 نشط" if not self.settings['maintenance'] else "🔴 صيانة"}

⚙️ <b>اختر الإجراء:</b>
"""
        
        keyboard = [
            [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users")],
            [InlineKeyboardButton("💰 شحن الرصيد", callback_data="admin_charge")],
            [InlineKeyboardButton("⚙️ تغيير الأسعار", callback_data="admin_prices")],
            [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")],
            [InlineKeyboardButton("🛠️ إعدادات البوت", callback_data="admin_settings")],
            [InlineKeyboardButton("📚 إدارة المواد", callback_data="admin_materials")],
            [InlineKeyboardButton("🔙 رجوع للبوت", callback_data="back_home")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query:
            await query.edit_message_text(panel_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(panel_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    
    async def handle_admin_users(self, query):
        """عرض إدارة المستخدمين"""
        users_count = len(self.user_manager.users)
        
        keyboard = [
            [InlineKeyboardButton("🔍 بحث عن مستخدم", callback_data="admin_user_search")],
            [InlineKeyboardButton("📋 قائمة المستخدمين (الصفحة 1)", callback_data="admin_user_list_1")],
            [InlineKeyboardButton("💰 أفضل 10 مستخدمين", callback_data="admin_top_users")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]
        ]
        
        await query.edit_message_text(
            f"👥 <b>إدارة المستخدمين</b>\n\n"
            f"📊 عدد المستخدمين: {users_count}\n\n"
            f"اختر الإجراء:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    
    async def handle_admin_charge(self, query):
        """عرض قائمة الشحن"""
        keyboard = [
            [InlineKeyboardButton("💰 شحن مستخدم", callback_data="admin_charge_user")],
            [InlineKeyboardButton("💸 خصم من مستخدم", callback_data="admin_deduct_user")],
            [InlineKeyboardButton("🎁 شحن جماعي", callback_data="admin_bulk_charge")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]
        ]
        
        await query.edit_message_text(
            "💰 <b>إدارة الشحن والرصيد</b>\n\n"
            "اختر نوع المعاملة:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    
    async def handle_admin_charge_user(self, query, context: ContextTypes.DEFAULT_TYPE):
        """بدء عملية شحن مستخدم"""
        await query.edit_message_text(
            "💰 <b>شحن مستخدم</b>\n\n"
            "أرسل ID المستخدم:\n"
            "<code>123456789</code>",
            parse_mode=ParseMode.HTML
        )
        context.user_data['admin_action'] = 'charge_user'
        return CHARGE_USER
    
    async def handle_admin_deduct_user(self, query, context: ContextTypes.DEFAULT_TYPE):
        """بدء عملية خصم من مستخدم"""
        await query.edit_message_text(
            "💸 <b>خصم من مستخدم</b>\n\n"
            "أرسل ID المستخدم:\n"
            "<code>123456789</code>",
            parse_mode=ParseMode.HTML
        )
        context.user_data['admin_action'] = 'deduct_user'
        return CHARGE_USER
    
    async def handle_charge_user_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """استقبال ID المستخدم للشحن/الخصم"""
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            return ConversationHandler.END
        
        text = update.message.text.strip()
        
        if not text.isdigit():
            await update.message.reply_text("❌ <b>أدخل ID صحيح</b>", parse_mode=ParseMode.HTML)
            return CHARGE_USER
        
        target_id = int(text)
        context.user_data['charge_target'] = target_id
        
        action = context.user_data.get('admin_action', '')
        
        if action == 'charge_user':
            await update.message.reply_text(
                f"✅ <b>تم تحديد المستخدم:</b> {target_id}\n\n"
                f"💰 <b>أرسل المبلغ للشحن:</b>\n"
                f"<code>5000</code>",
                parse_mode=ParseMode.HTML
            )
        elif action == 'deduct_user':
            await update.message.reply_text(
                f"✅ <b>تم تحديد المستخدم:</b> {target_id}\n\n"
                f"💸 <b>أرسل المبلغ للخصم:</b>\n"
                f"<code>1000</code>",
                parse_mode=ParseMode.HTML
            )
        
        return CHARGE_AMOUNT
    
    async def handle_charge_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """استقبال المبلغ للشحن/الخصم"""
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            return ConversationHandler.END
        
        text = update.message.text.strip()
        
        if not text.isdigit():
            await update.message.reply_text("❌ <b>أدخل مبلغاً صحيحاً</b>", parse_mode=ParseMode.HTML)
            return CHARGE_AMOUNT
        
        amount = int(text)
        target_id = context.user_data.get('charge_target')
        action = context.user_data.get('admin_action', '')
        
        if action == 'charge_user':
            if self.user_manager.update_balance(target_id, amount, "شحن من المدير"):
                user_data = self.user_manager.get_user(target_id)
                new_balance = user_data.get("balance", 0)
                
                await update.message.reply_text(
                    f"✅ <b>تم الشحن بنجاح!</b>\n\n"
                    f"👤 <b>المستخدم:</b> {target_id}\n"
                    f"💰 <b>المبلغ:</b> {amount:,} دينار\n"
                    f"💳 <b>الرصيد الجديد:</b> {new_balance:,} دينار",
                    parse_mode=ParseMode.HTML
                )
                
                # إرسال إشعار للمستخدم
                try:
                    await context.bot.send_message(
                        chat_id=target_id,
                        text=f"🎉 <b>تم شحن رصيدك!</b>\n\n"
                             f"💰 <b>المبلغ:</b> {amount:,} دينار\n"
                             f"💳 <b>رصيدك الحالي:</b> {new_balance:,} دينار",
                        parse_mode=ParseMode.HTML
                    )
                except:
                    pass
            else:
                await update.message.reply_text("❌ <b>فشل في الشحن. تحقق من ID المستخدم</b>", parse_mode=ParseMode.HTML)
        
        elif action == 'deduct_user':
            if self.user_manager.update_balance(target_id, -amount, "خصم من المدير"):
                user_data = self.user_manager.get_user(target_id)
                new_balance = user_data.get("balance", 0)
                
                await update.message.reply_text(
                    f"✅ <b>تم الخصم بنجاح!</b>\n\n"
                    f"👤 <b>المستخدم:</b> {target_id}\n"
                    f"💸 <b>المبلغ:</b> {amount:,} دينار\n"
                    f"💳 <b>الرصيد الجديد:</b> {new_balance:,} دينار",
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text("❌ <b>فشل في الخصم. تحقق من ID المستخدم والرصيد</b>", parse_mode=ParseMode.HTML)
        
        # تنظيف
        context.user_data.pop('admin_action', None)
        context.user_data.pop('charge_target', None)
        
        # العودة للوحة التحكم
        await self.admin_panel(update, context)
        return ConversationHandler.END
    
    async def handle_admin_prices(self, query):
        """عرض قائمة الأسعار"""
        prices_text = "<b>💰 الأسعار الحالية:</b>\n\n"
        
        service_names = {
            "exemption": "حساب درجة الإعفاء",
            "summarize": "تلخيص الملازم",
            "qa": "سؤال وجواب",
            "materials": "ملازمي ومرشحاتي"
        }
        
        for service, price in self.settings["prices"].items():
            prices_text += f"{service_names.get(service, service)}: {price:,} دينار\n"
        
        keyboard = []
        for service in self.settings["prices"]:
            service_name = service_names.get(service, service)
            keyboard.append([InlineKeyboardButton(
                f"✏️ تعديل {service_name}", callback_data=f"admin_price_{service}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")])
        
        await query.edit_message_text(
            prices_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    
    async def handle_admin_price_change(self, query, context: ContextTypes.DEFAULT_TYPE, service: str):
        """بدء تغيير السعر"""
        service_names = {
            "exemption": "حساب درجة الإعفاء",
            "summarize": "تلخيص الملازم",
            "qa": "سؤال وجواب",
            "materials": "ملازمي ومرشحاتي"
        }
        
        service_name = service_names.get(service, service)
        current_price = self.settings["prices"].get(service, 1000)
        
        await query.edit_message_text(
            f"💰 <b>تغيير سعر {service_name}</b>\n\n"
            f"السعر الحالي: {current_price:,} دينار\n\n"
            f"أرسل السعر الجديد:\n"
            f"<code>1500</code>",
            parse_mode=ParseMode.HTML
        )
        context.user_data['price_service'] = service
        return PRICE_CHANGE
    
    async def handle_price_change(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """استقبال السعر الجديد"""
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            return ConversationHandler.END
        
        text = update.message.text.strip()
        
        if not text.isdigit():
            await update.message.reply_text("❌ <b>أدخل سعراً صحيحاً</b>", parse_mode=ParseMode.HTML)
            return PRICE_CHANGE
        
        new_price = int(text)
        service = context.user_data.get('price_service', '')
        
        if service:
            self.settings["prices"][service] = new_price
            DataManager.save_data(ADMIN_FILE, self.settings)
            
            service_names = {
                "exemption": "حساب درجة الإعفاء",
                "summarize": "تلخيص الملازم",
                "qa": "سؤال وجواب",
                "materials": "ملازمي ومرشحاتي"
            }
            
            await update.message.reply_text(
                f"✅ <b>تم تغيير السعر بنجاح!</b>\n\n"
                f"📝 <b>الخدمة:</b> {service_names.get(service, service)}\n"
                f"💰 <b>السعر الجديد:</b> {new_price:,} دينار",
                parse_mode=ParseMode.HTML
            )
            
            # تحديث الأسعار العالمية
            SERVICE_PRICES[service] = new_price
        
        context.user_data.pop('price_service', None)
        await self.admin_panel(update, context)
        return ConversationHandler.END
    
    async def handle_admin_stats(self, query):
        """عرض الإحصائيات"""
        users = self.user_manager.users
        
        total_users = len(users)
        active_users = sum(1 for user in users.values() if user.get("balance", 0) > 0)
        total_balance = sum(user.get("balance", 0) for user in users.values())
        
        services_count = {
            "exemption": 0,
            "summarize": 0,
            "qa": 0,
            "materials": 0
        }
        
        for user in users.values():
            for service in user.get("used_services", []):
                service_type = service.get("service", "")
                if service_type in services_count:
                    services_count[service_type] += 1
        
        stats_text = f"""
📊 <b>إحصائيات مفصلة</b>

👥 <b>المستخدمين:</b>
- الإجمالي: {total_users:,}
- النشطين: {active_users:,}
- النسبة: {(active_users/total_users*100) if total_users > 0 else 0:.1f}%

💰 <b>الماليات:</b>
- إجمالي الرصيد: {total_balance:,} دينار
- متوسط الرصيد: {(total_balance/total_users) if total_users > 0 else 0:,.0f} دينار

📈 <b>الخدمات المستخدمة:</b>
- حساب الإعفاء: {services_count['exemption']:,}
- تلخيص الملازم: {services_count['summarize']:,}
- سؤال وجواب: {services_count['qa']:,}
- المواد: {services_count['materials']:,}
- الإجمالي: {sum(services_count.values()):,}

🕐 <b>آخر تحديث:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        keyboard = [
            [InlineKeyboardButton("🔄 تحديث", callback_data="admin_stats")],
            [InlineKeyboardButton("📥 تصدير البيانات", callback_data="admin_export")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]
        ]
        
        await query.edit_message_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    
    async def handle_admin_settings(self, query):
        """عرض إعدادات البوت"""
        maintenance_status = "🔴 مفعل" if self.settings['maintenance'] else "🟢 معطل"
        
        settings_text = f"""
⚙️ <b>إعدادات البوت</b>

🔧 <b>وضع الصيانة:</b> {maintenance_status}
🎁 <b>الهدية الترحيبية:</b> {self.settings['welcome_bonus']:,} دينار
👥 <b>مكافأة الدعوة:</b> {self.settings['referral_bonus']:,} دينار

🔗 <b>الروابط:</b>
- القناة: {self.settings['channel_link'][:30]}...
- الدعم: {self.settings['support_link']}
"""
        
        keyboard = [
            [InlineKeyboardButton("🔧 وضع الصيانة", callback_data="admin_toggle_maintenance")],
            [InlineKeyboardButton("🎁 الهدية الترحيبية", callback_data="admin_change_welcome")],
            [InlineKeyboardButton("👥 مكافأة الدعوة", callback_data="admin_change_referral")],
            [InlineKeyboardButton("📢 رابط القناة", callback_data="admin_change_channel")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]
        ]
        
        await query.edit_message_text(
            settings_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    
    async def handle_admin_materials(self, query):
        """عرض إدارة المواد"""
        materials = self.materials_manager.materials
        
        keyboard = [
            [InlineKeyboardButton("➕ إضافة مادة", callback_data="admin_material_add")],
            [InlineKeyboardButton("📋 عرض المواد", callback_data="admin_material_list_1")],
            [InlineKeyboardButton("🗑️ حذف مادة", callback_data="admin_material_delete")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]
        ]
        
        await query.edit_message_text(
            f"📚 <b>إدارة المواد التعليمية</b>\n\n"
            f"📊 عدد المواد: {len(materials)}\n\n"
            f"اختر الإجراء:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    
    async def handle_admin_material_add(self, query, context: ContextTypes.DEFAULT_TYPE):
        """بدء إضافة مادة"""
        await query.edit_message_text(
            "➕ <b>إضافة مادة جديدة</b>\n\n"
            "أرسل تفاصيل المادة بالشكل التالي:\n\n"
            "<code>اسم المادة | الوصف | المرحلة | رابط التحميل</code>\n\n"
            "مثال:\n"
            "<code>رياضيات السادس | ملزمة شاملة | السادس الإعدادي | https://example.com/file.pdf</code>",
            parse_mode=ParseMode.HTML
        )
        return MATERIAL_ADD
    
    async def handle_material_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """استقبال تفاصيل المادة"""
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            return ConversationHandler.END
        
        text = update.message.text.strip()
        parts = text.split('|')
        
        if len(parts) >= 4:
            name = parts[0].strip()
            description = parts[1].strip()
            stage = parts[2].strip()
            url = parts[3].strip()
            
            new_material = {
                "id": len(self.materials_manager.materials) + 1,
                "name": name,
                "description": description,
                "stage": stage,
                "file_url": url,
                "added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            self.materials_manager.add_material(new_material)
            
            await update.message.reply_text(
                f"✅ <b>تم إضافة المادة بنجاح!</b>\n\n"
                f"📚 <b>الاسم:</b> {name}\n"
                f"📝 <b>الوصف:</b> {description}\n"
                f"🎓 <b>المرحلة:</b> {stage}\n"
                f"🔗 <b>الرابط:</b> {url[:50]}...",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text("❌ <b>تنسيق غير صحيح. استخدم | لفصل الحقول</b>", parse_mode=ParseMode.HTML)
            return MATERIAL_ADD
        
        await self.admin_panel(update, context)
        return ConversationHandler.END
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة جميع عمليات الرد"""
        query = update.callback_query
        await query.answer()
        
        try:
            if query.data == "admin_panel":
                await self.admin_panel(update, context)
            
            elif query.data == "admin_users":
                await self.handle_admin_users(query)
            
            elif query.data == "admin_charge":
                await self.handle_admin_charge(query)
            
            elif query.data == "admin_charge_user":
                await self.handle_admin_charge_user(query, context)
                return CHARGE_USER
            
            elif query.data == "admin_deduct_user":
                await self.handle_admin_deduct_user(query, context)
                return CHARGE_USER
            
            elif query.data == "admin_prices":
                await self.handle_admin_prices(query)
            
            elif query.data.startswith("admin_price_"):
                service = query.data.replace("admin_price_", "")
                await self.handle_admin_price_change(query, context, service)
                return PRICE_CHANGE
            
            elif query.data == "admin_stats":
                await self.handle_admin_stats(query)
            
            elif query.data == "admin_settings":
                await self.handle_admin_settings(query)
            
            elif query.data == "admin_toggle_maintenance":
                self.settings['maintenance'] = not self.settings['maintenance']
                DataManager.save_data(ADMIN_FILE, self.settings)
                status = "تم تفعيل" if self.settings['maintenance'] else "تم إلغاء"
                await query.answer(f"✅ {status} وضع الصيانة")
                await self.handle_admin_settings(query)
            
            elif query.data == "admin_materials":
                await self.handle_admin_materials(query)
            
            elif query.data == "admin_material_add":
                await self.handle_admin_material_add(query, context)
                return MATERIAL_ADD
            
            elif query.data == "back_home":
                await self.handle_back_home(update, context)
            
            # باقي الأزرار للخدمات العادية
            elif query.data.startswith("service_"):
                await self.handle_service_selection(update, context)
            
            elif query.data == "balance":
                await self.handle_balance_check(update, context)
            
            elif query.data == "stats":
                await self.handle_stats(update, context)
            
            elif query.data == "invite":
                await self.handle_invite(update, context)
            
            elif query.data.startswith("stage_"):
                stage = query.data.replace("stage_", "")
                await self.show_stage_materials(query, stage)
            
            else:
                await query.answer("⏳ جاري التحميل...")
        
        except Exception as e:
            logger.error(f"Error in callback handler: {e}")
            await query.answer("❌ حدث خطأ. حاول مرة أخرى")
    
    # باقي الدوال للخدمات العادية (نفس الدوال السابقة)
    async def handle_service_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة اختيار الخدمة"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        service = query.data.replace("service_", "")
        
        if not self.user_manager.can_afford(user_id, service):
            await query.edit_message_text(
                f"❌ <b>رصيدك غير كافي لهذه الخدمة!</b>\n\n"
                f"💰 سعر الخدمة: {SERVICE_PRICES.get(service, 1000)} دينار\n"
                f"💳 رصيدك الحالي: {self.user_manager.get_user(user_id)['balance']} دينار\n\n"
                f"📞 تواصل مع الدعم الفني للشحن: @{SUPPORT_USERNAME}",
                parse_mode=ParseMode.HTML
            )
            return
        
        if service == "exemption":
            await self.show_exemption_calculator(query)
        elif service == "summarize":
            await query.edit_message_text(
                "📤 <b>أرسل ملف PDF المراد تلخيصه</b>\n\n"
                "💰 سعر الخدمة: 1000 دينار\n"
                "⏳ قد تستغرق العملية بضع دقائق",
                parse_mode=ParseMode.HTML
            )
            context.user_data['awaiting_pdf'] = True
            context.user_data['selected_service'] = "summarize"
        elif service == "qa":
            await query.edit_message_text(
                "❓ <b>أرسل سؤالك الآن</b>\n\n"
                "💰 سعر الخدمة: 1000 دينار\n"
                "⏳ جاهز للإجابة على أسئلتك",
                parse_mode=ParseMode.HTML
            )
            context.user_data['awaiting_question'] = True
            context.user_data['selected_service'] = "qa"
        elif service == "materials":
            await self.show_materials_menu(query)
    
    async def show_exemption_calculator(self, query):
        """عرض آلة حساب الإعفاء"""
        user_id = query.from_user.id
        
        if not self.user_manager.can_afford(user_id, "exemption"):
            await query.edit_message_text(
                f"❌ <b>رصيدك غير كافي!</b>\n\n"
                f"💰 سعر الخدمة: {SERVICE_PRICES['exemption']} دينار\n"
                f"💳 رصيدك الحالي: {self.user_manager.get_user(user_id)['balance']} دينار",
                parse_mode=ParseMode.HTML
            )
            return
        
        keyboard = [
            [InlineKeyboardButton("🏠 الرجوع للرئيسية", callback_data="back_home")],
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🧮 <b>حاسبة درجة الإعفاء</b>\n\n"
            "أدخل درجاتك لثلاثة كورسات:\n"
            "1. درجة الكورس الأول\n"
            "2. درجة الكورس الثاني\n"
            "3. درجة الكورس الثالث\n\n"
            "📝 <b>أرسل الدرجات بهذا الشكل:</b>\n"
            "<code>90 85 95</code>\n\n"
            "أو أرسل كل درجة على حدة:\n"
            "أولاً: <code>90</code>\n"
            "ثانياً: <code>85</code>\n"
            "ثالثاً: <code>95</code>\n\n"
            "🎯 <b>المعدل المطلوب للإعفاء:</b> 90 فما فوق\n"
            "💰 <b>سعر الخدمة:</b> 1000 دينار",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    
    async def handle_exemption_calculation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة حساب درجة الإعفاء"""
        user_id = update.effective_user.id
        
        try:
            text = update.message.text.strip()
            
            if len(text.split()) >= 3:
                scores = list(map(float, text.split()[:3]))
                
                if not self.user_manager.charge_service(user_id, "exemption"):
                    await update.message.reply_text(
                        f"❌ <b>رصيدك غير كافي!</b>\n\n"
                        f"رصيدك: {self.user_manager.get_user(user_id)['balance']} دينار",
                        parse_mode=ParseMode.HTML
                    )
                    return
                
                await self.calculate_and_send_result(update, user_id, scores)
                return
            
            try:
                score = float(text)
                if score < 0 or score > 100:
                    await update.message.reply_text("⚠️ أدخل درجة بين 0 و 100")
                    return
                
                user_data = self.user_manager.get_user(user_id)
                user_data.setdefault("pending_scores", []).append(score)
                
                if len(user_data["pending_scores"]) == 1:
                    await update.message.reply_text(
                        f"✅ تم حفظ الدرجة الأولى: {score}\n"
                        f"📝 أرسل الدرجة الثانية الآن"
                    )
                elif len(user_data["pending_scores"]) == 2:
                    await update.message.reply_text(
                        f"✅ تم حفظ الدرجة الثانية: {score}\n"
                        f"📝 أرسل الدرجة الثالثة الآن"
                    )
                elif len(user_data["pending_scores"]) >= 3:
                    scores = user_data["pending_scores"][-3:]
                    
                    if not self.user_manager.charge_service(user_id, "exemption"):
                        await update.message.reply_text(
                            f"❌ <b>رصيدك غير كافي!</b>\n\n"
                            f"رصيدك: {self.user_manager.get_user(user_id)['balance']} دينار",
                            parse_mode=ParseMode.HTML
                        )
                        self.user_manager.clear_pending_scores(user_id)
                        return
                    
                    await self.calculate_and_send_result(update, user_id, scores)
                    self.user_manager.clear_pending_scores(user_id)
                
                self.user_manager.save_users()
                
            except ValueError:
                await update.message.reply_text("⚠️ أدخل رقماً صحيحاً بين 0 و 100")
                
        except Exception as e:
            logger.error(f"Error in exemption calculation: {e}")
            await update.message.reply_text("❌ حدث خطأ في الحساب. حاول مرة أخرى")
    
    async def calculate_and_send_result(self, update: Update, user_id: int, scores: list):
        """حساب النتيجة وإرسالها"""
        average = sum(scores) / 3
        
        if average >= 90:
            message = f"""
🎉 <b>تهانينا! تم إعفاؤك من المادة</b> 🎉

📊 <b>درجاتك:</b>
الكورس الأول: {scores[0]}
الكورس الثاني: {scores[1]}  
الكورس الثالث: {scores[2]}

🧮 <b>المعدل:</b> {average:.2f}

✅ <b>أنت معفي من المادة</b>

💰 تم خصم: {SERVICE_PRICES['exemption']} دينار
💳 رصيدك المتبقي: {self.user_manager.get_user(user_id)['balance']} دينار
"""
        else:
            message = f"""
📊 <b>درجاتك:</b>
الكورس الأول: {scores[0]}
الكورس الثاني: {scores[1]}
الكورس الثالث: {scores[2]}

🧮 <b>المعدل:</b> {average:.2f}

⚠️ <b>المعدل أقل من 90</b>
❌ <b>لم تحصل على الإعفاء</b>

💰 تم خصم: {SERVICE_PRICES['exemption']} دينار
💳 رصيدك المتبقي: {self.user_manager.get_user(user_id)['balance']} دينار
"""
        
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)
        
        user_data = self.user_manager.get_user(user_id)
        user_data.setdefault("exemption_scores", []).append({
            "scores": scores,
            "average": average,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "exempted": average >= 90
        })
        self.user_manager.save_users()
    
    async def handle_pdf_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة ملف PDF للتلخيص"""
        user_id = update.effective_user.id
        
        if not context.user_data.get('awaiting_pdf'):
            return
        
        if not self.user_manager.charge_service(user_id, "summarize"):
            await update.message.reply_text(
                f"❌ <b>رصيدك غير كافي!</b>\n\n"
                f"رصيدك: {self.user_manager.get_user(user_id)['balance']} دينار",
                parse_mode=ParseMode.HTML
            )
            context.user_data['awaiting_pdf'] = False
            return
        
        document = update.message.document
        if not document.mime_type == 'application/pdf':
            await update.message.reply_text("❌ يرجى إرسال ملف PDF فقط")
            return
        
        await update.message.reply_text("⏳ جاري تحميل الملف...")
        
        try:
            file = await document.get_file()
            pdf_path = f"temp_{user_id}.pdf"
            await file.download_to_drive(pdf_path)
            
            await update.message.reply_text("📖 جاري قراءة الملف وتلخيصه...")
            
            text = self.ai_service.extract_text_from_pdf(pdf_path)
            
            if len(text) < 100:
                await update.message.reply_text("❌ الملف فارغ أو لا يحتوي على نص قابل للقراءة")
                os.remove(pdf_path)
                context.user_data['awaiting_pdf'] = False
                return
            
            await update.message.reply_text("🤖 جاري التلخيص بالذكاء الاصطناعي...")
            
            summary = self.ai_service.summarize_pdf(pdf_path)
            
            if summary.startswith("❌") or summary.startswith("حدث خطأ"):
                await update.message.reply_text(f"❌ {summary}")
                os.remove(pdf_path)
                context.user_data['awaiting_pdf'] = False
                return
            
            await update.message.reply_text("📄 جاري إنشاء ملف PDF جديد...")
            
            output_path = f"summary_{user_id}.pdf"
            success = self.ai_service.create_summary_pdf(text[:1000], summary, output_path)
            
            if success:
                await update.message.reply_document(
                    document=open(output_path, 'rb'),
                    caption=f"✅ <b>تم تلخيص الملزمة بنجاح</b>\n\n"
                           f"📊 <b>ملخص التلخيص:</b>\n{summary[:200]}...\n\n"
                           f"💰 تم خصم: {SERVICE_PRICES['summarize']} دينار\n"
                           f"💳 رصيدك المتبقي: {self.user_manager.get_user(user_id)['balance']} دينار",
                    parse_mode=ParseMode.HTML
                )
                
                os.remove(pdf_path)
                os.remove(output_path)
            else:
                await update.message.reply_text(
                    "✅ <b>تم التلخيص بنجاح!</b>\n\n"
                    f"{summary[:1500]}\n\n"
                    f"💰 تم خصم: {SERVICE_PRICES['summarize']} دينار\n"
                    f"💳 رصيدك المتبقي: {self.user_manager.get_user(user_id)['balance']} دينار",
                    parse_mode=ParseMode.HTML
                )
                os.remove(pdf_path)
        
        except Exception as e:
            logger.error(f"Error processing PDF: {e}")
            await update.message.reply_text(f"❌ حدث خطأ في معالجة الملف: {str(e)[:100]}")
        
        context.user_data['awaiting_pdf'] = False
    
    async def handle_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الأسئلة"""
        user_id = update.effective_user.id
        
        if not context.user_data.get('awaiting_question'):
            return
        
        question = update.message.text.strip()
        
        if len(question) < 5:
            await update.message.reply_text("❌ السؤال قصير جداً. يرجى كتابة سؤال مفصل")
            return
        
        if not self.user_manager.charge_service(user_id, "qa"):
            await update.message.reply_text(
                f"❌ <b>رصيدك غير كافي!</b>\n\n"
                f"رصيدك: {self.user_manager.get_user(user_id)['balance']} دينار",
                parse_mode=ParseMode.HTML
            )
            context.user_data['awaiting_question'] = False
            return
        
        await update.message.reply_text("🤖 جاري البحث عن الإجابة...")
        
        try:
            answer = self.ai_service.answer_question(question)
            
            if answer.startswith("❌") or answer.startswith("حدث خطأ"):
                await update.message.reply_text(f"❌ {answer}")
                self.user_manager.update_balance(user_id, SERVICE_PRICES['qa'], "استرجاع رصيد لخطأ في الخدمة")
            else:
                await update.message.reply_text(
                    f"❓ <b>سؤالك:</b>\n{question}\n\n"
                    f"💡 <b>الإجابة:</b>\n{answer[:3000]}\n\n"
                    f"💰 تم خصم: {SERVICE_PRICES['qa']} دينار\n"
                    f"💳 رصيدك المتبقي: {self.user_manager.get_user(user_id)['balance']} دينار",
                    parse_mode=ParseMode.HTML
                )
        
        except Exception as e:
            logger.error(f"Error answering question: {e}")
            await update.message.reply_text(f"❌ حدث خطأ في الإجابة: {str(e)[:100]}")
            self.user_manager.update_balance(user_id, SERVICE_PRICES['qa'], "استرجاع رصيد لخطأ في الخدمة")
        
        context.user_data['awaiting_question'] = False
    
    async def show_materials_menu(self, query):
        """عرض قائمة المواد"""
        user_id = query.from_user.id
        
        if not self.user_manager.can_afford(user_id, "materials"):
            await query.edit_message_text(
                f"❌ <b>رصيدك غير كافي!</b>\n\n"
                f"💰 سعر الخدمة: {SERVICE_PRICES['materials']} دينار\n"
                f"💳 رصيدك الحالي: {self.user_manager.get_user(user_id)['balance']} دينار",
                parse_mode=ParseMode.HTML
            )
            return
        
        stages = self.materials_manager.get_all_stages()
        
        if not stages:
            keyboard = [[InlineKeyboardButton("🏠 الرئيسية", callback_data="back_home")]]
            await query.edit_message_text(
                "📭 <b>لا توجد مواد متاحة حالياً</b>\n\n"
                "📞 تواصل مع الدعم الفني لإضافة مواد جديدة",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
            return
        
        if not self.user_manager.charge_service(user_id, "materials"):
            await query.edit_message_text(
                f"❌ <b>فشل في خصم المبلغ!</b>",
                parse_mode=ParseMode.HTML
            )
            return
        
        keyboard = []
        for stage in stages:
            keyboard.append([InlineKeyboardButton(f"📘 {stage}", callback_data=f"stage_{stage}")])
        
        keyboard.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="back_home")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"📖 <b>اختر المرحلة الدراسية:</b>\n\n"
            f"💰 تم خصم: {SERVICE_PRICES['materials']} دينار\n"
            f"💳 رصيدك المتبقي: {self.user_manager.get_user(user_id)['balance']} دينار",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    
    async def show_stage_materials(self, query, stage: str):
        """عرض مواد مرحلة محددة"""
        materials = self.materials_manager.get_materials_by_stage(stage)
        
        if not materials:
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="service_materials")]]
            await query.edit_message_text(
                f"📭 <b>لا توجد مواد لمرحلة {stage}</b>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
            return
        
        message = f"<b>📚 مواد مرحلة {stage}:</b>\n\n"
        
        keyboard = []
        for material in materials:
            btn_text = f"📄 {material.get('name', 'بدون اسم')}"
            file_url = material.get('file_url', '#')
            keyboard.append([InlineKeyboardButton(btn_text, url=file_url)])
            
            message += f"<b>📖 {material.get('name', 'بدون اسم')}</b>\n"
            message += f"📝 {material.get('description', '')[:100]}...\n\n"
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="service_materials")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    
    async def handle_balance_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض رصيد المستخدم"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        user_data = self.user_manager.get_user(user_id)
        
        balance_text = f"""
💰 <b>رصيدك الحالي:</b> {user_data['balance']} دينار عراقي

📊 <b>آخر المعاملات:</b>
"""
        
        transactions = user_data.get('transactions', [])[-5:]
        if transactions:
            for trans in transactions:
                sign = "+" if trans['amount'] > 0 else ""
                date = trans['date'].split()[0]
                balance_text += f"\n{date}: {sign}{trans['amount']} - {trans['description'][:30]}"
        else:
            balance_text += "\nلا توجد معاملات سابقة"
        
        keyboard = [
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="back_home")],
            [InlineKeyboardButton("📥 شحن الرصيد", url=f"https://t.me/{SUPPORT_USERNAME}")]
        ]
        
        await query.edit_message_text(
            balance_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    
    async def handle_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض إحصائيات المستخدم"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        user_data = self.user_manager.get_user(user_id)
        
        stats_text = f"""
📊 <b>إحصائياتك الشخصية</b>

👤 <b>المعلومات:</b>
- تاريخ الانضمام: {user_data['joined_date']}
- الرصيد الحالي: {user_data['balance']} دينار

📈 <b>النشاط:</b>
- عدد الخدمات المستخدمة: {len(user_data.get('used_services', []))}
- عدد حسابات الإعفاء: {len(user_data.get('exemption_scores', []))}
- عدد الأصدقاء المدعوين: {len(user_data.get('invited_users', []))}

🔗 <b>رابط الدعوة الخاص بك:</b>
<code>https://t.me/{BOT_USERNAME.replace('@', '')}?start={user_id}</code>

💸 <b>مكافأة الدعوة:</b> {REFERRAL_BONUS} دينار لكل صديق
"""
        
        keyboard = [
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="back_home")],
            [InlineKeyboardButton("💰 رصيدي", callback_data="balance")]
        ]
        
        await query.edit_message_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    
    async def handle_invite(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض معلومات الدعوة"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        user_data = self.user_manager.get_user(user_id)
        
        invite_text = f"""
👥 <b>دعوة الأصدقاء</b>

💰 <b>احصل على {REFERRAL_BONUS} دينار لكل صديق يدخل عبر رابطك!</b>

🔗 <b>رابط الدعوة الخاص بك:</b>
<code>https://t.me/{BOT_USERNAME.replace('@', '')}?start={user_id}</code>

📊 <b>إحصائيات الدعوة:</b>
- عدد الأصدقاء المدعوين: {len(user_data.get('invited_users', []))}
- أرباح الدعوة: {len(user_data.get('invited_users', [])) * REFERRAL_BONUS} دينار
"""
        
        keyboard = [
            [InlineKeyboardButton("🏠 الرئيسية", callback_data="back_home")],
            [InlineKeyboardButton("📤 مشاركة", switch_inline_query=f"انضم إلى بوت يلا نتعلم التعليمي!")]
        ]
        
        await query.edit_message_text(
            invite_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    
    async def handle_back_home(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """العودة للصفحة الرئيسية"""
        query = update.callback_query
        await query.answer()
        
        user = query.from_user
        user_data = self.user_manager.get_user(user.id)
        
        welcome_message = f"""
🎓 <b>مرحباً بعودتك {user.first_name}!</b>

💰 <b>رصيدك الحالي:</b> {user_data['balance']} دينار

اختر الخدمة:
"""
        
        keyboard = [
            [InlineKeyboardButton("🧮 حساب درجة الإعفاء", callback_data="service_exemption")],
            [InlineKeyboardButton("📚 تلخيص الملازم", callback_data="service_summarize")],
            [InlineKeyboardButton("❓ سؤال وجواب", callback_data="service_qa")],
            [InlineKeyboardButton("📖 ملازمي ومرشحاتي", callback_data="service_materials")],
            [InlineKeyboardButton("💰 رصيدي", callback_data="balance"),
             InlineKeyboardButton("📊 إحصائياتي", callback_data="stats")],
            [InlineKeyboardButton("👥 دعوة أصدقاء", callback_data="invite"),
             InlineKeyboardButton("🆘 الدعم الفني", url=f"https://t.me/{SUPPORT_USERNAME}")],
        ]
        
        if user.id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("👑 لوحة التحكم", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            welcome_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الرسائل النصية"""
        message_type = update.message.chat.type
        
        if message_type == "private":
            text = update.message.text
            
            if not text or len(text.strip()) < 1:
                return
            
            # إذا كان المستخدم يرسل درجات
            if text.replace('.', '', 1).isdigit() or (text.count(' ') >= 2 and all(part.replace('.', '', 1).isdigit() for part in text.split()[:3])):
                await self.handle_exemption_calculation(update, context)
            elif context.user_data.get('awaiting_question'):
                await self.handle_question(update, context)
            elif context.user_data.get('awaiting_pdf'):
                await update.message.reply_text("📤 يرجى إرسال ملف PDF فقط")
            else:
                await update.message.reply_text(
                    "🤖 <b>استخدم الأزرار للتفاعل مع البوت</b>\n\n"
                    "📝 اكتب /start لعرض القائمة الرئيسية",
                    parse_mode=ParseMode.HTML
                )
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة الأخطاء"""
        logger.error(f"Update {update} caused error {context.error}")
        
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ <b>حدث خطأ غير متوقع</b>\n\n"
                    f"🆘 تواصل مع الدعم الفني: @{SUPPORT_USERNAME}",
                    parse_mode=ParseMode.HTML
                )
            except:
                pass
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إلغاء العملية"""
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            return ConversationHandler.END
        
        await update.message.reply_text("❌ <b>تم إلغاء العملية</b>", parse_mode=ParseMode.HTML)
        await self.admin_panel(update, context)
        return ConversationHandler.END
    
    def run(self):
        """تشغيل البوت"""
        print("🤖 البوت يعمل الآن...")
        print(f"👑 المدير: {ADMIN_ID}")
        print(f"🆘 الدعم: @{SUPPORT_USERNAME}")
        
        app = Application.builder().token(TOKEN).build()
        
        # إنشاء ConversationHandler للوحة التحكم
        admin_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.handle_callback)],
            states={
                CHARGE_USER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_charge_user_id),
                    CallbackQueryHandler(self.handle_callback)
                ],
                CHARGE_AMOUNT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_charge_amount),
                    CallbackQueryHandler(self.handle_callback)
                ],
                PRICE_CHANGE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_price_change),
                    CallbackQueryHandler(self.handle_callback)
                ],
                MATERIAL_ADD: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_material_add),
                    CallbackQueryHandler(self.handle_callback)
                ],
                ADMIN_MENU: [
                    CallbackQueryHandler(self.handle_callback)
                ]
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel),
                CallbackQueryHandler(self.handle_callback, pattern="^back_home$|^admin_panel$")
            ],
            map_to_parent={
                ConversationHandler.END: ADMIN_MENU
            }
        )
        
        # إضافة handlers
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("admin", self.admin_panel))
        app.add_handler(admin_conv_handler)
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        app.add_handler(MessageHandler(filters.Document.PDF, self.handle_pdf_file))
        app.add_error_handler(self.error_handler)
        
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

# ============= تشغيل البوت =============
if __name__ == "__main__":
    bot = YallaNataalamBot()
    bot.run()
