import os
import threading

from flask import Flask
from supabase import create_client
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


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
# RENDER WEB SERVER
# ==========================================

web = Flask(__name__)


@web.route("/")
def home():
    return "🔥 MINE RUSH BACKEND RUNNING"


@web.route("/health")
def health():
    return "OK"


def run_web():
    port = int(os.getenv("PORT", "10000"))

    web.run(
        host="0.0.0.0",
        port=port
    )


# ==========================================
# TELEGRAM /START
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.effective_user:
        return

    telegram_id = update.effective_user.id
    username = update.effective_user.username

    try:

        # Check existing user
        result = (
            supabase
            .table("users")
            .select("*")
            .eq("telegram_id", telegram_id)
            .execute()
        )

        # ==================================
        # NEW USER
        # ==================================

        if not result.data:

            new_user = {
                "telegram_id": telegram_id,
                "username": username,
                "note_balance": 0,
                "sikka_balance": 0,
                "xp": 0,
                "level": 1
            }

            supabase \
                .table("users") \
                .insert(new_user) \
                .execute()

            message = (
                "🔥 MINE RUSH 🔥\n\n"
                "🎉 Welcome to MINE RUSH!\n\n"
                "🪙 NOTE: 0\n"
                "🪙 SIKKA: 0\n"
                "⭐ Level: 1\n"
                "⚡ XP: 0\n\n"
                "Your account has been created successfully."
            )

        # ==================================
        # EXISTING USER
        # ==================================

        else:

            user = result.data[0]

            note = user.get("note_balance", 0)
            sikka = user.get("sikka_balance", 0)
            level = user.get("level", 1)
            xp = user.get("xp", 0)

            message = (
                "🔥 MINE RUSH 🔥\n\n"
                f"🪙 NOTE: {note}\n"
                f"🪙 SIKKA: {sikka}\n"
                f"⭐ Level: {level}\n"
                f"⚡ XP: {xp}\n\n"
                "Welcome back! 🚀"
            )

        await update.message.reply_text(message)

    except Exception as e:

        print("START ERROR:", e)

        await update.message.reply_text(
            "⚠️ MINE RUSH mein temporary problem aa gayi.\n"
            "Thodi der baad dobara /start bhejo."
        )


# ==========================================
# TELEGRAM BOT
# ==========================================

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

    print("=================================")
    print("🔥 MINE RUSH BOT STARTING...")
    print("📡 TELEGRAM POLLING STARTING...")
    print("🗄️ SUPABASE CONNECTED")
    print("=================================")

    # Remove old webhook and pending updates,
    # then start polling.
    application.run_polling(
        drop_pending_updates=True
    )


# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":

    print("Starting MINE RUSH backend...")

    # Start Render web server
    web_thread = threading.Thread(
        target=run_web,
        daemon=True
    )

    web_thread.start()

    print("🌐 WEB SERVER STARTED")

    # Start Telegram bot
    run_bot()
