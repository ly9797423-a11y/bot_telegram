# ssm_bot.py - النسخة المحدثة
import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import sqlite3
import hashlib
import random
import string

# المكتبات المطلوبة للتثبيت عبر pip
try:
    import pdfkit
    from PIL import Image
    import io
    import aiohttp
    from telegram import (
        Update,
        InlineKeyboardButton,
        InlineKeyboardMarkup,
        InputFile,
        BotCommand
    )
    from telegram.ext import (
        Application,
        CommandHandler,
        CallbackQueryHandler,
        MessageHandler,
        filters,
        ContextTypes,
        ConversationHandler
    )
    from telegram.constants import ParseMode
    import google.generativeai as genai
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    import arabic_reshaper
    from bidi.algorithm import get_display
    import qrcode
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER
except ImportError as e:
    print(f"خطأ في استيراد المكتبات: {e}")
    print("يرجى تثبيت المتطلبات باستخدام: pip install -r requirements.txt")
    exit(1)

# ==================== CONFIGURATION ====================
TOKEN = "8481569753:AAH3alhJ0hcHldht-PxV7j8TzBlRsMqAqGI"
GEMINI_API_KEY = "AIzaSyAqlug21bw_eI60ocUtc1Z76NhEUc-zuzY"
ADMIN_ID = 6130994941
SUPPORT_USERNAME = "Allawi04@"
BOT_USERNAME = "@FC4Xbot"
DATABASE_NAME = "ssm_bot.db"

# مسارات الخطوط - سنستخدم خطوط افتراضية
FONT_ARABIC = "DejaVuSans"  # خط افتراضي يدعم العربية
FONT_ENGLISH = "Helvetica"

# أسعار الخدمات (بالدينار العراقي)
SERVICE_PRICES = {
    "exemption": 1000,
    "summarize": 1000,
    "qna": 1000,
    "materials": 1000
}

# ==================== LOGGING ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== DATABASE SETUP ====================
def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # جدول المستخدمين
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        balance INTEGER DEFAULT 0,
        invited_by INTEGER,
        join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_banned INTEGER DEFAULT 0,
        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # جدول العمليات
    cursor.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        type TEXT,
        description TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )''')
    
    # جدول الدعوات
    cursor.execute('''CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inviter_id INTEGER,
        invited_id INTEGER UNIQUE,
        reward_claimed INTEGER DEFAULT 0,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (inviter_id) REFERENCES users(user_id),
        FOREIGN KEY (invited_id) REFERENCES users(user_id)
    )''')
    
    # جدول الملازم
    cursor.execute('''CREATE TABLE IF NOT EXISTS materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        description TEXT,
        file_id TEXT,
        grade TEXT,
        added_by INTEGER,
        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        downloads INTEGER DEFAULT 0,
        FOREIGN KEY (added_by) REFERENCES users(user_id)
    )''')
    
    # جدول الإعدادات
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    
    # جدول استخدام الخدمات
    cursor.execute('''CREATE TABLE IF NOT EXISTS service_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        service_type TEXT,
        cost INTEGER,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )''')
    
    # إعدادات افتراضية
    default_settings = [
        ('welcome_bonus', '1000'),
        ('referral_bonus', '500'),
        ('maintenance', '0'),
        ('bot_channel', ''),
        ('support_username', SUPPORT_USERNAME),
        ('exemption_price', '1000'),
        ('summarize_price', '1000'),
        ('qna_price', '1000'),
        ('materials_price', '1000')
    ]
    
    for key, value in default_settings:
        cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, value))
    
    # فهرس لتحسين الأداء
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_balance ON users(balance)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_referrals_inviter ON referrals(inviter_id)')
    
    conn.commit()
    conn.close()

# ==================== HELPER FUNCTIONS ====================
def get_db_connection():
    return sqlite3.connect(DATABASE_NAME, check_same_thread=False)

def get_user_data(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_user_balance(user_id: int, amount: int, trans_type: str, desc: str = ""):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # تحديث الرصيد
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        
        # تسجيل العملية
        cursor.execute('''INSERT INTO transactions (user_id, amount, type, description)
                          VALUES (?, ?, ?, ?)''', (user_id, amount, trans_type, desc))
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error updating balance: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def check_balance(user_id: int, service_type: str) -> Tuple[bool, int]:
    """التحقق من الرصيد وإرجاع حالة الدفع والسعر"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # الحصول على سعر الخدمة من الإعدادات
    cursor.execute('SELECT value FROM settings WHERE key = ?', (f"{service_type}_price",))
    result = cursor.fetchone()
    price = int(result[0]) if result else SERVICE_PRICES.get(service_type, 1000)
    
    # الحصول على رصيد المستخدم
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    conn.close()
    
    if not user:
        return False, price
    
    balance = user[0]
    return balance >= price, price

def format_arabic(text: str) -> str:
    """تنسيق النص العربي للعرض الصحيح"""
    try:
        reshaped_text = arabic_reshaper.reshape(text)
        return get_display(reshaped_text)
    except:
        return text

def create_referral_link(user_id: int) -> str:
    """إنشاء رابط دعوة فريد"""
    hash_input = f"{user_id}{datetime.now().timestamp()}"
    hash_code = hashlib.md5(hash_input.encode()).hexdigest()[:8]
    return f"https://t.me/{BOT_USERNAME[1:]}?start=ref_{user_id}_{hash_code}"

def log_service_usage(user_id: int, service_type: str, cost: int):
    """تسجيل استخدام الخدمة"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO service_usage (user_id, service_type, cost)
                      VALUES (?, ?, ?)''', (user_id, service_type, cost))
    conn.commit()
    conn.close()

