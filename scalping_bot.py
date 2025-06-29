import ccxt
import time
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')

def init_exchange():
    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'options': {'defaultType': 'spot'},
    })
    exchange.set_sandbox_mode(True)  # à mettre False pour live
    return exchange

exchange = init_exchange()

def fetch_ohlcv(symbol, timeframe='1m', limit=100):
    data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def add_indicators(df):
    # EMA rapides et lentes
    df['EMA7'] = df['close'].ewm(span=7, adjust=False).mean()
    df['EMA25'] = df['close'].ewm(span=25, adjust=False).mean()
    
    # RSI 14
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    RS = gain / loss
    df['RSI'] = 100 - (100 / (1 + RS))
    
    # Bollinger Bands 20, 2 std dev
    df['MA20'] = df['close'].rolling(window=20).mean()
    df['stddev'] = df['close'].rolling(window=20).std()
    df['BB_upper'] = df['MA20'] + (df['stddev'] * 2)
    df['BB_lower'] = df['MA20'] - (df['stddev'] * 2)
    
    return df

def check_buy_signal(df):
    # EMA7 croise au-dessus EMA25 + RSI < 30 + prix <= BB_lower
    if (df['EMA7'].iloc[-2] <= df['EMA25'].iloc[-2] and
        df['EMA7'].iloc[-1] > df['EMA25'].iloc[-1] and
        df['RSI'].iloc[-1] < 30 and
        df['close'].iloc[-1] <= df['BB_lower'].iloc[-1]):
        return True
    return False

def check_sell_signal(df):
    # EMA7 croise en dessous EMA25 + RSI > 70 + prix >= BB_upper
    if (df['EMA7'].iloc[-2] >= df['EMA25'].iloc[-2] and
        df['EMA7'].iloc[-1] < df['EMA25'].iloc[-1] and
        df['RSI'].iloc[-1] > 70 and
        df['close'].iloc[-1] >= df['BB_upper'].iloc[-1]):
        return True
    return False

def get_balance():
    balance = exchange.fetch_balance()
    usd = balance['total'].get('USDT', 0)
    btc = balance['total'].get('BTC', 0)
    return usd, btc

def place_order(symbol, side, amount):
    try:
        order = exchange.create_order(symbol, 'market', side, amount)
        return order
    except Exception as e:
        print(f"Erreur lors de l'ordre {side}: {e}")
        return None

def print_trade_summary(order):
    usd_balance, btc_balance = get_balance()
    btc_in_usd = btc_balance * order['price'] if order and 'price' in order else 0
    total = usd_balance + btc_in_usd
    print(f"--- {order['side'].upper()} exécuté ---")
    print(f"Symbol: {order['symbol']} - Amount: {order['amount']} - Prix moyen: {order['price']}")
    print(f"Solde USDT: {usd_balance:.2f} | BTC: {btc_balance:.6f} (~{btc_in_usd:.2f} USDT) | Total estimé: {total:.2f} USDT")
    print("----------------------------")

def main():
    symbol = 'BTC/USDT'
    timeframe = '1m'

    while True:
        try:
            df = fetch_ohlcv(symbol, timeframe, limit=100)
            df = add_indicators(df)

            usd_balance, btc_balance = get_balance()
            trade_amount_usd = usd_balance * 0.01  # 1% du solde USDT
            current_price = df['close'].iloc[-1]
            trade_amount_btc = trade_amount_usd / current_price

            if check_buy_signal(df) and usd_balance >= trade_amount_usd:
                order = place_order(symbol, 'buy', trade_amount_btc)
                if order:
                    print_trade_summary(order)
            elif check_sell_signal(df) and btc_balance >= trade_amount_btc:
                order = place_order(symbol, 'sell', trade_amount_btc)
                if order:
                    print_trade_summary(order)

            time.sleep(5)  # 5 sec pour rester dans les limites

        except Exception as e:
            print(f"Erreur boucle principale: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
