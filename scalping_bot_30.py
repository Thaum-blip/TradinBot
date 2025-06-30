import ccxt
import time
import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

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
timeframe = '15s'  # Base timeframe for simulation
simulated_timeframe = 30  # Simulated timeframe in seconds
short_window = 7
long_window = 25

trade_log_file = 'trades.log'
stop_loss_pct = 0.003  # 0.3% stop loss
take_profit_pct = 0.005  # 0.5% take profit

# Stockage trades pour calcul gain/perte
trade_history = []

# Gestion des positions ouvertes
open_positions = []  # Liste des positions ouvertes

def fetch_trades():
    trades = exchange.fetch_trades(symbol, limit=100)
    df = pd.DataFrame(trades)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[['timestamp', 'price', 'amount']]
    return df

def simulate_ohlcv(trades_df):
    end_time = trades_df['timestamp'].iloc[-1]
    start_time = end_time - timedelta(seconds=simulated_timeframe)

    subset = trades_df[(trades_df['timestamp'] > start_time) & (trades_df['timestamp'] <= end_time)]
    if subset.empty:
        return None

    open_price = subset['price'].iloc[0]
    high_price = subset['price'].max()
    low_price = subset['price'].min()
    close_price = subset['price'].iloc[-1]
    volume = subset['amount'].sum()

    return pd.DataFrame([{
        'timestamp': end_time,
        'open': open_price,
        'high': high_price,
        'low': low_price,
        'close': close_price,
        'volume': volume
    }])

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
    ticker = exchange.fetch_ticker(symbol)
    price = ticker['last']
    size = (usd_balance * 0.01) / price
    size = round(size, 6)
    return size

def monitor_positions():
    global open_positions
    ticker = exchange.fetch_ticker(symbol)
    current_price = ticker['last']

    for position in open_positions[:]:
        if position['side'] == 'buy':
            if current_price <= position['stop_loss']:
                print(f"Stop loss touché pour position LONG. Vente immédiate au prix {current_price}")
                order = place_order('sell', position['amount'])
                if order:
                    profit = (current_price - position['price']) * position['amount']
                    trade_history.append({'side': 'buy', 'profit': profit})
                    write_log(f"STOP LOSS LONG - VENDU {position['amount']} BTC à {current_price:.2f}, Profit: {profit:.2f} USDT")
                open_positions.remove(position)

            elif current_price >= position['take_profit']:
                print(f"Take profit touché pour position LONG. Vente au prix {current_price}")
                order = place_order('sell', position['amount'])
                if order:
                    profit = (current_price - position['price']) * position['amount']
                    trade_history.append({'side': 'buy', 'profit': profit})
                    write_log(f"TAKE PROFIT LONG - VENDU {position['amount']} BTC à {current_price:.2f}, Profit: {profit:.2f} USDT")
                open_positions.remove(position)

        elif position['side'] == 'sell':
            if current_price >= position['stop_loss']:
                print(f"Stop loss touché pour position SHORT. Achat immédiat au prix {current_price}")
                order = place_order('buy', position['amount'])
                if order:
                    profit = (position['price'] - current_price) * position['amount']
                    trade_history.append({'side': 'sell', 'profit': profit})
                    write_log(f"STOP LOSS SHORT - ACHAT {position['amount']} BTC à {current_price:.2f}, Profit: {profit:.2f} USDT")
                open_positions.remove(position)

            elif current_price <= position['take_profit']:
                print(f"Take profit touché pour position SHORT. Achat au prix {current_price}")
                order = place_order('buy', position['amount'])
                if order:
                    profit = (position['price'] - current_price) * position['amount']
                    trade_history.append({'side': 'sell', 'profit': profit})
                    write_log(f"TAKE PROFIT SHORT - ACHAT {position['amount']} BTC à {current_price:.2f}, Profit: {profit:.2f} USDT")
                open_positions.remove(position)

def main():
    print("Démarrage scalping bot...")
    last_signal = None

    while True:
        try:
            trades_df = fetch_trades()
            simulated_ohlcv = simulate_ohlcv(trades_df)

            if simulated_ohlcv is None:
                print("Pas assez de données pour simuler une bougie 30s.")
                time.sleep(5)
                continue

            df = pd.concat([pd.DataFrame(simulated_ohlcv)], ignore_index=True)
            df = calculate_moving_averages(df)
            signal = check_signals(df)

            usd_balance, btc_balance = fetch_balances()
            monitor_positions()

            if signal and signal != last_signal and len(open_positions) < 10:
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
                            open_positions.append({'side': 'buy', 'amount': size, 'price': current_price, 'stop_loss': stop_loss, 'take_profit': take_profit})
                            write_log(f"ACHAT {size} BTC à {current_price:.2f}, SL: {stop_loss:.2f}, TP: {take_profit:.2f}")
                            print(f"Achat effectué : {size} BTC à {current_price:.2f}")

                    elif signal == 'sell' and btc_balance >= size:
                        order = place_order('sell', size)
                        if order:
                            stop_loss = current_price * (1 + stop_loss_pct)
                            take_profit = current_price * (1 - take_profit_pct)
                            open_positions.append({'side': 'sell', 'amount': size, 'price': current_price, 'stop_loss': stop_loss, 'take_profit': take_profit})
                            write_log(f"VENTE {size} BTC à {current_price:.2f}, SL: {stop_loss:.2f}, TP: {take_profit:.2f}")
                            print(f"Vente effectuée : {size} BTC à {current_price:.2f}")

                last_signal = signal

            time.sleep(simulated_timeframe)

        except Exception as e:
            print(f"Erreur dans la boucle principale : {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
