import ccxt
import time
import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime
import json # Pour enregistrer les trades en format JSON

load_dotenv()

API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')

# --- Configuration du bot ---
# Le type de trading 'spot' signifie que vous achetez et vendez l'actif réel.
# Pour le 'short' selling sur marge ou futures, il faudrait changer 'defaultType'.
# Pour ce code, une "vente" en spot signifie vendre des BTC que vous possédez.
# Une "position short" dans ce contexte signifie que vous avez des USDT et cherchez à les échanger contre des BTC à un prix plus bas.
# Une "position long" signifie que vous avez des BTC et cherchez à les échanger contre des USDT à un prix plus haut.

def init_exchange():
    """Initialise l'objet exchange CCXT pour Binance."""
    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'options': {'defaultType': 'spot'},
        'enableRateLimit': True, # Active la gestion automatique des limites de taux
    })
    exchange.set_sandbox_mode(True)
    return exchange

exchange = init_exchange()

symbol = 'BTC/USDT'
timeframe = '1m'
short_window = 7
long_window = 25

trade_log_file = 'trades.json' # Changement de format pour une meilleure analyse
stop_loss_pct = 0.003  # 0.3% stop loss
take_profit_pct = 0.005  # 0.5% take profit
position_sizing_pct = 0.01 # 1% du solde USD pour chaque trade d'achat

# --- Stockage des données de trading ---
# Gardons un historique des trades fermés pour l'analyse
closed_trades = []
# Chaque position ouverte sera un dictionnaire avec plus de détails
# {'id': unique_id, 'type': 'long'/'short', 'amount': X, 'entry_price': Y, 'stop_loss': SL, 'take_profit': TP, 'status': 'open', 'entry_time': datetime}
open_positions = {} # Utilisation d'un dictionnaire pour un accès plus facile par ID de position

# Variables de contrôle du bot
last_signal = None # Pour éviter de répéter les trades sur le même signal
current_position_type = None # Pour savoir si nous sommes actuellement en "long" ou "short" (conceptuellement)

# --- Fonctions utilitaires ---

