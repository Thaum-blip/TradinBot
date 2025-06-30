import time
import talib
import numpy as np
from binance.client import Client
from binance.enums import *
from datetime import datetime
import csv

# Configuration Binance API
API_KEY = 'your_api_key'
API_SECRET = 'your_api_secret'
client = Client(API_KEY, API_SECRET)

# Paramètres de trading
SYMBOL = 'BTCUSDT'
TRADE_QUANTITY = 0.001  # Quantité à trader
TIMEFRAME = '1m'  # Intervalle de temps pour les données
STOP_LOSS_PERCENT = 0.005  # Stop loss à 0.5%
TAKE_PROFIT_PERCENT = 0.007  # Take profit à 0.7%
VOLUME_THRESHOLD = 100  # Volume minimal requis
FEE_PERCENT = 0.001  # Frais de Binance (~0.1%)

# Fichier de logs
LOG_FILE = "trading_logs.csv"

def init_logs():
    with open(LOG_FILE, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Time", "Action", "Price", "Quantity", "Profit/Loss"])

def log_transaction(action, price, quantity, profit_loss=0):
    with open(LOG_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([datetime.now(), action, price, quantity, profit_loss])

def fetch_data(symbol, interval, limit=50):
    klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    closes = np.array([float(kline[4]) for kline in klines], dtype=np.float64)
    volumes = np.array([float(kline[5]) for kline in klines], dtype=np.float64)
    return closes, volumes

def calculate_indicators(closes):
    rsi = talib.RSI(closes, timeperiod=14)
    sma_short = talib.SMA(closes, timeperiod=5)
    sma_long = talib.SMA(closes, timeperiod=20)
    return rsi, sma_short, sma_long

def place_order(order_type, quantity, price):
    try:
        if order_type == 'BUY':
            order = client.order_limit_buy(
                symbol=SYMBOL, quantity=quantity, price=price
            )
        elif order_type == 'SELL':
            order = client.order_limit_sell(
                symbol=SYMBOL, quantity=quantity, price=price
            )
        print(f"Order placed: {order_type} {quantity} {SYMBOL} at {price}")
    except Exception as e:
        print(f"Failed to place order: {e}")

def main():
    init_logs()
    position = None  # Current position ("LONG" or None)
    entry_price = 0

    while True:
        closes, volumes = fetch_data(SYMBOL, TIMEFRAME)
        if len(closes) < 20:
            print("Not enough data yet...")
            time.sleep(5)
            continue

        rsi, sma_short, sma_long = calculate_indicators(closes)
        last_close = closes[-1]
        last_volume = volumes[-1]

        print(f"Last close: {last_close}, RSI: {rsi[-1]:.2f}, Volume: {last_volume}")

        # Vérifier le volume minimal
        if last_volume < VOLUME_THRESHOLD:
            print("Volume too low, skipping...")
            time.sleep(5)
            continue

        # Logique d'achat/vente
        if position is None:
            if sma_short[-1] > sma_long[-1] and rsi[-1] < 30:
                # Acheter
                entry_price = last_close
                place_order('BUY', TRADE_QUANTITY, entry_price)
                position = 'LONG'
                log_transaction('BUY', entry_price, TRADE_QUANTITY)
        elif position == 'LONG':
            stop_loss = entry_price * (1 - STOP_LOSS_PERCENT)
            take_profit = entry_price * (1 + TAKE_PROFIT_PERCENT)

            if last_close <= stop_loss:
                # Vendre avec stop loss
                place_order('SELL', TRADE_QUANTITY, last_close)
                position = None
                log_transaction('SELL', last_close, TRADE_QUANTITY, last_close - entry_price - (entry_price * FEE_PERCENT))

            elif last_close >= take_profit:
                # Vendre avec take profit
                place_order('SELL', TRADE_QUANTITY, last_close)
                position = None
                log_transaction('SELL', last_close, TRADE_QUANTITY, last_close - entry_price - (entry_price * FEE_PERCENT))

        time.sleep(5)  # Délai entre les boucles

if __name__ == "__main__":
    main()
