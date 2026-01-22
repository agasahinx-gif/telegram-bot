import os
import logging
import sys
import traceback
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
    "gerizekalı", "oç", "kahpe", "piç", "mal", "sik", "sikik", "sikmek", "sik kafa", "oe", "amk", "amcik", "amcık", "orospu", "orospu evladı", "orospi", "orospu evladi", "piç", "piç kurusu", "taşak", "xnxx", "xnx", "porno", "taşşak", "çük", "götveren", "göt veren", "göt veren", "got veren", "yarragimin basi", "yarrağımın başı",
    "yarag", "yarak", 
    "idiot", "dumb", "bitch", "fuck", "shit", "asshole", "bastard",
    "dick", "cunt", "motherfucker", "fucker", "damn", "bollocks",
    "ostur", "osdur", "amcıq", "dıllaq", "amk", "orospu", "sik", "sikmek", "sg", "sıçmak", "gay", "trans", "lezbiyen", "qozumaki", "yarram", "yala daşşağımı", "daşşağ", "peyser", "peysər", "Блядь", "отвали", "дерьмо", "Сука", "Заткнись", "хуй", "пизда", "отвали", "Блядь",  "Че за галима такая?", "Мудак", "Пошел на хуй", "Блядь", 
]

block_notice = {
    'az': "🚫 Təəssüf ki, xəbərdarlıq olmağına baxmayaraq, qeyri etik danışığa görə admin tərəfindən bloklandınız. Hər ehtimala qarşı olaraq qeydə alınan səs vəya mesaj tipli yazışmalar gözdən keçiriləcək və sizə lazım olduğu vəziyyətdə xəbərdarlıq ediləcək.",
    'tr': "🚫 Maalesef yapılan uyarı ya rağmen etik olmayan dil nedeniyle admin tarafından engellendiniz. Olası bir duruma karşı, kaydedilen sesli veya yazılı mesajlar incelenecek ve gerekirse size bildirimde bulunulacaktır.",
    'ru': "🚫 К сожалению, несмотря на данное предупреждение  вы были заблокированы админом за неэтичное поведение. На всякий случай, записанные голосовые или текстовые сообщения будут просмотрены, и при необходимости вы будете уведомлены.",
    'en': "🚫 Unfortunately, despite the warning given you have been blocked by the admin due to inappropriate behavior. For any possible reason, recorded voice or text messages will be reviewed, and you will be notified if nessesery."
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
            'az': "🇦🇿 ✅ Dil seçimi tamamlandı. Müraciətinizin səbəbini ətraflı şəkildə qeyd edin. Adminin sizinlə əlaqə saxlaya bilməsi üçün əlaqə nömrəsi qeyd etməyiniz vacibdir!📲 Diqqət‼️ Xidmət səviyyəsinin ölçülməsi məqsədi ilə danışıqlar qeydə alınır.",
            'tr': "🇹🇷 ✅ Dil seçimi tamamlandı. Lütfen başvurunuzun sebebini detaylı şekilde yazın. Adminin sizinle iletişim kura bilmesi için telefon numaranızı yazmanız önemlidir!📲 Dikkat‼️ Hizmet seviyyesinin hesaplanması nedeni ile konuşmalar kayıt altına alınmaktadır.",
            'ru': "🇷🇺 ✅ Язык выбран Пожалуйста. подробно укажите причину запроса. Важно не записывать свой contact номер, чтобы администратор мог с вами связаться!📲 Внимание‼️ Разговоры записываются для целей расчета уровня обслуживания.",
            'en': "🇬🇧 ✅ Language selected. Please provide detailed reason for your request. It is important that you do provide your contact number so that the admin can contact you!📲 Attention‼️ Conversations are recorded for the purpose of calculating the level of service"
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
        'az': "⚠️ Danışığınız etik deyil. Təkrarlanarsa admin tərəfindən botdan uzaqlaşdırılacaqsınız 🚫",
        'tr': "⚠️ Konuşmanız etik değil. Tekrarlanırsa admin tarafından botdan uzaklaştırılacaksınız 🚫",
        'ru': "⚠️ Ваше поведение неэтично. В случае повторения админ удалит вас из бота 🚫",
        'en': "⚠️ Your behavior is inappropriate. If repeated, you will be removed from the bot by admin 🚫"
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
        'az': "✅ Müraciətiniz qeydə alındı. Ən qısa zamanda admin tərəfindən geri dönüş olunacaq",
        'tr': "✅ Başvurunuz alındı. Admin tarafından kısa zaman içerisinde geri dönüş olunacaktır",
        'ru': "✅ Ваш запрос получен. Администратор ответит в ближайшее время.",
        'en': "✅ Your request has been received. The admin will respond shortly."
    }

    await update.message.reply_text(responses.get(lang, responses['az']))


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if is_user_blocked(user_id):
        return

    user = update.message.from_user
    username = f"@{user.username}" if user.username else "Yoxdur"

    await context.bot.forward_message(
        chat_id=OPERATOR_ID,
        from_chat_id=update.message.chat.id,
        message_id=update.message.message_id
    )

    info_message = (
        f"🎙️ Yeni səsli mesaj:\n\n"
        f"👤 Ad Soyad: {user.full_name}\n"
        f"🆔 ID: {user_id}\n"
        f"🔗 Username: {username}"
    )

    await context.bot.send_message(chat_id=OPERATOR_ID, text=info_message)

    lang = get_user_language(user_id)
    responses = {
        'az': "✅ Səsli mesajınız qeydə alındı. Ən qısa zamanda admin tərəfindən geri dönüş olunacaq",
        'tr': "✅ Sesli mesajınız alındı. Admin tarafından kısa zaman içerisinde geri dönüş olunacaktır",
        'ru': "✅ Голосовое сообщение получено. Администратор ответит в ближайшее время",
        'en': "✅ Voice message received. The admin will respond shortly"
    }

    await update.message.reply_text(responses.get(lang, responses['az']))


