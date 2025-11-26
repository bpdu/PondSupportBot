import os
import requests
from dotenv import load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils import load_prompt, refresh_line

print("[DEBUG] Loaded features.py from:", __file__)

# === Load BeQuick token ===
dotenv_path = "secrets/pondsupportbot2/bequick.env"
load_dotenv(dotenv_path)

API_URL = "https://pondmobile-atom-api.bequickapps.com"
API_TOKEN = os.getenv("BEQUICK_TOKEN")
if not API_TOKEN:
    raise ValueError("Token not found in bequick.env")


# === Convert KB → MB/GB string ===
def kb_to_readable(kb_value: float) -> str:
    mb = kb_value / 1024
    return f"{mb / 1024:.3f} GB" if mb >= 1024 else f"{mb:.2f} MB"


# === Fetch data usage ===
def check_usage(line_id: int | str):
    url = f"{API_URL}/lines/{line_id}/query_service_details"
    headers = {"X-AUTH-TOKEN": API_TOKEN, "Content-Type": "application/json"}

    print(f"[BeQuick Usage] Checking usage for line_id={line_id} at: {url}")

    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"[BeQuick Usage] Status: {response.status_code}")

        if response.status_code != 200:
            template = load_prompt("usage_status")
            return template.format(status=response.status_code)

        data = response.json() or {}
        usage_summary = data.get("usage_summary", {})
        data_usage = usage_summary.get("international_data", {})

        total_kb = float(data_usage.get("total", 0))
        remaining_kb = float(data_usage.get("remaining", 0))
        used_kb = float(data_usage.get("used_by_this_line", data_usage.get("used", 0)))

        used_str = kb_to_readable(used_kb)
        total_str = kb_to_readable(total_kb)
        remaining_str = kb_to_readable(remaining_kb)

        template = load_prompt("usage")
        return template.format(used=used_str, total=total_str, remaining=remaining_str)

    except requests.exceptions.RequestException as e:
        print(f"[BeQuick Usage] Connection error: {e}")
        return load_prompt("usage_error")


# === Handle refresh request ===
def handle_refresh_request(phone_number: str):
    """
    Network reset линии через BeQuick:
    POST /lines/:line_id/network_reset

    Возвращает ОДНУ строку.
    """
    from auth import normalize_mdn, get_line_id

    mdn = normalize_mdn(phone_number)
    line_id = get_line_id(mdn)

    if not line_id:
        return "❌ Your number was not found as a POND customer."

    url = f"{API_URL}/lines/{line_id}/network_reset"
    headers = {"X-AUTH-TOKEN": API_TOKEN, "Content-Type": "application/json"}

    print(f"[BeQuick Refresh] POST {url} (mdn={mdn})")

    try:
        response = requests.post(url, headers=headers, timeout=10)
        print(f"[BeQuick Refresh] Status: {response.status_code}")

        # Успешные статусы
        if response.status_code in (200, 201, 202, 204):
            return "✅ Your line is refreshed."

        # Ошибка статуса
        return f"❌ Refresh failed. Status: {response.status_code}"

    except requests.exceptions.RequestException as e:
        print(f"[BeQuick Refresh] Connection error: {e}")
        return "⚠️ BeQuick connection error. Try again later."




# def handle_refresh_request(phone_number: str):
#     """
#     Creates message + inline button for contacting @pondsupport
#     and inserts MDN into refresh.txt template.
#     """
#     from auth import normalize_mdn, get_line_id
#
#     mdn = normalize_mdn(phone_number)
#     line_id = get_line_id(mdn)
#
#     if not line_id:
#         return "❌ Your number is not registered as a POND mobile customer."
#
#     # support chat link
#     url = refresh_line(mdn)
#
#     # load template and insert MDN + link
#     template = load_prompt("refresh")
#     message = template.format(mdn=mdn)
#
#     # create inline button for Telegram
#     keyboard = InlineKeyboardMarkup()
#     keyboard.add(InlineKeyboardButton(text="💬 Open Support Chat", url=url))
#
#     return message, keyboard
