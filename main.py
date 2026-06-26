from flask import Flask, request
import os
import time
from pybit.unified_trading import HTTP

app = Flask(__name__)

# === НАСТРОЙКИ ===
API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")
TESTNET = False

session = HTTP(
    api_key=API_KEY, 
    api_secret=API_SECRET, 
    testnet=TESTNET,
    recv_window=10000  # увеличиваем таймаут
)

TRADE_MARGIN_PERCENT = 0.05
MAX_MARGIN_USAGE = 0.50
LEVERAGE = 10

@app.route('/webhook', methods=['POST'])
def webhook():
    start_time = time.time()
    try:
        data = request.get_json(silent=True) or request.data.decode('utf-8', errors='ignore')
        message = str(data).upper()

        print("=== СИГНАЛ ===")
        print(message[:300])  # чтобы не спамить

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

        # Быстрый баланс + позиция
        try:
            balance_resp = session.get_wallet_balance(accountType="UNIFIED")
            balance = float(balance_resp['result']['list'][0]['totalEquity'])
            margin_for_trade = max(10, balance * TRADE_MARGIN_PERCENT)  # минимум 10$

            # Проверка лимита
            pos_resp = session.get_positions(category="linear")
            positions = pos_resp.get('result', {}).get('list', [])
            used = sum(float(p.get('positionIM', 0)) for p in positions)
            
            if used + margin_for_trade > balance * MAX_MARGIN_USAGE:
                print("Лимит 50% превышен")
                return "Limit reached", 200
        except:
            margin_for_trade = 15  # fallback

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
            qty=margin_for_trade,
            qtyType="margin",
            positionIdx=0
        )

        print(f"✅ УСПЕХ {side} {symbol} | {margin_for_trade:.1f}$")
        return "Success", 200

    except Exception as e:
        print("❌ Ошибка:", str(e)[:200])
        return "Error", 500
    finally:
        print(f"Время выполнения: {time.time() - start_time:.2f} сек")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