async def cavab(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OPERATOR_ID:
        return

    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("❗️ İstifadə edin: /cavab <id> <mesaj>")
            return

        target_id = int(args[0])
        reply_text = ' '.join(args[1:])

        admin_answers = {
            'az': "👤 Adminin cavabı:\n\n",
            'tr': "👤 Adminin cevabı:\n\n",
            'ru': "👤 Ответ администратора:\n\n",
            'en': "👤 Admin's answer:\n\n"
        }

        lang = get_user_language(target_id)
        prefix = admin_answers.get(lang, admin_answers['az'])

        await context.bot.send_message(chat_id=target_id, text=prefix + reply_text)
        await update.message.reply_text("✅ Cavab göndərildi.")

    except Exception as e:
        await update.message.reply_text(f"❌ Xəta: {e}")


async def blok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OPERATOR_ID:
        return

    try:
        target_id = int(context.args[0])
        set_user_blocked(target_id, True)

        lang = get_user_language(target_id)
        await context.bot.send_message(chat_id=target_id, text=block_notice.get(lang, block_notice['az']))

        await update.message.reply_text("🚫 İstifadəçi bloklandı.")
    except:
        await update.message.reply_text("❗️ İstifadə edin: /blok <id>")


async def blokuac(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OPERATOR_ID:
        return

    try:
        target_id = int(context.args[0])
        set_user_blocked(target_id, False)
        await update.message.reply_text("✅ Blok açıldı.")
    except:
        await update.message.reply_text("❗️ İstifadə edin: /blokuac <id>")


def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.error(msg="Exception while handling an update:", exc_info=context.error)

    if context.error and "Conflict: terminated by other getUpdates request" in str(context.error):
        logging.warning("Duplicate instance detected. This is expected during some restarts.")
        return

    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    message = f"❌ Xəta:\n<pre>{tb_string}</pre>"

    if context and context.bot:
        import asyncio
        async def send_error():
            try:
                await context.bot.send_message(chat_id=OPERATOR_ID, text=message, parse_mode='HTML')
            except:
                pass
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(send_error())
            else:
                asyncio.run(send_error())
        except:
            pass


if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(CommandHandler('cavab', cavab))
    app.add_handler(CommandHandler('blok', blok))
    app.add_handler(CommandHandler('blokuac', blokuac))

    app.add_error_handler(error_handler)

    print("✅ Operator bot başladı... CTRL+C ilə dayandırın.")
    app.run_polling()
  
