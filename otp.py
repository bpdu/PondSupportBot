import time
import secrets

OTP_TTL_SECONDS = 60
OTP_MAX_ATTEMPTS = 3

otp_state = {}

def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"

def start(chat_id: int, mdn: str) -> str:
    code = generate_code()
    otp_state[chat_id] = {
        "code": code,
        "expires_at": time.time() + OTP_TTL_SECONDS,
        "attempts_left": OTP_MAX_ATTEMPTS,
        "mdn": mdn,
    }
    return code

def is_waiting(chat_id: int) -> bool:
    s = otp_state.get(chat_id)
    if not s:
        return False
    if time.time() > s["expires_at"]:
        otp_state.pop(chat_id, None)
        return False
    return True

def peek_code(chat_id: int) -> str | None:
    s = otp_state.get(chat_id)
    if not s:
        return None
    if time.time() > s["expires_at"]:
        otp_state.pop(chat_id, None)
        return None
    return s.get("code")

def verify(chat_id: int, user_input: str) -> str:
    s = otp_state.get(chat_id)
    if not s:
        return "NO_SESSION"

    if time.time() > s["expires_at"]:
        otp_state.pop(chat_id, None)
        return "EXPIRED"

    if s["attempts_left"] <= 0:
        otp_state.pop(chat_id, None)
        return "LOCKED"

    clean = "".join(ch for ch in (user_input or "") if ch.isdigit())
    if clean == s["code"]:
        return "OK"

    s["attempts_left"] -= 1
    if s["attempts_left"] <= 0:
        otp_state.pop(chat_id, None)
        return "LOCKED"

    return "WRONG"

def consume_mdn(chat_id: int):
    s = otp_state.pop(chat_id, None)
    if not s:
        return None
    return s.get("mdn")
