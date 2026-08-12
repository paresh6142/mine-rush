import os
import json
import time
import hmac
import hashlib
import traceback
import urllib.request
import urllib.parse

from urllib.parse import parse_qsl

from flask import Flask, request, jsonify, send_from_directory

from supabase import create_client


# =========================================================
# CONFIG
# =========================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

SUPABASE_URL = os.getenv("SUPABASE_URL")

SUPABASE_SERVICE_ROLE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY"
)

RENDER_URL = os.getenv(
    "RENDER_EXTERNAL_URL",
    "https://mine-rush-bot.onrender.com"
).rstrip("/")


if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN is missing"
    )


if not SUPABASE_URL:
    raise RuntimeError(
        "SUPABASE_URL is missing"
    )


if not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError(
        "SUPABASE_SERVICE_ROLE_KEY is missing"
    )


# =========================================================
# SUPABASE
# =========================================================

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY
)


# =========================================================
# FLASK
# =========================================================

web = Flask(__name__)


# =========================================================
# TELEGRAM API
# =========================================================

def telegram_api(
    method,
    payload=None
):

    try:

        url = (
            "https://api.telegram.org/"
            f"bot{TELEGRAM_BOT_TOKEN}/"
            f"{method}"
        )

        if payload is None:
            payload = {}

        data = json.dumps(
            payload
        ).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type":
                    "application/json"
            },
            method="POST"
        )

        with urllib.request.urlopen(
            req,
            timeout=20
        ) as response:

            result = json.loads(
                response
                .read()
                .decode("utf-8")
            )

            print(
                f"TELEGRAM {method}:",
                result
            )

            return result

    except Exception as e:

        print(
            f"TELEGRAM API ERROR {method}:",
            str(e)
        )

        traceback.print_exc()

        return None


# =========================================================
# MINI APP URL
# =========================================================

MINI_APP_URL = (
    f"{RENDER_URL}/app"
)


# =========================================================
# PLAY BUTTON
# =========================================================

def play_keyboard():

    return {

        "inline_keyboard": [

            [

                {

                    "text":
                        "🎮 PLAY MINE RUSH",

                    "web_app": {

                        "url":
                            MINI_APP_URL

                    }

                }

            ]

        ]

    }


# =========================================================
# SET MENU BUTTON
# =========================================================

def setup_menu_button():

    result = telegram_api(
        "setChatMenuButton",
        {
            "menu_button": {

                "type":
                    "web_app",

                "text":
                    "🎮 PLAY",

                "web_app": {

                    "url":
                        MINI_APP_URL

                }

            }

        }
    )

    if result and result.get("ok"):

        print(
            "✅ TELEGRAM MENU BUTTON SET"
        )

    else:

        print(
            "❌ TELEGRAM MENU BUTTON FAILED"
        )


# =========================================================
# WEBHOOK
# =========================================================

def setup_webhook():

    webhook_url = (
        f"{RENDER_URL}/telegram"
    )

    result = telegram_api(
        "setWebhook",
        {
            "url":
                webhook_url,

            "allowed_updates": [
                "message"
            ]
        }
    )

    if result and result.get("ok"):

        print(
            "✅ WEBHOOK SET:",
            webhook_url
        )

    else:

        print(
            "❌ WEBHOOK SET FAILED"
        )


# =========================================================
# TELEGRAM INIT DATA VALIDATION
# =========================================================

