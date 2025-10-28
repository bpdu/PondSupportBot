import os
from dotenv import load_dotenv
import telebot
from utils import load_prompt
import auth
import features

# --- load token from telegram-token.env ---
dotenv_path = 'secrets/pondsupportbot2/telegram-token.env'
if not os.path.exists(dotenv_path):
    raise FileNotFoundError(f"File telegram-token.env not found on {dotenv_path}")

load_dotenv(dotenv_path)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("Token not found in the file! Check file telegram-token.env")

bot = telebot.TeleBot(TOKEN)


# --- MAIN MENU keyboard ---
def main_menu_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton(text="Support", callback_data="support"))
    keyboard.add(telebot.types.InlineKeyboardButton(text="Sales", callback_data="sales"))
    keyboard.add(telebot.types.InlineKeyboardButton(text="Check usage", callback_data="check_usage"))
    keyboard.add(telebot.types.InlineKeyboardButton(
        text="Check Coverage",
        url='https://www.pondmobile.com/coverage-map-pm/'
    ))
    return keyboard


# --- BACK button keyboard ---
def back_button():
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton(text="⬅️ Back to Menu", callback_data="main_menu"))
    return keyboard


# --- /start command handler ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = load_prompt("welcome")
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu_keyboard())


# --- callback handler ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == "support":
        bot.send_message(call.message.chat.id, load_prompt("support"), reply_markup=back_button())

    elif call.data == "sales":
        bot.send_message(call.message.chat.id, load_prompt("sales"), reply_markup=back_button())

    elif call.data == "check_usage":
        request_user_contact(call.message)

    elif call.data == "main_menu":
        bot.send_message(call.message.chat.id, "Main menu:", reply_markup=main_menu_keyboard())


# --- request contact from user ---
def request_user_contact(message):
    keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    contact_button = telebot.types.KeyboardButton(
        text="📱 Share my phone number",
        request_contact=True
    )
    keyboard.add(contact_button)

    bot.send_message(
        message.chat.id,
        "Please share your phone number so we can verify your account:",
        reply_markup=keyboard
    )


# --- process received contact ---
@bot.message_handler(content_types=['contact'])
def process_contact(message):
    remove_keyboard = telebot.types.ReplyKeyboardRemove()
    bot.send_message(message.chat.id, "Thanks! Verifying your account...", reply_markup=remove_keyboard)

    phone_number = message.contact.phone_number
    mdn = phone_number[-10:]  # берем последние 10 цифр

    if auth.is_customer(mdn):
        user_usage = features.check_usage(mdn)
        usage_text = load_prompt("usage")

        bot.send_message(
            message.chat.id,
            f"{usage_text}\n\n📊 Your current usage: {user_usage} MB",
            parse_mode="Markdown",
            reply_markup=back_button()
        )
    else:
        bot.send_message(
            message.chat.id,
            "Your number is not registered as a POND mobile customer.",
            reply_markup=back_button()
        )


# --- start bot ---
if __name__ == "__main__":
    print("Pond Mobile bot is running...")
    bot.polling(none_stop=True, interval=0, timeout=20)
