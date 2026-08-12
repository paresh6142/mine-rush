import os
import json
import time
import hmac
import hashlib
import traceback
import urllib.request
import urllib.parse

from urllib.parse import parse_qsl

from flask import Flask, request, jsonify
from flask_cors import CORS

from supabase import create_client


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY"
)


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
# CORS
# =========================================================

CORS(
    web,
    resources={
        r"/api/*": {
            "origins": "*"
        }
    }
)


# =========================================================
# TELEGRAM MINI APP INIT DATA VALIDATION
# =========================================================

def validate_telegram_init_data(init_data):

    try:

        if not init_data:
            print(
                "AUTH ERROR: init_data missing"
            )
            return None


        # Convert Telegram query string
        # into dictionary

        data = dict(
            parse_qsl(
                init_data,
                keep_blank_values=True
            )
        )


        # Telegram sends hash separately

        received_hash = data.pop(
            "hash",
            None
        )


        if not received_hash:

            print(
                "AUTH ERROR: hash missing"
            )

            return None


        # =================================================
        # CHECK AUTH DATE
        # =================================================

        try:

            auth_date = int(
                data.get(
                    "auth_date",
                    0
                )
            )

        except Exception:

            print(
                "AUTH ERROR: invalid auth_date"
            )

            return None


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
                "AUTH ERROR: initData expired"
            )

            return None


        # =================================================
        # DATA CHECK STRING
        # =================================================

        data_check_string = "\n".join(
            f"{key}={value}"
            for key, value in sorted(
                data.items()
            )
        )


        # =================================================
        # TELEGRAM SECRET KEY
        # =================================================

        secret_key = hmac.new(
            b"WebAppData",
            TELEGRAM_BOT_TOKEN.encode(
                "utf-8"
            ),
            hashlib.sha256
        ).digest()


        # =================================================
        # CALCULATE HASH
        # =================================================

        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(
                "utf-8"
            ),
            hashlib.sha256
        ).hexdigest()


        # =================================================
        # COMPARE HASH
        # =================================================

        if not hmac.compare_digest(
            calculated_hash,
            received_hash
        ):

            print(
                "AUTH ERROR: hash mismatch"
            )

            return None


        print(
            "✅ TELEGRAM INIT DATA VALID"
        )

        return data


    except Exception as e:

        print(
            "❌ TELEGRAM AUTH ERROR:"
        )

        print(
            str(e)
        )

        traceback.print_exc()

        return None


# =========================================================
# SEND TELEGRAM MESSAGE
# =========================================================

def send_telegram_message(
    chat_id,
    text
):

    try:

        url = (
            "https://api.telegram.org/"
            f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        )


        data = urllib.parse.urlencode({

            "chat_id": chat_id,

            "text": text

        }).encode(
            "utf-8"
        )


        telegram_request = (
            urllib.request.Request(
                url,
                data=data,
                method="POST"
            )
        )


        with urllib.request.urlopen(
            telegram_request,
            timeout=15
        ) as response:

            result = (
                response
                .read()
                .decode("utf-8")
            )


            print(
                "TELEGRAM RESPONSE:",
                result
            )


            return result


    except Exception as e:

        print(
            "❌ TELEGRAM SEND ERROR:"
        )

        print(
            str(e)
        )

        traceback.print_exc()

        return None


# =========================================================
# HOME
# =========================================================

@web.route("/")
def home():

    return (
        "🔥 MINE RUSH BACKEND RUNNING"
    )


# =========================================================
# HEALTH
# =========================================================

