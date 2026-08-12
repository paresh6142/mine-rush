import os
import json
import hmac
import hashlib
import secrets
import string
from datetime import datetime, timezone, timedelta
from urllib.parse import parse_qsl, unquote

from flask import Flask, request, jsonify, send_from_directory
from supabase import create_client, Client
from urllib.request import Request, urlopen
from urllib.parse import urlencode


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

WEBAPP_URL = os.getenv(
    "WEBAPP_URL",
    "https://mine-rush-bot.onrender.com"
).strip().rstrip("/")

BOT_USERNAME = os.getenv(
    "BOT_USERNAME",
    "MineRushGameBot"
).strip()


if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing")

if not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_KEY is missing")


supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

app = Flask(__name__)


# =========================================================
# TIME
# =========================================================

def utc_now():
    return datetime.now(timezone.utc)


# =========================================================
# TELEGRAM API
# =========================================================

def telegram_api(method, data):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"

    encoded = urlencode(data).encode()

    req = Request(
        url,
        data=encoded,
        headers={
            "Content-Type":
            "application/x-www-form-urlencoded"
        }
    )

    with urlopen(req, timeout=15) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


# =========================================================
# TELEGRAM MINI APP AUTH
# =========================================================

def validate_telegram_init_data(init_data):

    if not init_data:
        raise ValueError(
            "Telegram Mini App authentication data missing"
        )

    pairs = dict(parse_qsl(
        init_data,
        keep_blank_values=True
    ))

    received_hash = pairs.pop("hash", None)

    if not received_hash:
        raise ValueError(
            "Telegram authentication hash missing"
        )

    data_check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(pairs.items())
    )

    secret_key = hmac.new(
        b"WebAppData",
        BOT_TOKEN.encode(),
        hashlib.sha256
    ).digest()

    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(
        calculated_hash,
        received_hash
    ):
        raise ValueError(
            "Invalid Telegram authentication"
        )

    user_json = pairs.get("user")

    if not user_json:
        raise ValueError(
            "Telegram user data missing"
        )

    return json.loads(
        unquote(user_json)
    )


# =========================================================
# USER
# =========================================================

