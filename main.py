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

def extract_price(soup):
    """Extract price from the product page"""
    try:
        # Common price selectors for e-commerce sites
        price_selectors = [
            'span[data-testid*="price"]',
            '.price',
            '[class*="price"]',
            '[data-testid*="price"]',
            'span[class*="rupee"]',
            'div[class*="price"]'
        ]
        
        # Look for price in various formats
        for selector in price_selectors:
            price_elements = soup.select(selector)
            for element in price_elements:
                text = element.get_text().strip()
                # Extract numbers from price text (₹200, Rs.200, 200, etc.)
                import re
                price_match = re.search(r'[\d,]+(?:\.\d+)?', text.replace(',', ''))
                if price_match:
                    price = float(price_match.group())
                    if 50 <= price <= 10000:  # Reasonable price range filter
                        print(f"[DEBUG] Found price: ₹{price} in element: {text}")
                        return price
        
        # Fallback: search for price in page title or meta tags
        title = soup.title.string if soup.title else ""
        price_match = re.search(r'₹\s*([\d,]+)', title)
        if price_match:
            price = float(price_match.group(1).replace(',', ''))
            print(f"[DEBUG] Found price in title: ₹{price}")
            return price
            
        print("[WARNING] Could not find price on page")
        return None
        
    except Exception as e:
        print(f"[ERROR] Error extracting price: {e}")
        return None

def check_stock_and_price():
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(PRODUCT_URL, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"[ERROR] HTTP {response.status_code} when fetching product page")
            return None, None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        print(f"[DEBUG] Page title: {soup.title.string if soup.title else 'No title'}")
        
        # Extract price
        current_price = extract_price(soup)
        
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
        print(f"[DEBUG] Current price: ₹{current_price}")
        
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
        return in_stock, current_price
        
    except Exception as e:
        print(f"[ERROR] Error checking stock and price: {e}")
        return None, None

def stock_loop():
    previous_status = None
    previous_price = None
    
    # Send initial startup message
    send_telegram_message("🤖 Stock & Price monitor started! Monitoring product...")
    
    while True:
        try:
            in_stock, current_price = check_stock_and_price()
            
            if in_stock is None:
                print("[WARNING] Could not determine stock status, skipping this check")
                time.sleep(CHECK_INTERVAL)
                continue
                
            print(f"[INFO] In Stock: {in_stock}, Price: ₹{current_price}")
            
            # Prepare price info for messages
            price_text = f"₹{current_price}" if current_price else "Price not found"
            
            # Check for stock status changes
            stock_changed = previous_status is not None and in_stock != previous_status
            
            # Check for price changes (only if both prices are available)
            price_changed = (previous_price is not None and current_price is not None and 
                           abs(current_price - previous_price) >= 1)  # Only notify for changes ≥ ₹1
            
            # Send notifications
            if stock_changed:
                if in_stock:
                    send_telegram_message(f"🟢 Product is BACK IN STOCK!\n💰 Current Price: {price_text}\n{PRODUCT_URL}")
                else:
                    send_telegram_message(f"🔴 Product is OUT OF STOCK!\n💰 Last Price: {price_text}\n{PRODUCT_URL}")
            elif price_changed:
                price_diff = current_price - previous_price
                if price_diff > 0:
                    emoji = "📈"
                    change_text = f"increased by ₹{price_diff:.2f}"
                else:
                    emoji = "📉"
                    change_text = f"decreased by ₹{abs(price_diff):.2f}"
                
                status_emoji = "✅" if in_stock else "❌"
                send_telegram_message(f"{emoji} PRICE CHANGE!\n💰 New Price: {price_text} (was ₹{previous_price})\n📊 Price {change_text}\n🛒 Stock Status: {status_emoji}\n{PRODUCT_URL}")
            elif previous_status is None:
                # Send initial status
                status_text = "IN STOCK ✅" if in_stock else "OUT OF STOCK ❌"
                send_telegram_message(f"📊 Initial status: {status_text}\n💰 Current Price: {price_text}\n{PRODUCT_URL}")
                
            previous_status = in_stock
            if current_price is not None:
                previous_price = current_price
            
        except Exception as e:
            print(f"[ERROR] Unexpected error in stock loop: {e}")
            
        time.sleep(CHECK_INTERVAL)

# === START ===
threading.Thread(target=run_flask).start()
stock_loop()