def update_last_active(user_id: int):
    """تحديث وقت النشاط الأخير"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

# ==================== GEMINI AI SETUP ====================
def setup_gemini():
    """تهيئة Gemini AI"""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        return genai.GenerativeModel('gemini-pro')
    except Exception as e:
        logger.error(f"Failed to setup Gemini: {e}")
        return None

async def generate_ai_response(prompt: str) -> str:
    """التفاعل مع Gemini AI"""
    try:
        model = setup_gemini()
        if not model:
            return "عذراً، خدمة الذكاء الاصطناعي غير متاحة حالياً."
        
        response = await asyncio.to_thread(model.generate_content, prompt)
        return response.text
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return "عذراً، حدث خطأ في معالجة طلبك. يرجى المحاولة لاحقاً."

async def process_image_with_ai(image_bytes: bytes, question: str = "") -> str:
    """معالجة الصور مع Gemini Vision"""
    try:
        model = genai.GenerativeModel('gemini-pro-vision')
        image = Image.open(io.BytesIO(image_bytes))
        
        if question:
            prompt = f"أجب عن هذا السؤال بناءً على الصورة: {question}\nباللغة العربية وبأسلوب تعليمي مناسب للمنهج العراقي."
        else:
            prompt = "ما الموجود في هذه الصورة؟ أجب باللغة العربية وبأسلوب تعليمي مناسب."
        
        response = await asyncio.to_thread(model.generate_content, [prompt, image])
        return response.text
    except Exception as e:
        logger.error(f"Vision AI Error: {e}")
        return "عذراً، حدث خطأ في معالجة الصورة."

# ==================== PDF HANDLING ====================
def create_arabic_style():
    """إنشاء نمط للغة العربية في PDF"""
    styles = getSampleStyleSheet()
    
    # إنشاء نمط للعربية
    arabic_style = ParagraphStyle(
        'ArabicStyle',
        parent=styles['Normal'],
        fontName=FONT_ARABIC,
        fontSize=12,
        alignment=TA_RIGHT,
        rightIndent=20,
        leftIndent=20,
        spaceAfter=12,
        wordWrap='CJK'
    )
    
    return arabic_style

def create_summary_pdf(content: str, filename: str = "ملخص.pdf") -> Optional[str]:
    """إنشاء ملف PDF ملخص"""
    try:
        # إنشاء ملف مؤقت
        temp_dir = tempfile.gettempdir()
        pdf_path = os.path.join(temp_dir, filename)
        
        # إنشاء المستند
        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # المحتوى
        story = []
        arabic_style = create_arabic_style()
        
        # عنوان المستند
        title = Paragraph("<b>ملخص المادة الدراسية</b>", arabic_style)
        story.append(title)
        story.append(Spacer(1, 12))
        
        # تاريخ الإنشاء
        date_str = Paragraph(f"<i>تاريخ الإنشاء: {datetime.now().strftime('%Y-%m-%d %H:%M')}</i>", arabic_style)
        story.append(date_str)
        story.append(Spacer(1, 24))
        
        # تقسيم المحتوى إلى فقرات
        paragraphs = content.split('\n\n')
        for para in paragraphs:
            if para.strip():
                # تنسيق النص العربي
                formatted_para = format_arabic(para.strip())
                p = Paragraph(formatted_para, arabic_style)
                story.append(p)
                story.append(Spacer(1, 12))
        
        # تذييل الصفحة
        footer = Paragraph("<i>تم الإنشاء بواسطة بوت 'يلا نتعلم' للطلاب العراقيين</i>", arabic_style)
        story.append(Spacer(1, 24))
        story.append(footer)
        
        # بناء PDF
        doc.build(story)
        return pdf_path
        
    except Exception as e:
        logger.error(f"PDF Creation Error: {e}")
        return None

async def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """استخراج النص من ملف PDF"""
    try:
        # هذه دالة بسيطة - في الإنتاج الحقيقي تحتاج مكتبة مثل PyPDF2
        return "نموذج نص مستخرج من PDF. في النسخة الكاملة سيتم:\n1. استخراج النص الحقيقي من PDF\n2. تنظيف النص وتنسيقه\n3. إعداد الملخص"
    except Exception as e:
        logger.error(f"PDF Extraction Error: {e}")
        return ""

# ==================== TELEGRAM BOT HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء البوت وإضافة المستخدم الجديد"""
    user = update.effective_user
    user_id = user.id
    
    # تحديث النشاط
    update_last_active(user_id)
    
    # التحقق من وضع الصيانة
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE key = "maintenance"')
    maintenance = cursor.fetchone()[0]
    
    if maintenance == '1':
        await update.message.reply_text("⛔ البوت تحت الصيانة حالياً. الرجاء المحاولة لاحقاً.")
        conn.close()
        return
    
    # التحقق إذا كان المستخدم جديداً
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    existing_user = cursor.fetchone()
    
    if not existing_user:
        # منحة الترحيب
        welcome_bonus = int(cursor.execute(
            'SELECT value FROM settings WHERE key = "welcome_bonus"'
        ).fetchone()[0])
        
        # التحقق من رابط الدعوة
        referral_id = None
        if context.args:
            ref_arg = context.args[0]
            if ref_arg.startswith('ref_'):
                try:
                    parts = ref_arg.split('_')
                    if len(parts) >= 2:
                        referral_id = int(parts[1])
                except:
                    pass
        
        # إضافة المستخدم
        cursor.execute('''INSERT INTO users (user_id, username, first_name, last_name, balance)
                          VALUES (?, ?, ?, ?, ?)''',
                       (user_id, user.username, user.first_name, user.last_name, welcome_bonus))
        
        # تسجيل منحة الترحيب
        cursor.execute('''INSERT INTO transactions (user_id, amount, type, description)
                          VALUES (?, ?, ?, ?)''',
                       (user_id, welcome_bonus, 'welcome_bonus', 'منحة ترحيبية'))
        
        # مكافأة الدعوة
        if referral_id:
            referral_bonus = int(cursor.execute(
                'SELECT value FROM settings WHERE key = "referral_bonus"'
            ).fetchone()[0])
            
            # التحقق إذا لم يتم تسجيل الدعوة مسبقاً
            cursor.execute('SELECT * FROM referrals WHERE invited_id = ?', (user_id,))
            if not cursor.fetchone():
                # تسجيل الدعوة
                cursor.execute('''INSERT INTO referrals (inviter_id, invited_id)
                                  VALUES (?, ?)''', (referral_id, user_id))
                
                # منح المكافأة للمدعو
                cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                              (referral_bonus, user_id))
                
                # تسجيل العملية
                cursor.execute('''INSERT INTO transactions (user_id, amount, type, description)
                                  VALUES (?, ?, ?, ?)''',
                              (referral_id, referral_bonus, 'referral_bonus', f'مكافأة دعوة للمستخدم {user_id}'))
        
        conn.commit()
        
        welcome_text = f"""
        🎉 أهلاً وسهلاً {user.first_name}!
        
        ✅ تم إضافتك بنجاح إلى بوت (يلا نتعلم)
        
        🎁 حصلت على منحة ترحيبية: {welcome_bonus} دينار
        
        💰 رصيدك الحالي: {welcome_bonus} دينار
        
        📚 يمكنك الآن استخدام خدمات البوت المميزة:
        
        1. 🧮 حساب درجة الإعفاء الفردي
        2. 📄 تلخيص الملازم بالذكاء الاصطناعي
        3. ❓ أسئلة وأجوبة أي مادة
        4. 📚 ملازمي ومرشحاتي
        
        🔗 لدعوة الأصدقاء والحصول على مكافآت:
        استخدم زر 'دعوة أصدقاء' أدناه
        """
    else:
        welcome_text = f"""
        👋 أهلاً بعودتك {user.first_name}!
        
        📊 رصيدك الحالي: {existing_user[4]} دينار
        
        📚 اختر الخدمة التي تحتاجها من القائمة أدناه:
        """
    
    conn.close()
    
    # عرض القائمة الرئيسية
    await show_main_menu(update, context, welcome_text)

