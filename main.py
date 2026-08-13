
import json

import os

import requests

from fastapi import FastAPI, Request

from uvicorn import run

app = FastAPI()

# ==========================================

# НАСТРОЙКИ

# ==========================================

GREEN_API_INSTANCE_ID = os.getenv("GREEN_API_INSTANCE_ID")

GREEN_API_TOKEN = os.getenv("GREEN_API_TOKEN")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GREEN_API_URL = (

    f"https://api.green-api.com/waInstance{GREEN_API_INSTANCE_ID}"

)

# Запоминаем, какой товар интересует каждого клиента

user_sessions = {}

# ==========================================

# ПРОВЕРКА КЛЮЧЕЙ

# ==========================================

print("==========================================")

print("ЗАПУСК БОТА")

print("==========================================")

if GREEN_API_INSTANCE_ID:

    print("GREEN_API_INSTANCE_ID: OK")

else:

    print("ОШИБКА: GREEN_API_INSTANCE_ID отсутствует")

if GREEN_API_TOKEN:

    print("GREEN_API_TOKEN: OK")

else:

    print("ОШИБКА: GREEN_API_TOKEN отсутствует")

if GEMINI_API_KEY:

    print("GEMINI_API_KEY: OK")

else:

    print("ОШИБКА: GEMINI_API_KEY отсутствует")

# ==========================================

# ЗАГРУЗКА PRODUCTS.JSON

# ==========================================

def load_products():

    try:

        with open(

            "products.json",

            "r",

            encoding="utf-8"

        ) as f:

            data = json.load(f)

            print(

                f"Загружено кампаний: {len(data)}"

            )

            print(

                f"Кампании: {list(data.keys())}"

            )

            return data

    except Exception as e:

        print(

            f"ОШИБКА products.json: {e}"

        )

        return {}

PRODUCTS_DB = load_products()

# ==========================================

# WHATSAPP — ОТПРАВКА СООБЩЕНИЯ

# ==========================================

def send_whatsapp_message(

    chat_id: str,

    text: str

):

    url = (

        f"{GREEN_API_URL}"

        f"/sendMessage/{GREEN_API_TOKEN}"

    )

    payload = {

        "chatId": chat_id,

        "message": text

    }

    headers = {

        "Content-Type": "application/json"

    }

    try:

        response = requests.post(

            url,

            json=payload,

            headers=headers,

            timeout=15

        )

        print(

            f"WhatsApp SEND: "

            f"{response.status_code}"

        )

        print(

            f"WhatsApp RESPONSE: "

            f"{response.text}"

        )

        if response.status_code >= 400:

            print(

                "ОШИБКА Green API:"

            )

            print(response.text)

    except Exception as e:

        print(

            f"ОШИБКА отправки WhatsApp: {e}"

        )

# ==========================================

# ПОИСК ТОВАРА ПО КЛЮЧЕВЫМ СЛОВАМ

# ==========================================

def detect_campaign(message_text: str):

    text_lower = message_text.lower()

    print(

        f"Ищем товар для сообщения: "

        f"{text_lower}"

    )

    for campaign_id, data in PRODUCTS_DB.items():

        keywords = data.get(

            "trigger_keywords",

            []

        )

        for keyword in keywords:

            if keyword.lower() in text_lower:

                print(

                    f"НАЙДЕН ТОВАР: "

                    f"{campaign_id}"

                )

                return campaign_id

    print(

        "Товар по ключевым словам НЕ найден"

    )

    return None

# ==========================================

# ОБЩИЙ ПРОМПТ

# ==========================================