def validate_telegram_init_data(
    init_data
):

    try:

        if not init_data:

            print(
                "❌ INIT DATA EMPTY"
            )

            return None


        data = dict(
            parse_qsl(
                init_data,
                keep_blank_values=True
            )
        )


        received_hash = data.pop(
            "hash",
            None
        )


        if not received_hash:

            print(
                "❌ TELEGRAM HASH MISSING"
            )

            return None


        auth_date = int(
            data.get(
                "auth_date",
                0
            )
        )


        current_time = int(
            time.time()
        )


        # 24 hour validity

        if (
            auth_date <= 0
            or
            current_time - auth_date > 86400
        ):

            print(
                "❌ TELEGRAM INIT DATA EXPIRED"
            )

            return None


        data_check_string = "\n".join(

            f"{key}={value}"

            for key, value in sorted(
                data.items()
            )

        )


        secret_key = hmac.new(

            b"WebAppData",

            TELEGRAM_BOT_TOKEN.encode(
                "utf-8"
            ),

            hashlib.sha256

        ).digest()


        calculated_hash = hmac.new(

            secret_key,

            data_check_string.encode(
                "utf-8"
            ),

            hashlib.sha256

        ).hexdigest()


        if not hmac.compare_digest(

            calculated_hash,

            received_hash

        ):

            print(
                "❌ TELEGRAM HASH INVALID"
            )

            return None


        print(
            "✅ TELEGRAM INIT DATA VALID"
        )


        return data


    except Exception as e:

        print(
            "❌ INIT DATA ERROR:",
            str(e)
        )

        traceback.print_exc()

        return None


# =========================================================
# SEND TELEGRAM MESSAGE
# =========================================================

def send_message(
    chat_id,
    text,
    reply_markup=None
):

    payload = {

        "chat_id":
            chat_id,

        "text":
            text

    }


    if reply_markup:

        payload[
            "reply_markup"
        ] = reply_markup


    return telegram_api(
        "sendMessage",
        payload
    )


# =========================================================
# HOME
# =========================================================

@web.route("/")
def home():

    return """

    <html>

    <head>

    <title>MINE RUSH</title>

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    </head>

    <body
        style="
        background:#090d13;
        color:white;
        font-family:Arial;
        text-align:center;
        padding-top:60px;
        "
    >

        <h1>🔥 MINE RUSH</h1>

        <p>Backend is running.</p>

        <p>
            Open MINE RUSH from Telegram.
        </p>

    </body>

    </html>

    """


# =========================================================
# MINI APP
# =========================================================

@web.route("/app")
def app():

    return send_from_directory(
        os.path.dirname(
            os.path.abspath(__file__)
        ),
        "index.html"
    )


# =========================================================
# HEALTH
# =========================================================

@web.route("/health")
def health():

    return jsonify({

        "ok":
            True,

        "service":
            "MINE RUSH",

        "status":
            "running",

        "mini_app":
            MINI_APP_URL

    })


# =========================================================
# TELEGRAM WEBHOOK
# =========================================================

@web.post("/telegram")
def telegram_webhook():

    print(
        "📩 TELEGRAM UPDATE RECEIVED"
    )


    try:

        update = request.get_json(
            force=True
        )


        if not update:

            return "OK"


        message = update.get(
            "message"
        )


        if not message:

            return "OK"


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


        telegram_id = telegram_user.get(
            "id"
        )


        username = telegram_user.get(
            "username"
        )


        first_name = telegram_user.get(
            "first_name",
            "Player"
        )


        text = message.get(
            "text",
            ""
        )


        print(
            "TELEGRAM USER:",
            telegram_id
        )


        print(
            "TEXT:",
            text
        )


        # =================================================
        # START
        # =================================================

        if text.strip() == "/start":


            # ---------------------------------------------
            # FIND USER
            # ---------------------------------------------

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


            # =================================================
            # CREATE USER
            # =================================================

            if not result.data:


                print(
                    "🆕 CREATING USER"
                )


                insert_result = (

                    supabase

                    .table("users")

                    .insert({

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
                            1

                    })

                    .execute()

                )


                note = 0

                sikka = 0

                xp = 0

                level = 1


                welcome_text = (

                    "🔥 MINE RUSH\n\n"

                    f"Welcome "
                    f"{first_name}! 🚀\n\n"

                    "Your MINE RUSH account "
                    "has been created.\n\n"

                    "🪙 NOTE: 0\n"
                    "🪙 SIKKA: 0\n"
                    "⭐ LEVEL: 1\n"
                    "⚡ XP: 0\n\n"

                    "Ready to start mining?"

                )


            # =================================================
            # EXISTING USER
            # =================================================

            else:


                print(
                    "👤 EXISTING USER"
                )


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


                welcome_text = (

                    "🔥 MINE RUSH\n\n"

                    f"Welcome back "
                    f"{first_name}! 👋\n\n"

                    f"🪙 NOTE: {note}\n"
                    f"🪙 SIKKA: {sikka}\n"
                    f"⭐ LEVEL: {level}\n"
                    f"⚡ XP: {xp}\n\n"

                    "Your mining journey "
                    "continues. ⛏️"

                )


            # =================================================
            # SEND PLAY BUTTON
            # =================================================

            send_message(

                chat_id,

                welcome_text,

                play_keyboard()

            )


            print(
                "✅ PLAY BUTTON SENT"
            )


        return "OK"


    except Exception as e:

        print(
            "❌ WEBHOOK ERROR:",
            str(e)
        )

        traceback.print_exc()

        return "OK"


