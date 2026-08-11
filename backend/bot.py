import os
import threading

from flask import Flask, request
from supabase import create_client

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

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

application = (
    Application
    .builder()
    .token(TELEGRAM_BOT_TOKEN)
    .build()
)


@web.route("/")
def home():
    return "🔥 MINE RUSH BACKEND RUNNING"


@web.route("/health")
def health():
    return "OK"


# ==========================================
# TELEGRAM START
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    telegram_id = update.effective_user.id
    username = update.effective_user.username

    try:

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
                "🎉 Welcome to MINE RUSH!\n\n"
                "🪙 NOTE: 0\n"
                "🪙 SIKKA: 0\n"
                "⭐ Level: 1\n"
                "⚡ XP: 0\n\n"
                "Your account has been created!"
            )

        else:

            user = result.data[0]

            message = (
                "🔥 MINE RUSH 🔥\n\n"
                f"🪙 NOTE: {user.get('note_balance', 0)}\n"
                f"🪙 SIKKA: {user.get('sikka_balance', 0)}\n"
                f"⭐ Level: {user.get('level', 1)}\n"
                f"⚡ XP: {user.get('xp', 0)}\n\n"
                "Welcome back! 🚀"
            )

        await update.message.reply_text(message)

    except Exception as e:

        print("START ERROR:", e)

        await update.message.reply_text(
            "⚠️ Temporary error. Please try again."
        )


application.add_handler(
    CommandHandler("start", start)
)


# ==========================================
# TELEGRAM WEBHOOK
# ==========================================

@web.post("/telegram")
def telegram_webhook():

    try:

        update = Update.de_json(
            request.get_json(force=True),
            application.bot
        )

        application.update_queue.put_nowait(update)

        return "OK"

    except Exception as e:

        print("WEBHOOK ERROR:", e)

        return "ERROR", 500


# ==========================================
# START
# ==========================================

def run_web():

    port = int(os.getenv("PORT", "10000"))

    web.run(
        host="0.0.0.0",
        port=port
    )


if __name__ == "__main__":

    print("=================================")
    print("🔥 MINE RUSH WEBHOOK BOT")
    print("🗄️ SUPABASE CONNECTED")
    print("=================================")

    # Initialize Telegram application
    application.initialize()

    # Set Telegram webhook
    webhook_url = os.getenv(
        "RENDER_EXTERNAL_URL",
        ""
    ) + "/telegram"

    application.bot.set_webhook(
        url=webhook_url,
        drop_pending_updates=True
    )

    print("WEBHOOK:", webhook_url)

    # Start Flask
    run_web()