async def show_main_menu(update, context, text=None):
    """عرض القائمة الرئيسية"""
    keyboard = [
        [InlineKeyboardButton("🧮 حساب درجة الإعفاء", callback_data='service_exemption')],
        [InlineKeyboardButton("📄 تلخيص الملازم", callback_data='service_summarize')],
        [InlineKeyboardButton("❓ أسئلة وأجوبة", callback_data='service_qna')],
        [InlineKeyboardButton("📚 ملازمي ومرشحاتي", callback_data='service_materials')],
        [InlineKeyboardButton("💰 رصيدي", callback_data='balance'), 
         InlineKeyboardButton("🔗 دعوة أصدقاء", callback_data='invite')],
        [InlineKeyboardButton("👑 لوحة التحكم", callback_data='admin_panel')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if isinstance(update, Update) and update.message:
        await update.message.reply_text(format_arabic(text or "🏠 القائمة الرئيسية"), 
                                       reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            format_arabic(text or "🏠 القائمة الرئيسية"),
            reply_markup=reply_markup
        )

async def handle_service_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار الخدمة"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    service_type = query.data.replace('service_', '')
    
    # تحديث النشاط
    update_last_active(user_id)
    
    # التحقق من الرصيد
    has_balance, price = check_balance(user_id, service_type)
    
    if not has_balance:
        await query.edit_message_text(
            format_arabic(f"""
            ⚠️ رصيدك غير كافي لهذه الخدمة
            
            💰 السعر: {price} دينار
            💵 رصيدك الحالي: {get_user_data(user_id)[4]} دينار
            
            📞 لشحن الرصيد تواصل مع الدعم:
            {SUPPORT_USERNAME}
            """),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 شحن الرصيد", url=f"https://t.me/{SUPPORT_USERNAME[1:]}")],
                [InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]
            ])
        )
        return
    
    # خصم المبلغ
    if not update_user_balance(user_id, -price, 'service_payment', f'دفع خدمة {service_type}'):
        await query.edit_message_text("❌ حدث خطأ في المعاملة. يرجى المحاولة لاحقاً.")
        return
    
    # تسجيل استخدام الخدمة
    log_service_usage(user_id, service_type, price)
    
    if service_type == 'exemption':
        await handle_exemption_calc(query, context)
    elif service_type == 'summarize':
        await query.edit_message_text(
            format_arabic("""
            📤 أرسل ملف PDF الآن وسأقوم بتلخيصه لك...
            
            ⚠️ الملاحظات:
            • يجب أن يكون الملف بصيغة PDF
            • حجم الملف لا يتعدى 20MB
            • سيكون الملخص باللغة العربية
            """),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]
            ])
        )
        context.user_data['awaiting_pdf'] = True
        context.user_data['service_type'] = 'summarize'
    elif service_type == 'qna':
        await query.edit_message_text(
            format_arabic("""
            ❓ أسئلة وأجوبة أي مادة
            
            📤 أرسل سؤالك الآن أو صورة تحتوي على السؤال...
            
            ⚠️ الملاحظات:
            • يمكنك إرسال سؤال نصي
            • أو إرسال صورة تحتوي على السؤال
            • الإجابات بناءً على المنهج العراقي
            """),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]
            ])
        )
        context.user_data['awaiting_question'] = True
        context.user_data['service_type'] = 'qna'
    elif service_type == 'materials':
        await show_materials(query, context)

