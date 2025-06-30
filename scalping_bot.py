import ccxt
import time
import pandas as pd
from dotenv import load_dotenv
import os
import talib  # Pour RSI (il faudra installer : pip install TA-Lib)

load_dotenv()

API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')

def init_exchange():
    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'options': {'defaultType': 'spot'},
    })
    exchange.set_sandbox_mode(True)
    return exchange

exchange = init_exchange()

def fetch_ohlcv(symbol, timeframe, limit=50):
    data = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def calculate_indicators(df):
    df['SMA_short'] = df['close'].rolling(window=7).mean()
    df['SMA_long'] = df['close'].rolling(window=25).mean()
    df['RSI'] = talib.RSI(df['close'], timeperiod=14)
    return df

def check_signals(df):
    # On regarde si SMA_short croise SMA_long à la hausse
    buy_signal = (df['SMA_short'].iloc[-1] > df['SMA_long'].iloc[-1]) and (df['SMA_short'].iloc[-2] <= df['SMA_long'].iloc[-2])
    # Et RSI < 70 (pas suracheté)
    buy_signal = buy_signal and (df['RSI'].iloc[-1] < 70)

    # Croisement à la baisse
    sell_signal = (df['SMA_short'].iloc[-1] < df['SMA_long'].iloc[-1]) and (df['SMA_short'].iloc[-2] >= df['SMA_long'].iloc[-2])
    # Et RSI > 30 (pas survendu)
    sell_signal = sell_signal and (df['RSI'].iloc[-1] > 30)

    if buy_signal:
        return 'buy'
    elif sell_signal:
        return 'sell'
    else:
        return None

def get_balances():
    balance = exchange.fetch_balance()
    usd = balance['free'].get('USDT', 0)
    btc = balance['free'].get('BTC', 0)
    return usd, btc

def place_order(symbol, side, amount):
    try:
        order = exchange.create_order(symbol, 'market', side, amount)
        return order
    except Exception as e:
        print(f"Erreur lors de l'exécution de l'ordre : {e}")
        return None

def print_order_summary(order):
    if not order:
        print("Aucun ordre passé.")
        return
    print(f"Ordre {order['side'].upper()} passé:")
    print(f"  Symbole : {order['symbol']}")
    print(f"  Montant : {order['amount']}")
    print(f"  Prix moyen : {order['average']}")
    print(f"  Coût total : {order['cost']}")
    usd, btc = get_balances()
    total_in_usd = usd + btc * order['average']
    print(f"Soldes actuels après ordre:")
    print(f"  USDT : {usd:.2f}")
    print(f"  BTC  : {btc:.6f} (~{btc * order['average']:.2f} USDT)")
    print(f"  Total estimé en USDT : {total_in_usd:.2f}")

def main():
    symbol = 'BTC/USDT'
    timeframe = '1m'

    print("Lancement du scalping bot...")

    while True:
        try:
            df = fetch_ohlcv(symbol, timeframe)
            df = calculate_indicators(df)
            signal = check_signals(df)
            usd_balance, btc_balance = get_balances()

            amount_to_trade = (usd_balance * 0.01) / df['close'].iloc[-1]  # 1% du solde USD converti en BTC

            if signal == 'buy' and usd_balance > 10:
                order = place_order(symbol, 'buy', round(amount_to_trade, 6))
                print_order_summary(order)
            elif signal == 'sell' and btc_balance > 0.0001:
                order = place_order(symbol, 'sell', round(btc_balance * 0.01, 6))  # 1% du BTC détenu
                print_order_summary(order)
            else:
                print(f"Aucun signal ou fonds insuffisants. USDT: {usd_balance:.2f}, BTC: {btc_balance:.6f}")

            time.sleep(5)  # boucle toutes les 5 secondes
        except Exception as e:
            print(f"Erreur dans la boucle principale : {e}")

if __name__ == "__main__":
    main()
