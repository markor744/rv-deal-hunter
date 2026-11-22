"""READ-ONLY look at the Twilio sending number. Changes nothing, prints no secrets or numbers.

Reads from environment variables:
  TWILIO_ACCOUNT_SID, and either TWILIO_AUTH_TOKEN or TWILIO_API_KEY_SID + TWILIO_API_KEY_SECRET
  TWILIO_FROM (the sending number) and/or TWILIO_MESSAGING_SERVICE_SID

Run:  python tools/twilio_check.py
"""
from __future__ import annotations

import os
import sys

import requests

TOLL_FREE = {"800", "833", "844", "855", "866", "877", "888"}


def auth():
    e = os.environ
    if e.get("TWILIO_API_KEY_SID") and e.get("TWILIO_API_KEY_SECRET"):
        return e["TWILIO_API_KEY_SID"], e["TWILIO_API_KEY_SECRET"]
    if e.get("TWILIO_AUTH_TOKEN"):
        return e["TWILIO_ACCOUNT_SID"], e["TWILIO_AUTH_TOKEN"]
    sys.exit("Missing TWILIO_AUTH_TOKEN or TWILIO_API_KEY_SID + TWILIO_API_KEY_SECRET")


def get(url, **params):
    r = requests.get(url, params=params, auth=auth(), timeout=30)
    if r.status_code >= 300:
        return {"_error": f"HTTP {r.status_code}"}
    return r.json()


def main():
    e = os.environ
    acct = e.get("TWILIO_ACCOUNT_SID") or sys.exit("Missing TWILIO_ACCOUNT_SID")
    base = f"https://api.twilio.com/2010-04-01/Accounts/{acct}"
    numbers = []
    if e.get("TWILIO_FROM"):
        numbers.append(e["TWILIO_FROM"].strip())
    svc = e.get("TWILIO_MESSAGING_SERVICE_SID")
    if svc:
        for pn in get(f"https://messaging.twilio.com/v1/Services/{svc}/PhoneNumbers").get("phone_numbers", []):
            numbers.append(pn["phone_number"])
    if not numbers:
        sys.exit("No TWILIO_FROM and no numbers found in the messaging service.")

    for i, num in enumerate(dict.fromkeys(numbers), 1):
        digits = num.lstrip("+")
        if len(digits) <= 6:
            kind = "short code"
        elif digits.startswith("1") and digits[1:4] in TOLL_FREE:
            kind = "toll-free"
        else:
            kind = "local (long code)"
        look = get(f"https://lookups.twilio.com/v2/PhoneNumbers/{num}")
        country = look.get("country_code", "unknown")
        print(f"Sending number #{i}: type = {kind}, country = {country}")

        inc = get(f"{base}/IncomingPhoneNumbers.json", PhoneNumber=num).get("incoming_phone_numbers", [])
        pn_sid = inc[0]["sid"] if inc else None
        if not pn_sid:
            print("  This number is not owned by this account (or the key cannot see it).")
            continue
        if kind == "toll-free":
            v = get("https://messaging.twilio.com/v1/Tollfree/Verifications", TollfreePhoneNumberSid=pn_sid)
            vs = v.get("verifications", [])
            if vs:
                x = vs[0]
                print(f"  Toll-free verification: {x.get('status')}; use case: {x.get('use_case_categories')}")
                print(f"  Described as: {(x.get('use_case_summary') or '')[:160]}")
            else:
                print("  Toll-free verification: none found (unverified toll-free texts are blocked)")
        elif kind.startswith("local") and country == "US":
            found = False
            for s in get("https://messaging.twilio.com/v1/Services", PageSize=50).get("services", []):
                pns = get(f"https://messaging.twilio.com/v1/Services/{s['sid']}/PhoneNumbers").get("phone_numbers", [])
                if any(p["sid"] == pn_sid for p in pns):
                    found = True
                    camp = get(f"https://messaging.twilio.com/v1/Services/{s['sid']}/Compliance/Usa2p").get("compliance", [])
                    print(f"  In messaging service named: {s.get('friendly_name')}")
                    if camp:
                        c = camp[0]
                        print(f"  A2P 10DLC campaign: status = {c.get('campaign_status')}, use case = {c.get('us_app_to_person_usecase')}")
                        print(f"  Described as: {(c.get('description') or '')[:160]}")
                    else:
                        print("  A2P 10DLC campaign: none (unregistered US local numbers are heavily filtered)")
            if not found:
                print("  Not in any messaging service, so no A2P 10DLC campaign (US carriers filter these)")
        elif country == "CA":
            print("  Canadian local number: US A2P 10DLC registration does not apply to it.")


if __name__ == "__main__":
    main()
