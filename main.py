from flask import Flask
import threading
import requests
from bs4 import BeautifulSoup
import time

# ==== CONFIG ====
PRODUCT_URL = 'https://www.zeptonow.com/pn/taj-mahal-tea-rich-and-flavourful-chai/pvid/4ac2eaf8-4f7f-4b66-9d6a-2c7100199094'
CHECK_INTERVAL = 2 * 1  # 15 minutes

# Telegram
TELEGRAM_TOKEN = '7314069619:AAEwlHGphXG22HDC72sLLM-e2EwPuuTLikU'
CHAT_ID = '1574906622'

app = Flask('')

@app.route('/')
def home():
    return "Stock monitor is active."

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=payload)

def check_stock_status():
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(PRODUCT_URL, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Look for "Out of Stock" text
    out_of_stock = soup.find(string=lambda t: "out of stock" in t.lower())
    in_stock = out_of_stock is None
    return in_stock

def stock_loop():
    previous_status = None
    while True:
        try:
            in_stock = check_stock_status()
            print(f"[INFO] In Stock: {in_stock}")
            if previous_status is not None and in_stock != previous_status:
                if in_stock:
                    send_telegram_message(f"🟢 Product is BACK IN STOCK!\n{PRODUCT_URL}")
                else:
                    send_telegram_message(f"🔴 Product is OUT OF STOCK again.\n{PRODUCT_URL}")
            previous_status = in_stock
        except Exception as e:
            print(f"[ERROR] {e}")
        time.sleep(CHECK_INTERVAL)

# === START ===
threading.Thread(target=run_flask).start()
stock_loop()
