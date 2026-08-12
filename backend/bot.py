import os
import time
import secrets
import string
from datetime import datetime, timezone, timedelta

import requests
from flask import Flask, request, jsonify
from supabase import create_client, Client


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = (
    os.getenv("BOT_TOKEN")
    or os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("TELEGRAM_TOKEN")
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
)

PORT = int(os.getenv("PORT", "10000"))

APP_URL = os.getenv(
    "APP_URL",
    "https://mine-rush-bot.onrender.com/app"
)

WEBHOOK_URL = os.getenv(
    "WEBHOOK_URL",
    "https://mine-rush-bot.onrender.com/telegram"
)

MINING_HOURS = 4

# Default reward for one complete 4-hour mining session.
# You can later change this from Render Environment Variables.
MINING_BASE_REWARD = int(
    os.getenv("MINING_BASE_REWARD", "100")
)

DAILY_BONUS_SIKKA = int(
    os.getenv("DAILY_BONUS_SIKKA", "100")
)


# =========================================================
# APP
# =========================================================

app = Flask(__name__)


# =========================================================
# SUPABASE
# =========================================================

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing")

if not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is missing")

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY
)


# =========================================================
# TELEGRAM API
# =========================================================

TELEGRAM_API = (
    f"https://api.telegram.org/bot{BOT_TOKEN}"
    if BOT_TOKEN
    else None
)


def telegram(method, data=None):

    if not TELEGRAM_API:
        print("BOT TOKEN IS MISSING")
        return None

    try:

        response = requests.post(
            f"{TELEGRAM_API}/{method}",
            json=data or {},
            timeout=15
        )

        print(
            "TELEGRAM",
            method,
            response.status_code
        )

        try:
            return response.json()
        except Exception:
            return {
                "ok": False,
                "raw": response.text
            }

    except Exception as e:

        print(
            "TELEGRAM ERROR:",
            repr(e)
        )

        return None


def send_message(chat_id, text, keyboard=None):

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }

    if keyboard:
        payload["reply_markup"] = keyboard

    return telegram(
        "sendMessage",
        payload
    )


# =========================================================
# KEYBOARDS
# =========================================================

def main_keyboard():

    return {
        "inline_keyboard": [
            [
                {
                    "text": "🎮 PLAY MINE RUSH",
                    "web_app": {
                        "url": APP_URL
                    }
                }
            ],
            [
                {
                    "text": "📊 My Account",
                    "callback_data": "account"
                },
                {
                    "text": "🎁 Bonus",
                    "callback_data": "bonus"
                }
            ],
            [
                {
                    "text": "👥 Referral",
                    "callback_data": "referral"
                },
                {
                    "text": "🏆 Leaderboard",
                    "callback_data": "leaderboard"
                }
            ]
        ]
    }


# =========================================================
# HELPERS
# =========================================================

def now_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat()


def generate_referral_code():

    chars = string.ascii_uppercase + string.digits

    return "".join(
        secrets.choice(chars)
        for _ in range(8)
    )


def get_user_by_telegram(telegram_id):

    try:

        result = (
            supabase
            .table("users")
            .select("*")
            .eq("telegram_id", int(telegram_id))
            .limit(1)
            .execute()
        )

        if result.data:
            return result.data[0]

        return None

    except Exception as e:

        print(
            "GET USER ERROR:",
            repr(e)
        )

        return None


def get_user_by_id(user_id):

    try:

        result = (
            supabase
            .table("users")
            .select("*")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )

        if result.data:
            return result.data[0]

        return None

    except Exception as e:

        print(
            "GET USER ID ERROR:",
            repr(e)
        )

        return None


def get_user_from_init_data():

    """
    The frontend sends Telegram WebApp initData.

    For now we extract user information from the
    WebApp payload. Telegram launch happens inside
    the trusted Telegram Mini App.
    """

    import urllib.parse
    import json

    init_data = (
        request.form.get("init_data")
        or request.headers.get("X-Telegram-Init-Data")
        or ""
    )

    if not init_data:
        return None

    try:

        params = urllib.parse.parse_qs(
            init_data
        )

        user_values = params.get("user")

        if not user_values:
            return None

        telegram_user = json.loads(
            user_values[0]
        )

        telegram_id = telegram_user.get("id")

        if not telegram_id:
            return None

        return get_user_by_telegram(
            telegram_id
        )

    except Exception as e:

        print(
            "INIT DATA ERROR:",
            repr(e)
        )

        return None


