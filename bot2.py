# bot2.py
import telebot
import auth
import features
import utils

telegram_token = utils.load_token("TELEGRAM")
bot = telebot.TeleBot(telegram_token)
print("POND Mobile BOT is running...")

# In-memory storage
user_mdns = {}        # chat_id -> normalized mdn
user_actions = {}     # chat_id -> "usage" or "refresh" (regular clients)
manager_state = {}    # chat_id -> "usage_other" / "refresh_other"


# Keyboards
def main_menu_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        telebot.types.InlineKeyboardButton("Check Usage", callback_data="check_usage"),
        telebot.types.InlineKeyboardButton("Refresh Line", callback_data="refresh_line")
    )
    keyboard.add(
        telebot.types.InlineKeyboardButton(
            "Check Coverage",
            url="www.pondmobile.com/coverage-map-pm"
        )
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


# /start
@bot.message_handler(commands=["start"])
def send_welcome(message):
    stat = utils.load_stat()
    stat["visitors"] += 1
    utils.save_stat(stat)
    send_welcome_text(message.chat.id)


# Handle buttons
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    data = call.data

    if data == "main_menu":
        send_welcome_text(chat_id)

    elif data == "check_usage":
        user_actions[chat_id] = "usage"
        utils.increment_button("usage")
        keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        keyboard.add(telebot.types.KeyboardButton("📱 Share my phone", request_contact=True))
        text = utils.load_prompt("share_phone_usage")
        bot.send_message(chat_id, text, reply_markup=keyboard)

    elif data == "refresh_line":
        user_actions[chat_id] = "refresh"
        utils.increment_button("refresh")
        keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        keyboard.add(telebot.types.KeyboardButton("📱 Share my phone", request_contact=True))
        text = utils.load_prompt("share_phone_refresh")
        bot.send_message(chat_id, text, reply_markup=keyboard)

    elif data == "support":
        utils.increment_button("support")
        content = utils.load_prompt("support")
        bot.send_message(chat_id, content, reply_markup=back_menu_keyboard("main_menu"))

    elif data == "sales":
        utils.increment_button("sales")
        content = utils.load_prompt("sales")
        bot.send_message(chat_id, content, reply_markup=back_menu_keyboard("main_menu"))

    elif data == "support_back":
        bot.send_message(chat_id, "🧑‍💻 Support menu:", reply_markup=back_menu_keyboard("main_menu"))

    # Manager: own usage
    elif data == "manager_usage_self":
        mdn = user_mdns.get(chat_id)
        line_id = auth.get_line_id(mdn) if mdn else None
        if not line_id:
            bot.send_message(chat_id, utils.load_prompt("not_registered"))
            send_welcome_text(chat_id)
            return
        bot.send_message(chat_id, utils.load_prompt("usage_checking_wait"))
        usage = features.check_usage(line_id)
        bot.send_message(
            chat_id,
            usage,
            reply_markup=back_menu_keyboard("main_menu"),
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )

    # Manager: other usage
    elif data == "manager_usage_other":
        manager_state[chat_id] = "usage_other"
        text = utils.load_prompt("manager_enter_other_usage")
        bot.send_message(chat_id, text)

    # Manager: own refresh
    elif data == "manager_refresh_self":
        mdn = user_mdns.get(chat_id)
        if not mdn:
            bot.send_message(chat_id, utils.load_prompt("not_registered"))
            send_welcome_text(chat_id)
            return
        message_text = features.handle_refresh_request(mdn)
        bot.send_message(
            chat_id,
            message_text,
            reply_markup=back_menu_keyboard("main_menu"),
            disable_web_page_preview=True,
        )

    # Manager: other refresh
    elif data == "manager_refresh_other":
        manager_state[chat_id] = "refresh_other"
        text = utils.load_prompt("manager_enter_other_refresh")
        bot.send_message(chat_id, text)


# Handle shared phone contact
@bot.message_handler(content_types=["contact"])
def process_contact(message):
    chat_id = message.chat.id
    phone_number = message.contact.phone_number
    normalized_mdn = auth.normalize_mdn(phone_number)
    user_mdns[chat_id] = normalized_mdn

    remove_keyboard = telebot.types.ReplyKeyboardRemove()
    bot.send_message(chat_id, utils.load_prompt("verifying_account"), reply_markup=remove_keyboard)

    line_id = auth.get_line_id(normalized_mdn)
    if not line_id:
        bot.send_message(chat_id, utils.load_prompt("not_registered"))
        bot.send_message(chat_id, utils.load_prompt("returning_main_menu"), reply_markup=main_menu_keyboard())
        user_actions.pop(chat_id, None)
        return

    # Manager flow: меню зависит от исходного действия
    if auth.is_manager(normalized_mdn):
        content = utils.load_prompt("manager_access")
        action = user_actions.get(chat_id)
        if action == "refresh":
            kb = manager_refresh_keyboard()
        else:
            kb = manager_usage_keyboard()
        bot.send_message(chat_id, content, reply_markup=kb)
        user_actions.pop(chat_id, None)
        return

    # Regular client flow
    action = user_actions.get(chat_id)

    if action == "refresh":
        message_text = features.handle_refresh_request(phone_number)
        bot.send_message(
            chat_id,
            message_text,
            reply_markup=back_menu_keyboard("main_menu"),
            disable_web_page_preview=True,
        )
        user_actions.pop(chat_id, None)
        return

    # default -> usage
    bot.send_message(chat_id, utils.load_prompt("usage_checking_wait"))
    usage = features.check_usage(line_id)
    bot.send_message(
        chat_id,
        usage,
        reply_markup=back_menu_keyboard("main_menu"),
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )
    user_actions.pop(chat_id, None)


# Handle text input
@bot.message_handler(content_types=["text"])
def block_text(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()
    state = manager_state.get(chat_id)

    # Manager: usage for other number
    if state == "usage_other":
        target = auth.normalize_mdn(text)
        line_id = auth.get_line_id(target)
        if not line_id:
            bot.send_message(chat_id, utils.load_prompt("not_registered"))
            manager_state.pop(chat_id, None)
            return
        bot.send_message(chat_id, utils.load_prompt("usage_checking_wait"))
        usage = features.check_usage(line_id)
        manager_state.pop(chat_id, None)
        bot.send_message(
            chat_id,
            usage,
            reply_markup=back_menu_keyboard("main_menu"),
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        return

    # Manager: refresh for other number
    if state == "refresh_other":
        target = auth.normalize_mdn(text)
        message_text = features.handle_refresh_request(target)
        manager_state.pop(chat_id, None)
        bot.send_message(
            chat_id,
            message_text,
            reply_markup=back_menu_keyboard("main_menu"),
            disable_web_page_preview=True,
        )
        return

    # Default: block manual typing
    warning_text = utils.load_prompt("block_text_warning")
    bot.send_message(chat_id, warning_text, reply_markup=main_menu_keyboard())


# Start polling
if __name__ == "__main__":
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"[ERROR] Polling crashed: {e}")