GENERAL_SYSTEM_PROMPT = """

Ты — вежливый менеджер онлайн-магазина perizat.optom.

Магазин находится на Дордое.

Мы продаём бытовую технику, кухонную технику,

товары Smeg, Dyson и кухонную утварь.

Твоя задача — помогать клиентам выбрать товар,

отвечать на вопросы и подводить клиента к покупке.

ВАЖНЫЕ ПРАВИЛА:

1. Если клиент пишет на русском — отвечай на русском.

2. Если клиент пишет на кыргызском —

отвечай на грамотном и естественном кыргызском.

3. Не придумывай цены и характеристики,

если их нет в информации о товарах.

4. Если клиент спрашивает, какие товары есть,

расскажи, что можно подобрать Dyson,

Smeg, кухонную технику и посуду.

5. Если клиент хочет купить товар,

уточни имя, номер телефона и адрес доставки.

6. Пиши коротко и естественно,

как настоящий менеджер WhatsApp.

7. Не говори клиенту, что ты искусственный интеллект.

8. Не используй слишком длинные сообщения.

"""

# ==========================================

# GEMINI

# ==========================================

def ask_ai(

    campaign_id: str,

    user_message: str

):

    if not GEMINI_API_KEY:

        print(

            "ОШИБКА: GEMINI_API_KEY отсутствует"

        )

        return (

            "Саламатсызбы! "

            "Азыр техникалык көйгөй болуп жатат."

        )

    # --------------------------------------

    # Если товар найден

    # --------------------------------------

    if campaign_id:

        product_data = PRODUCTS_DB.get(

            campaign_id

        )

        if product_data:

            system_instruction = (

                product_data.get(

                    "system_prompt",

                    GENERAL_SYSTEM_PROMPT

                )

            )

            product_name = product_data.get(

                "product_name",

                ""

            )

        else:

            system_instruction = (

                GENERAL_SYSTEM_PROMPT

            )

            product_name = ""

    else:

        # ----------------------------------

        # Если товар НЕ найден

        # Всё равно запускаем AI

        # ----------------------------------

        system_instruction = (

            GENERAL_SYSTEM_PROMPT

        )

        product_name = ""

    # --------------------------------------

    # Формируем prompt

    # --------------------------------------

    prompt_text = f"""

{system_instruction}

"""

    if product_name:

        prompt_text += f"""

ТОВАР, КОТОРЫМ СЕЙЧАС ИНТЕРЕСУЕТСЯ КЛИЕНТ:

{product_name}

"""

    prompt_text += f"""

СООБЩЕНИЕ КЛИЕНТА:

{user_message}

Ответь клиенту прямо сейчас.

"""

    # --------------------------------------

    # Gemini

    # --------------------------------------

    model_name = "gemini-3.6-flash"

    url = (

        "https://generativelanguage.googleapis.com/"

        f"v1beta/models/{model_name}:generateContent"

    )

    payload = {

        "contents": [

            {

                "role": "user",

                "parts": [

                    {

                        "text": prompt_text

                    }

                ]

            }

        ],

        "generationConfig": {

            "maxOutputTokens": 500

        }

    }

    headers = {

        "Content-Type": "application/json",

        "x-goog-api-key": GEMINI_API_KEY

    }

    print(

        "=========================================="

    )

    print(

        "ОТПРАВЛЯЕМ ЗАПРОС В GEMINI"

    )

    print(

        f"Модель: {model_name}"

    )

    print(

        f"Campaign: {campaign_id}"

    )

    print(

        f"Сообщение: {user_message}"

    )

    try:

        response = requests.post(

            url,

            json=payload,

            headers=headers,

            timeout=30

        )

        print(

            f"GEMINI STATUS: "

            f"{response.status_code}"

        )

        print(

            f"GEMINI RESPONSE: "

            f"{response.text}"

        )

        if response.status_code != 200:

            return (

                "Саламатсызбы! "

                "Бир аздан соң менеджер "

                "сизге жооп берет."

            )

        data = response.json()

        candidates = data.get(

            "candidates",

            []

        )

        if not candidates:

            print(

                "Gemini не вернул candidates"

            )

            return (

                "Саламатсызбы! "

                "Бир аздан соң маалымат беребиз."

            )

        parts = (

            candidates[0]

            .get("content", {})

            .get("parts", [])

        )

        for part in parts:

            text = part.get("text")

            if text:

                print(

                    "GEMINI ОТВЕТ:"

                )

                print(text)

                return text.strip()

        print(

            "Gemini вернул ответ без текста"

        )

    except Exception as e:

        print(

            f"ОШИБКА GEMINI: {e}"

        )

    return (

        "Саламатсызбы! "

        "Бир аздан соң менеджер "

        "сизге жооп берет."

    )