def create_transaction(
    user_id,
    currency,
    amount,
    tx_type,
    description
):

    try:

        supabase.table(
            "transactions"
        ).insert({

            "user_id": user_id,
            "currency": currency,
            "amount": amount,
            "type": tx_type,
            "description": description

        }).execute()

        return True

    except Exception as e:

        print(
            "TRANSACTION ERROR:",
            repr(e)
        )

        return False


# =========================================================
# USER CREATION
# =========================================================

def create_user(
    telegram_user,
    referral_code=None
):

    telegram_id = int(
        telegram_user["id"]
    )

    username = telegram_user.get(
        "username"
    )

    first_name = telegram_user.get(
        "first_name",
        "Gamer"
    )

    existing = get_user_by_telegram(
        telegram_id
    )

    if existing:
        return existing


    new_referral_code = None

    for _ in range(10):

        candidate = generate_referral_code()

        try:

            check = (
                supabase
                .table("users")
                .select("id")
                .eq(
                    "referral_code",
                    candidate
                )
                .limit(1)
                .execute()
            )

            if not check.data:

                new_referral_code = candidate
                break

        except Exception:
            pass


    if not new_referral_code:
        new_referral_code = generate_referral_code()


    insert_data = {

        "telegram_id": telegram_id,

        "username": (
            username
            or first_name
        ),

        "note_balance": 0,

        "sikka_balance": 0,

        "xp": 0,

        "level": 1,

        "energy": 100,

        "boost_percent": 0,

        "mining_rate":
            MINING_BASE_REWARD,

        "pending_reward": 0,

        "referral_code":
            new_referral_code,

        "referral_count": 0,

        "total_mined": 0

    }


    # -----------------------------------------------------
    # Referral
    # -----------------------------------------------------

    referrer = None

    if referral_code:

        try:

            ref_result = (
                supabase
                .table("users")
                .select("*")
                .eq(
                    "referral_code",
                    referral_code.upper()
                )
                .limit(1)
                .execute()
            )

            if ref_result.data:

                referrer = ref_result.data[0]

                # Prevent self-referral
                if int(
                    referrer["telegram_id"]
                ) == telegram_id:

                    referrer = None

        except Exception as e:

            print(
                "REFERRAL LOOKUP ERROR:",
                repr(e)
            )


    if referrer:

        insert_data["referred_by"] = (
            referrer["id"]
        )


    # -----------------------------------------------------
    # Create user
    # -----------------------------------------------------

    try:

        result = (
            supabase
            .table("users")
            .insert(insert_data)
            .execute()
        )

        if not result.data:
            return None

        user = result.data[0]

    except Exception as e:

        print(
            "CREATE USER ERROR:",
            repr(e)
        )

        return None


    # -----------------------------------------------------
    # Referral reward
    # -----------------------------------------------------

    if referrer:

        try:

            referrer_sikka = float(
                referrer.get(
                    "sikka_balance",
                    0
                ) or 0
            )

            supabase.table(
                "users"
            ).update({

                "sikka_balance":
                    referrer_sikka + 50,

                "referral_count":
                    int(
                        referrer.get(
                            "referral_count",
                            0
                        ) or 0
                    ) + 1

            }).eq(
                "id",
                referrer["id"]
            ).execute()


            create_transaction(

                referrer["id"],

                "SIKKA",

                50,

                "referral",

                "Referral reward"

            )

        except Exception as e:

            print(
                "REFERRAL REWARD ERROR:",
                repr(e)
            )


    return user


# =========================================================
# USER SUMMARY
# =========================================================

