import os
import threading

from flask import Flask
from supabase import create_client
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# =========================
# ENVIRONMENT VARIABLES
# =========================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing")

if not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is missing")


# =========================
# SUPABASE
# =========================

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY
)


# =========================
# WEB SERVER FOR RENDER
# =========================

web = Flask(__name__)


@web.route("/")
def home():
    return "MINE RUSH BACKEND RUNNING"


@web.route("/health")
def health():
    return "OK"


def run_web():
    port = int(os.getenv("PORT", "10000"))
    web.run(
        host="0.0.0.0",
        port=port
    )


# =========================
# TELEGRAM BOT
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    telegram_id = update.effective_user.id
    username = update.effective_user.username

    # Check whether user already exists
    result = (
        supabase
        .table("users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .execute()
    )

    if not result.data:

        supabase.table("users").insert({
            "telegram_id": telegram_id,
            "username": username,
            "note_balance": 0,
            "sikka_balance": 0,
            "xp": 0,
            "level": 1
        }).execute()

        message = (
            "🔥 MINE RUSH 🔥\n\n"
            "Welcome to MINE RUSH!\n\n"
            "🪙 NOTE: 0\n"
            "🪙 SIKKA: 0\n"
            "⭐ Level: 1\n\n"
            "Your account has been created."
        )

    else:

        user = result.data[0]

        message = (
            "🔥 MINE RUSH 🔥\n\n"
            f"🪙 NOTE: {user['note_balance']}\n"
            f"🪙 SIKKA: {user['sikka_balance']}\n"
            f"⭐ Level: {user['level']}\n\n"
            "MINE RUSH is ready."
        )

    await update.message.reply_text(message)


# =========================
# START BOT
# =========================

def run_bot():

    application = (
        Application
        .builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    print("MINE RUSH BOT STARTING...")

    application.run_polling()


# =========================
# MAIN
# =========================

if __name__ == "__main__":

    web_thread = threading.Thread(
        target=run_web,
        daemon=True
    )

    web_thread.start()

    print("MINE RUSH WEB SERVER STARTED")
    print("MINE RUSH BACKEND STARTED")

    run_bot()
