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

# Хранилище сессий клиентов: {"номер_телефона": "код_товара"}
user_sessions = {}


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================
def load_products():
  """Загрузка базы товаров из JSON файла"""
  try:
    with open("products.json", "r", encoding="utf-8") as f:
      return json.load(f)
  except Exception as e:
    print(f"Ошибка загрузки products.json: {e}")
    return {}


PRODUCTS_DB = load_products()


def send_whatsapp_message(chat_id: str, text: str):
  """Отправка текстового сообщения в WhatsApp через Green API"""
  url = f"{GREEN_API_URL}/sendMessage/{GREEN_API_TOKEN}"
  payload = {"chatId": chat_id, "message": text}
  headers = {"Content-Type": "application/json"}
  try:
    requests.post(url, json=payload, headers=headers)
  except Exception as e:
    print(f"Ошибка отправки в WhatsApp: {e}")


def detect_campaign(message_text: str):
  """Определяем, по какому товару/ключевому слову пишет клиент"""
  text_lower = message_text.lower()
  for campaign_id, data in PRODUCTS_DB.items():
    keywords = data.get("trigger_keywords", [])
    for kw in keywords:
      if kw.lower() in text_lower:
        return campaign_id
  return None


def ask_ai(campaign_id: str, user_message: str) -> str:
  """Запрос к Gemini ИИ через прямой REST API без зависимостей от SDK"""
  product_data = PRODUCTS_DB.get(campaign_id)
  if not product_data:
    return "Спасибо за обращение! Наш менеджер скоро ответит вам."

  system_instruction = product_data["system_prompt"]

  # Используем прямое обращение к API Google
  url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

  payload = {
      "contents": [
          {
              "role": "user",
              "parts": [{
                  "text": (
                      f"{system_instruction}\n\nВопрос"
                      f" клиента: {user_message}"
                  )
              }],
          }
      ]
  }

  headers = {"Content-Type": "application/json"}

  try:
    response = requests.post(url, json=payload, headers=headers, timeout=15)
    res_data = response.json()

    if response.status_code == 200:
      candidates = res_data.get("candidates", [])
      if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        if parts:
          return parts[0].get("text", "")
    else:
      print(f"Ошибка REST API Gemini ({response.status_code}): {res_data}")

  except Exception as e:
    print(f"Ошибка обращения к Gemini REST API: {e}")

  return "Саламатсызбы! Бир аздан соң маалымат беребиз..."


# ==========================================
# ВЕБХУК ДЛЯ ПРИЕМА СООБЩЕНИЙ С WHATSAPP
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

    # 1. Проверяем, есть ли ключевое слово товара в сообщении
    new_campaign = detect_campaign(text_message)
    if new_campaign:
      user_sessions[chat_id] = new_campaign

    # 2. Достаем текущую тему диалога
    current_campaign = user_sessions.get(chat_id)

    # 3. Если тема определена — генерируем ответ через Gemini
    if current_campaign:
      ai_response = ask_ai(current_campaign, text_message)
      send_whatsapp_message(chat_id, ai_response)
    else:
      # Сообщение без ключевого слова и без активной сессии
      send_whatsapp_message(
          chat_id, "Саламатсызбы! Бир аздан соң маалымат беребиз..."
      )

  return {"status": "ok"}


if __name__ == "__main__":
  run("main:app", host="0.0.0.0", port=10000, reload=True)