def user_summary(user):

    note = float(
        user.get(
            "note_balance",
            0
        ) or 0
    )

    sikka = float(
        user.get(
            "sikka_balance",
            0
        ) or 0
    )

    xp = int(
        user.get(
            "xp",
            0
        ) or 0
    )

    level = int(
        user.get(
            "level",
            1
        ) or 1
    )

    energy = int(
        user.get(
            "energy",
            100
        ) or 0
    )

    boost = float(
        user.get(
            "boost_percent",
            0
        ) or 0
    )

    mining_rate = float(
        user.get(
            "mining_rate",
            MINING_BASE_REWARD
        ) or MINING_BASE_REWARD
    )

    started = user.get(
        "mining_started_at"
    )

    ends = user.get(
        "mining_ends_at"
    )

    mining_active = False
    mining_complete = False

    if started and ends:

        try:

            end_dt = datetime.fromisoformat(
                ends.replace(
                    "Z",
                    "+00:00"
                )
            )

            current = now_utc()

            if current < end_dt:

                mining_active = True

            else:

                mining_complete = True

        except Exception:
            pass


    return {

        "id": user.get("id"),

        "telegram_id":
            user.get("telegram_id"),

        "username":
            user.get("username"),

        "note":
            note,

        "sikka":
            sikka,

        "level":
            level,

        "xp":
            xp,

        "energy":
            energy,

        "boost":
            boost,

        "mining_rate":
            mining_rate,

        "mining_started_at":
            started,

        "mining_ends_at":
            ends,

        "pending_reward":
            float(
                user.get(
                    "pending_reward",
                    0
                ) or 0
            ),

        "mining_active":
            mining_active,

        "mining_complete":
            mining_complete,

        "referral_code":
            user.get(
                "referral_code"
            ),

        "referral_count":
            int(
                user.get(
                    "referral_count",
                    0
                ) or 0
            )

    }


# =========================================================
# TELEGRAM /start
# =========================================================

def handle_start(message):

    chat = message.get(
        "chat",
        {}
    )

    telegram_user = message.get(
        "from",
        {}
    )

    chat_id = chat.get(
        "id"
    )

    if not chat_id:
        return


    text = message.get(
        "text",
        ""
    )

    parts = text.split(
        maxsplit=1
    )

    referral_code = None

    if len(parts) > 1:

        referral_code = parts[1].strip()


    user = create_user(
        telegram_user,
        referral_code
    )


    if not user:

        send_message(
            chat_id,
            "⚠️ MINE RUSH server problem.\nPlease try again."
        )

        return


    summary = user_summary(
        user
    )


    message_text = (
        "🔥 <b>MINE RUSH</b> 🔥\n\n"

        f"🪙 NOTE: "
        f"<b>{summary['note']:.0f}</b>\n"

        f"🪙 SIKKA: "
        f"<b>{summary['sikka']:.0f}</b>\n"

        f"⭐ LEVEL: "
        f"<b>{summary['level']}</b>\n"

        f"⚡ XP: "
        f"<b>{summary['xp']}</b>\n\n"

        f"Welcome back, "
        f"<b>{telegram_user.get('first_name', 'Gamer')}</b>! 👋\n\n"

        "Your mining journey continues. ⛏️"
    )


    send_message(
        chat_id,
        message_text,
        main_keyboard()
    )


# =========================================================
# TELEGRAM WEBHOOK
# =========================================================

