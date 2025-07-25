from flask import Flask
import threading
import requests
from bs4 import BeautifulSoup
import time
import os

# ==== CONFIG ====
PRODUCT_URL = 'https://www.zeptonow.com/pn/taj-mahal-tea-rich-and-flavourful-chai/pvid/4ac2eaf8-4f7f-4b66-9d6a-2c7100199094'
CHECK_INTERVAL = 2 * 1  # 2 seconds for testing, change to 15*60 for 15 minutes

# Telegram - Use environment variables for security
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '7314069619:AAEwlHGphXG22HDC72sLLM-e2EwPuuTLikU')
CHAT_ID = os.getenv('CHAT_ID', '1574906622')

app = Flask('')

@app.route('/')
def home():
    return "Stock monitor is active."

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message}
        response = requests.post(url, data=payload, timeout=10)
        
        if response.status_code == 200:
            print(f"[SUCCESS] Message sent: {message}")
            return True
        else:
            print(f"[ERROR] Telegram API error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram message: {e}")
        return False

def check_stock_status():
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(PRODUCT_URL, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"[ERROR] HTTP {response.status_code} when fetching product page")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        print(f"[DEBUG] Page title: {soup.title.string if soup.title else 'No title'}")
        
        # Look for Add to Cart button or similar buy buttons
        add_to_cart_buttons = [
            soup.find('button', string=lambda t: t and 'add to cart' in t.lower()),
            soup.find('button', string=lambda t: t and 'add' in t.lower()),
            soup.find('button', string=lambda t: t and 'buy' in t.lower()),
            soup.find('div', {'class': lambda x: x and 'add' in str(x).lower()}),
            soup.find('button', {'class': lambda x: x and 'add' in str(x).lower()})
        ]
        
        # Look for specific out of stock indicators
        out_of_stock_indicators = [
            soup.find('button', string=lambda t: t and 'out of stock' in t.lower()),
            soup.find('div', string=lambda t: t and 'out of stock' in t.lower()),
            soup.find('span', string=lambda t: t and 'out of stock' in t.lower()),
            soup.find('button', {'disabled': True, 'class': lambda x: x and 'disabled' in str(x).lower()}),
            soup.find(string=lambda t: t and 'currently unavailable' in t.lower()),
            soup.find(string=lambda t: t and 'sold out' in t.lower())
        ]
        
        # Check for "Add to Cart" type buttons (indicates in stock)
        has_add_button = any(btn for btn in add_to_cart_buttons if btn)
        
        # Check for explicit out of stock indicators
        has_out_of_stock = any(indicator for indicator in out_of_stock_indicators if indicator)
        
        print(f"[DEBUG] Add to cart button found: {has_add_button}")
        print(f"[DEBUG] Out of stock indicator found: {has_out_of_stock}")
        
        # If we find an add button and no out of stock indicator, it's in stock
        if has_add_button and not has_out_of_stock:
            in_stock = True
        elif has_out_of_stock:
            in_stock = False
        else:
            # Fallback: look at page content more broadly
            page_text = soup.get_text().lower()
            if 'add to cart' in page_text or 'buy now' in page_text:
                in_stock = True
            elif 'out of stock' in page_text or 'unavailable' in page_text:
                in_stock = False
            else:
                # Default to True if we can't determine (assume in stock)
                in_stock = True
                print("[WARNING] Could not definitively determine stock status, assuming in stock")
        
        print(f"[DEBUG] Final determination - In Stock: {in_stock}")
        return in_stock
        
    except Exception as e:
        print(f"[ERROR] Error checking stock status: {e}")
        return None

def stock_loop():
    previous_status = None
    
    # Send initial startup message
    send_telegram_message("🤖 Stock monitor started! Monitoring product...")
    
    while True:
        try:
            in_stock = check_stock_status()
            
            if in_stock is None:
                print("[WARNING] Could not determine stock status, skipping this check")
                time.sleep(CHECK_INTERVAL)
                continue
                
            print(f"[INFO] In Stock: {in_stock}")
            
            # Send notification on status change
            if previous_status is not None and in_stock != previous_status:
                if in_stock:
                    send_telegram_message(f"🟢 Product is BACK IN STOCK!\n{PRODUCT_URL}")
                else:
                    send_telegram_message(f"🔴 Product is OUT OF STOCK!\n{PRODUCT_URL}")
            elif previous_status is None:
                # Send initial status
                status_text = "IN STOCK ✅" if in_stock else "OUT OF STOCK ❌"
                send_telegram_message(f"📊 Initial status: {status_text}\n{PRODUCT_URL}")
                
            previous_status = in_stock
            
        except Exception as e:
            print(f"[ERROR] Unexpected error in stock loop: {e}")
            
        time.sleep(CHECK_INTERVAL)

# === START ===
threading.Thread(target=run_flask).start()
stock_loop()
