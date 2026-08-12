import os
import string
import secrets
import urllib.parse
import json
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

MINING_REWARD = int(
    os.getenv("MINING_BASE_REWARD", "100")
)

DAILY_BONUS = int(
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
    raise RuntimeError("SUPABASE_URL missing")

if not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError(
        "SUPABASE_SERVICE_ROLE_KEY missing"
    )

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY
)


# =========================================================
# TELEGRAM
# =========================================================

TELEGRAM_API = (
    f"https://api.telegram.org/bot{BOT_TOKEN}"
    if BOT_TOKEN else None
)


def telegram(method, data=None):

    if not TELEGRAM_API:
        print("BOT TOKEN MISSING")
        return None

    try:

        r = requests.post(
            f"{TELEGRAM_API}/{method}",
            json=data or {},
            timeout=20
        )

        try:
            return r.json()
        except Exception:
            return {
                "ok": False,
                "raw": r.text
            }

    except Exception as e:

        print(
            "TELEGRAM ERROR:",
            repr(e)
        )

        return None


def send_message(
    chat_id,
    text,
    keyboard=None
):

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
# HELPERS
# =========================================================

def now_utc():

    return datetime.now(
        timezone.utc
    )


def iso(dt):

    return dt.isoformat()


def generate_referral_code():

    chars = (
        string.ascii_uppercase
        + string.digits
    )

    return "".join(
        secrets.choice(chars)
        for _ in range(8)
    )


# =========================================================
# REFERRAL CODE
# IMPORTANT:
# ALSO FIXES OLD USERS WHO HAVE NULL CODE
# =========================================================

def ensure_referral_code(user):

    current = user.get(
        "referral_code"
    )

    if current:
        return user

    for _ in range(20):

        code = generate_referral_code()

        try:

            check = (
                supabase
                .table("users")
                .select("id")
                .eq(
                    "referral_code",
                    code
                )
                .limit(1)
                .execute()
            )

            if check.data:
                continue


            result = (
                supabase
                .table("users")
                .update({
                    "referral_code":
                        code
                })
                .eq(
                    "id",
                    user["id"]
                )
                .execute()
            )

            if result.data:

                return result.data[0]

        except Exception as e:

            print(
                "REFERRAL CODE ERROR:",
                repr(e)
            )

            break

    return user


# =========================================================
# USER
# =========================================================

def get_user_by_telegram(
    telegram_id
):

    try:

        result = (
            supabase
            .table("users")
            .select("*")
            .eq(
                "telegram_id",
                int(telegram_id)
            )
            .limit(1)
            .execute()
        )

        if not result.data:
            return None

        user = result.data[0]

        # FIX OLD USERS
        user = ensure_referral_code(
            user
        )

        return user

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
            .eq(
                "id",
                user_id
            )
            .limit(1)
            .execute()
        )

        if not result.data:
            return None

        return ensure_referral_code(
            result.data[0]
        )

    except Exception as e:

        print(
            "GET USER ID ERROR:",
            repr(e)
        )

        return None


# =========================================================
# CREATE USER
# =========================================================