@app.route(
    "/telegram",
    methods=["POST"]
)
def telegram_webhook():

    try:

        update = request.get_json(
            silent=True
        ) or {}

        print(
            "TELEGRAM UPDATE:",
            update
        )


        # Message
        if update.get("message"):

            message = update[
                "message"
            ]

            text = message.get(
                "text",
                ""
            )

            if text.startswith(
                "/start"
            ):

                handle_start(
                    message
                )


        # Callback button
        if update.get(
            "callback_query"
        ):

            callback = update[
                "callback_query"
            ]

            callback_id = callback.get(
                "id"
            )

            data = callback.get(
                "data"
            )

            telegram_user = callback.get(
                "from",
                {}
            )

            user = get_user_by_telegram(
                telegram_user.get("id")
            )


            if callback_id:

                telegram(
                    "answerCallbackQuery",
                    {
                        "callback_query_id":
                            callback_id
                    }
                )


            if not user:
                return jsonify({
                    "ok": True
                })


            chat_id = callback[
                "message"
            ][
                "chat"
            ][
                "id"
            ]


            if data == "account":

                s = user_summary(
                    user
                )

                send_message(

                    chat_id,

                    "📊 <b>MY ACCOUNT</b>\n\n"

                    f"🪙 NOTE: "
                    f"{s['note']:.0f}\n"

                    f"🪙 SIKKA: "
                    f"{s['sikka']:.0f}\n"

                    f"⭐ LEVEL: "
                    f"{s['level']}\n"

                    f"⚡ XP: "
                    f"{s['xp']}\n\n"

                    f"👥 Referrals: "
                    f"{s['referral_count']}"
                )


            elif data == "bonus":

                claim_daily_bonus(
                    user,
                    chat_id
                )


            elif data == "referral":

                s = user_summary(
                    user
                )

                bot_info = telegram(
                    "getMe"
                )

                bot_username = "MINE_RUSH_BOT"

                if (
                    bot_info
                    and bot_info.get("ok")
                ):

                    bot_username = (
                        bot_info["result"]
                        ["username"]
                    )


                link = (
                    "https://t.me/"
                    + bot_username
                    + "?start="
                    + str(
                        s["referral_code"]
                    )
                )


                send_message(

                    chat_id,

                    "👥 <b>REFERRAL</b>\n\n"

                    f"Your code:\n"
                    f"<code>{s['referral_code']}</code>\n\n"

                    f"Invite friends:\n"
                    f"{link}\n\n"

                    "🎁 Earn 50 SIKKA "
                    "for each successful referral."
                )


            elif data == "leaderboard":

                send_leaderboard(
                    chat_id
                )


        return jsonify({
            "ok": True
        })


    except Exception as e:

        print(
            "WEBHOOK ERROR:",
            repr(e)
        )

        return jsonify({
            "ok": True
        })


# =========================================================
# HEALTH
# =========================================================

@app.route(
    "/health",
    methods=["GET"]
)
def health():

    return jsonify({

        "ok": True,

        "service":
            "MINE RUSH",

        "status":
            "running"

    })


@app.route(
    "/",
    methods=["GET"]
)
def home():

    return jsonify({

        "service":
            "MINE RUSH",

        "status":
            "online",

        "mini_app":
            "/app"

    })


# =========================================================
# MINI APP
# =========================================================

@app.route(
    "/app",
    methods=["GET"]
)
def mini_app():

    # Render serves the root index.html.
    # This route allows Telegram to open /app.
    try:

        with open(
            os.path.join(
                os.path.dirname(
                    os.path.dirname(
                        os.path.abspath(
                            __file__
                        )
                    )
                ),
                "index.html"
            ),
            "r",
            encoding="utf-8"
        ) as f:

            return f.read()

    except Exception as e:

        print(
            "APP FILE ERROR:",
            repr(e)
        )

        return (
            "<h1>MINE RUSH</h1>"
            "<p>Mini App file not found.</p>"
        ), 404


# =========================================================
# API: ME
# =========================================================

@app.route(
    "/api/me",
    methods=["POST"]
)
def api_me():

    try:

        user = get_user_from_init_data()

        if not user:

            return jsonify({

                "ok": False,

                "error":
                    "Telegram user not found"

            }), 401


        # Auto-complete mining state
        user = settle_completed_mining(
            user
        )


        return jsonify({

            "ok": True,

            "user":
                user_summary(user)

        })


    except Exception as e:

        print(
            "API ME ERROR:",
            repr(e)
        )

        return jsonify({

            "ok": False,

            "error":
                "Server error"

        }), 500


# =========================================================
# MINING STATE
# =========================================================

def settle_completed_mining(user):

    started = user.get(
        "mining_started_at"
    )

    ends = user.get(
        "mining_ends_at"
    )

    if not started or not ends:

        return user


    try:

        end_dt = datetime.fromisoformat(
            ends.replace(
                "Z",
                "+00:00"
            )
        )

    except Exception:

        return user


    if now_utc() < end_dt:

        return user


    # Already claimed?
    pending = float(
        user.get(
            "pending_reward",
            0
        ) or 0
    )

    if pending > 0:

        return user


    rate = float(
        user.get(
            "mining_rate",
            MINING_BASE_REWARD
        ) or MINING_BASE_REWARD
    )

    boost = float(
        user.get(
            "boost_percent",
            0
        ) or 0
    )

    reward = rate * (
        1 + boost / 100
    )


    try:

        updated = (
            supabase
            .table("users")
            .update({

                "pending_reward":
                    reward

            })
            .eq(
                "id",
                user["id"]
            )
            .execute()
        )


        if updated.data:

            return updated.data[0]


    except Exception as e:

        print(
            "SETTLE ERROR:",
            repr(e)
        )


    return user


