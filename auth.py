import re
import requests
import utils
import os

API_TOKEN = utils.load_token("BEQUICK")
API_URL = "https://pondmobile-atom-api.bequickapps.com"

def normalize_mdn(phone_number: str) -> str:
    digits = re.sub(r"\D", "", phone_number)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits

def load_managers_list(path: str | None = None) -> set:
    if path is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base_dir, "resources", "pond_manager_access.txt")

    if not os.path.exists(path):
        print(f"[AUTH] managers file not found: {path}")
        return set()

    managers = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                clean = normalize_mdn(line.strip())
                if clean:
                    managers.add(clean)
    except Exception as e:
        print(f"[AUTH] error loading managers from {path}: {e}")
        return set()

    print(f"[AUTH] loaded {len(managers)} managers: {managers}")
    return managers

MANAGERS = load_managers_list()

def get_line_id(mdn: str):
    clean_mdn = normalize_mdn(mdn)
    url = f"{API_URL}/lines?by_quick_find[]={clean_mdn}"
    headers = {
        "X-AUTH-TOKEN": API_TOKEN,
        "Content-Type": "application/json"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"[BeQuick] Error {resp.status_code}: {resp.text}")
            return None

        data = resp.json() or {}
        lines = data.get("lines", [])
        if not lines:
            return None

        return lines[0].get("id")

    except requests.exceptions.RequestException as e:
        print(f"[BeQuick] Connection error: {e}")
        return None

def is_client(mdn: str) -> bool:
    return get_line_id(mdn) is not None

def is_manager(mdn: str) -> bool:
    normalized = normalize_mdn(mdn)
    return normalized in MANAGERS and is_client(normalized)