async def handle_exemption_calc(query, context):
    """حساب درجة الإعفاء"""
    await query.edit_message_text(
        format_arabic("""
        🧮 حساب درجة الإعفاء الفردي
        
        أدخل درجات الكورسات الثلاثة (بين 0-100)
        
        📝 مثال:
        85 90 95
        
        سيتم حساب المعدل وتحديد إذا كنت معفياً (المعدل ≥ 90)
        
        ⚠️ أدخل الدرجات مفصولة بمسافات:
        """),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]
        ])
    )
    context.user_data['awaiting_grades'] = True

async def process_grades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة درجات الإعفاء"""
    if not context.user_data.get('awaiting_grades'):
        return
    
    try:
        grades_text = update.message.text.strip()
        grades = list(map(float, grades_text.split()))
        
        if len(grades) != 3:
            await update.message.reply_text("⚠️ يرجى إدخال 3 درجات فقط (مثال: 85 90 95)")
            return
        
        invalid_grades = [g for g in grades if g < 0 or g > 100]
        if invalid_grades:
            await update.message.reply_text("⚠️ الدرجات يجب أن تكون بين 0 و 100")
            return
        
        average = sum(grades) / 3
        
        if average >= 90:
            result = f"""
            🎉 مبروك! أنت معفي من المادة
            
            📊 الدرجات المدخلة:
            • الكورس الأول: {grades[0]}
            • الكورس الثاني: {grades[1]}  
            • الكورس الثالث: {grades[2]}
            
            🧮 المعدل: {average:.2f}
            
            ✅ معدلك 90 أو أعلى، أنت معفي بنجاح!
            
            🎊 تهانينا على هذا الإنجاز!
            """
        else:
            result = f"""
            ⚠️ للأسف لست معفياً
            
            📊 الدرجات المدخلة:
            • الكورس الأول: {grades[0]}
            • الكورس الثاني: {grades[1]}
            • الكورس الثالث: {grades[2]}
            
            🧮 المعدل: {average:.2f}
            
            ❌ معدلك أقل من 90، تحتاج إلى تحسين درجاتك.
            
            💡 نصيحة: ركز على المواد التي تحتاج تحسين
            """
        
        await update.message.reply_text(format_arabic(result))
        
        # تنظيف البيانات والعودة للقائمة
        context.user_data.pop('awaiting_grades', None)
        await asyncio.sleep(2)
        await show_main_menu(update, context, "🏠 العودة للقائمة الرئيسية")
        
    except ValueError:
        await update.message.reply_text("⚠️ يرجى إدخال أرقام صحيحة (مثال: 85 90 95)")

async def process_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة ملف PDF للتلخيص"""
    if not context.user_data.get('awaiting_pdf'):
        return
    
    if not update.message.document:
        await update.message.reply_text("⚠️ يرجى إرسال ملف PDF")
        return
    
    document = update.message.document
    
    if not document.file_name.lower().endswith('.pdf'):
        await update.message.reply_text("⚠️ الملف يجب أن يكون بصيغة PDF")
        return
    
    if document.file_size > 20 * 1024 * 1024:  # 20MB
        await update.message.reply_text("⚠️ حجم الملف كبير جداً (الحد الأقصى 20MB)")
        return
    
    # إعلام المستخدم بالمعالجة
    processing_msg = await update.message.reply_text("🔄 جاري معالجة الملف وتلخيصه...")
    
    try:
        # تنزيل الملف
        file = await document.get_file()
        file_bytes = await file.download_as_bytearray()
        
        # استخراج النص من PDF
        extracted_text = await extract_text_from_pdf(file_bytes)
        
        if not extracted_text:
            await update.message.reply_text("❌ لم أستطع قراءة النص من الملف")
            return
        
        # استخدام الذكاء الاصطناعي لتلخيص النص
        summary_prompt = f"""
        قم بتلخيص النص التالي بطريقة علمية ومنظمة مع الحفاظ على المعلومات الأساسية:
        
        {extracted_text[:3000]}  # إرسال جزء من النص فقط
        
        التلخيص يجب أن يكون:
        1. باللغة العربية الفصحى
        2. منظم بنقاط رئيسية
        3. يحوي المعلومات الأساسية فقط
        4. مناسب للطلاب العراقيين
        5. لا يتعدى 500 كلمة
        """
        
        summary = await generate_ai_response(summary_prompt)
        
        # إنشاء ملف PDF جديد
        pdf_path = create_summary_pdf(summary, f"ملخص_{document.file_name}")
        
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as f:
                await update.message.reply_document(
                    document=InputFile(f, filename=f"ملخص_{document.file_name}"),
                    caption=format_arabic("""
                    📄 تم تلخيص ملفك بنجاح!
                    
                    ✅ تم إنشاء ملف PDF جديد يحتوي على:
                    • الملخص المنظم
                    • المعلومات الأساسية
                    • تنسيق عربي صحيح
                    
                    📝 يمكنك الآن مراجعة الملخص بسهولة
                    """)
                )
            os.remove(pdf_path)
        else:
            # إرسال الملخص كنص إذا فشل إنشاء PDF
            await update.message.reply_text(
                format_arabic(f"📝 ملخص الملف:\n\n{summary[:3000]}"),
                parse_mode=ParseMode.MARKDOWN
            )
    
    except Exception as e:
        logger.error(f"PDF Processing Error: {e}")
        await update.message.reply_text("❌ حدث خطأ في معالجة الملف. يرجى المحاولة لاحقاً.")
    
    finally:
        await processing_msg.delete()
        context.user_data.pop('awaiting_pdf', None)
        context.user_data.pop('service_type', None)
        
        # العودة للقائمة بعد 3 ثواني
        await asyncio.sleep(3)
        await show_main_menu(update, context, "🏠 العودة للقائمة الرئيسية")