# =========================================================
# START MINING
# =========================================================

@app.route(
    "/api/mining/start",
    methods=["POST"]
)
def api_start_mining():

    try:

        user = get_user_from_init_data()

        if not user:

            return jsonify({
                "ok": False,
                "error":
                    "Unauthorized"
            }), 401


        user = settle_completed_mining(
            user
        )


        # Existing active mining
        started = user.get(
            "mining_started_at"
        )

        ends = user.get(
            "mining_ends_at"
        )


        if started and ends:

            try:

                end_dt = datetime.fromisoformat(
                    ends.replace(
                        "Z",
                        "+00:00"
                    )
                )

                if now_utc() < end_dt:

                    return jsonify({

                        "ok": False,

                        "error":
                            "Mining already active",

                        "user":
                            user_summary(user)

                    }), 400

            except Exception:
                pass


        # Pending reward must be claimed first
        pending = float(
            user.get(
                "pending_reward",
                0
            ) or 0
        )

        if pending > 0:

            return jsonify({

                "ok": False,

                "error":
                    "Claim your previous reward first"

            }), 400


        start = now_utc()

        end = (
            start
            + timedelta(
                hours=MINING_HOURS
            )
        )


        result = (
            supabase
            .table("users")
            .update({

                "mining_started_at":
                    iso(start),

                "mining_ends_at":
                    iso(end),

                "pending_reward":
                    0

            })
            .eq(
                "id",
                user["id"]
            )
            .execute()
        )


        if not result.data:

            return jsonify({

                "ok": False,

                "error":
                    "Unable to start mining"

            }), 500


        updated_user = result.data[0]


        return jsonify({

            "ok": True,

            "message":
                "Mining started",

            "user":
                user_summary(
                    updated_user
                )

        })


    except Exception as e:

        print(
            "START MINING ERROR:",
            repr(e)
        )

        return jsonify({

            "ok": False,

            "error":
                "Server error"

        }), 500


# =========================================================
# CLAIM MINING
# =========================================================

@app.route(
    "/api/mining/claim",
    methods=["POST"]
)
def api_claim_mining():

    try:

        user = get_user_from_init_data()

        if not user:

            return jsonify({

                "ok": False,

                "error":
                    "Unauthorized"

            }), 401


        user = settle_completed_mining(
            user
        )


        ends = user.get(
            "mining_ends_at"
        )


        if not ends:

            return jsonify({

                "ok": False,

                "error":
                    "No mining session"

            }), 400


        try:

            end_dt = datetime.fromisoformat(
                ends.replace(
                    "Z",
                    "+00:00"
                )
            )

        except Exception:

            return jsonify({

                "ok": False,

                "error":
                    "Invalid mining timer"

            }), 400


        if now_utc() < end_dt:

            remaining = int(
                (
                    end_dt
                    - now_utc()
                ).total_seconds()
            )

            return jsonify({

                "ok": False,

                "error":
                    "Mining is not complete",

                "remaining":
                    remaining

            }), 400


        reward = float(
            user.get(
                "pending_reward",
                0
            ) or 0
        )


        if reward <= 0:

            # Safety calculation
            rate = float(
                user.get(
                    "mining_rate",
                    MINING_BASE_REWARD
                ) or MINING_BASE_REWARD
            )

            boost = float(
                user.get(
                    "boost_percent",
                    0
                ) or 0
            )

            reward = rate * (
                1 + boost / 100
            )


        old_note = float(
            user.get(
                "note_balance",
                0
            ) or 0
        )

        old_total = float(
            user.get(
                "total_mined",
                0
            ) or 0
        )

        new_note = (
            old_note
            + reward
        )

        new_total = (
            old_total
            + reward
        )


        # XP
        old_xp = int(
            user.get(
                "xp",
                0
            ) or 0
        )

        old_level = int(
            user.get(
                "level",
                1
            ) or 1
        )

        new_xp = (
            old_xp
            + int(reward)
        )

        new_level = (
            new_xp // 1000
        ) + 1


        result = (
            supabase
            .table("users")
            .update({

                "note_balance":
                    new_note,

                "total_mined":
                    new_total,

                "xp":
                    new_xp,

                "level":
                    new_level,

                "pending_reward":
                    0,

                "mining_started_at":
                    None,

                "mining_ends_at":
                    None

            })
            .eq(
                "id",
                user["id"]
            )
            .execute()
        )


        if not result.data:

            return jsonify({

                "ok": False,

                "error":
                    "Could not claim reward"

            }), 500


        create_transaction(

            user["id"],

            "NOTE",

            reward,

            "mining",

            "4-hour mining reward"

        )


        updated = result.data[0]


        return jsonify({

            "ok": True,

            "reward":
                reward,

            "level":
                new_level,

            "user":
                user_summary(updated)

        })


    except Exception as e:

        print(
            "CLAIM ERROR:",
            repr(e)
        )

        return jsonify({

            "ok": False,

            "error":
                "Server error"

        }), 500


