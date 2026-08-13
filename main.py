import json
import os
import requests
from fastapi import FastAPI, Request
from uvicorn import run

app = FastAPI()

# ==========================================
# КЛЮЧИ ДОСТУПА И НАСТРОЙКИ
# ==========================================
GREEN_API_INSTANCE_ID = os.getenv("GREEN_API_INSTANCE_ID", "710722709717")
GREEN_API_TOKEN = os.getenv(
    "GREEN_API_TOKEN", "f4e29103838f45ach23170c0efa7ba33haa728c3812b42d186"
)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GREEN_API_URL = (
    f"https://api.green-api.com/waInstance{GREEN_API_INSTANCE_ID}"
)

user_sessions = {}


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================
def load_products():
  try:
    with open("products.json", "r", encoding="utf-8") as f:
      return json.load(f)
  except Exception as e:
    print(f"Ошибка загрузки products.json: {e}")
    return {}


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
    keywords = data.get("trigger_keywords", [])
    for kw in keywords:
      if kw.lower() in text_lower:
        return campaign_id
  return None


def ask_ai(campaign_id: str, user_message: str) -> str:
  product_data = PRODUCTS_DB.get(campaign_id)
  if not product_data:
    return "Спасибо за обращение! Наш менеджер скоро ответит вам."

  system_instruction = product_data["system_prompt"]
  prompt_text = f"{system_instruction}\n\nВопрос клиента: {user_message}"

  headers = {"Content-Type": "application/json"}
  payload = {
      "contents": [
          {"role": "user", "parts": [{"text": prompt_text}]}
      ]
  }

  # Список точных имен моделей БЕЗ префикса "models/"
  models = ["gemini-2.5-flash", "gemini-1.5-flash"]

  for model_name in models:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
    try:
      response = requests.post(url, json=payload, headers=headers, timeout=15)
      res_data = response.json()

      if response.status_code == 200:
        candidates = res_data.get("candidates", [])
        if candidates:
          parts = candidates[0].get("content", {}).get("parts", [])
          if parts and parts[0].get("text"):
            return parts[0].get("text")
      else:
        print(f"Ошибка {model_name} ({response.status_code}): {res_data}")
    except Exception as e:
      print(f"Сбой запроса к {model_name}: {e}")

  return "Саламатсызбы! Бир аздан соң маалымат беребиз..."


# ==========================================
# ВЕБХУК
# ==========================================
@app.post("/webhook")
async def receive_whatsapp(request: Request):
  data = await request.json()

  if data.get("typeWebhook") == "incomingMessageReceived":
    message_data = data.get("messageData", {})
    sender_data = data.get("senderData", {})

    chat_id = sender_data.get("chatId")
    text_message = ""

    if message_data.get("typeMessage") == "textMessage":
      text_message = message_data.get("textMessageData", {}).get(
          "textMessage", ""
      )

    if not text_message or not chat_id:
      return {"status": "ignored"}

    new_campaign = detect_campaign(text_message)
    if new_campaign:
      user_sessions[chat_id] = new_campaign

    current_campaign = user_sessions.get(chat_id)

    if current_campaign:
      ai_response = ask_ai(current_campaign, text_message)
      send_whatsapp_message(chat_id, ai_response)
    else:
      send_whatsapp_message(
          chat_id, "Саламатсызбы! Бир аздан соң маалымат беребиз..."
      )

  return {"status": "ok"}


if __name__ == "__main__":
  run("main:app", host="0.0.0.0", port=10000, reload=True)