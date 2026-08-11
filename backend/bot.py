import os
import json
import urllib.request
import urllib.parse
import traceback

from flask import Flask, request
from supabase import create_client


# ==========================================
# ENVIRONMENT VARIABLES
# ==========================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing")

if not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is missing")


# ==========================================
# SUPABASE
# ==========================================

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY
)


# ==========================================
# FLASK
# ==========================================

web = Flask(__name__)


@web.route("/")
def home():
    return "🔥 MINE RUSH BACKEND RUNNING"


@web.route("/health")
def health():
    return "OK"


# ==========================================
# SEND TELEGRAM MESSAGE
# ==========================================

def send_telegram_message(chat_id, text):

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text
    }).encode("utf-8")

    request_data = urllib.request.Request(
        url,
        data=data,
        method="POST"
    )

    with urllib.request.urlopen(
        request_data,
        timeout=15
    ) as response:

        result = response.read().decode("utf-8")

        print("TELEGRAM RESPONSE:", result)


# ==========================================
# TELEGRAM WEBHOOK
# ==========================================

@web.post("/telegram")
def telegram_webhook():

    print("📩 TELEGRAM UPDATE RECEIVED")

    try:

        data = request.get_json(force=True)

        print(
            "UPDATE:",
            json.dumps(data, ensure_ascii=False)
        )

        message = data.get("message")

        if not message:
            return "OK"

        chat = message.get("chat", {})
        user = message.get("from", {})

        chat_id = chat.get("id")
        text = message.get("text", "")

        telegram_id = user.get("id")
        username = user.get("username")

        print("USER ID:", telegram_id)
        print("USERNAME:", username)
        print("TEXT:", text)


        # ==================================
        # /START
        # ==================================

        if text.strip() == "/start":

            # Check user in Supabase
            result = (
                supabase
                .table("users")
                .select("*")
                .eq(
                    "telegram_id",
                    telegram_id
                )
                .execute()
            )


            # ==================================
            # NEW USER
            # ==================================

            if not result.data:

                print("NEW USER")

                supabase.table("users").insert({
                    "telegram_id": telegram_id,
                    "username": username,
                    "note_balance": 0,
                    "sikka_balance": 0,
                    "xp": 0,
                    "level": 1
                }).execute()

                note = 0
                sikka = 0
                xp = 0
                level = 1

                text_to_send = (
                    "🔥 MINE RUSH 🔥\n\n"
                    "🎉 Welcome to MINE RUSH!\n\n"
                    f"🪙 NOTE: {note}\n"
                    f"🪙 SIKKA: {sikka}\n"
                    f"⭐ Level: {level}\n"
                    f"⚡ XP: {xp}\n\n"
                    "Your account has been created! 🚀"
                )


            # ==================================
            # EXISTING USER
            # ==================================

            else:

                print("EXISTING USER")

                user_data = result.data[0]

                note = user_data.get(
                    "note_balance",
                    0
                )

                sikka = user_data.get(
                    "sikka_balance",
                    0
                )

                xp = user_data.get(
                    "xp",
                    0
                )

                level = user_data.get(
                    "level",
                    1
                )

                text_to_send = (
                    "🔥 MINE RUSH 🔥\n\n"
                    f"🪙 NOTE: {note}\n"
                    f"🪙 SIKKA: {sikka}\n"
                    f"⭐ Level: {level}\n"
                    f"⚡ XP: {xp}\n\n"
                    "Welcome back! 🚀"
                )


            # ==================================
            # SEND RESPONSE
            # ==================================

            send_telegram_message(
                chat_id,
                text_to_send
            )

            print("✅ START RESPONSE SENT")


        return "OK"


    except Exception as e:

        print("❌ WEBHOOK ERROR")
        print(str(e))
        traceback.print_exc()

        # Telegram ko 500 na bheje,
        # warna same update baar-baar retry ho sakta hai.
        return "OK"


# ==========================================
# START SERVER
# ==========================================

if __name__ == "__main__":

    print("=================================")
    print("🔥 MINE RUSH BACKEND STARTING")
    print("🗄️ SUPABASE CONNECTED")
    print("📡 WEBHOOK MODE")
    print("=================================")

    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    web.run(
        host="0.0.0.0",
        port=port
    )