# =========================================================
# MINI APP USER API
# =========================================================

@web.post("/api/me")
def get_me():

    print(
        "📱 MINI APP /api/me"
    )


    try:


        # Form data
        init_data = request.form.get(
            "init_data",
            ""
        )


        if not init_data:

            return jsonify({

                "ok":
                    False,

                "error":
                    "Telegram authentication missing"

            }), 401


        # =================================================
        # VALIDATE
        # =================================================

        validated = (

            validate_telegram_init_data(
                init_data
            )

        )


        if not validated:

            return jsonify({

                "ok":
                    False,

                "error":
                    "Invalid Telegram authentication"

            }), 401


        # =================================================
        # USER
        # =================================================

        user_json = validated.get(
            "user"
        )


        if not user_json:

            return jsonify({

                "ok":
                    False,

                "error":
                    "Telegram user missing"

            }), 401


        telegram_user = json.loads(
            user_json
        )


        telegram_id = telegram_user.get(
            "id"
        )


        username = telegram_user.get(
            "username"
        )


        first_name = telegram_user.get(
            "first_name"
        )


        if not telegram_id:

            return jsonify({

                "ok":
                    False,

                "error":
                    "Telegram ID missing"

            }), 401


        print(
            "AUTHENTICATED USER:",
            telegram_id
        )


        # =================================================
        # FIND USER
        # =================================================

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


        # =================================================
        # CREATE USER
        # =================================================

        if not result.data:


            print(
                "CREATING MINI APP USER"
            )


            insert_result = (

                supabase

                .table("users")

                .insert({

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
                        1

                })

                .execute()

            )


            user = insert_result.data[0]


        else:

            user = result.data[0]


        # =================================================
        # RESPONSE
        # =================================================

        response_user = {

            "telegram_id":
                telegram_id,

            "username":
                username,

            "first_name":
                first_name,

            "note":
                user.get(
                    "note_balance",
                    0
                ),

            "sikka":
                user.get(
                    "sikka_balance",
                    0
                ),

            "xp":
                user.get(
                    "xp",
                    0
                ),

            "level":
                user.get(
                    "level",
                    1
                )

        }


        print(
            "USER DATA:",
            response_user
        )


        return jsonify({

            "ok":
                True,

            "user":
                response_user

        })


    except Exception as e:

        print(
            "❌ /api/me ERROR:",
            str(e)
        )

        traceback.print_exc()


        return jsonify({

            "ok":
                False,

            "error":
                "Server error"

        }), 500


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":


    print(
        "=========================================="
    )

    print(
        "🔥 MINE RUSH BACKEND STARTING"
    )

    print(
        "🗄️ SUPABASE CONNECTED"
    )

    print(
        "📱 MINI APP:",
        MINI_APP_URL
    )

    print(
        "=========================================="
    )


    # Set Telegram menu button
    setup_menu_button()


    # Set Telegram webhook
    setup_webhook()


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