def create_user(
    telegram_user,
    referral_code=None
):

    telegram_id = int(
        telegram_user["id"]
    )

    username = (
        telegram_user.get(
            "username"
        )
        or telegram_user.get(
            "first_name"
        )
        or "Gamer"
    )


    # Existing user
    existing = get_user_by_telegram(
        telegram_id
    )

    if existing:

        return existing


    # New referral code
    my_code = None

    for _ in range(20):

        candidate = (
            generate_referral_code()
        )

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

                my_code = candidate
                break

        except Exception:
            pass


    if not my_code:

        my_code = generate_referral_code()


    insert_data = {

        "telegram_id":
            telegram_id,

        "username":
            username,

        "note_balance":
            0,

        "sikka_balance":
            0,

        "xp":
            0,

        "level":
            1,

        "energy":
            100,

        "boost_percent":
            0,

        "mining_rate":
            MINING_REWARD,

        "pending_reward":
            0,

        "referral_code":
            my_code,

        "referral_count":
            0,

        "total_mined":
            0

    }


    # =====================================================
    # REFERRER
    # =====================================================

    referrer = None

    if referral_code:

        try:

            ref = (
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

            if ref.data:

                referrer = ref.data[0]

                if int(
                    referrer["telegram_id"]
                ) == telegram_id:

                    referrer = None

        except Exception as e:

            print(
                "REFERRER ERROR:",
                repr(e)
            )


    if referrer:

        insert_data[
            "referred_by"
        ] = referrer["id"]


    # =====================================================
    # INSERT
    # =====================================================

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


    # =====================================================
    # REFERRAL REWARD
    # =====================================================

    if referrer:

        try:

            old_sikka = float(
                referrer.get(
                    "sikka_balance",
                    0
                ) or 0
            )

            old_count = int(
                referrer.get(
                    "referral_count",
                    0
                ) or 0
            )


            supabase.table(
                "users"
            ).update({

                "sikka_balance":
                    old_sikka + 50,

                "referral_count":
                    old_count + 1

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
# TRANSACTION
# =========================================================

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

            "user_id":
                user_id,

            "currency":
                currency,

            "amount":
                amount,

            "type":
                tx_type,

            "description":
                description

        }).execute()

        return True

    except Exception as e:

        print(
            "TRANSACTION ERROR:",
            repr(e)
        )

        return False


# =========================================================
# TELEGRAM KEYBOARD
# =========================================================

def main_keyboard():

    return {

        "inline_keyboard": [

            [
                {
                    "text":
                        "🎮 PLAY MINE RUSH",

                    "web_app": {
                        "url": APP_URL
                    }
                }
            ],

            [
                {
                    "text":
                        "📊 My Account",

                    "callback_data":
                        "account"
                },

                {
                    "text":
                        "🎁 Bonus",

                    "callback_data":
                        "bonus"
                }
            ],

            [
                {
                    "text":
                        "👥 Referral",

                    "callback_data":
                        "referral"
                },

                {
                    "text":
                        "🏆 Leaderboard",

                    "callback_data":
                        "leaderboard"
                }
            ]

        ]

    }


# =========================================================
# USER SUMMARY
# =========================================================

def user_summary(user):

    return {

        "id":
            user.get("id"),

        "telegram_id":
            user.get("telegram_id"),

        "username":
            user.get("username"),

        "note":
            float(
                user.get(
                    "note_balance",
                    0
                ) or 0
            ),

        "sikka":
            float(
                user.get(
                    "sikka_balance",
                    0
                ) or 0
            ),

        "xp":
            int(
                user.get(
                    "xp",
                    0
                ) or 0
            ),

        "level":
            int(
                user.get(
                    "level",
                    1
                ) or 1
            ),

        "energy":
            int(
                user.get(
                    "energy",
                    100
                ) or 100
            ),

        "boost":
            float(
                user.get(
                    "boost_percent",
                    0
                ) or 0
            ),

        "mining_rate":
            float(
                user.get(
                    "mining_rate",
                    MINING_REWARD
                )
                or MINING_REWARD
            ),

        "mining_started_at":
            user.get(
                "mining_started_at"
            ),

        "mining_ends_at":
            user.get(
                "mining_ends_at"
            ),

        "pending_reward":
            float(
                user.get(
                    "pending_reward",
                    0
                ) or 0
            ),

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
# TELEGRAM START
# =========================================================

def handle_start(message):

    chat_id = (
        message
        .get("chat", {})
        .get("id")
    )

    telegram_user = (
        message
        .get("from", {})
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

        referral_code = (
            parts[1].strip()
        )


    user = create_user(
        telegram_user,
        referral_code
    )

    if not user:

        send_message(
            chat_id,
            "⚠️ Server error. Please try again."
        )

        return


    s = user_summary(user)


    text = (
        "🔥 <b>MINE RUSH</b> 🔥\n\n"

        f"⚫ NOTE: <b>{s['note']:.0f}</b>\n"

        f"⚫ SIKKA: <b>{s['sikka']:.0f}</b>\n"

        f"⭐ LEVEL: <b>{s['level']}</b>\n"

        f"⚡ XP: <b>{s['xp']}</b>\n\n"

        f"Welcome back, "
        f"<b>{telegram_user.get('first_name', 'Gamer')}</b>! 👋\n\n"

        "Your mining journey continues. ⛏️"
    )


    send_message(
        chat_id,
        text,
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

        update = (
            request.get_json(
                silent=True
            )
            or {}
        )


        # MESSAGE
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


        # CALLBACK
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

            tg_user = callback.get(
                "from",
                {}
            )

            user = get_user_by_telegram(
                tg_user.get("id")
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


            chat_id = (
                callback
                .get("message", {})
                .get("chat", {})
                .get("id")
            )


            if data == "account":

                s = user_summary(user)

                send_message(

                    chat_id,

                    "📊 <b>MY ACCOUNT</b>\n\n"

                    f"⚫ NOTE: {s['note']:.0f}\n"

                    f"⚫ SIKKA: {s['sikka']:.0f}\n"

                    f"⭐ LEVEL: {s['level']}\n"

                    f"⚡ XP: {s['xp']}\n\n"

                    f"👥 Referrals: "
                    f"{s['referral_count']}"
                )


            elif data == "bonus":

                claim_bonus(
                    user,
                    chat_id
                )


            elif data == "referral":

                s = user_summary(user)

                bot = telegram(
                    "getMe"
                )

                bot_username = (
                    "MineRushGameBot"
                )

                if (
                    bot
                    and bot.get("ok")
                ):

                    bot_username = (
                        bot["result"]
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
                    "for every successful referral."
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
# INIT DATA
# =========================================================

def get_user_from_init_data():

    init_data = (
        request.headers.get(
            "X-Telegram-Init-Data"
        )
        or request.form.get(
            "init_data"
        )
        or ""
    )


    if not init_data:
        return None


    try:

        params = (
            urllib.parse
            .parse_qs(init_data)
        )

        values = params.get(
            "user"
        )

        if not values:
            return None

        tg_user = json.loads(
            values[0]
        )

        telegram_id = tg_user.get(
            "id"
        )

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


# =========================================================
# HEALTH
# =========================================================

@app.route("/")
def home():

    return jsonify({

        "service":
            "MINE RUSH",

        "status":
            "online",

        "app":
            APP_URL

    })


@app.route("/health")
def health():

    return jsonify({
        "ok": True
    })


# =========================================================
# MINI APP
# =========================================================

@app.route("/app")
def app_page():

    try:

        root = os.path.dirname(
            os.path.dirname(
                os.path.abspath(
                    __file__
                )
            )
        )

        path = os.path.join(
            root,
            "index.html"
        )


        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            return f.read()


    except Exception as e:

        print(
            "INDEX ERROR:",
            repr(e)
        )

        return (
            "<h1>MINE RUSH</h1>"
            "<p>index.html not found</p>"
        ), 404


# =========================================================
# API ME
# =========================================================

@app.route(
    "/api/me",
    methods=["POST"]
)
def api_me():

    user = get_user_from_init_data()

    if not user:

        return jsonify({

            "ok": False,

            "error":
                "Telegram user not found"

        }), 401


    user = settle_mining(
        user
    )


    return jsonify({

        "ok": True,

        "user":
            user_summary(user)

    })


# =========================================================
# MINING SETTLEMENT
# =========================================================

def settle_mining(user):

    ends = user.get(
        "mining_ends_at"
    )

    if not ends:
        return user


    try:

        end = datetime.fromisoformat(
            ends.replace(
                "Z",
                "+00:00"
            )
        )

    except Exception:

        return user


    if now_utc() < end:
        return user


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
            MINING_REWARD
        ) or MINING_REWARD
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

        result = (
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


        if result.data:
            return result.data[0]


    except Exception as e:

        print(
            "SETTLE MINING ERROR:",
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
def start_mining():

    user = get_user_from_init_data()

    if not user:

        return jsonify({
            "ok": False,
            "error": "Unauthorized"
        }), 401


    user = settle_mining(user)


    if user.get(
        "pending_reward",
        0
    ):

        return jsonify({

            "ok": False,

            "error":
                "Claim previous reward first"

        }), 400


    ends = user.get(
        "mining_ends_at"
    )


    if ends:

        try:

            end = datetime.fromisoformat(
                ends.replace(
                    "Z",
                    "+00:00"
                )
            )

            if now_utc() < end:

                return jsonify({

                    "ok": False,

                    "error":
                        "Mining already active",

                    "user":
                        user_summary(user)

                }), 400

        except Exception:
            pass


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
                "Could not start mining"

        }), 500


    return jsonify({

        "ok": True,

        "user":
            user_summary(
                result.data[0]
            )

    })


# =========================================================
# CLAIM
# =========================================================

@app.route(
    "/api/mining/claim",
    methods=["POST"]
)
def claim_mining():

    user = get_user_from_init_data()

    if not user:

        return jsonify({
            "ok": False
        }), 401


    user = settle_mining(
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


    end = datetime.fromisoformat(
        ends.replace(
            "Z",
            "+00:00"
        )
    )


    if now_utc() < end:

        return jsonify({

            "ok": False,

            "error":
                "Mining not completed"

        }), 400


    reward = float(
        user.get(
            "pending_reward",
            0
        ) or 0
    )


    if reward <= 0:

        reward = float(
            user.get(
                "mining_rate",
                MINING_REWARD
            )
            or MINING_REWARD
        )


    old_note = float(
        user.get(
            "note_balance",
            0
        ) or 0
    )


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


    new_note = (
        old_note + reward
    )

    new_xp = (
        old_xp + int(reward)
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
            "ok": False
        }), 500


    create_transaction(

        user["id"],

        "NOTE",

        reward,

        "mining",

        "4 hour mining reward"

    )


    return jsonify({

        "ok": True,

        "reward":
            reward,

        "user":
            user_summary(
                result.data[0]
            )

    })


# =========================================================
# BONUS
# =========================================================

def claim_bonus(
    user,
    chat_id=None
):

    last = user.get(
        "last_bonus_at"
    )


    if last:

        try:

            dt = datetime.fromisoformat(
                last.replace(
                    "Z",
                    "+00:00"
                )
            )

            if (
                now_utc() - dt
            ).total_seconds() < 86400:

                if chat_id:

                    send_message(
                        chat_id,
                        "🎁 Bonus already claimed.\nCome back tomorrow."
                    )

                return

        except Exception:
            pass


    old = float(
        user.get(
            "sikka_balance",
            0
        ) or 0
    )


    result = (
        supabase
        .table("users")
        .update({

            "sikka_balance":
                old + DAILY_BONUS,

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

        DAILY_BONUS,

        "daily_bonus",

        "Daily bonus"

    )


    if chat_id:

        send_message(

            chat_id,

            "🎁 <b>DAILY BONUS</b>\n\n"
            "Congratulations! 🎉\n\n"
            f"+{DAILY_BONUS} SIKKA 🪙"

        )


@app.route(
    "/api/bonus",
    methods=["POST"]
)
def api_bonus():

    user = get_user_from_init_data()

    if not user:

        return jsonify({
            "ok": False
        }), 401


    last = user.get(
        "last_bonus_at"
    )


    if last:

        try:

            dt = datetime.fromisoformat(
                last.replace(
                    "Z",
                    "+00:00"
                )
            )

            seconds = (
                now_utc() - dt
            ).total_seconds()

            if seconds < 86400:

                return jsonify({

                    "ok": False,

                    "error":
                        "Already claimed",

                    "next":
                        int(
                            86400 - seconds
                        )

                }), 400

        except Exception:
            pass


    old = float(
        user.get(
            "sikka_balance",
            0
        ) or 0
    )


    result = (
        supabase
        .table("users")
        .update({

            "sikka_balance":
                old + DAILY_BONUS,

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
        DAILY_BONUS,
        "daily_bonus",
        "Daily bonus"

    )


    return jsonify({

        "ok": True,

        "reward":
            DAILY_BONUS,

        "user":
            user_summary(
                result.data[0]
            )

    })


# =========================================================
# REFERRAL API
# =========================================================

@app.route(
    "/api/referral",
    methods=["POST"]
)
def referral_api():

    user = get_user_from_init_data()

    if not user:

        return jsonify({
            "ok": False
        }), 401


    user = ensure_referral_code(
        user
    )


    bot = telegram(
        "getMe"
    )


    username = (
        "MineRushGameBot"
    )


    if (
        bot
        and bot.get("ok")
    ):

        username = (
            bot["result"]
            ["username"]
        )


    code = user.get(
        "referral_code"
    )


    link = (
        f"https://t.me/"
        f"{username}"
        f"?start={code}"
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


def send_leaderboard(
    chat_id
):

    rows = get_leaderboard()

    text = (
        "🏆 <b>MINE RUSH LEADERBOARD</b>\n\n"
    )


    if not rows:

        text += "No players yet."

    else:

        for i, row in enumerate(
            rows,
            1
        ):

            medal = "🔹"

            if i == 1:
                medal = "🥇"

            elif i == 2:
                medal = "🥈"

            elif i == 3:
                medal = "🥉"


            text += (
                f"{medal} {i}. "
                f"{row.get('username') or 'Gamer'} — "
                f"{float(row.get('note_balance', 0) or 0):.0f} NOTE "
                f"(LV {int(row.get('level', 1) or 1)})\n"
            )


    send_message(
        chat_id,
        text
    )


@app.route(
    "/api/leaderboard",
    methods=["POST"]
)
def leaderboard_api():

    user = get_user_from_init_data()

    if not user:

        return jsonify({
            "ok": False
        }), 401


    return jsonify({

        "ok": True,

        "leaderboard":
            get_leaderboard()

    })


# =========================================================
# WALLET
# =========================================================

@app.route(
    "/api/wallet",
    methods=["POST"]
)
def wallet_api():

    user = get_user_from_init_data()

    if not user:

        return jsonify({
            "ok": False
        }), 401


    tx = (
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
        .limit(30)
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
            tx.data or [],

        "withdrawals":
            withdrawals.data or []

    })


# =========================================================
# WEBHOOK SETUP
# =========================================================

def setup_webhook():

    if not BOT_TOKEN:
        return


    result = telegram(

        "setWebhook",

        {

            "url":
                WEBHOOK_URL,

            "allowed_updates": [
                "message",
                "callback_query"
            ]

        }

    )


    print(
        "WEBHOOK RESULT:",
        result
    )


# =========================================================
# START
# =========================================================

print(
    "================================"
)

print(
    "🔥 MINE RUSH BACKEND STARTING"
)

print(
    "APP:",
    APP_URL
)

print(
    "WEBHOOK:",
    WEBHOOK_URL
)

print(
    "⏱️ MINING:",
    MINING_HOURS,
    "HOURS"
)

print(
    "================================"
)


setup_webhook()


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False
    )
