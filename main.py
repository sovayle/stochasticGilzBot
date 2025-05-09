import requests
import os
from datetime import datetime, timedelta

# CONFIGURATION
TELEGRAM_TOKEN_GILZ = os.getenv("TELEGRAM_TOKEN_GILZ")
TELEGRAM_CHAT_ID_V2 = os.getenv("TELEGRAM_CHAT_ID_V2")
#TELEGRAM_CHAT_ID_2 = os.getenv("TELEGRAM_CHAT_ID_2")  # Add this

chat_ids = [TELEGRAM_CHAT_ID_V2] #, TELEGRAM_CHAT_ID_2]  # Add both

# Two API keys for failover
API_KEYS = [
    os.getenv("TWELVE_API_KEY_3"),
    os.getenv("TWELVE_API_KEY_4")
]

SYMBOLS = ["EUR/JPY"]
TIMEFRAMES = {
    "15min": 30,
    "1H": 30,
    "4h": 30
}

def fetch_data(symbol, interval):
    url = "https://api.twelvedata.com/time_series"

    for api_key in API_KEYS:
        params = {
            "symbol": symbol,
            "interval": interval,
            "outputsize": 100,
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
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for chat_id in chat_ids:
        payload = {"chat_id": chat_id, "text": text}
        requests.post(url, data=payload)

def main():
    threshold = 7  # Trigger alert if %K is near 0 or 100

    for tf, k_period in TIMEFRAMES.items():
        print(f"Checking data for {tf} timeframe...")

        for symbol in SYMBOLS:
            values = fetch_data(symbol, tf)
            if not values or len(values) < k_period:
                print(f"No data for {symbol} at {tf} timeframe.")
                continue

            print(f"Data successfully fetched for {symbol} at {tf} timeframe.")

            latest_candle = values[0]
            candle_time_str = latest_candle["datetime"]

            # Handle datetime with or without time (e.g. daily)
            try:
                candle_dt = datetime.strptime(candle_time_str, "%Y-%m-%d %H:%M:%S")
                shifted_time = candle_dt - timedelta(hours=7)
                shifted_time_str = shifted_time.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                candle_dt = datetime.strptime(candle_time_str, "%Y-%m-%d")
                shifted_time = candle_dt - timedelta(hours=7)
                shifted_time_str = shifted_time.strftime("%Y-%m-%d")

            k = calculate_stochastic(values, k_period)
            if k is None:
                continue

            print(f"{symbol} ({tf}) | Latest candle time: {shifted_time_str} | %K = {k}")

            if k <= threshold or k >= (100 - threshold):
                send_telegram_message(
                     f"🚨 {tf} | Time: {shifted_time_str} | Stoch 30 = {k} | Price = {float(values[0]['close']):.2f}",
                    chat_ids
                )

if __name__ == "__main__":
    main()
