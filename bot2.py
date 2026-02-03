import time
import requests
import telebot
from telebot import apihelper
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

import auth
import features
import utils
import otp

telegram_token = utils.load_token("TELEGRAM")
telegram_otp_token = utils.load_token("TELEGRAM_OTP")

bot = telebot.TeleBot(telegram_token)
otp_bot = telebot.TeleBot(telegram_otp_token)

user_mdns = {}
user_actions = {}
manager_state = {}
post_otp_action = {}
verified_until = {}
otp_bot_allowed = set()

VERIFIED_TTL_SECONDS = 120

SESSION = requests.Session()
RETRY = Retry(
    total=5,
    connect=5,
    read=5,
    backoff_factor=0.7,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=("GET", "POST"),
    raise_on_status=False,
)
ADAPTER = HTTPAdapter(max_retries=RETRY)
SESSION.mount("https://", ADAPTER)
SESSION.mount("http://", ADAPTER)
apihelper._get_req_session = lambda: SESSION


def send(tb: telebot.TeleBot, chat_id: int, text: str, **kwargs) -> bool:
    for _ in range(5):
        try:
            tb.send_message(chat_id, text, **kwargs)
            return True
        except Exception:
            time.sleep(0.8)
    return False


def now() -> float:
    return time.time()


def is_verified(chat_id: int) -> bool:
    exp = verified_until.get(chat_id, 0)
    if exp and now() < exp:
        return True
    verified_until.pop(chat_id, None)
    return False


def set_verified(chat_id: int):
    verified_until[chat_id] = now() + VERIFIED_TTL_SECONDS


def get_otp_bot_username() -> str | None:
    for _ in range(3):
        try:
            me = otp_bot.get_me()
            return getattr(me, "username", None)
        except Exception:
            time.sleep(0.6)
    return None


OTP_BOT_USERNAME = get_otp_bot_username()


def kb_otp_link():
    if not OTP_BOT_USERNAME:
        return None
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("Open OTP bot", url=f"https://t.me/{OTP_BOT_USERNAME}"))
    return kb


def kb_main(chat_id: int):
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        telebot.types.InlineKeyboardButton("Check Usage", callback_data="check_usage"),
        telebot.types.InlineKeyboardButton("Refresh Line", callback_data="refresh_line"),
    )
    kb.add(telebot.types.InlineKeyboardButton("Check Coverage", url="https://www.pondmobile.com/coverage-map-pm"))
    kb.add(
        telebot.types.InlineKeyboardButton("Contact Support", callback_data="support"),
        telebot.types.InlineKeyboardButton("Contact Sales", callback_data="sales"),
    )
    if OTP_BOT_USERNAME and chat_id not in otp_bot_allowed:
        kb.add(telebot.types.InlineKeyboardButton("Open OTP bot", url=f"https://t.me/{OTP_BOT_USERNAME}"))
    return kb