@web.route("/health")
def health():

    return jsonify({

        "ok": True,

        "service": "MINE RUSH",

        "status": "running"

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

        data = request.get_json(
            force=True
        )


        print(
            "TELEGRAM UPDATE:",
            json.dumps(
                data,
                ensure_ascii=False
            )
        )


        message = data.get(
            "message"
        )


        # Ignore updates without message

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


        text = message.get(
            "text",
            ""
        )


        print(
            "TELEGRAM ID:",
            telegram_id
        )


        print(
            "USERNAME:",
            username
        )


        print(
            "TEXT:",
            text
        )


        # =================================================
        # /START
        # =================================================

        if text.strip() == "/start":

            print(
                "START COMMAND RECEIVED"
            )


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
            # NEW USER
            # =================================================

            if not result.data:

                print(
                    "CREATING NEW USER"
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


                user = (
                    insert_result.data[0]
                )


                message_text = (

                    "🔥 MINE RUSH 🔥\n\n"

                    "🎉 Welcome to MINE RUSH!\n\n"

                    "🪙 NOTE: 0\n"

                    "🪙 SIKKA: 0\n"

                    "⭐ Level: 1\n"

                    "⚡ XP: 0\n\n"

                    "Your account has been "
                    "created! 🚀"

                )


            # =================================================
            # EXISTING USER
            # =================================================

            else:

                print(
                    "EXISTING USER"
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


                message_text = (

                    "🔥 MINE RUSH 🔥\n\n"

                    f"🪙 NOTE: {note}\n"

                    f"🪙 SIKKA: {sikka}\n"

                    f"⭐ Level: {level}\n"

                    f"⚡ XP: {xp}\n\n"

                    "Welcome back! 🚀"

                )


            # =================================================
            # SEND TELEGRAM RESPONSE
            # =================================================

            send_telegram_message(
                chat_id,
                message_text
            )


            print(
                "✅ START RESPONSE SENT"
            )


        return "OK"


    except Exception as e:

        print(
            "❌ WEBHOOK ERROR:"
        )


        print(
            str(e)
        )


        traceback.print_exc()


        # Return 200 so Telegram does not
        # repeatedly resend the same update.

        return "OK"


# =========================================================
# MINI APP USER API
# =========================================================

@web.post("/api/me")
def get_me():

    print(
        "📱 MINI APP /api/me REQUEST"
    )


    try:

        # =================================================
        # GET TELEGRAM INIT DATA
        # =================================================

        init_data = request.headers.get(
            "X-Telegram-Init-Data",
            ""
        )


        if not init_data:

            print(
                "❌ MINI APP AUTH DATA MISSING"
            )


            return jsonify({

                "ok": False,

                "error":
                    "Telegram authentication data missing"

            }), 401


        # =================================================
        # VALIDATE TELEGRAM DATA
        # =================================================

        validated = (
            validate_telegram_init_data(
                init_data
            )
        )


        if not validated:

            print(
                "❌ MINI APP AUTH INVALID"
            )


            return jsonify({

                "ok": False,

                "error":
                    "Invalid Telegram authentication"

            }), 401


        # =================================================
        # GET TELEGRAM USER
        # =================================================

        user_json = validated.get(
            "user"
        )


        if not user_json:

            print(
                "❌ TELEGRAM USER MISSING"
            )


            return jsonify({

                "ok": False,

                "error":
                    "Telegram user missing"

            }), 401


        try:

            telegram_user = json.loads(
                user_json
            )

        except Exception:

            print(
                "❌ TELEGRAM USER JSON INVALID"
            )


            return jsonify({

                "ok": False,

                "error":
                    "Invalid Telegram user data"

            }), 401


        # =================================================
        # USER INFORMATION
        # =================================================

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

            print(
                "❌ TELEGRAM ID MISSING"
            )


            return jsonify({

                "ok": False,

                "error":
                    "Telegram ID missing"

            }), 401


        print(
            "AUTHENTICATED TELEGRAM USER:",
            telegram_id
        )


        # =================================================
        # FIND USER IN SUPABASE
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
        # CREATE USER IF NOT EXISTS
        # =================================================

        if not result.data:

            print(
                "MINI APP: CREATING USER"
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


            user = (
                insert_result.data[0]
            )


        # =================================================
        # EXISTING USER
        # =================================================

        else:

            print(
                "MINI APP: EXISTING USER"
            )


            user = result.data[0]


        # =================================================
        # PREPARE RESPONSE
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
            "USER DATA SENT:",
            response_user
        )


        return jsonify({

            "ok": True,

            "user":
                response_user

        })


    except Exception as e:

        print(
            "❌ /api/me ERROR:"
        )


        print(
            str(e)
        )


        traceback.print_exc()


        return jsonify({

            "ok": False,

            "error":
                "Server error"

        }), 500


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":


    print(
        "================================="
    )


    print(
        "🔥 MINE RUSH BACKEND STARTING"
    )


    print(
        "🗄️ SUPABASE CONNECTED"
    )


    print(
        "📡 TELEGRAM WEBHOOK MODE"
    )


    print(
        "📱 MINI APP API ENABLED"
    )


    print(
        "🌐 CORS ENABLED"
    )


    print(
        "================================="
    )


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
