from flask import Flask, request
import os
from pybit.unified_trading import HTTP

app = Flask(__name__)

# === НАСТРОЙКИ ===
API_KEY = os.getenv("BYBIT_API_KEY")
API_SECRET = os.getenv("BYBIT_API_SECRET")
TESTNET = False  # True для теста

session = HTTP(api_key=API_KEY, api_secret=API_SECRET, testnet=TESTNET)

TRADE_MARGIN_PERCENT = 0.05   # 5% от баланса на одну сделку
MAX_MARGIN_USAGE = 0.50       # максимум 50% депозита в открытых позициях

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json() or request.data.decode('utf-8')
        message = str(data).upper()

        print("Сигнал:", message)

        # Определяем направление
        if "ENTER-LONG" in message:
            side = "Buy"
        elif "ENTER-SHORT" in message:
            side = "Sell"
        else:
            return "Ignored", 200

        # Извлекаем тикер
        ticker = None
        for word in message.split():
            if "USDT" in word:
                ticker = word.replace(".P", "").strip()
                break

        if not ticker:
            ticker = "BTCUSDT"

        symbol = ticker + ".P"

        # === РАСЧЁТ РАЗМЕРА ПОЗИЦИИ ===
        # Получаем баланс
        balance = session.get_wallet_balance(accountType="UNIFIED")['result']['list'][0]['totalEquity']
        balance = float(balance)

        margin_for_trade = balance * TRADE_MARGIN_PERCENT

        # Проверка лимита 50%
        positions = session.get_positions(category="linear")['result']['list']
        used_margin = sum(float(p['positionIM']) for p in positions if float(p['positionIM']) > 0)

        if used_margin + margin_for_trade > balance * MAX_MARGIN_USAGE:
            print("Превышен лимит 50% маржи. Сделка отклонена.")
            return "Margin limit reached", 200

        # Открываем ордер
        order = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            orderType="Market",
            qty=margin_for_trade,           # в USDT
            qtyType="margin",               # важно!
            leverage=10
        )

        print(f"✅ {side} по {symbol} | Маржа: {margin_for_trade:.2f}$")
        return "Success", 200

    except Exception as e:
        print("Ошибка:", e)
        return "Error", 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
