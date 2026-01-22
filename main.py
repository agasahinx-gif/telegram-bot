import os
import logging
import threading
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from flask import Flask

# --- CONFIG ---
BOT_TOKEN = os.environ.get("TOKEN")
OPERATOR_ID = int(os.environ.get("OPERATOR_ID", 7670252496))
DATABASE_URL = os.environ.get("DATABASE_URL")

# --- DATABASE SETUP ---
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            language TEXT,
            is_blocked BOOLEAN DEFAULT FALSE
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

def set_user_language(user_id, lang):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO users (user_id, language) VALUES (%s, %s)
        ON CONFLICT (user_id) DO UPDATE SET language = %s
    ''', (user_id, lang, lang))
    conn.commit()
    cur.close()
    conn.close()

def get_user_language(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT language FROM users WHERE user_id = %s', (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else 'az'

def set_user_blocked(user_id, blocked):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO users (user_id, is_blocked) VALUES (%s, %s)
        ON CONFLICT (user_id) DO UPDATE SET is_blocked = %s
    ''', (user_id, blocked, blocked))
    conn.commit()
    cur.close()
    conn.close()

def is_user_blocked(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT is_blocked FROM users WHERE user_id = %s', (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else False

init_db()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Yasaklı sözlər
forbidden_words = [
    "salak", "yarrak", "yarak", "pipi", "göt", "orospu", "amcik",
    "bicbala", "sikdir", "sikiş", "sikişmək", "qehbe", "gijdillax", "peysər", "dillaq", "qozumaki",
    "gerizekalı", "oç", "kahpe", "piç", "mal", "sik", "sikik", "sikmek",
    "idiot", "dumb", "bitch", "fuck", "shit", "asshole", "bastard",
    "dick", "cunt", "motherfucker", "fucker", "damn", "bollocks"
]

block_notice = {
    'az': "🚫 Təəssüf ki, qeyri etik danışığa görə admin tərəfindən bloklandınız.",
    'tr': "🚫 Maalesef etik olmayan dil nedeniyle admin tarafından engellendiniz.",
    'ru': "🚫 К сожалению, вы были заблокированы админом за неэтичное поведение.",
    'en': "🚫 Unfortunately, you have been blocked by the admin due to inappropriate behavior."
}

# --- Flask server ---
app_server = Flask(__name__)

@app_server.route('/')
def home():
    return "Bot is running!"

def run():
    app_server.run(host='0.0.0.0', port=5000, use_reloader=False)

def keep_alive():
    t = threading.Thread(target=run)
    t.daemon = True
    t.start()

# --- Telegram Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    lang = get_user_language(user_id)
    
    keyboard = [
        [
            InlineKeyboardButton("🇦🇿 Azərbaycanca", callback_data='lang_az'),
            InlineKeyboardButton("🇹🇷 Türkçe", callback_data='lang_tr'),
        ],
        [
            InlineKeyboardButton("🇷🇺 Русский", callback_data='lang_ru'),
            InlineKeyboardButton("🇬🇧 English", callback_data='lang_en'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    start_messages = {
        'az': "Merhaba! 👋\nLütfen konuşmak istediğiniz dili seçin:\n\nHi! 👋\nPlease select your language:",
        'tr': "Merhaba! 👋\nLütfen konuşmak istediğiniz dili seçin:\n\nHi! 👋\nPlease select your language:",
        'ru': "Merhaba! 👋\nLütfen konuşmak istediğiniz dili seçin:\n\nHi! 👋\nPlease select your language:",
        'en': "Merhaba! 👋\nLütfen konuşmak istediğiniz dili seçin:\n\nHi! 👋\nPlease select your language:"
    }
    
    await update.message.reply_text(
        start_messages.get(lang, start_messages['az']),
        reply_markup=reply_markup
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data.startswith("lang_"):
        selected_lang = query.data.split('_')[1]
        set_user_language(user_id, selected_lang)

        messages = {
            'az': "🇦🇿 ✅ Dil seçimi tamamlandı. Müraciətinizin səbəbini ətraflı şəkildə qeyd edin.",
            'tr': "🇹🇷 ✅ Dil seçimi tamamlandı. Lütfen başvurunuzun sebebini detaylı şekilde yazın.",
            'ru': "🇷🇺 ✅ Язык выбран. Пожалуйста, подробно укажите причину запроса.",
            'en': "🇬🇧 ✅ Language selected. Please provide detailed reason for your request."
        }

        await query.edit_message_text(messages[selected_lang])

def contains_forbidden_word(text: str) -> bool:
    text = text.lower()
    return any(word in text for word in forbidden_words)

async def send_forbidden_alert(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    user = update.message.from_user
    user_id = user.id
    username = f"@{user.username}" if user.username else "Yoxdur"
    lang = get_user_language(user_id)

    alert_message = (
        f"⚠️ Yasaklı söz istifadə edildi!\n\n"
        f"👤 İstifadəçi: {user.full_name}\n"
        f"🆔 ID: {user_id}\n"
        f"🔗 Username: {username}\n\n"
        f"💬 Mesaj:\n{text}"
    )

    await context.bot.send_message(chat_id=OPERATOR_ID, text=alert_message)

    warnings = {
        'az': "⚠️ Danışığınız etik deyil. Təkrarlanarsa admin tərəfindən bloklanacaqsınız 🚫",
        'tr': "⚠️ Konuşmanız etik değil. Tekrarlanırsa admin tarafından engelleneceksiniz 🚫",
        'ru': "⚠️ Ваше поведение неэтично. В случае повторения вас заблокируют 🚫",
        'en': "⚠️ Your behavior is inappropriate. If repeated, you will be blocked 🚫"
    }

    await update.message.reply_text(warnings.get(lang, warnings['az']))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if is_user_blocked(user_id):
        return

    text = update.message.text
    if text and contains_forbidden_word(text):
        await send_forbidden_alert(update, context, text)
        return

    user = update.message.from_user
    username = f"@{user.username}" if user.username else "Yoxdur"
    lang = get_user_language(user_id)

    operator_message = (
        f"📨 Yeni müraciət:\n\n"
        f"👤 Ad Soyad: {user.full_name}\n"
        f"🆔 ID: {user_id}\n"
        f"🔗 Username: {username}\n\n"
        f"💬 Mesaj:\n{text}"
    )
    await context.bot.send_message(chat_id=OPERATOR_ID, text=operator_message)

    responses = {
        'az': "✅ Müraciətiniz qeydə alındı.",
        'tr': "✅ Başvurunuz alındı.",
        'ru': "✅ Ваш запрос получен.",
        'en': "✅ Your request has been received."
    }
    await update.message.reply_text(responses.get(lang, responses['az']))

# --- Bot start ---
if __name__ == '__main__':
    keep_alive()  # Flask server for 24/7

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("✅ Operator bot başladı... CTRL+C ilə dayandırın.")
    app.run_polling()
