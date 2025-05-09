import requests
import os
from datetime import datetime, timedelta

# CONFIGURATION
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN_GILZ")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_V2")

chat_ids = [TELEGRAM_CHAT_ID]

# Two API keys for failover
API_KEYS = [
    os.getenv("TWELVE_API_KEY_3"),
    os.getenv("TWELVE_API_KEY_4")
]

SYMBOLS = ["EUR/JPY", "GBP/USD", "CHF/JPY", "EUR/USD"]
TIMEFRAMES = ["15min", "1h", "4h", "1day"]
K_PERIODS = [30, 65, 100]
THRESHOLD_LOW = 3
THRESHOLD_HIGH = 97

def fetch_data(symbol, interval):
    url = "https://api.twelvedata.com/time_series"

    for api_key in API_KEYS:
        params = {
            "symbol": symbol,
            "interval": interval,
            "outputsize": 150,  # Ensure we have enough data for %K=100
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
    for tf in TIMEFRAMES:
        print(f"📊 Checking data for {tf} timeframe...")

        for symbol in SYMBOLS:
            values = fetch_data(symbol, tf)
            if not values or len(values) < max(K_PERIODS):
                print(f"❌ Insufficient data for {symbol} ({tf}).")
                continue

            latest_candle = values[0]
            candle_time_str = latest_candle["datetime"]

            try:
                candle_dt = datetime.strptime(candle_time_str, "%Y-%m-%d %H:%M:%S")
                shifted_time = candle_dt - timedelta(hours=7)
                shifted_time_str = shifted_time.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                candle_dt = datetime.strptime(candle_time_str, "%Y-%m-%d")
                shifted_time = candle_dt - timedelta(hours=7)
                shifted_time_str = shifted_time.strftime("%Y-%m-%d")

            stoch_values = {}
            for k_period in K_PERIODS:
                k_value = calculate_stochastic(values, k_period)
                if k_value is None:
                    print(f"⚠️ Not enough data for %K={k_period} on {symbol} ({tf})")
                    break
                stoch_values[k_period] = k_value

            if len(stoch_values) != len(K_PERIODS):
                continue  # Skip if any of the stoch values are missing

            k30, k65, k100 = stoch_values[30], stoch_values[65], stoch_values[100]

            print(f"{symbol} ({tf}) | Time: {shifted_time_str} | %K30={k30} | %K65={k65} | %K100={k100}")

            if all(k <= THRESHOLD_LOW for k in [k30, k65, k100]):
                send_telegram_message(
                    f"🟢 *Stoch GILA BUY Opportunity* 🚨\n{symbol} | {tf}\nTime: {shifted_time_str}\n%K30={k30}, %K65={k65}, %K100={k100}\nPrice: {float(values[0]['close']):.2f}",
                    chat_ids
                )

            elif all(k >= THRESHOLD_HIGH for k in [k30, k65, k100]):
                send_telegram_message(
                    f"🔴 *Stoch GILA SELL Opportunity* 🚨\n{symbol} | {tf}\nTime: {shifted_time_str}\n%K30={k30}, %K65={k65}, %K100={k100}\nPrice: {float(values[0]['close']):.2f}",
                    chat_ids
                )

if __name__ == "__main__":
    main()
