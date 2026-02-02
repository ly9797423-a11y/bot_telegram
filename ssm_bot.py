#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت: يلا نتعلم
المطور: @Allawi04 (ID: 6130994941)
الإصدار: 3.0 - مخصص للسيرفر
"""

import os
import sys
import logging
import asyncio
import json
import io
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any

# =============================================
# استيراد المكتبات مع معالجة الأخطاء
# =============================================
try:
    # Telegram
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        CallbackQueryHandler,
        ConversationHandler,
        ContextTypes,
        filters
    )
    from telegram.constants import ParseMode
    
    # الذكاء الاصطناعي
    import google.generativeai as genai
    
    # قاعدة البيانات
    from pymongo import MongoClient, ASCENDING, DESCENDING
    
    # PDF (بدون مشاكل)
    import PyPDF2
    
    # النصوص العربية
    import arabic_reshaper
    from bidi.algorithm import get_display
    
    logger.info("✅ تم استيراد جميع المكتبات بنجاح")
    
except ImportError as e:
    print(f"❌ خطأ في استيراد المكتبات: {e}")
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
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# =============================================
# إعدادات البوت
# =============================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8481569753:AAHTdbWwu0BHmoo_iHPsye8RkTptWzfiQWU")
DEVELOPER_ID = 6130994941  # ⬅️ ايدي المطور
DEVELOPER_USERNAME = "Allawi04"
BOT_USERNAME = "FC4Xbot"

# =============================================
# إعدادات الذكاء الاصطناعي
# =============================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyAqlug21bw_eI60ocUtc1Z76NhEUc-zuzY")
try:
    genai.configure(api_key=GEMINI_API_KEY)
    GEMINI_AVAILABLE = True
except Exception as e:
    logger.warning(f"⚠️ Gemini غير متاح: {e}")
    GEMINI_AVAILABLE = False

# =============================================
# قاعدة البيانات المبسطة
# =============================================
class SimpleDatabase:
    """قاعدة بيانات مبسطة في الذاكرة للسيرفر"""
    
    def __init__(self):
        self.users = {}
        self.transactions = []
        self.settings = {
            "service_price": 1000,
            "welcome_bonus": 1000,
            "invite_bonus": 500,
            "maintenance_mode": False,
            "bot_channel": f"@{BOT_USERNAME}",
            "support_channel": f"@{DEVELOPER_USERNAME}",
            "currency": "دينار عراقي",
            "min_charge": 1000
        }
        self.admins = {DEVELOPER_ID: {"username": DEVELOPER_USERNAME, "role": "super_admin"}}
        self.services = [
            {"name": "حساب درجة الإعفاء", "price": 1000, "active": True, "icon": "🧮"},
            {"name": "تلخيص الملازم", "price": 1000, "active": True, "icon": "📄"},
            {"name": "سؤال وجواب", "price": 1000, "active": True, "icon": "❓"},
            {"name": "ملازمي ومرشحاتي", "price": 1000, "active": True, "icon": "📚"}
        ]
        
        logger.info("✅ تم تهيئة قاعدة البيانات المبسطة")
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        return self.users.get(user_id)
    
    def create_user(self, user_id: int, username: str = None, first_name: str = None) -> Dict:
        user_data = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "balance": self.settings["welcome_bonus"],
            "invite_code": f"INV{user_id}",
            "invited_users": [],
            "total_spent": 0,
            "total_services": 0,
            "created_at": datetime.now(),
            "last_active": datetime.now(),
            "banned": False,
            "ban_reason": None
        }
        
        self.users[user_id] = user_data
        
        # تسجيل المعاملة
        self.transactions.append({
            "transaction_id": f"WEL{user_id}{int(datetime.now().timestamp())}",
            "user_id": user_id,
            "amount": self.settings["welcome_bonus"],
            "type": "welcome_bonus",
            "description": "مكافأة ترحيبية",
            "timestamp": datetime.now()
        })
        
        return user_data
    
    def get_or_create_user(self, user_id: int, username: str = None, first_name: str = None) -> Dict:
        user = self.get_user(user_id)
        if not user:
            user = self.create_user(user_id, username, first_name)
        return user
    
    def update_user(self, user_id: int, updates: Dict) -> bool:
        try:
            if user_id in self.users:
                self.users[user_id].update(updates)
                return True
            return False
        except:
            return False
    
    def update_balance(self, user_id: int, amount: int, operation: str = "add") -> bool:
        user = self.get_user(user_id)
        if not user:
            return False
        
        if operation == "add":
            user["balance"] += amount
        elif operation == "subtract":
            if user["balance"] < amount:
                return False
            user["balance"] -= amount
        else:
            return False
        
        return True

# إنشاء قاعدة البيانات
db = SimpleDatabase()

# =============================================
# دوال المساعدة
# =============================================
def reshape_arabic(text: str) -> str:
    """إعادة تشكيل النص العربي"""
    try:
        reshaped_text = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped_text)
        return bidi_text
    except:
        return text

async def ask_gemini(question: str) -> str:
    """سؤال الذكاء الاصطناعي"""
    if not GEMINI_AVAILABLE:
        return "عذراً، خدمة الذكاء الاصطناعي غير متاحة حالياً."
    
    try:
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        أنت مساعد تعليمي متخصص في المنهج العراقي.
        أجب على السؤال التالي بإجابة علمية دقيقة ومنظمة:
        
        السؤال: {question}
        
        متطلبات الإجابة:
        1. الدقة العلمية
        2. الوضوح والبساطة
        3. التنسيق الجيد
        4. الالتزام بالمنهج العراقي
        """
        
        response = await asyncio.to_thread(model.generate_content, prompt)
        return response.text
    except Exception as e:
        logger.error(f"خطأ في الذكاء الاصطناعي: {e}")
        return "عذراً، حدث خطأ في المعالجة."