async def process_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأسئلة بالذكاء الاصطناعي"""
    if not context.user_data.get('awaiting_question'):
        return
    
    processing_msg = await update.message.reply_text("🤔 جاري البحث عن الإجابة المناسبة...")
    
    try:
        question_text = ""
        
        if update.message.photo:
            # معالجة الصورة
            photo = update.message.photo[-1]
            file = await photo.get_file()
            image_bytes = await file.download_as_bytearray()
            
            if update.message.caption:
                question_text = update.message.caption
                answer = await process_image_with_ai(image_bytes, question_text)
            else:
                answer = await process_image_with_ai(image_bytes)
                
        elif update.message.text:
            # معالجة النص
            question_text = update.message.text
            prompt = f"""
            أجب عن هذا السؤال كخبير في المنهج العراقي:
            
            السؤال: {question_text}
            
            المتطلبات:
            1. الإجابة باللغة العربية الفصحى
            2. الإجابة تعليمية ومنهجية
            3. مراعاة مستوى الطالب
            4. إذا كان السؤال رياضياً، اذكر الخطوات
            5. كن دقيقاً ومفيداً
            6. لا تخرج عن نطاق السؤال
            """
            
            answer = await generate_ai_response(prompt)
        
        else:
            await update.message.reply_text("⚠️ يرجى إرسال نص أو صورة تحتوي على السؤال")
            return
        
        # إرسال الإجابة
        response_text = f"""
        🧠 الإجابة:
        
        {answer}
        
        📚 تمت الإجابة بناءً على المنهج العراقي
        💡 إذا كان لديك المزيد من الأسئلة، لا تتردد في السؤال
        """
        
        await update.message.reply_text(format_arabic(response_text))
    
    except Exception as e:
        logger.error(f"QnA Error: {e}")
        await update.message.reply_text("❌ حدث خطأ في معالجة سؤالك. يرجى المحاولة لاحقاً.")
    
    finally:
        await processing_msg.delete()
        context.user_data.pop('awaiting_question', None)
        context.user_data.pop('service_type', None)
        
        # العودة للقائمة بعد 3 ثواني
        await asyncio.sleep(3)
        await show_main_menu(update, context, "🏠 العودة للقائمة الرئيسية")

async def show_materials(query, context):
    """عرض الملازم والمرشحات"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, name, description, grade, downloads 
        FROM materials 
        ORDER BY downloads DESC, added_date DESC 
        LIMIT 20
    ''')
    materials = cursor.fetchall()
    conn.close()
    
    if not materials:
        await query.edit_message_text(
            format_arabic("""
            📭 لا توجد ملازم متاحة حالياً.
            
            📖 سيتم إضافة الملازم قريباً.
            
            📞 يمكنك اقتراح ملازم عبر التواصل مع الدعم.
            """),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]
            ])
        )
        return
    
    keyboard = []
    for mat_id, name, desc, grade, downloads in materials:
        btn_text = f"{name[:20]}... ({grade}) 📥 {downloads}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f'mat_{mat_id}')])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')])
    
    await query.edit_message_text(
        format_arabic("📚 الملازم والمرشحات المتاحة:\n\nاختر من القائمة:"),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def send_material(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال ملف الملزمة"""
    query = update.callback_query
    await query.answer()
    
    mat_id = int(query.data.replace('mat_', ''))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT name, file_id FROM materials WHERE id = ?', (mat_id,))
    material = cursor.fetchone()
    
    if material:
        # تحديث عدد التنزيلات
        cursor.execute('UPDATE materials SET downloads = downloads + 1 WHERE id = ?', (mat_id,))
        conn.commit()
        
        await query.message.reply_document(
            document=material[1],
            caption=format_arabic(f"📚 {material[0]}\n\n✅ تم التحميل بنجاح")
        )
    else:
        await query.message.reply_text("❌ الملف غير متوفر")
    
    conn.close()

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض رصيد المستخدم"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = get_user_data(user_id)
    
    if not user:
        await query.edit_message_text("❌ لم يتم العثور على بياناتك")
        return
    
    # الحصول على أسعار الخدمات
    conn = get_db_connection()
    cursor = conn.cursor()
    
    prices = {}
    for service in ['exemption', 'summarize', 'qna', 'materials']:
        cursor.execute('SELECT value FROM settings WHERE key = ?', (f"{service}_price",))
        result = cursor.fetchone()
        prices[service] = int(result[0]) if result else 1000
    
    conn.close()
    
    balance_text = f"""
    💰 معلومات رصيدك:
    
    👤 الاسم: {user[2] or 'غير معروف'}
    ⚖️ الرصيد الحالي: {user[4]} دينار
    📅 تاريخ الانضمام: {user[6][:10]}
    
    💸 أسعار الخدمات:
    • 🧮 حساب الإعفاء: {prices['exemption']} دينار
    • 📄 تلخيص PDF: {prices['summarize']} دينار
    • ❓ أسئلة وأجوبة: {prices['qna']} دينار
    • 📚 الملازم: {prices['materials']} دينار
    
    📈 لشحن الرصيد:
    1. تواصل مع الدعم: {SUPPORT_USERNAME}
    2. أو ادعو أصدقاء للحصول على مكافآت
    """
    
    await query.edit_message_text(
        format_arabic(balance_text),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 دعوة أصدقاء", callback_data='invite'),
             InlineKeyboardButton("💳 شحن رصيد", url=f"https://t.me/{SUPPORT_USERNAME[1:]}")],
            [InlineKeyboardButton("📊 سجل المعاملات", callback_data='transactions')],
            [InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]
        ])
    )

async def show_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض معلومات الدعوة"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    referral_link = create_referral_link(user_id)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # عدد المدعوين
    cursor.execute('SELECT COUNT(*) FROM referrals WHERE inviter_id = ?', (user_id,))
    invite_count = cursor.fetchone()[0]
    
    # المكافأة
    referral_bonus = int(cursor.execute(
        'SELECT value FROM settings WHERE key = "referral_bonus"'
    ).fetchone()[0])
    
    # إجمالي المكافآت المكتسبة
    cursor.execute('''
        SELECT COALESCE(SUM(amount), 0) 
        FROM transactions 
        WHERE user_id = ? AND type = 'referral_bonus'
    ''', (user_id,))
    total_earned = cursor.fetchone()[0]
    
    conn.close()
    
    invite_text = f"""
    🔗 نظام الدعوة والمكافآت
    
    📊 إحصائيات دعوتك:
    • عدد مدعويك: {invite_count} شخص
    • مكافأة لكل دعوة: {referral_bonus} دينار
    • إجمالي أرباحك: {total_earned} دينار
    
    💰 كيف تحصل على المكافأة:
    1. شارك رابط الدعوة مع أصدقائك
    2. عند انضمامهم للبوت عبر الرابط
    3. تحصل على {referral_bonus} دينار تلقائياً
    4. يمكنهم بدورهم دعوة آخرين
    
    📎 رابط دعوتك الخاص:
    {referral_link}
    
    📢 شارك الرابط الآن واكسب المزيد!
    """
    
    share_text = f"انضم إلى بوت 'يلا نتعلم' للطلاب العراقيين! 🤓\n\n{referral_link}"
    
    await query.edit_message_text(
        format_arabic(invite_text),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 مشاركة الرابط", 
             url=f"https://t.me/share/url?url={referral_link}&text={share_text}")],
            [InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]
        ]),
        disable_web_page_preview=True
    )

# ==================== ADMIN PANEL ====================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لوحة تحكم المدير"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.message.reply_text("⛔ ليس لديك صلاحية الوصول لهذه الصفحة.")
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # إحصائيات
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE DATE(join_date) = DATE("now")')
    today_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(balance) FROM users')
    total_balance = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT value FROM settings WHERE key = "maintenance"')
    maintenance = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM transactions WHERE DATE(date) = DATE("now")')
    today_transactions = cursor.fetchone()[0]
    
    conn.close()
    
    admin_text = f"""
    👑 لوحة تحكم المدير
    
    📊 الإحصائيات العامة:
    • إجمالي المستخدمين: {total_users}
    • المستخدمين الجدد اليوم: {today_users}
    • إجمالي الأرصدة: {total_balance} دينار
    • المعاملات اليوم: {today_transactions}
    • وضع الصيانة: {'✅ مفعل' if maintenance == '1' else '❌ غير مفعل'}
    
    ⚙️ اختر الإجراء المناسب:
    """
    
    keyboard = [
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data='admin_users')],
        [InlineKeyboardButton("💰 شحن رصيد مستخدم", callback_data='admin_charge')],
        [InlineKeyboardButton("⛔ حظر/فك حظر", callback_data='admin_ban')],
        [InlineKeyboardButton("⚙️ تغيير الأسعار", callback_data='admin_prices')],
        [InlineKeyboardButton("🛠️ وضع الصيانة", callback_data='admin_maintenance')],
        [InlineKeyboardButton("📈 إحصائيات متقدمة", callback_data='admin_stats')],
        [InlineKeyboardButton("📚 إدارة الملازم", callback_data='admin_materials')],
        [InlineKeyboardButton("🎁 تعديل المكافآت", callback_data='admin_rewards')],
        [InlineKeyboardButton("📊 عرض المستخدمين", callback_data='admin_view_users')],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data='main_menu')]
    ]
    
    await query.edit_message_text(
        format_arabic(admin_text),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_charge_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شحن رصيد مستخدم"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        return
    
    await query.edit_message_text(
        format_arabic("💰 شحن رصيد مستخدم\n\nأرسل أيدي المستخدم:"),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع للوحة", callback_data='admin_panel')]
        ])
    )
    
    context.user_data['admin_action'] = 'charge'
    return 'AWAITING_CHARGE_USER_ID'

async def handle_admin_charge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة شحن رصيد المستخدم"""
    if update.message.from_user.id != ADMIN_ID:
        return
    
    if 'admin_action' not in context.user_data:
        return
    
    if context.user_data['admin_action'] == 'charge':
        try:
            user_id = int(update.message.text)
            context.user_data['charge_user_id'] = user_id
            context.user_data['admin_action'] = 'charge_amount'
            
            await update.message.reply_text("أرسل المبلغ بالدينار العراقي:")
            return 'AWAITING_CHARGE_AMOUNT'
        except ValueError:
            await update.message.reply_text("⚠️ أيدي المستخدم يجب أن يكون رقماً صحيحاً")
            return 'AWAITING_CHARGE_USER_ID'
    
    elif context.user_data['admin_action'] == 'charge_amount':
        try:
            amount = int(update.message.text)
            user_id = context.user_data['charge_user_id']
            
            # التحقق من وجود المستخدم
            user = get_user_data(user_id)
            if not user:
                await update.message.reply_text("❌ المستخدم غير موجود")
            else:
                # تحديث الرصيد
                if update_user_balance(user_id, amount, 'admin_charge', 
                                    f'شحن بواسطة المدير {ADMIN_ID}'):
                    
                    # إرسال إشعار للمستخدم
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=format_arabic(f"""
                            💰 إشعار شحن رصيد
                            
                            ✅ تم شحن رصيدك بمبلغ: {amount} دينار
                            
                            ⚖️ رصيدك الجديد: {user[4] + amount} دينار
                            
                            📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}
                            
                            📞 للاستفسار: {SUPPORT_USERNAME}
                            """)
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify user: {e}")
                    
                    await update.message.reply_text(f"✅ تم شحن {amount} دينار للمستخدم {user_id}")
                else:
                    await update.message.reply_text("❌ فشلت عملية الشحن")
            
            # تنظيف البيانات
            context.user_data.pop('admin_action', None)
            context.user_data.pop('charge_user_id', None)
            
            # العودة للوحة التحكم
            await asyncio.sleep(2)
            await admin_panel(update, context)
            
        except ValueError:
            await update.message.reply_text("⚠️ المبلغ يجب أن يكون رقماً صحيحاً")
            return 'AWAITING_CHARGE_AMOUNT'

async def admin_change_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تغيير أسعار الخدمات"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    prices_text = "💰 أسعار الخدمات الحالية:\n\n"
    for service_key, service_name in [
        ('exemption_price', 'حساب الإعفاء'),
        ('summarize_price', 'تلخيص PDF'),
        ('qna_price', 'أسئلة وأجوبة'),
        ('materials_price', 'الملازم')
    ]:
        cursor.execute('SELECT value FROM settings WHERE key = ?', (service_key,))
        price = cursor.fetchone()[0]
        prices_text += f"• {service_name}: {price} دينار\n"
    
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("تغيير سعر حساب الإعفاء", callback_data='change_price_exemption')],
        [InlineKeyboardButton("تغيير سعر تلخيص PDF", callback_data='change_price_summarize')],
        [InlineKeyboardButton("تغيير سعر الأسئلة والأجوبة", callback_data='change_price_qna')],
        [InlineKeyboardButton("تغيير سعر الملازم", callback_data='change_price_materials')],
        [InlineKeyboardButton("🔙 رجوع للوحة", callback_data='admin_panel')]
    ]
    
    await query.edit_message_text(
        format_arabic(prices_text),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def change_service_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تغيير سعر خدمة معينة"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        return
    
    service = query.data.replace('change_price_', '')
    
    service_names = {
        'exemption': 'حساب الإعفاء الفردي',
        'summarize': 'تلخيص الملازم',
        'qna': 'أسئلة وأجوبة',
        'materials': 'ملازمي ومرشحاتي'
    }
    
    context.user_data['changing_price'] = service
    
    await query.edit_message_text(
        format_arabic(f"✏️ تغيير سعر خدمة {service_names.get(service, service)}\n\nأرسل السعر الجديد بالدينار:"),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data='admin_prices')]
        ])
    )
    
    return 'AWAITING_NEW_PRICE'

async def save_new_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حفظ السعر الجديد"""
    if update.message.from_user.id != ADMIN_ID:
        return
    
    try:
        new_price = int(update.message.text)
        service = context.user_data.get('changing_price')
        
        if new_price <= 0:
            await update.message.reply_text("⚠️ السعر يجب أن يكون أكبر من صفر")
            return 'AWAITING_NEW_PRICE'
        
        if service:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE settings SET value = ? WHERE key = ?', (str(new_price), f"{service}_price"))
            conn.commit()
            conn.close()
            
            # تحديث السعر في الذاكرة
            SERVICE_PRICES[service] = new_price
            
            service_names = {
                'exemption': 'حساب الإعفاء الفردي',
                'summarize': 'تلخيص الملازم',
                'qna': 'أسئلة وأجوبة',
                'materials': 'ملازمي ومرشحاتي'
            }
            
            await update.message.reply_text(f"✅ تم تغيير سعر {service_names.get(service, service)} إلى {new_price} دينار")
            
            # تنظيف البيانات
            context.user_data.pop('changing_price', None)
            
            # العودة للوحة التحكم
            await asyncio.sleep(2)
            await admin_panel(update, context)
            
    except ValueError:
        await update.message.reply_text("⚠️ يرجى إرسال رقم صحيح")
        return 'AWAITING_NEW_PRICE'

async def toggle_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تفعيل/إلغاء وضع الصيانة"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE key = "maintenance"')
    current_status = cursor.fetchone()[0]
    
    new_status = '0' if current_status == '1' else '1'
    cursor.execute('UPDATE settings SET value = ? WHERE key = "maintenance"', (new_status,))
    conn.commit()
    conn.close()
    
    status_text = "✅ تم تفعيل وضع الصيانة" if new_status == '1' else "❌ تم إلغاء وضع الصيانة"
    
    await query.edit_message_text(
        format_arabic(status_text),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع للوحة", callback_data='admin_panel')]
        ])
    )

async def admin_view_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة المستخدمين"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, username, first_name, balance, join_date 
        FROM users 
        ORDER BY join_date DESC 
        LIMIT 100
    ''')
    users = cursor.fetchall()
    conn.close()
    
    if not users:
        await query.edit_message_text("📭 لا يوجد مستخدمين حتى الآن.")
        return
    
    # تجميع النص
    users_text = "👥 آخر 100 مستخدم:\n\n"
    for user_id, username, first_name, balance, join_date in users:
        users_text += f"🆔 {user_id} | 👤 {first_name or 'غير معروف'} | @{username or 'N/A'} | 💰 {balance} | 📅 {join_date[:10]}\n"
    
    # إرسال النص (قد يحتاج إلى تقسيم إذا كان طويلاً)
    if len(users_text) > 4000:
        chunks = [users_text[i:i+4000] for i in range(0, len(users_text), 4000)]
        for i, chunk in enumerate(chunks):
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=chunk,
                disable_web_page_preview=True
            )
    else:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=users_text,
            disable_web_page_preview=True
        )
    
    await query.edit_message_text(
        "✅ تم إرسال قائمة المستخدمين إليك في الرسائل الخاصة.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع للوحة", callback_data='admin_panel')]
        ])
    )