def create_user_if_missing(telegram_user):

    telegram_id = int(
        telegram_user["id"]
    )

    result = (
        supabase
        .table("users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0]

    referral_code = "".join(
        secrets.choice(
            string.ascii_uppercase +
            string.digits
        )
        for _ in range(8)
    )

    new_user = {
        "telegram_id": telegram_id,
        "username":
            telegram_user.get("username")
            or telegram_user.get("first_name")
            or "Gamer",

        "note_balance": 0,
        "sikka_balance": 0,

        "xp": 0,
        "level": 1,

        "energy": 100,
        "boost_percent": 0,
        "mining_rate": 100,

        "referral_code": referral_code,
        "referral_count": 0,

        "mining_started_at": None,
        "mining_ends_at": None,

        "last_bonus_at": None,
    }

    inserted = (
        supabase
        .table("users")
        .insert(new_user)
        .execute()
    )

    return inserted.data[0]


def get_user_by_telegram_id(
    telegram_id
):

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
        raise ValueError(
            "User account not found"
        )

    return result.data[0]


# =========================================================
# CURRENT MINI APP USER
# =========================================================

def current_user():

    init_data = request.headers.get(
        "X-Telegram-Init-Data",
        ""
    )

    telegram_user = validate_telegram_init_data(
        init_data
    )

    return create_user_if_missing(
        telegram_user
    )


# =========================================================
# SAFE USER DATA
# =========================================================

def safe_user(user):

    mining_active = False
    mining_end = user.get(
        "mining_ends_at"
    )

    if mining_end:

        try:
            end_time = datetime.fromisoformat(
                str(mining_end)
                .replace("Z", "+00:00")
            )

            if end_time > utc_now():
                mining_active = True

        except Exception:
            mining_active = False

    return {

        "id":
            user.get("id"),

        "telegram_id":
            user.get("telegram_id"),

        "username":
            user.get("username")
            or "Gamer",

        "note":
            float(
                user.get("note_balance")
                or 0
            ),

        "sikka":
            float(
                user.get("sikka_balance")
                or 0
            ),

        "xp":
            int(
                user.get("xp")
                or 0
            ),

        "level":
            int(
                user.get("level")
                or 1
            ),

        "energy":
            int(
                user.get("energy")
                if user.get("energy") is not None
                else 100
            ),

        "boost":
            float(
                user.get("boost_percent")
                or 0
            ),

        "mining_active":
            mining_active,

        "mining_end":
            mining_end,
    }


# =========================================================
# UPDATE USER
# =========================================================

def update_user(user_id, values):

    result = (
        supabase
        .table("users")
        .update(values)
        .eq("id", user_id)
        .execute()
    )

    return result.data[0]


# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():

    return send_from_directory(
        os.path.dirname(
            os.path.dirname(__file__)
        ),
        "index.html"
    )


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():

    return jsonify({
        "ok": True,
        "service": "MINE RUSH"
    })


# =========================================================
# GET USER
# =========================================================

@app.get("/api/me")
def api_me():

    try:

        user = current_user()

        return jsonify({
            "ok": True,
            "user": safe_user(user)
        })

    except Exception as e:

        print("ME ERROR:", repr(e))

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 400


# =========================================================
# START 4 HOUR MINING
# =========================================================

@app.post("/api/mine/start")
def start_mining():

    try:

        user = current_user()

        existing_end = user.get(
            "mining_ends_at"
        )

        if existing_end:

            try:

                end_time = datetime.fromisoformat(
                    str(existing_end)
                    .replace("Z", "+00:00")
                )

                if end_time > utc_now():

                    return jsonify({
                        "ok": False,
                        "error":
                            "Mining is already running"
                    }), 409

            except Exception:
                pass

        start_time = utc_now()

        end_time = (
            start_time +
            timedelta(hours=4)
        )

        updated = update_user(
            user["id"],
            {
                "mining_started_at":
                    start_time.isoformat(),

                "mining_ends_at":
                    end_time.isoformat()
            }
        )

        return jsonify({
            "ok": True,
            "user": safe_user(updated)
        })

    except Exception as e:

        print("MINING ERROR:", repr(e))

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 400


# =========================================================
# DAILY BONUS STATUS
# =========================================================

@app.get("/api/bonus/status")
def bonus_status():

    try:

        user = current_user()

        last_bonus = user.get(
            "last_bonus_at"
        )

        if not last_bonus:

            return jsonify({
                "ok": True,
                "available": True,
                "next_claim_at": None
            })

        last_time = datetime.fromisoformat(
            str(last_bonus)
            .replace("Z", "+00:00")
        )

        next_time = (
            last_time +
            timedelta(hours=24)
        )

        available = (
            utc_now() >= next_time
        )

        return jsonify({
            "ok": True,
            "available": available,
            "next_claim_at":
                None
                if available
                else next_time.isoformat()
        })

    except Exception as e:

        print("BONUS STATUS ERROR:", repr(e))

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 400


# =========================================================
# CLAIM DAILY BONUS
# =========================================================

@app.post("/api/bonus/claim")
def claim_bonus():

    try:

        user = current_user()

        last_bonus = user.get(
            "last_bonus_at"
        )

        if last_bonus:

            last_time = datetime.fromisoformat(
                str(last_bonus)
                .replace("Z", "+00:00")
            )

            next_time = (
                last_time +
                timedelta(hours=24)
            )

            if utc_now() < next_time:

                return jsonify({
                    "ok": False,
                    "error":
                        "Daily bonus already claimed. Try again after 24 hours."
                }), 409

        current_sikka = float(
            user.get("sikka_balance")
            or 0
        )

        updated = update_user(
            user["id"],
            {
                "sikka_balance":
                    current_sikka + 100,

                "last_bonus_at":
                    utc_now().isoformat()
            }
        )

        try:

            supabase.table(
                "transactions"
            ).insert({

                "user_id":
                    user["id"],

                "currency":
                    "SIKKA",

                "amount":
                    100,

                "type":
                    "bonus",

                "description":
                    "Daily bonus"

            }).execute()

        except Exception as transaction_error:

            print(
                "TRANSACTION LOG ERROR:",
                repr(transaction_error)
            )

        return jsonify({
            "ok": True,
            "user": safe_user(updated)
        })

    except Exception as e:

        print("BONUS CLAIM ERROR:", repr(e))

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 400


# =========================================================
# REFERRAL
# =========================================================

@app.get("/api/referral")
def referral():

    try:

        user = current_user()

        code = (
            user.get("referral_code")
            or "NONE"
        )

        result = (
            supabase
            .table("users")
            .select(
                "id",
                count="exact"
            )
            .eq(
                "referred_by",
                user["id"]
            )
            .execute()
        )

        count = result.count or 0

        link = (
            f"https://t.me/"
            f"{BOT_USERNAME}"
            f"?start={code}"
        )

        return jsonify({
            "ok": True,
            "code": code,
            "count": count,
            "link": link
        })

    except Exception as e:

        print("REFERRAL ERROR:", repr(e))

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 400


# =========================================================
# LEADERBOARD
# =========================================================

@app.get("/api/leaderboard")
def leaderboard():

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

        return jsonify({
            "ok": True,
            "rows":
                result.data or []
        })

    except Exception as e:

        print(
            "LEADERBOARD ERROR:",
            repr(e)
        )

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 400


# =========================================================
# WITHDRAWAL LIST
# =========================================================

@app.get("/api/withdrawals")
def withdrawals():

    try:

        user = current_user()

        result = (
            supabase
            .table("withdrawals")
            .select(
                "note_amount,status,created_at"
            )
            .eq(
                "user_id",
                user["id"]
            )
            .order(
                "created_at",
                desc=True
            )
            .limit(10)
            .execute()
        )

        return jsonify({
            "ok": True,
            "rows":
                result.data or []
        })

    except Exception as e:

        print(
            "WITHDRAWALS ERROR:",
            repr(e)
        )

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 400


# =========================================================
# WITHDRAW
# =========================================================

@app.post("/api/withdraw")
def withdraw():

    try:

        user = current_user()

        data = (
            request
            .get_json(
                force=True
            )
            or {}
        )

        amount = float(
            data.get(
                "note_amount",
                0
            )
        )

        method = str(
            data.get(
                "payment_method",
                ""
            )
        ).strip()

        details = str(
            data.get(
                "payment_details",
                ""
            )
        ).strip()

        # Minimum withdrawal
        if amount < 10000:

            return jsonify({
                "ok": False,
                "error":
                    "Minimum withdrawal is 10,000 NOTE"
            }), 400

        balance = float(
            user.get(
                "note_balance"
            )
            or 0
        )

        if amount > balance:

            return jsonify({
                "ok": False,
                "error":
                    "Insufficient NOTE balance"
            }), 400

        if not method:

            return jsonify({
                "ok": False,
                "error":
                    "Payment method is required"
            }), 400

        if not details:

            return jsonify({
                "ok": False,
                "error":
                    "Payment details are required"
            }), 400

        new_balance = (
            balance - amount
        )

        updated = update_user(
            user["id"],
            {
                "note_balance":
                    new_balance
            }
        )

        try:

            supabase.table(
                "withdrawals"
            ).insert({

                "user_id":
                    user["id"],

                "note_amount":
                    amount,

                "inr_amount":
                    amount / 10000,

                "payment_method":
                    method,

                "payment_details":
                    details,

                "status":
                    "pending"

            }).execute()

        except Exception as withdrawal_error:

            print(
                "WITHDRAWAL INSERT ERROR:",
                repr(withdrawal_error
                )
            )

            # IMPORTANT:
            # If withdrawal record failed,
            # restore user's balance.

            update_user(
                user["id"],
                {
                    "note_balance":
                        balance
                }
            )

            raise ValueError(
                "Could not create withdrawal request"
            )

        return jsonify({
            "ok": True,
            "user":
                safe_user(updated)
        })

    except Exception as e:

        print(
            "WITHDRAW ERROR:",
            repr(e)
        )

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 400


# =========================================================
# MARKET
# =========================================================

@app.get("/api/market")
def market():

    try:

        result = (
            supabase
            .table("market_items")
            .select(
                "id,name,description,price_sikka"
            )
            .eq(
                "active",
                True
            )
            .order(
                "id"
            )
            .execute()
        )

        items = []

        for item in (
            result.data or []
        ):

            items.append({

                "id":
                    item["id"],

                "name":
                    item["name"],

                "description":
                    item.get(
                        "description"
                    ) or "",

                "price":
                    float(
                        item[
                            "price_sikka"
                        ]
                    )
            })

        return jsonify({
            "ok": True,
            "items": items
        })

    except Exception as e:

        print(
            "MARKET ERROR:",
            repr(e)
        )

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 400


# =========================================================
# MARKET PURCHASE
# =========================================================

@app.post("/api/market/buy")
def market_buy():

    try:

        user = current_user()

        data = (
            request
            .get_json(
                force=True
            )
            or {}
        )

        item_id = int(
            data.get(
                "item_id"
            )
        )

        result = (
            supabase
            .table("market_items")
            .select("*")
            .eq(
                "id",
                item_id
            )
            .eq(
                "active",
                True
            )
            .limit(1)
            .execute()
        )

        if not result.data:

            return jsonify({
                "ok": False,
                "error":
                    "Market item not found"
            }), 404

        item = result.data[0]

        price = float(
            item["price_sikka"]
        )

        balance = float(
            user.get(
                "sikka_balance"
            )
            or 0
        )

        if balance < price:

            return jsonify({
                "ok": False,
                "error":
                    "Not enough SIKKA"
            }), 400

        changes = {

            "sikka_balance":
                balance - price
        }

        if item_id == 1:

            energy = int(
                user.get(
                    "energy"
                )
                or 100
            )

            changes["energy"] = min(
                100,
                energy + 20
            )

        elif item_id == 2:

            boost = float(
                user.get(
                    "boost_percent"
                )
                or 0
            )

            changes[
                "boost_percent"
            ] = boost + 10

        elif item_id == 3:

            rate = int(
                user.get(
                    "mining_rate"
                )
                or 100
            )

            changes[
                "mining_rate"
            ] = rate + 25

        updated = update_user(
            user["id"],
            changes
        )

        try:

            supabase.table(
                "transactions"
            ).insert({

                "user_id":
                    user["id"],

                "currency":
                    "SIKKA",

                "amount":
                    -price,

                "type":
                    "market",

                "description":
                    item["name"]

            }).execute()

        except Exception as e:

            print(
                "MARKET TRANSACTION ERROR:",
                repr(e)
            )

        return jsonify({
            "ok": True,
            "user":
                safe_user(updated)
        })

    except Exception as e:

        print(
            "MARKET BUY ERROR:",
            repr(e)
        )

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 400


# =========================================================
# TELEGRAM WEBHOOK
# =========================================================

@app.post("/telegram")
def telegram_webhook():

    try:

        update = (
            request
            .get_json(
                silent=True
            )
            or {}
        )

        message = (
            update.get(
                "message"
            )
            or {}
        )

        telegram_user = (
            message.get(
                "from"
            )
            or {}
        )

        chat = (
            message.get(
                "chat"
            )
            or {}
        )

        if not telegram_user:

            return jsonify({
                "ok": True
            })

        user = create_user_if_missing(
            telegram_user
        )

        text = (
            message.get(
                "text"
            )
            or ""
        ).strip()

        # -------------------------------------------------
        # /start
        # -------------------------------------------------

        if text.startswith(
            "/start"
        ):

            parts = text.split(
                maxsplit=1
            )

            referral_code = (
                parts[1].strip()
                if len(parts) > 1
                else ""
            )

            # Referral only once
            if (
                referral_code
                and not user.get(
                    "referred_by"
                )
                and referral_code != user.get(
                    "referral_code"
                )
            ):

                ref_result = (
                    supabase
                    .table("users")
                    .select("id")
                    .eq(
                        "referral_code",
                        referral_code
                    )
                    .limit(1)
                    .execute()
                )

                if ref_result.data:

                    referrer_id = (
                        ref_result
                        .data[0]
                        ["id"]
                    )

                    user = update_user(
                        user["id"],
                        {
                            "referred_by":
                                referrer_id
                        }
                    )

                    referrer = (
                        get_user_by_id(
                            referrer_id
                        )
                    )

                    referrer_sikka = float(
                        referrer.get(
                            "sikka_balance"
                        )
                        or 0
                    )

                    referrer_count = int(
                        referrer.get(
                            "referral_count"
                        )
                        or 0
                    )

                    update_user(
                        referrer_id,
                        {
                            "sikka_balance":
                                referrer_sikka + 50,

                            "referral_count":
                                referrer_count + 1
                        }
                    )

            note = int(
                float(
                    user.get(
                        "note_balance"
                    )
                    or 0
                )
            )

            sikka = int(
                float(
                    user.get(
                        "sikka_balance"
                    )
                    or 0
                )
            )

            level = int(
                user.get(
                    "level"
                )
                or 1
            )

            xp = int(
                user.get(
                    "xp"
                )
                or 0
            )

            username = (
                user.get(
                    "username"
                )
                or telegram_user.get(
                    "first_name"
                )
                or "Gamer"
            )

            text_out = (
                "🔥 MINE RUSH 🔥\n\n"

                f"🪙 NOTE: {note}\n"
                f"🪙 SIKKA: {sikka}\n"
                f"⭐ LEVEL: {level}\n"
                f"⚡ XP: {xp}\n\n"

                f"Welcome back, "
                f"{username}! 👋\n\n"

                "⛏️ Start your 4-hour mining session."
            )

            keyboard = {

                "inline_keyboard": [

                    [
                        {
                            "text":
                                "🎮 PLAY MINE RUSH",

                            "web_app":
                            {
                                "url":
                                    WEBAPP_URL + "/"
                            }
                        }
                    ],

                    [
                        {
                            "text":
                                "🎁 BONUS",

                            "callback_data":
                                "bonus"
                        },

                        {
                            "text":
                                "👥 REFERRAL",

                            "callback_data":
                                "referral"
                        }
                    ],

                    [
                        {
                            "text":
                                "🏆 LEADERBOARD",

                            "callback_data":
                                "leaderboard"
                        }
                    ]
                ]
            }

            telegram_api(
                "sendMessage",
                {
                    "chat_id":
                        chat["id"],

                    "text":
                        text_out,

                    "reply_markup":
                        json.dumps(
                            keyboard
                        )
                }
            )

        else:

            telegram_api(
                "sendMessage",
                {
                    "chat_id":
                        chat["id"],

                    "text":
                        "Use /start to open MINE RUSH."
                }
            )

        return jsonify({
            "ok": True
        })

    except Exception as e:

        print(
            "WEBHOOK ERROR:",
            repr(e)
        )

        # Always return 200 to Telegram
        # so Telegram does not endlessly retry
        # the same update.

        return jsonify({
            "ok": True
        })


# =========================================================
# HELPER
# =========================================================

def get_user_by_id(
    user_id
):

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

        raise ValueError(
            "Referrer account not found"
        )

    return result.data[0]


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    print(
        "🌐 MINE RUSH WEB SERVER STARTING..."
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