def kb_back(prev=None):
    kb = telebot.types.InlineKeyboardMarkup()
    if prev:
        kb.add(telebot.types.InlineKeyboardButton("⬅️ Back", callback_data=prev))
    kb.add(telebot.types.InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"))
    return kb


def kb_mgr_usage():
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        telebot.types.InlineKeyboardButton("📊 Check my usage", callback_data="manager_usage_self"),
        telebot.types.InlineKeyboardButton("🔎 Check other number", callback_data="manager_usage_other"),
    )
    kb.add(telebot.types.InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"))
    return kb


def kb_mgr_refresh():
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        telebot.types.InlineKeyboardButton("📡 Refresh my line", callback_data="manager_refresh_self"),
        telebot.types.InlineKeyboardButton("♻️ Refresh other number", callback_data="manager_refresh_other"),
    )
    kb.add(telebot.types.InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"))
    return kb


def kb_share_phone():
    kb = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    kb.add(telebot.types.KeyboardButton("📱 Share my POND phone number", request_contact=True))
    return kb


def welcome(chat_id: int):
    content = utils.load_prompt("welcome")
    if not content.strip():
        content = utils.load_prompt("welcome_fallback")
    send(bot, chat_id, content, reply_markup=kb_main(chat_id))


def maybe_hint_otp(chat_id: int):
    if chat_id in otp_bot_allowed:
        return
    kb = kb_otp_link()
    if not kb:
        return
    send(bot, chat_id, "Open the OTP bot and press Start once to receive verification codes.", reply_markup=kb)


def ask_phone(chat_id: int, prompt_name: str):
    send(bot, chat_id, utils.load_prompt(prompt_name), reply_markup=kb_share_phone())
    maybe_hint_otp(chat_id)


def otp_send(chat_id: int, code: str) -> bool:
    ok = send(otp_bot, chat_id, f"🔐 {code}")
    if ok:
        otp_bot_allowed.add(chat_id)
    return ok


def require_otp(chat_id: int, mdn: str | None, action: dict):
    if not mdn:
        send(bot, chat_id, utils.load_prompt("not_registered"))
        welcome(chat_id)
        return

    if is_verified(chat_id):
        post_otp_action[chat_id] = action
        run_action(chat_id, mdn)
        return

    post_otp_action[chat_id] = action
    code = otp.start(chat_id, mdn)

    if otp_send(chat_id, code):
        send(bot, chat_id, "The verification code was sent in a separate OTP chat. Please enter it here.")
        return

    kb = kb_otp_link()
    if kb:
        send(bot, chat_id, "Open the OTP bot and press Start once. Then try again.", reply_markup=kb)
    else:
        send(bot, chat_id, "Open the OTP bot and press Start once. Then try again.")


def do_usage(chat_id: int, mdn: str):
    line_id = auth.get_line_id(mdn)
    if not line_id:
        send(bot, chat_id, utils.load_prompt("not_registered"))
        welcome(chat_id)
        return
    send(bot, chat_id, utils.load_prompt("usage_checking_wait"))
    usage = features.check_usage(line_id)
    send(
        bot,
        chat_id,
        usage,
        reply_markup=kb_back("main_menu"),
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


def do_refresh(chat_id: int, mdn: str):
    msg = features.handle_refresh_request(mdn)
    send(bot, chat_id, msg, reply_markup=kb_back("main_menu"), disable_web_page_preview=True)


def run_action(chat_id: int, mdn: str):
    action = post_otp_action.pop(chat_id, None)
    if not action:
        welcome(chat_id)
        return

    t = action.get("type")

    actions = {
        "manager_menu_usage": lambda: send(bot, chat_id, utils.load_prompt("manager_access"), reply_markup=kb_mgr_usage()),
        "manager_menu_refresh": lambda: send(bot, chat_id, utils.load_prompt("manager_access"), reply_markup=kb_mgr_refresh()),
        "regular_usage": lambda: do_usage(chat_id, mdn),
        "regular_refresh": lambda: do_refresh(chat_id, mdn),
        "manager_usage_self": lambda: do_usage(chat_id, mdn),
        "manager_refresh_self": lambda: do_refresh(chat_id, mdn),
        "manager_usage_other": lambda: (manager_state.__setitem__(chat_id, "usage_other"), send(bot, chat_id, utils.load_prompt("manager_enter_other_usage"))),
        "manager_refresh_other": lambda: (manager_state.__setitem__(chat_id, "refresh_other"), send(bot, chat_id, utils.load_prompt("manager_enter_other_refresh"))),
    }

    fn = actions.get(t)
    if fn:
        fn()
    else:
        welcome(chat_id)


@bot.message_handler(commands=["start"])
def on_start(message):
    stat = utils.load_stat()
    stat["visitors"] += 1
    utils.save_stat(stat)
    welcome(message.chat.id)
    maybe_hint_otp(message.chat.id)


@bot.callback_query_handler(func=lambda call: True)
def on_callback(call):
    chat_id = call.message.chat.id
    data = call.data

    if data == "main_menu":
        welcome(chat_id)
        return

    if data == "check_usage":
        utils.increment_button("usage")
        user_actions[chat_id] = "usage"
        ask_phone(chat_id, "share_phone_usage")
        return

    if data == "refresh_line":
        utils.increment_button("refresh")
        user_actions[chat_id] = "refresh"
        ask_phone(chat_id, "share_phone_refresh")
        return

    if data == "support":
        utils.increment_button("support")
        send(bot, chat_id, utils.load_prompt("support"), reply_markup=kb_back("main_menu"))
        return

    if data == "sales":
        utils.increment_button("sales")
        send(bot, chat_id, utils.load_prompt("sales"), reply_markup=kb_back("main_menu"))
        return

    mdn = user_mdns.get(chat_id)

    protected = {
        "manager_usage_self": {"type": "manager_usage_self"},
        "manager_refresh_self": {"type": "manager_refresh_self"},
        "manager_usage_other": {"type": "manager_usage_other"},
        "manager_refresh_other": {"type": "manager_refresh_other"},
    }

    action = protected.get(data)
    if action:
        require_otp(chat_id, mdn, action)
        return


@bot.message_handler(content_types=["contact"])
def on_contact(message):
    chat_id = message.chat.id

    c = message.contact
    if not c or not getattr(c, "phone_number", None):
        send(bot, chat_id, "Please share your phone using the button.")
        return

    if c.user_id is not None and c.user_id != message.from_user.id:
        send(bot, chat_id, "Please share your own phone using the button.")
        return

    mdn = auth.normalize_mdn(c.phone_number)
    user_mdns[chat_id] = mdn

    send(bot, chat_id, utils.load_prompt("verifying_account"), reply_markup=telebot.types.ReplyKeyboardRemove())

    if not auth.get_line_id(mdn):
        send(bot, chat_id, utils.load_prompt("not_registered"))
        welcome(chat_id)
        user_actions.pop(chat_id, None)
        return

    action = user_actions.get(chat_id, "usage")

    if auth.is_manager(mdn):
        require_otp(chat_id, mdn, {"type": "manager_menu_refresh" if action == "refresh" else "manager_menu_usage"})
        user_actions.pop(chat_id, None)
        return

    require_otp(chat_id, mdn, {"type": "regular_refresh" if action == "refresh" else "regular_usage"})
    user_actions.pop(chat_id, None)


@bot.message_handler(content_types=["text"])
def on_text(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()

    if otp.is_waiting(chat_id):
        r = otp.verify(chat_id, text)
        if r == "OK":
            set_verified(chat_id)
            mdn = otp.consume_mdn(chat_id)
            run_action(chat_id, mdn)
            return
        if r in ("EXPIRED", "LOCKED"):
            send(bot, chat_id, "The verification code is no longer valid.")
            return
        if r == "WRONG":
            send(bot, chat_id, "Invalid code.")
            return
        return

    state = manager_state.get(chat_id)

    if state == "usage_other":
        manager_state.pop(chat_id, None)
        target = auth.normalize_mdn(text)
        do_usage(chat_id, target)
        return

    if state == "refresh_other":
        manager_state.pop(chat_id, None)
        target = auth.normalize_mdn(text)
        do_refresh(chat_id, target)
        return

    send(bot, chat_id, utils.load_prompt("block_text_warning"), reply_markup=kb_main(chat_id))


def run_polling():
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
        except Exception:
            time.sleep(2.0)


if __name__ == "__main__":
    run_polling()
