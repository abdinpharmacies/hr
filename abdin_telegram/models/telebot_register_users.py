import telebot
import sqlite3
import re
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = '5589615908:AAGUpFRgyCkladAjXWe-rSiSiNHOblNwyIM'
bot = telebot.TeleBot(BOT_TOKEN)
bot.remove_webhook()
# --- Setup SQLite DB ---
conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    username TEXT,
    language_code TEXT,
    employee_code TEXT
)
''')
conn.commit()


def save_user(user, employee_code=None):
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, first_name, last_name, username, language_code, employee_code)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        user.id,
        user.first_name,
        user.last_name,
        user.username,
        user.language_code,
        employee_code
    ))
    conn.commit()


def update_employee_code(user_id, code):
    cursor.execute("UPDATE users SET employee_code = ? WHERE user_id = ?", (code, user_id))
    conn.commit()


def get_user_ids_by_employee_codes(codes):
    placeholders = ','.join(['?'] * len(codes))
    cursor.execute(f"SELECT user_id FROM users WHERE employee_code IN ({placeholders})", codes)
    return [row[0] for row in cursor.fetchall()]


# --- Register button handler (in group or private) ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    markup = InlineKeyboardMarkup()
    register_btn = InlineKeyboardButton("✅ Register", callback_data="register_me")
    markup.add(register_btn)
    bot.send_message(message.chat.id, "Welcome! Click below to register and enter your employee code.",
                     reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "register_me")
def handle_register_button(call):
    user = call.from_user
    save_user(user)  # Temporarily save without code
    bot.answer_callback_query(call.id, "✅ Please reply with your employee code.")
    bot.send_message(call.message.chat.id, "📋 Please reply to this message with your employee code.")


# --- Capture employee code if user replied after pressing Register ---
@bot.message_handler(func=lambda msg: msg.reply_to_message and "employee code" in msg.reply_to_message.text.lower())
def capture_employee_code(message):
    user_id = message.from_user.id
    employee_code = message.text.strip()
    if not re.match(r'^\d+$', employee_code):
        bot.reply_to(message, "❌ Invalid code. Please enter a number only.")
        return
    update_employee_code(user_id, employee_code)
    bot.reply_to(message, f"✅ Your employee code ({employee_code}) has been saved!")


# --- Watch messages from bot to scan and forward if codes match ---
@bot.message_handler(func=lambda m: m.text and re.search(r'-\s*\d+', m.text))
def watch_bot_messages(message):
    text = message.text or ""
    # Find all employee codes in the format "اسم - 279"
    codes = re.findall(r'[-–]\s*(\d+)', text)
    print(f"{text=}")
    print(f"{codes=}")
    print(f"{message.from_user.username=}")
    if codes:
        user_ids = get_user_ids_by_employee_codes(codes)
        for uid in user_ids:
            try:
                bot.forward_message(uid, message.chat.id, message.message_id)
            except Exception as e:
                print(f"Could not forward to {uid}: {e}")


# --- Optional: Handle private message fallback ---
@bot.message_handler(func=lambda m: m.chat.type == 'private')
def handle_private_message(message):
    user = message.from_user
    save_user(user)
    bot.reply_to(message, f"Hi {user.first_name}! Your user ID is {user.id}")


bot.polling()
