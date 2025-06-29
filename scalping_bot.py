import ccxt
import time
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()

# Charger les clés API depuis .env
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')

# Initialiser l'instance de l'exchange
def init_exchange():
    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'options': {'defaultType': 'spot'},
    })
    exchange.set_sandbox_mode(True)
    return exchange

exchange = init_exchange()

# Récupérer les données OHLCV pour effectuer des analyses
def fetch_ohlcv(symbol, timeframe, limit=50):
    data = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

# Calculer les moyennes mobiles
def calculate_moving_averages(df, short_window, long_window):
    df['SMA_short'] = df['close'].rolling(window=short_window).mean()
    df['SMA_long'] = df['close'].rolling(window=long_window).mean()
    return df

# Vérifier les signaux d'achat/vente
def check_signals(df):
    if df['SMA_short'].iloc[-1] > df['SMA_long'].iloc[-1] and df['SMA_short'].iloc[-2] <= df['SMA_long'].iloc[-2]:
        return 'buy'
    elif df['SMA_short'].iloc[-1] < df['SMA_long'].iloc[-1] and df['SMA_short'].iloc[-2] >= df['SMA_long'].iloc[-2]:
        return 'sell'
    return None

# Exécuter un ordre avec gestion de la taille basée sur le solde
def place_order(symbol, side, usd_balance, btc_balance):
    try:
        if side == 'buy':
            amount_in_usd = usd_balance * 0.01  # 1% du solde USD
            ticker = exchange.fetch_ticker(symbol)
            price = ticker['last']
            amount = amount_in_usd / price
        else:  # sell
            amount = btc_balance * 0.01  # 1% du solde BTC

        order = exchange.create_order(symbol, 'market', side, amount)

        # Récupérer les soldes après l'exécution de l'ordre
        balance = exchange.fetch_balance()
        usd_balance = balance['total']['USDT']
        btc_balance = balance['total']['BTC']
        total_balance = usd_balance + (btc_balance * ticker['last'])

        print(f"Ordre {side} exécuté :")
        print({
            'id': order['id'],
            'timestamp': order['timestamp'],
            'datetime': order['datetime'],
            'symbol': order['symbol'],
            'side': order['side'],
            'price': order['price'],
            'amount': order['amount'],
            'cost': order['cost']
        })
        print(f"Nouveau solde : {usd_balance:.2f} USDT, {btc_balance:.6f} BTC, Total (USD) : {total_balance:.2f}")
    except Exception as e:
        print(f"Erreur lors de l'exécution de l'ordre : {e}")

# Boucle principale
def main():
    symbol = 'BTC/USDT'
    timeframe = '1m'

    while True:
        try:
            # Récupérer les soldes
            balance = exchange.fetch_balance()
            usd_balance = balance['total']['USDT']
            btc_balance = balance['total']['BTC']

            print(f"Solde disponible : {usd_balance:.2f} USDT, {btc_balance:.6f} BTC")

            # Récupérer les données de marché et analyser
            df = fetch_ohlcv(symbol, timeframe)
            df = calculate_moving_averages(df, short_window=7, long_window=25)
            signal = check_signals(df)

            # Passer un ordre basé sur les signaux
            if signal == 'buy' and usd_balance > 10:  # Exemple d'achat minimal à 10 USDT
                place_order(symbol, 'buy', usd_balance, btc_balance)
            elif signal == 'sell' and btc_balance > 0.001:
                place_order(symbol, 'sell', usd_balance, btc_balance)

            time.sleep(60)  # Attendre une minute avant la prochaine analyse
        except Exception as e:
            print(f"Erreur dans la boucle principale : {e}")

if __name__ == "__main__":
    main()