# =============================================
# دوال البوت الرئيسية
# =============================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء البوت"""
    user = update.effective_user
    
    # الحصول على بيانات المستخدم
    user_data = db.get_or_create_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name
    )
    
    # تحديث النشاط
    db.update_user(user.id, {"last_active": datetime.now()})
    
    # التحقق من الحظر
    if user_data.get("banned", False):
        await update.message.reply_text(
            f"⛔ حسابك محظور\nالسبب: {user_data.get('ban_reason', 'غير محدد')}\nتواصل مع @{DEVELOPER_USERNAME}"
        )
        return
    
    # التحقق من الصيانة
    if db.settings["maintenance_mode"] and user.id != DEVELOPER_ID:
        await update.message.reply_text("🔧 البوت تحت الصيانة. نعتذر للإزعاج.")
        return
    
    # إنشاء لوحة المفاتيح
    keyboard = [
        [InlineKeyboardButton("🧮 حساب الإعفاء", callback_data="service_exemption"),
         InlineKeyboardButton("📄 تلخيص الملازم", callback_data="service_summary")],
        [InlineKeyboardButton("❓ سؤال وجواب", callback_data="service_qa"),
         InlineKeyboardButton("📚 ملازمي ومرشحاتي", callback_data="service_files")],
        [InlineKeyboardButton("💰 رصيدي", callback_data="my_balance"),
         InlineKeyboardButton("📊 إحصائياتي", callback_data="my_stats"),
         InlineKeyboardButton("🔗 دعوة أصدقاء", callback_data="invite_friends")],
        [InlineKeyboardButton("💳 شحن الرصيد", callback_data="charge_balance"),
         InlineKeyboardButton("📜 سجل المعاملات", callback_data="transaction_history")],
        [InlineKeyboardButton("📢 قناة البوت", url=f"https://t.me/{BOT_USERNAME}"),
         InlineKeyboardButton("👨‍💻 الدعم الفني", url=f"https://t.me/{DEVELOPER_USERNAME}")]
    ]
    
    # ⭐ زر لوحة التحكم فقط للمطور ⭐
    if user.id == DEVELOPER_ID:
        keyboard.append([InlineKeyboardButton("👑 لوحة التحكم", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""
🎊 *مرحباً {user.first_name}!*

🏦 *رصيدك الحالي:* {user_data['balance']:,} دينار
🎁 *المكافأة الترحيبية:* {db.settings['welcome_bonus']:,} دينار

📚 *الخدمات المتاحة:*
🧮 حساب درجة الإعفاء الفردي
📄 تلخيص الملازم بالذكاء الاصطناعي  
❓ سؤال وجواب بالذكاء الاصطناعي
📚 ملازمي ومرشحاتي

💰 *سعر الخدمة:* {db.settings['service_price']:,} دينار

📲 *للشحن:* تواصل مع @{DEVELOPER_USERNAME}
🎯 *مكافأة الدعوة:* {db.settings['invite_bonus']:,} دينار لكل صديق

اختر الخدمة التي تريدها: 👇
    """
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_service_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار الخدمة"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
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
            await query.edit_message_text("❌ ليس لديك صلاحية!")
            return
        
        await handler(update, context)
    else:
        await query.edit_message_text("⚠️ الخدمة غير متاحة")

async def process_exemption_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خدمة حساب الإعفاء"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = db.get_user(user_id)
    
    # التحقق من الرصيد
    if user["balance"] < db.settings["service_price"]:
        await query.edit_message_text(
            f"❌ رصيدك غير كافي\nالسعر: {db.settings['service_price']:,} دينار\nرصيدك: {user['balance']:,} دينار"
        )
        return
    
    # خصم الرصيد
    if db.update_balance(user_id, db.settings["service_price"], "subtract"):
        # تحديث الإحصائيات
        db.update_user(user_id, {
            "total_services": user.get("total_services", 0) + 1,
            "total_spent": user.get("total_spent", 0) + db.settings["service_price"]
        })
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ تم خصم {db.settings['service_price']:,} دينار\n\n"
            "🧮 *حاسبة درجة الإعفاء*\n\n"
            "أدخل درجات الكورسات الثلاثة:\nمثال: `90 85 95`",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # حفظ حالة الانتظار
        context.user_data["awaiting_scores"] = True
    else:
        await query.edit_message_text("❌ خطأ في الخصم")

async def handle_scores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة درجات الإعفاء"""
    if not context.user_data.get("awaiting_scores"):
        return
    
    text = update.message.text.strip()
    
    try:
        # استخراج الأرقام
        numbers = re.findall(r'\d+\.?\d*', text)
        
        if len(numbers) < 3:
            await update.message.reply_text("❌ أدخل 3 درجات على الأقل\nمثال: 90 85 95")
            return
        
        scores = list(map(float, numbers[:3]))
        average = sum(scores) / 3
        
        if average >= 90:
            result = "🎉 *مبروك! أنت معفي من المادة*"
        else:
            result = f"❌ *لسيت معفي* (المطلوب 90)"
        
        # عرض النتيجة
        result_text = f"""
📊 *نتيجة حساب الإعفاء*

الدرجات:
1. {scores[0]:.1f}
2. {scores[1]:.1f}
3. {scores[2]:.1f}

🧮 المعدل: {average:.2f}

{result}
        """
        
        keyboard = [[InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            result_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # مسح حالة الانتظار
        context.user_data.pop("awaiting_scores", None)
        
    except Exception as e:
        await update.message.reply_text("❌ حدث خطأ في الحساب")

async def process_qa_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خدمة سؤال وجواب"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = db.get_user(user_id)
    
    if user["balance"] < db.settings["service_price"]:
        await query.edit_message_text(
            f"❌ رصيدك غير كافي\nالسعر: {db.settings['service_price']:,} دينار"
        )
        return
    
    if db.update_balance(user_id, db.settings["service_price"], "subtract"):
        db.update_user(user_id, {
            "total_services": user.get("total_services", 0) + 1,
            "total_spent": user.get("total_spent", 0) + db.settings["service_price"]
        })
        
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ تم خصم {db.settings['service_price']:,} دينار\n\n"
            "❓ *سؤال وجواب*\n\n"
            "أرسل سؤالك الآن وسأجيبك بإجابة علمية:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        context.user_data["awaiting_question"] = True
    else:
        await query.edit_message_text("❌ خطأ في الخصم")

async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأسئلة"""
    if not context.user_data.get("awaiting_question"):
        return
    
    question = update.message.text
    
    await update.message.reply_text("🤔 جاري البحث عن الإجابة...")
    
    answer = await ask_gemini(question)
    
    keyboard = [[InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"💡 *الإجابة:*\n\n{answer[:3000]}",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    context.user_data.pop("awaiting_question", None)

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الرصيد"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = db.get_user(user_id)
    
    balance_text = f"""
💰 *رصيدك الحالي*

🏦 الرصيد: {user['balance']:,} دينار
💸 إجمالي المشتريات: {user.get('total_spent', 0):,} دينار
📊 عدد الخدمات: {user.get('total_services', 0)}

💰 سعر الخدمة: {db.settings['service_price']:,} دينار
🎁 مكافأة الدعوة: {db.settings['invite_bonus']:,} دينار

💳 للشحن: تواصل مع @{DEVELOPER_USERNAME}
    """
    
    keyboard = [
        [InlineKeyboardButton("💳 شحن الرصيد", callback_data="charge_balance"),
         InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        balance_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لوحة التحكم للمطور"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id != DEVELOPER_ID:
        await query.edit_message_text("❌ ليس لديك صلاحية!")
        return
    
    admin_text = f"""
👑 *لوحة تحكم المطور*

📊 الإحصائيات:
👥 المستخدمين: {len(db.users):,}

⚙️ الإعدادات:
💰 سعر الخدمة: {db.settings['service_price']:,} دينار
🎁 مكافأة ترحيبية: {db.settings['welcome_bonus']:,} دينار
🎯 مكافأة الدعوة: {db.settings['invite_bonus']:,} دينار
🔧 الصيانة: {'✅ مفعل' if db.settings['maintenance_mode'] else '❌ معطل'}
    """
    
    keyboard = [
        [InlineKeyboardButton("💰 شحن رصيد", callback_data="admin_charge"),
         InlineKeyboardButton("⛔ حظر مستخدم", callback_data="admin_ban")],
        [InlineKeyboardButton("💰 تعديل الأسعار", callback_data="admin_prices"),
         InlineKeyboardButton("🔧 تبديل الصيانة", callback_data="admin_toggle_maintenance")],
        [InlineKeyboardButton("📢 إشعار للجميع", callback_data="admin_broadcast"),
         InlineKeyboardButton("👥 المستخدمين", callback_data="admin_users")],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        admin_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_charge_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شحن رصيد مستخدم"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id != DEVELOPER_ID:
        await query.edit_message_text("❌ ليس لديك صلاحية!")
        return
    
    await query.edit_message_text(
        "💰 *شحن رصيد*\n\n"
        "أرسل معرف المستخدم والمبلغ:\nمثال: `123456 5000`",
        parse_mode=ParseMode.MARKDOWN
    )
    
    context.user_data["admin_action"] = "charge"

async def handle_admin_charge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة شحن الرصيد"""
    if context.user_data.get("admin_action") != "charge":
        return
    
    text = update.message.text.strip()
    
    try:
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("❌ استخدم الصيغة: `user_id amount`")
            return
        
        target_id = int(parts[0])
        amount = int(parts[1])
        
        if amount <= 0:
            await update.message.reply_text("❌ المبلغ يجب أن يكون أكبر من الصفر")
            return
        
        user = db.get_user(target_id)
        if not user:
            await update.message.reply_text("❌ المستخدم غير موجود")
            return
        
        if db.update_balance(target_id, amount, "add"):
            # إشعار للمستخدم
            new_balance = db.get_user(target_id)["balance"]
            notification = f"""
🎉 *تم شحن رصيدك*

✅ المبلغ: {amount:,} دينار
🏦 الرصيد الجديد: {new_balance:,} دينار
📅 التاريخ: {datetime.now().strftime('%Y/%m/%d %H:%M')}

شكراً لاستخدامك بوت "يلا نتعلم"
            """
            
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=notification,
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
            
            await update.message.reply_text(
                f"✅ تم شحن {amount:,} دينار للمستخدم {target_id}"
            )
        else:
            await update.message.reply_text("❌ فشل في الشحن")
        
        context.user_data.pop("admin_action", None)
        
    except ValueError:
        await update.message.reply_text("❌ أدخل أرقام صحيحة")
    except Exception as e:
        await update.message.reply_text("❌ حدث خطأ")
        logger.error(f"خطأ في الشحن: {e}")

async def admin_toggle_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تبديل وضع الصيانة"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != DEVELOPER_ID:
        await query.edit_message_text("❌ ليس لديك صلاحية!")
        return
    
    db.settings["maintenance_mode"] = not db.settings["maintenance_mode"]
    status = "✅ مفعل" if db.settings["maintenance_mode"] else "❌ معطل"
    
    await query.edit_message_text(f"🔧 وضع الصيانة: {status}")

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العودة للرئيسية"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    
    keyboard = [
        [InlineKeyboardButton("🧮 حساب الإعفاء", callback_data="service_exemption"),
         InlineKeyboardButton("📄 تلخيص الملازم", callback_data="service_summary")],
        [InlineKeyboardButton("❓ سؤال وجواب", callback_data="service_qa"),
         InlineKeyboardButton("📚 ملازمي ومرشحاتي", callback_data="service_files")],
        [InlineKeyboardButton("💰 رصيدي", callback_data="my_balance"),
         InlineKeyboardButton("📊 إحصائياتي", callback_data="my_stats")],
        [InlineKeyboardButton("💳 شحن الرصيد", callback_data="charge_balance"),
         InlineKeyboardButton("📜 سجل المعاملات", callback_data="transaction_history")],
        [InlineKeyboardButton("📢 قناة البوت", url=f"https://t.me/{BOT_USERNAME}"),
         InlineKeyboardButton("👨‍💻 الدعم الفني", url=f"https://t.me/{DEVELOPER_USERNAME}")]
    ]
    
    if user.id == DEVELOPER_ID:
        keyboard.append([InlineKeyboardButton("👑 لوحة التحكم", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user_data = db.get_or_create_user(user.id)
    
    welcome_text = f"""
🏠 *القائمة الرئيسية*

مرحباً مرة أخرى {user.first_name}!

🏦 رصيدك: {user_data['balance']:,} دينار
💰 سعر الخدمة: {db.settings['service_price']:,} دينار

اختر الخدمة: 👇
    """
    
    await query.edit_message_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية"""
    text = update.message.text
    
    if text.startswith('/'):
        return
    
    # تحقق إذا كان في حالة انتظار
    if context.user_data.get("awaiting_scores"):
        await handle_scores(update, context)
    elif context.user_data.get("awaiting_question"):
        await handle_question(update, context)
    elif context.user_data.get("admin_action"):
        if context.user_data["admin_action"] == "charge":
            await handle_admin_charge(update, context)
    else:
        # رد عام
        await update.message.reply_text(
            "👋 أهلاً! استخدم الأزرار للتنقل بين الخدمات.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back_to_main")]
            ])
        )

# =============================================
# دوال أخرى (مختصرة للمساحة)
# =============================================
async def process_summary_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تلخيص الملازم"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📄 *تلخيص الملازم*\n\n"
        "هذه الخدمة قيد التطوير حالياً.\n"
        "ستتوفر قريباً بإذن الله.",
        parse_mode=ParseMode.MARKDOWN
    )

async def process_files_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ملازمي ومرشحاتي"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📚 *ملازمي ومرشحاتي*\n\n"
        "هذه الخدمة قيد التطوير حالياً.\n"
        "سيتم إضافة الملفات قريباً.",
        parse_mode=ParseMode.MARKDOWN
    )

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إحصائياتي"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = db.get_user(user_id)
    
    days = (datetime.now() - user["created_at"]).days
    if days == 0:
        days = 1
    
    stats_text = f"""
📊 *إحصائيات حسابك*

👤 المعرف: {user_id}
📅 تاريخ التسجيل: {user['created_at'].strftime('%Y/%m/%d')}
📆 أيام في البوت: {days} يوم

🏦 المالية:
💰 الرصيد: {user['balance']:,} دينار
💸 المشتريات: {user.get('total_spent', 0):,} دينار
🛒 الخدمات: {user.get('total_services', 0)}

📈 النشاط:
المعدل اليومي: {user.get('total_services', 0) / days:.1f} خدمة/يوم
    """
    
    keyboard = [[InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        stats_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def show_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دعوة أصدقاء"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = db.get_user(user_id)
    
    invite_text = f"""
🔗 *دعوة الأصدقاء*

🎁 المكافأة: {db.settings['invite_bonus']:,} دينار لكل صديق
👥 عدد المدعوين: {len(user.get('invited_users', []))}

*رابط الدعوة:*
`https://t.me/{BOT_USERNAME}?start={user['invite_code']}`

شارك الرابط مع أصدقائك واحصل على المكافأة!
    """
    
    keyboard = [[InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        invite_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def show_charge_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خيارات الشحن"""
    query = update.callback_query
    await query.answer()
    
    charge_text = f"""
💳 *شحن الرصيد*

🏦 الحد الأدنى: {db.settings['min_charge']:,} دينار
💰 سعر الخدمة: {db.settings['service_price']:,} دينار

*طريقة الشحن:*
1. تواصل مع @{DEVELOPER_USERNAME}
2. أرسل معرفك: `{query.from_user.id}`
3. أرسل المبلغ المطلوب
4. قم بالتحويل
5. سيتم شحن رصيدك فوراً

*للشحن السريع راسل الدعم مباشرة.*
    """
    
    keyboard = [
        [InlineKeyboardButton("👨‍💻 تواصل مع الدعم", url=f"https://t.me/{DEVELOPER_USERNAME}")],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        charge_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def show_transaction_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """سجل المعاملات"""
    query = update.callback_query
    await query.answer()
    
    history_text = """
📜 *سجل المعاملات*

هذه الخدمة قيد التطوير حالياً.
سيتم إضافتها قريباً بإذن الله.

💡 يمكنك:
- مراجعة رصيدك الحالي
- التواصل مع الدعم للاستفسار
    """
    
    keyboard = [[InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        history_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حظر مستخدم"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != DEVELOPER_ID:
        await query.edit_message_text("❌ ليس لديك صلاحية!")
        return
    
    await query.edit_message_text(
        "⛔ *حظر مستخدم*\n\n"
        "أرسل معرف المستخدم للحظر:\nمثال: `123456`",
        parse_mode=ParseMode.MARKDOWN
    )
    
    context.user_data["admin_action"] = "ban"

async def admin_manage_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إدارة الأسعار"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != DEVELOPER_ID:
        await query.edit_message_text("❌ ليس لديك صلاحية!")
        return
    
    prices_text = f"""
💰 *إدارة الأسعار*

السعر الحالي: {db.settings['service_price']:,} دينار
المكافأة الترحيبية: {db.settings['welcome_bonus']:,} دينار
مكافأة الدعوة: {db.settings['invite_bonus']:,} دينار

لتعديل السعر، أرسل:
`سعر 2000`
    """
    
    await query.edit_message_text(
        prices_text,
        parse_mode=ParseMode.MARKDOWN
    )
    
    context.user_data["admin_action"] = "update_price"

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إشعار للجميع"""
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

async def admin_show_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض المستخدمين"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != DEVELOPER_ID:
        await query.edit_message_text("❌ ليس لديك صلاحية!")
        return
    
    users = list(db.users.values())[:10]  # أول 10 مستخدمين
    total_users = len(db.users)
    
    users_text = f"👥 *آخر 10 مستخدمين*\n\n"
    for user in users:
        name = user.get('first_name', user.get('username', 'غير معروف'))
        balance = user.get('balance', 0)
        users_text += f"• {name} - {balance:,} دينار\n"
    
    users_text += f"\n📊 الإجمالي: {total_users:,} مستخدم"
    
    await query.edit_message_text(users_text, parse_mode=ParseMode.MARKDOWN)

# =============================================
# التشغيل الرئيسي
# =============================================
def main():
    """تشغيل البوت"""
    
    logger.info("🚀 بدء تشغيل بوت 'يلا نتعلم'")
    logger.info(f"👑 المطور: @Allawi04 (ID: {DEVELOPER_ID})")
    
    try:
        # إنشاء التطبيق
        application = Application.builder().token(BOT_TOKEN).build()
        
        # الأوامر
        application.add_handler(CommandHandler('start', start_command))
        
        # معالجات الأزرار
        application.add_handler(CallbackQueryHandler(handle_service_selection))
        application.add_handler(CallbackQueryHandler(back_to_main, pattern="^back_to_main$"))
        application.add_handler(CallbackQueryHandler(admin_toggle_maintenance, pattern="^admin_toggle_maintenance$"))
        application.add_handler(CallbackQueryHandler(admin_manage_prices, pattern="^admin_prices$"))
        application.add_handler(CallbackQueryHandler(admin_broadcast, pattern="^admin_broadcast$"))
        application.add_handler(CallbackQueryHandler(admin_show_users, pattern="^admin_users$"))
        application.add_handler(CallbackQueryHandler(admin_charge_user, pattern="^admin_charge$"))
        application.add_handler(CallbackQueryHandler(admin_ban_user, pattern="^admin_ban$"))
        
        # معالجة الرسائل النصية
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
        
        # بدء البوت
        logger.info("✅ البوت يعمل...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"🚨 خطأ فادح: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
