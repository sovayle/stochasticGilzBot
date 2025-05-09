import requests
import os
from datetime import datetime, timedelta

# CONFIGURATION
TELEGRAM_TOKEN_GILZ = os.getenv("TELEGRAM_TOKEN_GILZ")
TELEGRAM_CHAT_ID_V2 = os.getenv("TELEGRAM_CHAT_ID_V2")
chat_ids = [TELEGRAM_CHAT_ID_V2]

# API keys assigned per symbol
API_KEY_MAP = {
    "EUR/JPY": os.getenv("TWELVE_API_KEY_3"),
    "GBP/USD": os.getenv("TWELVE_API_KEY_4")
}

SYMBOLS = ["EUR/JPY", "GBP/USD"]
TIMEFRAMES = ["15min", "1h", "4h", "1day"]
K_PERIODS = [30, 65, 100]
THRESHOLD_LOW = 3
THRESHOLD_HIGH = 100 - THRESHOLD_LOW

def fetch_data(symbol, interval):
    """Fetch time series data using the API key assigned to the symbol."""
    api_key = API_KEY_MAP[symbol]
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": 70,
        "apikey": api_key
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"❌ HTTP {response.status_code} for {symbol}: {response.text}")
        return []

    data = response.json()
    if "values" in data:
        return data["values"]
    if data.get("code") == 429:
        print(f"⚠️ Rate limit hit for {symbol}. Key: {api_key}")
    else:
        print(f"❌ Unexpected error for {symbol}: {data}")
    return []

def calculate_stochastic(values, k_period):
    closes = [float(c["close"]) for c in values]
    highs  = [float(c["high"])  for c in values]
    lows   = [float(c["low"])   for c in values]

    if len(closes) < k_period:
        return None

    recent_close = closes[0]
    low_n  = min(lows[:k_period])
    high_n = max(highs[:k_period])
    if high_n == low_n:
        return None

    k = ((recent_close - low_n) / (high_n - low_n)) * 100
    return round(k, 2)

def send_telegram_message(text, chat_ids):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN_GILZ}/sendMessage"
    for chat_id in chat_ids:
        requests.post(url, data={"chat_id": chat_id, "text": text})

def main():
    for tf in TIMEFRAMES:
        print(f"\n📊 Checking data for {tf} timeframe...")
        for symbol in SYMBOLS:
            values = fetch_data(symbol, tf)
            if not values:
                print(f"❌ No data for {symbol} at {tf}")
                continue

            t0 = values[0]["datetime"]
            try:
                candle_dt = datetime.strptime(t0, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                candle_dt = datetime.strptime(t0, "%Y-%m-%d")
            shifted = candle_dt - timedelta(hours=7)
            time_str = shifted.strftime("%Y-%m-%d %H:%M:%S")

            k_values = [calculate_stochastic(values, p) for p in K_PERIODS]
            if None in k_values:
                continue

            print(f"{symbol} ({tf}) | {time_str} | %K30={k_values[0]} | %K65={k_values[1]} | %K100={k_values[2]}")

            if all(k <= THRESHOLD_LOW for k in k_values):
                signal = "🟢 BUY"
            elif all(k >= THRESHOLD_HIGH for k in k_values):
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
