import ccxt
import os
from dotenv import load_dotenv
import time
import pandas as pd
import ta  # technical analysis lib

load_dotenv()
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')

def init_exchange():
    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'},
    })
    exchange.set_sandbox_mode(True)
    return exchange

def fetch_ohlcv(exchange, symbol='BTC/USDT', timeframe='1m', limit=100):
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def apply_indicators(df):
    df['ma7'] = df['close'].rolling(window=7).mean()
    df['ma25'] = df['close'].rolling(window=25).mean()
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    return df

def check_signals(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Cross MA7 crossing MA25 upward => buy signal
    buy_signal = (prev['ma7'] < prev['ma25']) and (last['ma7'] > last['ma25']) and (last['rsi'] < 70)

    # Cross MA7 crossing MA25 downward => sell signal or RSI > 70
    sell_signal = ((prev['ma7'] > prev['ma25']) and (last['ma7'] < last['ma25'])) or (last['rsi'] > 70)

    return buy_signal, sell_signal

def main():
    exchange = init_exchange()
    symbol = 'BTC/USDT'
    position = None

    while True:
        df = fetch_ohlcv(exchange, symbol)
        df = apply_indicators(df)
        buy_signal, sell_signal = check_signals(df)

        price = df['close'].iloc[-1]
        print(f"Prix: {price:.2f}, Buy signal: {buy_signal}, Sell signal: {sell_signal}")

        if position is None and buy_signal:
            print("Signal achat détecté - Achat 0.001 BTC")
            order = exchange.create_market_buy_order(symbol, 0.001)
            print("Ordre d'achat:", order)
            position = 'long'

        elif position == 'long' and sell_signal:
            print("Signal vente détecté - Vente 0.001 BTC")
            order = exchange.create_market_sell_order(symbol, 0.001)
            print("Ordre de vente:", order)
            position = None
        else:
            print("Pas d'action, on attend...")

        time.sleep(60)  # Attendre 1 minute avant prochain check

if __name__ == "__main__":
    main()