async def cancel_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء إجراء المدير"""
    await update.message.reply_text("❌ تم إلغاء الإجراء.")
    context.user_data.clear()
    return ConversationHandler.END

# ==================== MAIN FUNCTION ====================
def main():
    """تشغيل البوت"""
    # تهيئة قاعدة البيانات
    init_db()
    
    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()
    
    # إضافة handlers الأساسية
    application.add_handler(CommandHandler("start", start))
    
    # معالجة الاختيارات من Inline Keyboard
    application.add_handler(CallbackQueryHandler(handle_service_selection, pattern='^service_'))
    application.add_handler(CallbackQueryHandler(show_balance, pattern='^balance$'))
    application.add_handler(CallbackQueryHandler(show_invite, pattern='^invite$'))
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin_panel$'))
    application.add_handler(CallbackQueryHandler(send_material, pattern='^mat_'))
    application.add_handler(CallbackQueryHandler(show_main_menu, pattern='^main_menu$'))
    
    # معالجة إجراءات المدير
    admin_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_charge_user, pattern='^admin_charge$'),
            CallbackQueryHandler(change_service_price, pattern='^change_price_')
        ],
        states={
            'AWAITING_CHARGE_USER_ID': [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_charge)
            ],
            'AWAITING_CHARGE_AMOUNT': [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_charge)
            ],
            'AWAITING_NEW_PRICE': [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_price)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_admin_action)]
    )
    application.add_handler(admin_conv_handler)
    
    # معالجات أخرى للمدير
    application.add_handler(CallbackQueryHandler(admin_change_prices, pattern='^admin_prices$'))
    application.add_handler(CallbackQueryHandler(toggle_maintenance, pattern='^admin_maintenance$'))
    application.add_handler(CallbackQueryHandler(admin_view_users, pattern='^admin_view_users$'))
    
    # معالجة الرسائل المختلفة
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_grades))
    application.add_handler(MessageHandler(filters.Document.PDF, process_pdf))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_question))
    application.add_handler(MessageHandler(filters.PHOTO, process_question))
    
    # بدء البوت
    print("🤖 بدء تشغيل بوت 'يلا نتعلم'...")
    print(f"👑 المدير: {ADMIN_ID}")
    print(f"💬 الدعم: {SUPPORT_USERNAME}")
    print("✅ البوت جاهز للعمل!")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    main()
