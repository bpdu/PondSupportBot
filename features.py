import os
import requests
import pathlib
from dotenv import load_dotenv
from utils import load_prompt, refresh_line
from auth import normalize_mdn, get_line_id

print("[DEBUG] Loaded features.py from:", __file__)

# Base directory (folder where this file is located)
BASE_DIR = pathlib.Path(__file__).resolve().parent

# === Load BeQuick token ===
dotenv_path = BASE_DIR / "secrets" / "pondsupportbot2" / "bequick.env"
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
    mdn = normalize_mdn(phone_number)
    line_id = get_line_id(mdn)

    if not line_id:
        return load_prompt("not_registered")

    url = f"{API_URL}/lines/{line_id}/network_reset"
    headers = {"X-AUTH-TOKEN": API_TOKEN, "Content-Type": "application/json"}

    print(f"[BeQuick Refresh] POST {url} (mdn={mdn})")

    try:
        response = requests.post(url, headers=headers, timeout=10)
        print(f"[BeQuick Refresh] Status: {response.status_code}")

        if response.status_code == 200:
            return load_prompt("refresh_success")

        template = load_prompt("refresh_failed")
        return template.format(status=response.status_code)

    except requests.exceptions.RequestException as e:
        print(f"[BeQuick Refresh] Connection error: {e}")
        return load_prompt("bequick_error")
