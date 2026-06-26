from flask import Flask, request
import os
import time
from pybit.unified_trading import HTTP

app = Flask(__name__)

API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")
TESTNET = False

session = HTTP(
    api_key=API_KEY, 
    api_secret=API_SECRET, 
    testnet=TESTNET,
    recv_window=20000
)

TRADE_MARGIN_PERCENT = 0.05
MAX_MARGIN_USAGE = 0.50
LEVERAGE = 10

# Защита от спама
last_trade_time = 0
MIN_TIME_BETWEEN_TRADES = 5  # минимум 5 секунд между сделками

@app.route('/webhook', methods=['POST'])
def webhook():
    global last_trade_time
    start = time.time()
    try:
        data = request.get_json(silent=True) or request.data.decode('utf-8', errors='ignore')
        message = str(data).upper()

        print("=== СИГНАЛ ===")
        print(message)

        if "ENTER-LONG" in message:
            side = "Buy"
        elif "ENTER-SHORT" in message:
            side = "Sell"
        else:
            return "Ignored", 200

        # Тикер
        ticker = None
        for word in message.split():
            if "USDT" in word.upper():
                ticker = word.replace(".P", "").strip().upper()
                break
        if not ticker:
            ticker = "BTCUSDT"
        symbol = ticker + ".P"

        print(f"→ {side} {symbol}")

        # Анти-спам
        now = time.time()
        if now - last_trade_time < MIN_TIME_BETWEEN_TRADES:
            print("⏳ Слишком часто — пропускаем")
            return "Too frequent", 200
        last_trade_time = now

        # Баланс
        try:
            bal = session.get_wallet_balance(accountType="UNIFIED")
            balance = float(bal['result']['list'][0]['totalEquity'])
            margin = max(10, round(balance * TRADE_MARGIN_PERCENT, 2))
            print(f"Баланс: {balance:.2f}$ → Маржа: {margin}$")
        except Exception as e:
            print("Ошибка баланса:", e)
            margin = 15

        # Проверка лимита
        try:
            pos = session.get_positions(category="linear")
            used = sum(float(p.get('positionIM', 0)) for p in pos.get('result', {}).get('list', []))
            if used + margin > balance * MAX_MARGIN_USAGE:
                print("Лимит 50% превышен")
                return "Limit reached", 200
        except:
            pass

        # Плечо
        try:
            session.set_leverage(category="linear", symbol=symbol, buyLeverage=LEVERAGE, sellLeverage=LEVERAGE)
        except:
            pass

        # Ордер
        order = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            orderType="Market",
            qty=margin,
            qtyType="margin",
            positionIdx=0
        )
        print(f"✅ УСПЕШНО {side} {symbol} | {margin}$")
        return "Success", 200

    except Exception as e:
        error_msg = str(e)
        print("❌ ОШИБКА:", error_msg)
        
        if "rate limit" in error_msg.lower() or "403" in error_msg:
            print("Rate limit от Bybit — ждём...")
            time.sleep(3)
        elif "ip" in error_msg.lower() or "usa" in error_msg.lower():
            print("Проблема с IP (USA) — Bybit блокирует")
        
        return "Error", 500
    finally:
        print(f"Время выполнения: {time.time()-start:.2f} сек\n")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