# =========================================================
# DAILY BONUS
# =========================================================

def claim_daily_bonus(
    user,
    chat_id=None
):

    last = user.get(
        "last_bonus_at"
    )

    if last:

        try:

            last_dt = datetime.fromisoformat(
                last.replace(
                    "Z",
                    "+00:00"
                )
            )

            if (
                now_utc()
                - last_dt
            ).total_seconds() < 86400:

                if chat_id:

                    send_message(

                        chat_id,

                        "🎁 <b>DAILY BONUS</b>\n\n"
                        "You already claimed today's bonus.\n"
                        "Come back tomorrow! ⏰"

                    )

                return False

        except Exception:
            pass


    old_sikka = float(
        user.get(
            "sikka_balance",
            0
        ) or 0
    )


    new_sikka = (
        old_sikka
        + DAILY_BONUS_SIKKA
    )


    try:

        result = (
            supabase
            .table("users")
            .update({

                "sikka_balance":
                    new_sikka,

                "last_bonus_at":
                    iso(now_utc())

            })
            .eq(
                "id",
                user["id"]
            )
            .execute()
        )


        create_transaction(

            user["id"],

            "SIKKA",

            DAILY_BONUS_SIKKA,

            "daily_bonus",

            "Daily bonus"

        )


        if chat_id:

            send_message(

                chat_id,

                "🎁 <b>DAILY BONUS</b>\n\n"
                f"Congratulations! 🎉\n\n"
                f"+{DAILY_BONUS_SIKKA} SIKKA 🪙"

            )


        return bool(
            result.data
        )


    except Exception as e:

        print(
            "BONUS ERROR:",
            repr(e)
        )

        return False


@app.route(
    "/api/bonus",
    methods=["POST"]
)
def api_bonus():

    try:

        user = get_user_from_init_data()

        if not user:

            return jsonify({

                "ok": False,

                "error":
                    "Unauthorized"

            }), 401


        old_sikka = float(
            user.get(
                "sikka_balance",
                0
            ) or 0
        )


        last = user.get(
            "last_bonus_at"
        )

        if last:

            try:

                last_dt = datetime.fromisoformat(
                    last.replace(
                        "Z",
                        "+00:00"
                    )
                )

                seconds = (
                    now_utc()
                    - last_dt
                ).total_seconds()

                if seconds < 86400:

                    return jsonify({

                        "ok": False,

                        "error":
                            "Bonus already claimed",

                        "next_in":
                            int(
                                86400
                                - seconds
                            )

                    }), 400

            except Exception:
                pass


        new_sikka = (
            old_sikka
            + DAILY_BONUS_SIKKA
        )


        result = (
            supabase
            .table("users")
            .update({

                "sikka_balance":
                    new_sikka,

                "last_bonus_at":
                    iso(now_utc())

            })
            .eq(
                "id",
                user["id"]
            )
            .execute()
        )


        create_transaction(

            user["id"],

            "SIKKA",

            DAILY_BONUS_SIKKA,

            "daily_bonus",

            "Daily bonus"

        )


        return jsonify({

            "ok": True,

            "reward":
                DAILY_BONUS_SIKKA,

            "user":
                user_summary(
                    result.data[0]
                )

        })


    except Exception as e:

        print(
            "API BONUS ERROR:",
            repr(e)
        )

        return jsonify({

            "ok": False,

            "error":
                "Server error"

        }), 500


