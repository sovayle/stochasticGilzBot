import requests
import os
import time
from datetime import datetime, timedelta

# CONFIGURATION
TELEGRAM_TOKEN_GILZ = os.getenv("TELEGRAM_TOKEN_GILZ")
TELEGRAM_CHAT_ID_V2 = os.getenv("TELEGRAM_CHAT_ID_V2")
chat_ids = [TELEGRAM_CHAT_ID_V2]

# Two API keys for failover
API_KEYS = [
    os.getenv("TWELVE_API_KEY_3"),
    os.getenv("TWELVE_API_KEY_4")
]

SYMBOLS = ["EUR/JPY", "GBP/USD", "CHF/JPY", "EUR/USD"]
TIMEFRAMES = ["15min", "1h", "4h", "1day"]
K_PERIODS = [30, 65, 100]
THRESHOLD = 3

def fetch_data(symbol, interval):
    url = "https://api.twelvedata.com/time_series"

    for api_key in API_KEYS:
        params = {
            "symbol": symbol,
            "interval": interval,
            "outputsize": 70,
            "apikey": api_key
        }
        response = requests.get(url, params=params)
        data = response.json()

        if "values" in data:
            return data["values"]

        if data.get("code") == 429:
            print("⚠️ API key rate limit hit. Trying next key...")
            continue

        print("❌ Unexpected API error.")
        return []

    print("‼️ All API keys exceeded their limits.")
    return []

def calculate_stochastic(values, k_period):
    closes = [float(c["close"]) for c in values]
    highs = [float(c["high"]) for c in values]
    lows = [float(c["low"]) for c in values]

    if len(closes) < k_period:
        return None

    recent_close = closes[0]
    low_n = min(lows[:k_period])
    high_n = max(highs[:k_period])

    if high_n - low_n == 0:
        return None

    k = ((recent_close - low_n) / (high_n - low_n)) * 100
    return round(k, 2)

def send_telegram_message(text, chat_ids):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN_GILZ}/sendMessage"
    for chat_id in chat_ids:
        payload = {"chat_id": chat_id, "text": text}
        requests.post(url, data=payload)

def main():
    for tf in TIMEFRAMES:
        print(f"\n📊 Checking data for {tf} timeframe...")
        for symbol in SYMBOLS:
            values = fetch_data(symbol, tf)
            time.sleep(3)  # 🕒 3-second delay between requests

            if not values:
                print(f"❌ No data for {symbol} at {tf} timeframe.")
                continue

            try:
                candle_dt = datetime.strptime(values[0]["datetime"], "%Y-%m-%d %H:%M:%S")
                shifted_time = candle_dt - timedelta(hours=7)
                time_str = shifted_time.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                candle_dt = datetime.strptime(values[0]["datetime"], "%Y-%m-%d")
                shifted_time = candle_dt - timedelta(hours=7)
                time_str = shifted_time.strftime("%Y-%m-%d")

            k_values = []
            for period in K_PERIODS:
                k = calculate_stochastic(values, period)
                k_values.append(k)

            if None in k_values:
                continue

            print(f"{symbol} ({tf}) | Time: {time_str} | %K30={k_values[0]} | %K65={k_values[1]} | %K100={k_values[2]}")

            # Check for Stoch GILA Opportunity
            if all(k <= THRESHOLD for k in k_values):
                signal = "🟢 BUY"
            elif all(k >= 100 - THRESHOLD for k in k_values):
                signal = "🔴 SELL"
            else:
                continue

            send_telegram_message(
                f"🔥 Stoch GILA Opportunity!\n"
                f"{symbol} ({tf}) | Time: {time_str}\n"
                f"%K30={k_values[0]}, %K65={k_values[1]}, %K100={k_values[2]}\n"
                f"Signal: {signal}",
                chat_ids
            )

if __name__ == "__main__":
    main()