def load_closed_trades():
    """Charge l'historique des trades fermés depuis le fichier JSON."""
    if os.path.exists(trade_log_file):
        with open(trade_log_file, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_closed_trades():
    """Sauvegarde l'historique des trades fermés dans le fichier JSON."""
    with open(trade_log_file, 'w') as f:
        json.dump(closed_trades, f, indent=4)

def write_log(message):
    """Écrit un message horodaté dans la console et un fichier de log."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    # Optionnel: Écrire aussi dans un fichier texte séparé pour les logs d'exécution
    with open('bot_activity.log', 'a') as f:
        f.write(log_message + '\n')

def fetch_ohlcv():
    """Récupère les données OHLCV pour le symbole et la timeframe spécifiés."""
    try:
        data = exchange.fetch_ohlcv(symbol, timeframe, limit=long_window + 5) # +5 pour s'assurer d'avoir assez de données pour les SMA
        if not data:
            write_log(f"Aucune donnée OHLCV récupérée pour {symbol} {timeframe}.")
            return pd.DataFrame()
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except ccxt.NetworkError as e:
        write_log(f"Erreur réseau lors de la récupération OHLCV: {e}")
        return pd.DataFrame()
    except ccxt.ExchangeError as e:
        write_log(f"Erreur d'échange lors de la récupération OHLCV: {e}")
        return pd.DataFrame()
    except Exception as e:
        write_log(f"Erreur inattendue lors de la récupération OHLCV: {e}")
        return pd.DataFrame()

def calculate_moving_averages(df):
    """Calcule les moyennes mobiles simples."""
    if len(df) < long_window: # S'assurer d'avoir assez de données
        return df
    df['SMA_short'] = df['close'].rolling(window=short_window).mean()
    df['SMA_long'] = df['close'].rolling(window=long_window).mean()
    return df

def check_signals(df):
    """Vérifie les signaux de trading basés sur les croisements de SMA."""
    if df.empty or len(df) < long_window:
        return None # Pas assez de données pour calculer les SMA

    # Assurez-vous que les SMA sont calculées et non-NaN pour les dernières valeurs
    if pd.isna(df['SMA_short'].iloc[-1]) or pd.isna(df['SMA_long'].iloc[-1]) or \
       pd.isna(df['SMA_short'].iloc[-2]) or pd.isna(df['SMA_long'].iloc[-2]):
        return None

    current_sma_short = df['SMA_short'].iloc[-1]
    current_sma_long = df['SMA_long'].iloc[-1]
    prev_sma_short = df['SMA_short'].iloc[-2]
    prev_sma_long = df['SMA_long'].iloc[-2]

    # Signal d'achat (croisement haussier)
    if current_sma_short > current_sma_long and prev_sma_short <= prev_sma_long:
        return 'buy'
    # Signal de vente (croisement baissier)
    elif current_sma_short < current_sma_long and prev_sma_short >= prev_sma_long:
        return 'sell'
    return None

def fetch_balances():
    """Récupère les soldes USD et BTC du compte."""
    try:
        balance = exchange.fetch_balance()
        usd = balance['total'].get('USDT', 0)
        btc = balance['total'].get('BTC', 0)
        return usd, btc
    except ccxt.NetworkError as e:
        write_log(f"Erreur réseau lors de la récupération des soldes: {e}")
        return 0, 0
    except ccxt.ExchangeError as e:
        write_log(f"Erreur d'échange lors de la récupération des soldes: {e}")
        return 0, 0
    except Exception as e:
        write_log(f"Erreur inattendue lors de la récupération des soldes: {e}")
        return 0, 0

def place_order(side, amount):
    """Place un ordre au marché et gère les erreurs."""
    try:
        # ccxt gère souvent la précision, mais on peut ajouter un arrondi si nécessaire
        # info = exchange.market(symbol) # Pour obtenir les infos sur le trading pair, lot size, etc.
        # amount = exchange.decimal_to_precision(amount, exchange.markets[symbol]['limits']['amount']['min'], exchange.markets[symbol]['precision']['amount'])
        
        # Pour une meilleure gestion des arrondis et minima de Binance
        # Récupérer les informations sur la paire pour la précision
        market = exchange.market(symbol)
        amount_precision = market['precision']['amount']
        min_amount = market['limits']['amount']['min']

        # Arrondir le montant à la précision de l'échange
        formatted_amount = exchange.amount_to_precision(symbol, amount)
        
        # Convertir en float pour la comparaison
        if float(formatted_amount) < min_amount:
            write_log(f"Le montant de l'ordre ({formatted_amount}) est inférieur au minimum ({min_amount}). Ordre non placé.")
            return None

        order = exchange.create_order(symbol, 'market', side, formatted_amount)
        return order
    except ccxt.InsufficientFunds as e:
        write_log(f"Fonds insuffisants pour placer un ordre {side} de {amount}: {e}")
        return None
    except ccxt.DDoSProtection as e:
        write_log(f"Protection DDoS activée, attente...: {e}")
        time.sleep(exchange.rateLimit / 1000) # Attendre le temps recommandé
        return None
    except ccxt.ExchangeNotAvailable as e:
        write_log(f"Échange non disponible: {e}")
        return None
    except ccxt.RequestTimeout as e:
        write_log(f"Requête expirée: {e}")
        return None
    except ccxt.NetworkError as e:
        write_log(f"Erreur réseau lors de l'ordre {side}: {e}")
        return None
    except ccxt.ExchangeError as e:
        write_log(f"Erreur d'échange lors de l'ordre {side}: {e}")
        return None
    except Exception as e:
        write_log(f"Erreur inattendue lors de l'ordre {side}: {e}")
        return None

def get_position_size(usd_balance, current_price):
    """Calcule la taille de la position en BTC basée sur un pourcentage du solde USD."""
    size_in_usd = usd_balance * position_sizing_pct
    size_in_btc = size_in_usd / current_price
    
    # Arrondir à la précision requise par l'échange pour BTC
    market = exchange.market(symbol)
    size_in_btc = exchange.amount_to_precision(symbol, size_in_btc)
    
    return float(size_in_btc) # Retourner en float pour les calculs

def calculate_win_loss_ratio():
    """Calcule le ratio de victoires/défaites des trades fermés."""
    wins = sum(1 for t in closed_trades if t.get('profit_usd', 0) > 0)
    losses = sum(1 for t in closed_trades if t.get('profit_usd', 0) < 0)
    
    if losses == 0:
        return wins # Si pas de pertes, le ratio est le nombre de victoires
    return wins / losses

def manage_positions():
    """
    Gère les positions ouvertes : vérifie les stop-loss et take-profit,
    et ferme les positions si les conditions sont remplies.
    """
    global open_positions, closed_trades

    ticker = exchange.fetch_ticker(symbol)
    current_price = ticker['last']

    # Itérer sur une copie des clés pour éviter les problèmes de modification en boucle
    for pos_id in list(open_positions.keys()):
        position = open_positions[pos_id]
        
        # Vérifier si la position est toujours "open"
        if position['status'] == 'open':
            if position['type'] == 'long': # Position d'achat
                # Vérifier Stop Loss
                if current_price <= position['stop_loss']:
                    write_log(f"STOP LOSS touché pour position LONG (ID: {pos_id}). Vente immédiate à {current_price:.2f}")
                    order = place_order('sell', position['amount'])
                    if order:
                        profit_usd = (current_price - position['entry_price']) * position['amount']
                        position.update({
                            'exit_price': current_price,
                            'profit_usd': profit_usd,
                            'exit_time': datetime.now().isoformat(),
                            'status': 'closed_sl'
                        })
                        closed_trades.append(position)
                        del open_positions[pos_id] # Supprimer de la liste des positions ouvertes
                        write_log(f"LONG fermé (SL) - Profit: {profit_usd:.2f} USDT")
                    else:
                        write_log(f"Échec de l'ordre de fermeture SL pour position LONG (ID: {pos_id}).")
                
                # Vérifier Take Profit
                elif current_price >= position['take_profit']:
                    write_log(f"TAKE PROFIT touché pour position LONG (ID: {pos_id}). Vente à {current_price:.2f}")
                    order = place_order('sell', position['amount'])
                    if order:
                        profit_usd = (current_price - position['entry_price']) * position['amount']
                        position.update({
                            'exit_price': current_price,
                            'profit_usd': profit_usd,
                            'exit_time': datetime.now().isoformat(),
                            'status': 'closed_tp'
                        })
                        closed_trades.append(position)
                        del open_positions[pos_id]
                        write_log(f"LONG fermé (TP) - Profit: {profit_usd:.2f} USDT")
                    else:
                        write_log(f"Échec de l'ordre de fermeture TP pour position LONG (ID: {pos_id}).")

            elif position['type'] == 'short': # Position de vente (spot)
                # Note: Pour le trading spot, une "position short" est conceptuellement "être en USDT" et attendre d'acheter BTC à bas prix.
                # Cela signifie que vous avez vendu vos BTC précédemment et attendez de les racheter.
                # La logique SL/TP est inversée par rapport à un long.
                
                # Vérifier Stop Loss (le prix est monté, on rachète à perte)
                if current_price >= position['stop_loss']:
                    write_log(f"STOP LOSS touché pour position SHORT (ID: {pos_id}). Achat immédiat à {current_price:.2f}")
                    order = place_order('buy', position['amount'])
                    if order:
                        profit_usd = (position['entry_price'] - current_price) * position['amount']
                        position.update({
                            'exit_price': current_price,
                            'profit_usd': profit_usd,
                            'exit_time': datetime.now().isoformat(),
                            'status': 'closed_sl'
                        })
                        closed_trades.append(position)
                        del open_positions[pos_id]
                        write_log(f"SHORT fermé (SL) - Profit: {profit_usd:.2f} USDT")
                    else:
                        write_log(f"Échec de l'ordre de fermeture SL pour position SHORT (ID: {pos_id}).")
                
                # Vérifier Take Profit (le prix a baissé, on rachète avec profit)
                elif current_price <= position['take_profit']:
                    write_log(f"TAKE PROFIT touché pour position SHORT (ID: {pos_id}). Achat à {current_price:.2f}")
                    order = place_order('buy', position['amount'])
                    if order:
                        profit_usd = (position['entry_price'] - current_price) * position['amount']
                        position.update({
                            'exit_price': current_price,
                            'profit_usd': profit_usd,
                            'exit_time': datetime.now().isoformat(),
                            'status': 'closed_tp'
                        })
                        closed_trades.append(position)
                        del open_positions[pos_id]
                        write_log(f"SHORT fermé (TP) - Profit: {profit_usd:.2f} USDT")
                    else:
                        write_log(f"Échec de l'ordre de fermeture TP pour position SHORT (ID: {pos_id}).")

def main():
    """Fonction principale du bot de trading."""
    global last_signal, current_position_type, closed_trades
    write_log("Démarrage du bot de trading...")
    
    # Charger les trades fermés existants au démarrage
    closed_trades = load_closed_trades()

    while True:
        try:
            # 1. Récupérer les données et calculer les indicateurs
            df = fetch_ohlcv()
            if df.empty or len(df) < long_window:
                write_log(f"Pas assez de données pour l'analyse. Attente {timeframe}...")
                time.sleep(exchange.rateLimit / 1000) # Attendre un peu
                continue

            df = calculate_moving_averages(df)
            signal = check_signals(df)
            
            # Récupérer les soldes et le prix actuel pour les décisions
            usd_balance, btc_balance = fetch_balances()
            ticker = exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            
            # 2. Gérer les positions ouvertes (SL/TP)
            manage_positions()

            # 3. Décider d'ouvrir une nouvelle position
            # Logique pour éviter d'ouvrir plusieurs positions du même type et de changer de direction trop vite
            if signal == 'buy' and current_position_type != 'long' and not open_positions: # S'il n'y a pas de position ouverte
                size = get_position_size(usd_balance, current_price)
                if size > exchange.market(symbol)['limits']['amount']['min']:
                    # Vérifier si on a assez d'USDT pour l'achat
                    if usd_balance >= current_price * size:
                        order = place_order('buy', size)
                        if order:
                            pos_id = str(datetime.now().timestamp()) # ID unique pour la position
                            stop_loss = current_price * (1 - stop_loss_pct)
                            take_profit = current_price * (1 + take_profit_pct)
                            open_positions[pos_id] = {
                                'id': pos_id,
                                'type': 'long',
                                'amount': float(order['amount']), # Assurez-vous que c'est le montant réel exécuté
                                'entry_price': float(order['price']), # Assurez-vous que c'est le prix réel exécuté
                                'stop_loss': stop_loss,
                                'take_profit': take_profit,
                                'status': 'open',
                                'entry_time': datetime.now().isoformat()
                            }
                            current_position_type = 'long'
                            write_log(f"ORDRE EXÉCUTÉ - ACHAT {order['amount']} BTC à {order['price']:.2f}. SL: {stop_loss:.2f}, TP: {take_profit:.2f}")
                        else:
                            write_log("Échec de l'ordre d'achat.")
                    else:
                        write_log(f"Fonds USDT insuffisants pour ACHAT. Solde: {usd_balance:.2f} USDT, Nécessaire: {current_price * size:.2f} USDT")
                else:
                    write_log(f"Taille d'ACHAT ({size:.6f}) trop faible pour placer un ordre.")

            elif signal == 'sell' and current_position_type != 'short' and not open_positions: # S'il n'y a pas de position ouverte
                # Pour une vente SPOT, la taille est le montant de BTC que vous possédez et êtes prêt à vendre
                size = btc_balance * position_sizing_pct # Vendre un % de votre BTC
                if size > exchange.market(symbol)['limits']['amount']['min']:
                    if btc_balance >= size:
                        order = place_order('sell', size)
                        if order:
                            pos_id = str(datetime.now().timestamp())
                            stop_loss = current_price * (1 + stop_loss_pct) # SL pour un short est au-dessus du prix d'entrée
                            take_profit = current_price * (1 - take_profit_pct) # TP pour un short est en dessous du prix d'entrée
                            open_positions[pos_id] = {
                                'id': pos_id,
                                'type': 'short',
                                'amount': float(order['amount']),
                                'entry_price': float(order['price']),
                                'stop_loss': stop_loss,
                                'take_profit': take_profit,
                                'status': 'open',
                                'entry_time': datetime.now().isoformat()
                            }
                            current_position_type = 'short'
                            write_log(f"ORDRE EXÉCUTÉ - VENTE {order['amount']} BTC à {order['price']:.2f}. SL: {stop_loss:.2f}, TP: {take_profit:.2f}")
                        else:
                            write_log("Échec de l'ordre de vente.")
                    else:
                        write_log(f"Fonds BTC insuffisants pour VENTE. Solde: {btc_balance:.6f} BTC, Nécessaire: {size:.6f} BTC")
                else:
                    write_log(f"Taille de VENTE ({size:.6f}) trop faible pour placer un ordre.")

            # Mise à jour du last_signal pour éviter les trades multiples sur le même signal si la position n'a pas été ouverte
            last_signal = signal
            
            # 4. Affichage des informations en temps réel
            total_balance = usd_balance + btc_balance * current_price
            write_log(f"Solde USDT: {usd_balance:.2f} | BTC: {btc_balance:.6f} | Total USDT: {total_balance:.2f} | Positions ouvertes: {len(open_positions)}")

            if closed_trades:
                ratio = calculate_win_loss_ratio()
                total_profit_loss = sum(t.get('profit_usd', 0) for t in closed_trades)
                write_log(f"Trades fermés: {len(closed_trades)} | Ratio G/P: {ratio:.2f} | Profit/Perte Total: {total_profit_loss:.2f} USDT")

            # 5. Sauvegarder les trades fermés régulièrement
            save_closed_trades()
            
            # 6. Attente avant la prochaine itération
            time.sleep(5)

        except ccxt.DDoSProtection as e:
            write_log(f"Protection DDoS activée. Attente prolongée: {e}")
            time.sleep(exchange.rateLimit / 1000 * 2) # Attendre plus longtemps
        except ccxt.NetworkError as e:
            write_log(f"Erreur réseau générale: {e}. Nouvelle tentative dans 10s.")
            time.sleep(10)
        except ccxt.ExchangeError as e:
            write_log(f"Erreur d'échange générale: {e}. Nouvelle tentative dans 10s.")
            time.sleep(10)
        except Exception as e:
            write_log(f"Erreur inattendue dans la boucle principale: {e}. Nouvelle tentative dans 10s.")
            time.sleep(10)

if __name__ == "__main__":
    main()