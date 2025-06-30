import ccxt
import time
import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime

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
    exchange.verbose = True  # Activer le mode debug
    return exchange

exchange = init_exchange()

symbol = 'BTC/USDT'
timeframe = '30s'  # Timeframe de 30 secondes
short_window = 7
long_window = 25

trade_log_file = 'trades.log'
stop_loss_pct = 0.003  # 0.3% stop loss
take_profit_pct = 0.005  # 0.5% take profit

# Stockage trades pour calcul gain/perte
trade_history = []

def fetch_ohlcv():
    try:
        data = exchange.fetch_ohlcv(symbol, timeframe, limit=50)
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"Erreur lors de la récupération des données OHLCV : {e}")
        return None

def calculate_moving_averages(df):
    df['SMA_short'] = df['close'].rolling(window=short_window).mean()
    df['SMA_long'] = df['close'].rolling(window=long_window).mean()
    return df

def check_signals(df):
    if df['SMA_short'].iloc[-1] > df['SMA_long'].iloc[-1] and df['SMA_short'].iloc[-2] <= df['SMA_long'].iloc[-2]:
        return 'buy'
    elif df['SMA_short'].iloc[-1] < df['SMA_long'].iloc[-1] and df['SMA_short'].iloc[-2] >= df['SMA_long'].iloc[-2]:
        return 'sell'
    return None

def write_log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(trade_log_file, 'a') as f:
        f.write(f"[{timestamp}] {message}\n")

def fetch_balances():
    try:
        balance = exchange.fetch_balance()
        usd = balance['total']['USDT']
        btc = balance['total']['BTC']
        return usd, btc
    except Exception as e:
        print(f"Erreur lors de la récupération des soldes : {e}")
        return 0, 0

def place_order(side, amount):
    try:
        order = exchange.create_order(symbol, 'market', side, amount)
        return order
    except Exception as e:
        print(f"Erreur lors du placement d'ordre {side}: {e}")
        return None

def get_position_size(usd_balance):
    try:
        ticker = exchange.fetch_ticker(symbol)
        price = ticker['last']
        size = (usd_balance * 0.01) / price
        size = round(size, 6)
        return size
    except Exception as e:
        print(f"Erreur lors du calcul de la taille de position : {e}")
        return 0

def calculate_ratio():
    wins = sum(1 for t in trade_history if t['profit'] > 0)
    losses = sum(1 for t in trade_history if t['profit'] < 0)
    ratio = wins / losses if losses > 0 else wins
    return ratio

def main():
    print("Démarrage scalping bot...")
    open_positions = []  # Liste pour suivre plusieurs positions ouvertes
    last_signal = None

    while True:
        try:
            print("Étape 1 : Récupération des données OHLCV...")
            df = fetch_ohlcv()
            if df is None or df.empty:
                print("Pas de données OHLCV disponibles.")
                time.sleep(5)
                continue

            print("Étape 2 : Calcul des moyennes mobiles...")
            df = calculate_moving_averages(df)

            print("Étape 3 : Vérification des signaux...")
            signal = check_signals(df)

            usd_balance, btc_balance = fetch_balances()

            # Mettre à jour les positions ouvertes
            print("Étape 4 : Vérification des positions ouvertes...")
            updated_positions = []
            for position in open_positions:
                ticker = exchange.fetch_ticker(symbol)
                current_price = ticker['last']

                if position['side'] == 'buy':
                    if current_price <= position['stop_loss']:
                        print(f"Stop loss touché pour LONG à {current_price}. Vente en cours...")
                        order = place_order('sell', position['amount'])
                        if order:
                            profit = (current_price - position['price']) * position['amount']
                            trade_history.append({'side': 'buy', 'profit': profit})
                            write_log(f"STOP LOSS LONG - Vendu {position['amount']} BTC à {current_price:.2f}, Profit: {profit:.2f}")
                    elif current_price >= position['take_profit']:
                        print(f"Take profit touché pour LONG à {current_price}. Vente en cours...")
                        order = place_order('sell', position['amount'])
                        if order:
                            profit = (current_price - position['price']) * position['amount']
                            trade_history.append({'side': 'buy', 'profit': profit})
                            write_log(f"TAKE PROFIT LONG - Vendu {position['amount']} BTC à {current_price:.2f}, Profit: {profit:.2f}")
                    else:
                        updated_positions.append(position)

            open_positions = updated_positions

            # Si moins de 10 trades ouverts, regarder pour ouvrir une nouvelle position
            if len(open_positions) < 10 and signal and signal != last_signal:
                size = get_position_size(usd_balance)
                if size >= 0.0001:
                    ticker = exchange.fetch_ticker(symbol)
                    current_price = ticker['last']
                    if signal == 'buy' and usd_balance >= current_price * size:
                        order = place_order('buy', size)
                        if order:
                            stop_loss = current_price * (1 - stop_loss_pct)
                            take_profit = current_price * (1 + take_profit_pct)
                            open_positions.append({'side': 'buy', 'amount': size, 'price': current_price, 'stop_loss': stop_loss, 'take_profit': take_profit})
                            write_log(f"ACHAT {size} BTC à {current_price:.2f}, SL: {stop_loss:.2f}, TP: {take_profit:.2f}")
                            print(f"Nouvelle position LONG ouverte : {size} BTC à {current_price:.2f}")
                last_signal = signal

            time.sleep(5)
        except Exception as e:
            print(f"Erreur dans la boucle principale : {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
