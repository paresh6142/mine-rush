import os
import asyncio

from flask import Flask, request
from supabase import create_client
from telegram import Bot, Update


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
# CONNECTIONS
# ==========================================

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY
)

bot = Bot(
    token=TELEGRAM_BOT_TOKEN
)

web = Flask(__name__)


# ==========================================
# HOME
# ==========================================

@web.route("/")
def home():
    return "🔥 MINE RUSH BACKEND RUNNING"


@web.route("/health")
def health():
    return "OK"


# ==========================================
# TELEGRAM WEBHOOK
# ==========================================

@web.post("/telegram")
def telegram_webhook():

    try:

        data = request.get_json(force=True)

        print("📩 TELEGRAM UPDATE RECEIVED")

        update = Update.de_json(
            data,
            bot
        )

        if update.message:

            message = update.message

            if message.text == "/start":

                telegram_id = message.from_user.id
                username = message.from_user.username

                print(
                    f"👤 START FROM USER: {telegram_id}"
                )

                # Check user
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

                    welcome = True

                # ==================================
                # EXISTING USER
                # ==================================

                else:

                    user = result.data[0]

                    note = user.get(
                        "note_balance",
                        0
                    )

                    sikka = user.get(
                        "sikka_balance",
                        0
                    )

                    xp = user.get(
                        "xp",
                        0
                    )

                    level = user.get(
                        "level",
                        1
                    )

                    welcome = False


                # ==================================
                # MESSAGE
                # ==================================

                if welcome:

                    text = (
                        "🔥 MINE RUSH 🔥\n\n"
                        "🎉 Welcome to MINE RUSH!\n\n"
                        f"🪙 NOTE: {note}\n"
                        f"🪙 SIKKA: {sikka}\n"
                        f"⭐ Level: {level}\n"
                        f"⚡ XP: {xp}\n\n"
                        "Your account has been created! 🚀"
                    )

                else:

                    text = (
                        "🔥 MINE RUSH 🔥\n\n"
                        f"🪙 NOTE: {note}\n"
                        f"🪙 SIKKA: {sikka}\n"
                        f"⭐ Level: {level}\n"
                        f"⚡ XP: {xp}\n\n"
                        "Welcome back! 🚀"
                    )


                # Send Telegram message
                asyncio.run(
                    bot.send_message(
                        chat_id=telegram_id,
                        text=text
                    )
                )

                print("✅ START RESPONSE SENT")


        return "OK"


    except Exception as e:

        print("❌ WEBHOOK ERROR:")
        print(e)

        return "ERROR", 500


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
