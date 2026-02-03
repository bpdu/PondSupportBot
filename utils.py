import os
import json
import pathlib
import subprocess
import urllib.parse
from dotenv import load_dotenv

BASE_DIR = pathlib.Path(__file__).resolve().parent

def load_prompt(name: str) -> str:
    path = BASE_DIR / "resources" / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"[ERROR] File not found: {path}")
    with open(path, "r", encoding="utf8") as file:
        return file.read()

def load_token(name: str) -> str:
    secrets_dir = BASE_DIR / "secrets" / "pondsupportbot2"
    candidates = [
        secrets_dir / f"{name}.env",
        secrets_dir / f"{name.lower()}.env",
        secrets_dir / f"{name.upper()}.env",
    ]
    dotenv_path = next((p for p in candidates if p.exists()), None)
    if not dotenv_path:
        raise FileNotFoundError(f"[ERROR] Env file not found: tried {[str(p) for p in candidates]}")

    load_dotenv(dotenv_path)
    token = os.getenv(f"{name.upper()}_TOKEN")
    if not token:
        raise ValueError(f"[ERROR] {name.upper()}_TOKEN not found in {dotenv_path}")
    return token

def refresh_line(mdn: str) -> str:
    base_url = "https://t.me/pondsupport"
    message = f"Dear customer support, this is my number {mdn}, please refresh my line"
    encoded = urllib.parse.quote(message)
    return f"{base_url}?text={encoded}"

STAT_FILE = BASE_DIR / "stat" / "stat.json"

def load_stat():
    if not STAT_FILE.exists():
        return {
            "visitors": 0,
            "buttons": {
                "sales": 0,
                "support": 0,
                "usage": 0,
                "coverage": 0,
                "refresh": 0
            }
        }
    with open(STAT_FILE, "r") as f:
        return json.load(f)

def save_stat(stat):
    STAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STAT_FILE, "w") as f:
        json.dump(stat, f, indent=2)

def increment_button(button_name):
    stat = load_stat()
    if button_name in stat["buttons"]:
        stat["buttons"][button_name] += 1
    else:
        stat["buttons"][button_name] = 1
    save_stat(stat)

def is_bot_running() -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", "pondsupportbot.service"],
            check=False
        )
        return result.returncode == 0
    except Exception:
        return False