# =========================================================
# REFERRAL
# =========================================================

@app.route(
    "/api/referral",
    methods=["POST"]
)
def api_referral():

    try:

        user = get_user_from_init_data()

        if not user:

            return jsonify({

                "ok": False

            }), 401


        bot_info = telegram(
            "getMe"
        )

        bot_username = (
            "MINE_RUSH_BOT"
        )

        if (
            bot_info
            and bot_info.get("ok")
        ):

            bot_username = (
                bot_info["result"]
                ["username"]
            )


        code = user.get(
            "referral_code"
        )


        link = (
            "https://t.me/"
            + bot_username
            + "?start="
            + str(code)
        )


        return jsonify({

            "ok": True,

            "code":
                code,

            "link":
                link,

            "count":
                int(
                    user.get(
                        "referral_count",
                        0
                    ) or 0
                )

        })


    except Exception as e:

        print(
            "REFERRAL API ERROR:",
            repr(e)
        )

        return jsonify({

            "ok": False

        }), 500


# =========================================================
# LEADERBOARD
# =========================================================

def get_leaderboard():

    try:

        result = (
            supabase
            .table("users")
            .select(
                "username,note_balance,level"
            )
            .order(
                "note_balance",
                desc=True
            )
            .limit(20)
            .execute()
        )

        return result.data or []

    except Exception as e:

        print(
            "LEADERBOARD ERROR:",
            repr(e)
        )

        return []


def send_leaderboard(chat_id):

    rows = get_leaderboard()

    if not rows:

        send_message(
            chat_id,
            "🏆 Leaderboard is empty."
        )

        return


    text = (
        "🏆 <b>MINE RUSH LEADERBOARD</b>\n\n"
    )


    for i, row in enumerate(
        rows,
        start=1
    ):

        name = (
            row.get(
                "username"
            )
            or "Gamer"
        )

        note = float(
            row.get(
                "note_balance",
                0
            ) or 0
        )

        level = int(
            row.get(
                "level",
                1
            ) or 1
        )


        medal = "🔹"

        if i == 1:
            medal = "🥇"

        elif i == 2:
            medal = "🥈"

        elif i == 3:
            medal = "🥉"


        text += (
            f"{medal} "
            f"<b>{i}.</b> "
            f"{name} — "
            f"{note:.0f} NOTE "
            f"(LV {level})\n"
        )


    send_message(
        chat_id,
        text
    )


@app.route(
    "/api/leaderboard",
    methods=["POST"]
)
def api_leaderboard():

    try:

        user = get_user_from_init_data()

        if not user:

            return jsonify({

                "ok": False

            }), 401


        rows = get_leaderboard()

        return jsonify({

            "ok": True,

            "leaderboard":
                rows

        })


    except Exception as e:

        print(
            "API LEADERBOARD ERROR:",
            repr(e)
        )

        return jsonify({

            "ok": False

        }), 500


# =========================================================
# WALLET
# =========================================================

@app.route(
    "/api/wallet",
    methods=["POST"]
)
def api_wallet():

    try:

        user = get_user_from_init_data()

        if not user:

            return jsonify({

                "ok": False

            }), 401


        transactions = (

            supabase
            .table("transactions")
            .select("*")
            .eq(
                "user_id",
                user["id"]
            )
            .order(
                "created_at",
                desc=True
            )
            .limit(50)
            .execute()
        )


        withdrawals = (

            supabase
            .table("withdrawals")
            .select("*")
            .eq(
                "user_id",
                user["id"]
            )
            .order(
                "created_at",
                desc=True
            )
            .limit(20)
            .execute()
        )


        return jsonify({

            "ok": True,

            "user":
                user_summary(user),

            "transactions":
                transactions.data or [],

            "withdrawals":
                withdrawals.data or []

        })


    except Exception as e:

        print(
            "WALLET ERROR:",
            repr(e)
        )

        return jsonify({

            "ok": False,

            "error":
                "Server error"

        }), 500


