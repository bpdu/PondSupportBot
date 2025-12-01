# bot2.py
import telebot
import auth
import features
import utils

telegram_token = utils.load_token("TELEGRAM")
bot = telebot.TeleBot(telegram_token)
print("POND Mobile BOT is running...")

# === In-memory storage ===
user_mdns = {}
user_actions = {}  # keeps user input: "usage" or "refresh"


# === Keyboards ===
def main_menu_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)

    keyboard.add(
        telebot.types.InlineKeyboardButton(text="Check Usage", callback_data="check_usage"),
        telebot.types.InlineKeyboardButton(text="Refresh Line", callback_data="refresh_line")
    )

    keyboard.add(
        telebot.types.InlineKeyboardButton(
            text="Check Coverage",
            url="www.pondmobile.com/coverage-map-pm"
        )
    )

    keyboard.add(
        telebot.types.InlineKeyboardButton(text="Contact Support", callback_data="support"),
        telebot.types.InlineKeyboardButton(text="Contact Sales", callback_data="sales")
    )

    return keyboard


def back_menu_keyboard(prev_section=None):
    keyboard = telebot.types.InlineKeyboardMarkup()
    if prev_section:
        keyboard.add(telebot.types.InlineKeyboardButton("⬅️ Back", callback_data=prev_section))
    keyboard.add(telebot.types.InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"))
    return keyboard


def send_welcome_text(chat_id):
    try:
        content = utils.load_prompt("welcome")
        if not content or not content.strip():
            raise ValueError("welcome.txt is empty")
    except (FileNotFoundError, ValueError):
        content = utils.load_prompt("welcome_fallback")
    bot.send_message(chat_id, content, reply_markup=main_menu_keyboard())


# === /start command ===
@bot.message_handler(commands=["start"])
def send_welcome(message):
    stat = utils.load_stat()
    stat["visitors"] += 1
    utils.save_stat(stat)
    send_welcome_text(message.chat.id)


# === Handle button presses ===
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id

    if call.data == "main_menu":
        send_welcome_text(chat_id)

    elif call.data == "check_usage":
        user_actions[chat_id] = "usage"
        utils.increment_button("usage")

        keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        button = telebot.types.KeyboardButton(text="📱 Share my phone", request_contact=True)
        keyboard.add(button)

        text = utils.load_prompt("share_phone_usage")
        bot.send_message(chat_id, text, reply_markup=keyboard)

    elif call.data == "refresh_line":
        user_actions[chat_id] = "refresh"
        utils.increment_button("refresh")

        keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        button = telebot.types.KeyboardButton(text="📱 Share my phone", request_contact=True)
        keyboard.add(button)

        text = utils.load_prompt("share_phone_refresh")
        bot.send_message(chat_id, text, reply_markup=keyboard)

    elif call.data == "support":
        utils.increment_button("support")
        try:
            content = utils.load_prompt("support")
            bot.send_message(chat_id, content, reply_markup=back_menu_keyboard("main_menu"))
        except FileNotFoundError:
            bot.send_message(
                chat_id,
                "⚠️ File resources/support.txt not found.",
                reply_markup=back_menu_keyboard("main_menu")
            )

    elif call.data == "sales":
        utils.increment_button("sales")
        try:
            content = utils.load_prompt("sales")
            bot.send_message(chat_id, content, reply_markup=back_menu_keyboard("main_menu"))
        except FileNotFoundError:
            bot.send_message(
                chat_id,
                "⚠️ File resources/sales.txt not found.",
                reply_markup=back_menu_keyboard("main_menu")
            )

    elif call.data == "support_back":
        bot.send_message(
            chat_id,
            "🧑‍💻 Support menu:",
            reply_markup=back_menu_keyboard(prev_section="main_menu")
        )


# === Handle shared phone contact ===
@bot.message_handler(content_types=["contact"])
def process_contact(message):
    phone_number = message.contact.phone_number
    normalized_mdn = auth.normalize_mdn(phone_number)
    user_mdns[message.chat.id] = normalized_mdn

    remove_keyboard = telebot.types.ReplyKeyboardRemove()
    verifying_text = utils.load_prompt("verifying_account")
    bot.send_message(message.chat.id, verifying_text, reply_markup=remove_keyboard)

    line_id = auth.get_line_id(normalized_mdn)
    if not line_id:
        not_registered_text = utils.load_prompt("not_registered")
        bot.send_message(message.chat.id, not_registered_text)

        returning_text = utils.load_prompt("returning_main_menu")
        bot.send_message(message.chat.id, returning_text, reply_markup=main_menu_keyboard())

        user_actions.pop(message.chat.id, None)
        return

    action = user_actions.get(message.chat.id)

    if action == "refresh":
        message_text = features.handle_refresh_request(phone_number)
        bot.send_message(
            message.chat.id,
            message_text,
            reply_markup=back_menu_keyboard("main_menu"),
            disable_web_page_preview=True
        )
        user_actions.pop(message.chat.id, None)
        return

    # default -> usage
    wait_text = utils.load_prompt("usage_checking_wait")
    bot.send_message(message.chat.id, wait_text)

    user_usage = features.check_usage(line_id)
    bot.send_message(
        message.chat.id,
        f"{user_usage}",
        reply_markup=back_menu_keyboard("main_menu"),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    user_actions.pop(message.chat.id, None)


# === Block manual typing (disable text input) ===
@bot.message_handler(content_types=["text"])
def block_text(message):
    warning_text = utils.load_prompt("block_text_warning")
    bot.send_message(
        message.chat.id,
        warning_text,
        reply_markup=main_menu_keyboard()
    )


# === Start polling ===
if __name__ == "__main__":
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"[ERROR] Polling crashed: {e}")