# ==========================================

# WEBHOOK

# ==========================================

@app.post("/webhook")

async def receive_whatsapp(

    request: Request

):

    print(

        "=========================================="

    )

    print(

        "ПОЛУЧЕН WEBHOOK"

    )

    try:

        data = await request.json()

        print(

            "WEBHOOK DATA:"

        )

        print(

            json.dumps(

                data,

                ensure_ascii=False

            )

        )

        # ----------------------------------

        # Проверяем тип webhook

        # ----------------------------------

        webhook_type = data.get(

            "typeWebhook"

        )

        print(

            f"typeWebhook: {webhook_type}"

        )

        if webhook_type != (

            "incomingMessageReceived"

        ):

            print(

                "Webhook не является входящим сообщением"

            )

            return {

                "status": "ignored"

            }

        # ----------------------------------

        # Получаем данные

        # ----------------------------------

        message_data = data.get(

            "messageData",

            {}

        )

        sender_data = data.get(

            "senderData",

            {}

        )

        chat_id = sender_data.get(

            "chatId"

        )

        text_message = ""

        # ----------------------------------

        # Текстовое сообщение

        # ----------------------------------

        if message_data.get(

            "typeMessage"

        ) == "textMessage":

            text_message = (

                message_data

                .get(

                    "textMessageData",

                    {}

                )

                .get(

                    "textMessage",

                    ""

                )

            )

        # ----------------------------------

        # Иногда Green API может передавать

        # extendedTextMessage

        # ----------------------------------

        elif message_data.get(

            "typeMessage"

        ) == "extendedTextMessage":

            text_message = (

                message_data

                .get(

                    "extendedTextMessageData",

                    {}

                )

                .get(

                    "text",

                    ""

                )

            )

        print(

            f"CHAT ID: {chat_id}"

        )

        print(

            f"TEXT: {text_message}"

        )

        # ----------------------------------

        # Проверка

        # ----------------------------------

        if not chat_id:

            print(

                "Нет chat_id"

            )

            return {

                "status": "ignored"

            }

        if not text_message:

            print(

                "Нет текста сообщения"

            )

            return {

                "status": "ignored"

            }

        # ----------------------------------

        # Ищем товар

        # ----------------------------------

        new_campaign = detect_campaign(

            text_message

        )

        # Если нашли товар —

        # сохраняем его за клиентом

        if new_campaign:

            user_sessions[chat_id] = (

                new_campaign

            )

        # Если товар не нашли —

        # используем предыдущий товар

        current_campaign = (

            user_sessions.get(chat_id)

        )

        print(

            f"CURRENT CAMPAIGN: "

            f"{current_campaign}"

        )

        # ----------------------------------

        # ВАЖНО:

        # AI вызывается ВСЕГДА

        # ----------------------------------

        ai_response = ask_ai(

            current_campaign,

            text_message

        )

        print(

            f"AI RESPONSE: {ai_response}"

        )

        # ----------------------------------

        # Отправляем ответ клиенту

        # ----------------------------------

        send_whatsapp_message(

            chat_id,

            ai_response

        )

        return {

            "status": "ok"

        }

    except Exception as e:

        print(

            f"КРИТИЧЕСКАЯ ОШИБКА WEBHOOK: {e}"

        )

        return {

            "status": "error"

        }

# ==========================================

# HEALTH CHECK

# ==========================================

@app.get("/")

async def home():

    return {

        "status": "online",

        "bot": "perizat.optom AI",

        "gemini": "gemini-3.6-flash"

    }

# ==========================================

# ЗАПУСК

# ==========================================

if _name_ == "_main_":

    run(

        "main:app",

        host="0.0.0.0",

        port=10000

    )