# =========================================================
# WITHDRAW
# =========================================================

@app.route(
    "/api/withdraw",
    methods=["POST"]
)
def api_withdraw():

    try:

        user = get_user_from_init_data()

        if not user:

            return jsonify({

                "ok": False,

                "error":
                    "Unauthorized"

            }), 401


        data = request.get_json(
            silent=True
        ) or {}


        amount = float(
            data.get(
                "amount",
                0
            )
        )

        method = str(
            data.get(
                "method",
                ""
            )
        ).strip()

        payment_details = str(
            data.get(
                "payment_details",
                ""
            )
        ).strip()


        if amount <= 0:

            return jsonify({

                "ok": False,

                "error":
                    "Invalid amount"

            }), 400


        if not method:

            return jsonify({

                "ok": False,

                "error":
                    "Payment method required"

            }), 400


        if not payment_details:

            return jsonify({

                "ok": False,

                "error":
                    "Payment details required"

            }), 400


        note_balance = float(
            user.get(
                "note_balance",
                0
            ) or 0
        )


        if amount > note_balance:

            return jsonify({

                "ok": False,

                "error":
                    "Insufficient NOTE balance"

            }), 400


        # 10,000 NOTE = ₹1
        inr_amount = (
            amount / 10000
        )


        if inr_amount < 1:

            return jsonify({

                "ok": False,

                "error":
                    "Minimum withdrawal is ₹1"

            }), 400


        new_balance = (
            note_balance
            - amount
        )


        update_result = (

            supabase
            .table("users")
            .update({

                "note_balance":
                    new_balance

            })
            .eq(
                "id",
                user["id"]
            )
            .execute()
        )


        if not update_result.data:

            return jsonify({

                "ok": False,

                "error":
                    "Could not process withdrawal"

            }), 500


        withdrawal = (

            supabase
            .table("withdrawals")
            .insert({

                "user_id":
                    user["id"],

                "note_amount":
                    amount,

                "inr_amount":
                    inr_amount,

                "payment_method":
                    method,

                "payment_details":
                    payment_details,

                "status":
                    "pending"

            })
            .execute()
        )


        create_transaction(

            user["id"],

            "NOTE",

            -amount,

            "withdrawal",

            "Withdrawal request"

        )


        return jsonify({

            "ok": True,

            "message":
                "Withdrawal request submitted",

            "amount":
                amount,

            "rupees":
                inr_amount,

            "status":
                "pending",

            "user":
                user_summary(
                    update_result.data[0]
                )

        })


    except Exception as e:

        print(
            "WITHDRAW ERROR:",
            repr(e)
        )

        return jsonify({

            "ok": False,

            "error":
                "Server error"

        }), 500


# =========================================================
# TELEGRAM WEBHOOK SETUP
# =========================================================

def setup_webhook():

    if not BOT_TOKEN:

        print(
            "⚠️ BOT TOKEN MISSING"
        )

        return


    print(
        "Setting Telegram webhook..."
    )


    result = telegram(

        "setWebhook",

        {
            "url":
                WEBHOOK_URL,

            "allowed_updates": [
                "message",
                "callback_query"
            ],

            "drop_pending_updates":
                False

        }

    )


    print(
        "WEBHOOK RESULT:",
        result
    )


# =========================================================
# STARTUP
# =========================================================

print(
    "================================"
)

print(
    "🔥 MINE RUSH BACKEND STARTING"
)

print(
    "================================"
)

print(
    "APP URL:",
    APP_URL
)

print(
    "WEBHOOK:",
    WEBHOOK_URL
)

print(
    "MINING:",
    f"{MINING_HOURS} HOURS"
)

print(
    "REWARD:",
    MINING_BASE_REWARD,
    "NOTE"
)

setup_webhook()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False
    )
