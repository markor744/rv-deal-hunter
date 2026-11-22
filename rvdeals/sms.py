"""Sends texts through Twilio's REST API using an API Key (not the main Auth Token).

Settings come from environment variables (GitHub Secrets in production). Their values,
including every phone number, are never printed or logged; output says "you" or "friend 2".

  TWILIO_ACCOUNT_SID            the account the key belongs to
  TWILIO_API_KEY_SID            the API Key made just for this tool
  TWILIO_API_KEY_SECRET         that key's secret
  TWILIO_FROM                   the sending number (or use TWILIO_MESSAGING_SERVICE_SID instead)
  TWILIO_MESSAGING_SERVICE_SID  optional, used instead of TWILIO_FROM when set
  ALERT_TO                      your mobile number, e.g. +1604...
  ALERT_FRIENDS                 optional: friends' numbers, separated by commas

DRY_RUN=1 prints the message text instead of sending it.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re

import requests

REQUIRED = ["TWILIO_ACCOUNT_SID", "TWILIO_API_KEY_SID", "TWILIO_API_KEY_SECRET", "ALERT_TO"]
E164 = re.compile(r"^\+[1-9]\d{9,14}$")
# Canadian area codes (CRTC list). A Canadian local number texting a US number needs US A2P 10DLC
# registration, so US numbers are skipped unless friends.us_friends is true.
CANADA_AREA = set("""204 226 236 249 250 257 263 289 306 343 354 365 367 368 382 403 416 418 428 431 437 438
450 468 474 506 514 519 537 548 579 581 584 587 600 604 613 639 647 672 683 705 709 742 753 778 780 782 807 819
825 867 873 879 902 905 942""".split())


def is_canadian(number: str) -> bool:
    return number.startswith("+1") and number[2:5] in CANADA_AREA


class SmsError(Exception):
    pass


def redact(text: str) -> str:
    """Hide phone numbers and Twilio IDs that error messages can contain."""
    text = re.sub(r"\+?\d[\d\s().-]{6,}\d", "[number hidden]", text or "")
    return re.sub(r"\b(AC|SK|MG|PN)[0-9a-fA-F]{32}\b", "[id hidden]", text)


def missing_settings() -> list[str]:
    miss = [k for k in REQUIRED if not os.environ.get(k)]
    if not (os.environ.get("TWILIO_FROM") or os.environ.get("TWILIO_MESSAGING_SERVICE_SID")):
        miss.append("TWILIO_FROM or TWILIO_MESSAGING_SERVICE_SID")
    return miss


def dry_run() -> bool:
    return os.environ.get("DRY_RUN", "").strip() not in ("", "0", "false", "no")


def _clean(n: str) -> str:
    """'+1 (604) 555-0199' -> '+16045550199'; a 10-digit number gets +1."""
    digits = re.sub(r"[^\d+]", "", n)
    if re.fullmatch(r"\d{10}", digits):
        digits = "+1" + digits
    elif re.fullmatch(r"1\d{10}", digits):
        digits = "+" + digits
    return digits


def owner() -> str | None:
    n = _clean(os.environ.get("ALERT_TO", ""))
    return n if E164.match(n) else None


def friends(max_friends: int, allow_us: bool = False) -> tuple[list[tuple[str, str]], list[str]]:
    """([(label, number)], [problems]). Labels are 'friend 1', 'friend 2'... in the order given."""
    raw = [x for x in re.split(r"[,;\n]+", os.environ.get("ALERT_FRIENDS", "")) if x.strip()]
    me = owner()
    out, problems, seen = [], [], set()
    for i, x in enumerate(raw, 1):
        n = _clean(x)
        if not E164.match(n):
            problems.append(f"friend {i}: not a valid number (use +1 and 10 digits), skipped")
        elif not allow_us and not is_canadian(n):
            problems.append(f"friend {i}: not a Canadian number, skipped (texting US numbers from a "
                            "Canadian local number needs A2P 10DLC registration; see README)")
        elif n == me or n in seen:
            problems.append(f"friend {i}: duplicate, skipped")
        elif len(out) >= max_friends:
            problems.append(f"friend {i}: over the limit of {max_friends} friends, skipped")
        else:
            seen.add(n)
            out.append((f"friend {i}", n))
    return out, problems


def friend_id(number: str) -> str:
    """A private fingerprint so the public state file can remember who got a welcome text
    without containing the number. Keyed with your own secret settings: not reversible."""
    key = (os.environ.get("ALERT_TO", "") + os.environ.get("TWILIO_ACCOUNT_SID", "")).encode()
    return hmac.new(key, number.encode(), hashlib.sha256).hexdigest()[:16]


def send(body: str, to: str, label: str = "you") -> str:
    """Send one text to one number. Returns 'sent' or 'dry-run'. Raises SmsError."""
    if dry_run():
        print(f"[DRY RUN] would text {label} ({len(body)} chars): {body}")
        return "dry-run"
    miss = missing_settings()
    if miss:
        raise SmsError("missing settings: " + ", ".join(miss))
    env = os.environ
    data = {"To": to, "Body": body}
    if env.get("TWILIO_MESSAGING_SERVICE_SID"):
        data["MessagingServiceSid"] = env["TWILIO_MESSAGING_SERVICE_SID"]
    else:
        data["From"] = env["TWILIO_FROM"]
    url = f"https://api.twilio.com/2010-04-01/Accounts/{env['TWILIO_ACCOUNT_SID']}/Messages.json"
    try:
        r = requests.post(url, data=data, auth=(env["TWILIO_API_KEY_SID"], env["TWILIO_API_KEY_SECRET"]),
                          timeout=30)
    except requests.RequestException as e:
        raise SmsError(f"could not reach Twilio ({type(e).__name__})") from None
    if r.status_code >= 300:
        try:
            j = r.json()
        except ValueError:
            raise SmsError(f"Twilio HTTP {r.status_code}") from None
        hint = " (they replied STOP; they can text START to rejoin)" if j.get("code") == 21610 else ""
        raise SmsError(redact(f"Twilio error {j.get('code')}: {j.get('message')}") + hint)
    print(f"text sent to {label} ({len(body)} chars)")
    return "sent"
