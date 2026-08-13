import os
import json
import requests
from fastapi import FastAPI, Request
from uvicorn import run
from google import genai

app = FastAPI()

# ==========================================
# КЛЮЧИ ДОСТУПА (Вставим на следующем шаге)
# ==========================================
GREEN_API_INSTANCE_ID = os.getenv("GREEN_API_INSTANCE_ID", "710722709717")
GREEN_API_TOKEN = os.getenv("GREEN_API_TOKEN", "f4e29103838f45ach23170c0efa7ba33haa728c3812b42d186")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GREEN_API_URL = f"https://api.green-api.com/waInstance{GREEN_API_INSTANCE_ID}"

# Инициализация ИИ Gemini
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Хранилище сессий клиентов: {"номер_телефона": "код_товара"}
user_sessions = {}

def load_products():
    with open("products.json", "r", encoding="utf-8") as f:
        return json.load(f)

PRODUCTS_DB = load_products()

def send_whatsapp_message(chat_id: str, text: str):
    url = f"{GREEN_API_URL}/sendMessage/{GREEN_API_TOKEN}"
    payload = {"chatId": chat_id, "message": text}
    headers = {"Content-Type": "application/json"}
    try:
        requests.post(url, json=payload, headers=headers)
    except Exception as e:
        print(f"Ошибка отправки в WhatsApp: {e}")

def detect_campaign(message_text: str):
    text_lower = message_text.lower()
    for campaign_id, data in PRODUCTS_DB.items():
        for keyword in data["trigger_keywords"]:
            if keyword in text_lower:
                return campaign_id
    return None

def ask_ai(campaign_id: str, user_message: str) -> str:
    product_data = PRODUCTS_DB.get(campaign_id)
    if not product_data:
        return "Спасибо за обращение! Наш менеджер скоро ответит вам."

    system_instruction = product_data["system_prompt"]
    prompt = f"{system_instruction}\n\nВопрос клиента: {user_message}"
    
    try:
        response = ai_client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
        )
        return response.text
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        return "Саламатсызбы! Бир аздан соң маалымат беребиз..."

@app.post("/webhook")
async def receive_whatsapp(request: Request):
    data = await request.json()
    
    if data.get("typeWebhook") == "incomingMessageReceived":
        message_data = data.get("messageData", {})
        sender_data = data.get("senderData", {})
        
        chat_id = sender_data.get("chatId")
        text_message = ""
        
        if message_data.get("typeMessage") == "textMessage":
            text_message = message_data.get("textMessageData", {}).get("textMessage", "")
        
        if not text_message or not chat_id:
            return {"status": "ignored"}

        # 1. Проверяем, пришёл ли клиент по новой рекламе
        new_campaign = detect_campaign(text_message)
        if new_campaign:
            user_sessions[chat_id] = new_campaign

        current_campaign = user_sessions.get(chat_id)

        # 2. Генерируем и отправляем ответ
        if current_campaign:
            ai_answer = ask_ai(current_campaign, text_message)
            send_whatsapp_message(chat_id, ai_answer)
        else:
            send_whatsapp_message(chat_id, "Саламатсызбы! Кайсы товар боюнча маалымат алайын дедиңиз эле?")

    return {"status": "ok"}

if __name__ == "__main__":
    run("main:app", host="0.0.0.0", port=8000, reload=True)