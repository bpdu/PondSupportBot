import time
import telebot
import auth
import features
import utils
import otp

telegram_token = utils.load_token("TELEGRAM")
bot = telebot.TeleBot(telegram_token)

user_mdns = {}
user_actions = {}
manager_state = {}
post_otp_action = {}
verified_until = {}

VERIFIED_TTL_SECONDS = 120

def is_verified(chat_id: int) -> bool:
    exp = verified_until.get(chat_id, 0)
    if exp and time.time() < exp:
        return True
    verified_until.pop(chat_id, None)
    return False

def set_verified(chat_id: int):
    verified_until[chat_id] = time.time() + VERIFIED_TTL_SECONDS

def main_menu_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        telebot.types.InlineKeyboardButton("Check Usage", callback_data="check_usage"),
        telebot.types.InlineKeyboardButton("Refresh Line", callback_data="refresh_line")
    )
    keyboard.add(
        telebot.types.InlineKeyboardButton("Check Coverage", url="https://www.pondmobile.com/coverage-map-pm")
    )
    keyboard.add(
        telebot.types.InlineKeyboardButton("Contact Support", callback_data="support"),
        telebot.types.InlineKeyboardButton("Contact Sales", callback_data="sales")
    )
    return keyboard

def back_menu_keyboard(prev_section=None):
    keyboard = telebot.types.InlineKeyboardMarkup()
    if prev_section:
        keyboard.add(telebot.types.InlineKeyboardButton("⬅️ Back", callback_data=prev_section))
    keyboard.add(telebot.types.InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"))
    return keyboard

def manager_usage_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        telebot.types.InlineKeyboardButton("📊 Check my usage", callback_data="manager_usage_self"),
        telebot.types.InlineKeyboardButton("🔎 Check other number", callback_data="manager_usage_other")
    )
    keyboard.add(telebot.types.InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"))
    return keyboard

def manager_refresh_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        telebot.types.InlineKeyboardButton("📡 Refresh my line", callback_data="manager_refresh_self"),
        telebot.types.InlineKeyboardButton("♻️ Refresh other number", callback_data="manager_refresh_other")
    )
    keyboard.add(telebot.types.InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"))
    return keyboard

def send_welcome_text(chat_id):
    content = utils.load_prompt("welcome")
    if not content.strip():
        content = utils.load_prompt("welcome_fallback")
    bot.send_message(chat_id, content, reply_markup=main_menu_keyboard())

def ask_share_phone(chat_id, prompt_name):
    keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    keyboard.add(telebot.types.KeyboardButton("📱 Share my phone", request_contact=True))
    bot.send_message(chat_id, utils.load_prompt(prompt_name), reply_markup=keyboard)

def run_post_otp(chat_id, mdn):
    action = post_otp_action.pop(chat_id, None)
    if not action:
        send_welcome_text(chat_id)
        return

    t = action.get("type")

    if t == "manager_menu_usage":
        bot.send_message(chat_id, utils.load_prompt("manager_access"), reply_markup=manager_usage_keyboard())
        return

    if t == "manager_menu_refresh":
        bot.send_message(chat_id, utils.load_prompt("manager_access"), reply_markup=manager_refresh_keyboard())
        return

    if t == "regular_usage":
        line_id = auth.get_line_id(mdn)
        bot.send_message(chat_id, utils.load_prompt("usage_checking_wait"))
        usage = features.check_usage(line_id)
        bot.send_message(chat_id, usage, reply_markup=back_menu_keyboard("main_menu"),
                         parse_mode="Markdown", disable_web_page_preview=True)
        return

    if t == "regular_refresh":
        msg = features.handle_refresh_request(mdn)
        bot.send_message(chat_id, msg, reply_markup=back_menu_keyboard("main_menu"),
                         disable_web_page_preview=True)
        return

def require_otp(chat_id, mdn, action):
    if is_verified(chat_id):
        post_otp_action[chat_id] = action
        run_post_otp(chat_id, mdn)
        return

    post_otp_action[chat_id] = action
    code = otp.start(chat_id, mdn)
    bot.send_message(chat_id, f"🔐 {code}")
    bot.send_message(chat_id, "Enter the verification code within 60 seconds.")

@bot.message_handler(content_types=["contact"])
def process_contact(message):
    chat_id = message.chat.id
    phone_number = message.contact.phone_number
    mdn = auth.normalize_mdn(phone_number)
    user_mdns[chat_id] = mdn

    bot.send_message(chat_id, utils.load_prompt("verifying_account"),
                     reply_markup=telebot.types.ReplyKeyboardRemove())

    action = user_actions.get(chat_id, "usage")

    if auth.is_manager(mdn):
        require_otp(chat_id, mdn, {"type": "manager_menu_usage" if action != "refresh" else "manager_menu_refresh"})
    else:
        require_otp(chat_id, mdn, {"type": "regular_usage" if action != "refresh" else "regular_refresh"})

    user_actions.pop(chat_id, None)

@bot.message_handler(content_types=["text"])
def block_text(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()

    if otp.is_waiting(chat_id):
        result = otp.verify(chat_id, text)

        if result == "OK":
            set_verified(chat_id)
            mdn = otp.consume_mdn(chat_id)
            run_post_otp(chat_id, mdn)
            return

        if result in ("EXPIRED", "LOCKED"):
            bot.send_message(chat_id, "The verification code is no longer valid.")
            return

        if result == "WRONG":
            bot.send_message(chat_id, "Invalid code.")
            return

        return

    bot.send_message(chat_id, utils.load_prompt("block_text_warning"),
                     reply_markup=main_menu_keyboard())

if __name__ == "__main__":
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
