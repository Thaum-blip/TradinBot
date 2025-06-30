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
    return exchange

exchange = init_exchange()

symbol = 'BTC/USDT'
timeframe = '1m'
short_window = 7
long_window = 25

trade_log_file = 'trades.log'
stop_loss_pct = 0.003  # 0.3% stop loss
take_profit_pct = 0.005  # 0.5% take profit

# Stockage trades pour calcul gain/perte
trade_history = []

def fetch_ohlcv():
    data = exchange.fetch_ohlcv(symbol, timeframe, limit=50)
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def calculate_moving_averages(df):
    df['SMA_short'] = df['close'].rolling(window=short_window).mean()
    df['SMA_long'] = df['close'].rolling(window=long_window).mean()
    return df

def check_signals(df):
    # Signal croisement simple des SMA pour entrée/sortie
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
    balance = exchange.fetch_balance()
    usd = balance['total']['USDT']
    btc = balance['total']['BTC']
    return usd, btc

def place_order(side, amount):
    try:
        order = exchange.create_order(symbol, 'market', side, amount)
        return order
    except Exception as e:
        print(f"Erreur ordre {side}: {e}")
        return None

def get_position_size(usd_balance):
    # 1% du solde USD converti en BTC au prix actuel
    ticker = exchange.fetch_ticker(symbol)
    price = ticker['last']
    size = (usd_balance * 0.01) / price
    # arrondi au lot minimal (ex: 0.0001)
    size = round(size, 6)
    return size

def calculate_ratio():
    wins = sum(1 for t in trade_history if t['profit'] > 0)
    losses = sum(1 for t in trade_history if t['profit'] < 0)
    ratio = wins / losses if losses > 0 else wins
    return ratio

def main():
    print("Démarrage scalping bot...")
    open_position = None  # None ou dict {side, amount, price, stop_loss, take_profit}
    last_signal = None

    while True:
        try:
            df = fetch_ohlcv()
            df = calculate_moving_averages(df)
            signal = check_signals(df)

            usd_balance, btc_balance = fetch_balances()

            # Mettre à jour open_position si position ouverte
            if open_position:
                ticker = exchange.fetch_ticker(symbol)
                current_price = ticker['last']

                # Check stop loss ou take profit
                if open_position['side'] == 'buy':
                    if current_price <= open_position['stop_loss']:
                        print(f"Stop loss touché pour position LONG. Vente immédiate au prix {current_price}")
                        order = place_order('sell', open_position['amount'])
                        if order:
                            profit = (current_price - open_position['price']) * open_position['amount']
                            trade_history.append({'side':'buy','profit': profit})
                            write_log(f"STOP LOSS LONG - VENDU {open_position['amount']} BTC à {current_price:.2f}, Profit: {profit:.2f} USDT")
                        open_position = None
                    elif current_price >= open_position['take_profit']:
                        print(f"Take profit touché pour position LONG. Vente au prix {current_price}")
                        order = place_order('sell', open_position['amount'])
                        if order:
                            profit = (current_price - open_position['price']) * open_position['amount']
                            trade_history.append({'side':'buy','profit': profit})
                            write_log(f"TAKE PROFIT LONG - VENDU {open_position['amount']} BTC à {current_price:.2f}, Profit: {profit:.2f} USDT")
                        open_position = None

                elif open_position['side'] == 'sell':
                    # Short selling pas dispo en spot, on va simuler avec achat à plus bas prix
                    if current_price >= open_position['stop_loss']:
                        print(f"Stop loss touché pour position SHORT. Achat immédiat au prix {current_price}")
                        order = place_order('buy', open_position['amount'])
                        if order:
                            profit = (open_position['price'] - current_price) * open_position['amount']
                            trade_history.append({'side':'sell','profit': profit})
                            write_log(f"STOP LOSS SHORT - ACHAT {open_position['amount']} BTC à {current_price:.2f}, Profit: {profit:.2f} USDT")
                        open_position = None
                    elif current_price <= open_position['take_profit']:
                        print(f"Take profit touché pour position SHORT. Achat au prix {current_price}")
                        order = place_order('buy', open_position['amount'])
                        if order:
                            profit = (open_position['price'] - current_price) * open_position['amount']
                            trade_history.append({'side':'sell','profit': profit})
                            write_log(f"TAKE PROFIT SHORT - ACHAT {open_position['amount']} BTC à {current_price:.2f}, Profit: {profit:.2f} USDT")
                        open_position = None

            # Si pas de position ouverte, on regarde si on doit ouvrir une position
            if not open_position and signal and signal != last_signal:
                size = get_position_size(usd_balance)
                if size < 0.0001:
                    print("Taille position trop faible, pas d'ordre.")
                else:
                    ticker = exchange.fetch_ticker(symbol)
                    current_price = ticker['last']
                    if signal == 'buy' and usd_balance >= current_price * size:
                        order = place_order('buy', size)
                        if order:
                            stop_loss = current_price * (1 - stop_loss_pct)
                            take_profit = current_price * (1 + take_profit_pct)
                            open_position = {'side':'buy', 'amount': size, 'price': current_price, 'stop_loss': stop_loss, 'take_profit': take_profit}
                            write_log(f"ACHAT {size} BTC à {current_price:.2f}, SL: {stop_loss:.2f}, TP: {take_profit:.2f}")
                            print(f"Achat effectué : {size} BTC à {current_price:.2f}")
                    elif signal == 'sell' and btc_balance >= size:
                        # Comme pas de short spot, on vend BTC qu'on a
                        order = place_order('sell', size)
                        if order:
                            stop_loss = current_price * (1 + stop_loss_pct)
                            take_profit = current_price * (1 - take_profit_pct)
                            open_position = {'side':'sell', 'amount': size, 'price': current_price, 'stop_loss': stop_loss, 'take_profit': take_profit}
                            write_log(f"VENTE {size} BTC à {current_price:.2f}, SL: {stop_loss:.2f}, TP: {take_profit:.2f}")
                            print(f"Vente effectuée : {size} BTC à {current_price:.2f}")

                last_signal = signal

            # Affichage solde à chaque boucle
            usd_balance, btc_balance = fetch_balances()
            ticker = exchange.fetch_ticker(symbol)
            total_balance = usd_balance + btc_balance * ticker['last']
            print(f"Solde USDT: {usd_balance:.2f} | BTC: {btc_balance:.6f} | Total USDT: {total_balance:.2f}")

            # Affichage ratio gain/perte
            if len(trade_history) > 0:
                ratio = calculate_ratio()
                print(f"Ratio gain/perte : {ratio:.2f}")

            time.sleep(5)

        except Exception as e:
            print(f"Erreur dans la boucle principale : {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
