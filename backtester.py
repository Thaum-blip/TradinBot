import pandas as pd
from datetime import datetime

# --- Paramètres de la stratégie (ceux que nous allons tester et optimiser) ---
# Ces valeurs seront initialisées ici pour le backtesting.
# Elles sont identiques à celles de votre bot de trading initial.
SHORT_WINDOW = 7
LONG_WINDOW = 25
STOP_LOSS_PCT = 0.003  # 0.3% stop loss
TAKE_PROFIT_PCT = 0.005  # 0.5% take profit
INITIAL_BALANCE_USDT = 10000 # Solde de départ fictif pour le backtest
POSITION_SIZING_PCT = 0.01 # 1% du capital pour chaque trade

# --- Fonction pour charger les données historiques ---
def load_historical_data(filename):
    """Charge les données OHLCV depuis un fichier CSV."""
    try:
        df = pd.read_csv(filename)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        # Assurez-vous que les données sont triées par timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)
        print(f"Données historiques chargées depuis {filename}. Nombre de bougies : {len(df)}")
        print(f"Période : {df['timestamp'].min()} à {df['timestamp'].max()}")
        return df
    except FileNotFoundError:
        print(f"Erreur: Le fichier {filename} n'a pas été trouvé. Assurez-vous que le téléchargement est terminé et que le nom est correct.")
        return pd.DataFrame()
    except Exception as e:
        print(f"Erreur lors du chargement ou du traitement du fichier CSV: {e}")
        return pd.DataFrame()

# --- Fonctions d'indicateurs (copiées de votre bot) ---
def calculate_moving_averages(df):
    """Calcule les moyennes mobiles simples."""
    if len(df) < LONG_WINDOW: # S'assurer d'avoir assez de données pour le calcul
        df['SMA_short'] = pd.NA
        df['SMA_long'] = pd.NA
        return df
    df['SMA_short'] = df['close'].rolling(window=SHORT_WINDOW, min_periods=1).mean()
    df['SMA_long'] = df['close'].rolling(window=LONG_WINDOW, min_periods=1).mean()
    return df

def check_signals(df_slice, last_signal):
    """
    Vérifie les signaux de trading basés sur les croisements de SMA.
    Prend une 'tranche' du DataFrame (la bougie actuelle et la précédente).
    """
    if len(df_slice) < 2 or pd.isna(df_slice['SMA_short'].iloc[-1]) or pd.isna(df_slice['SMA_long'].iloc[-1]) or \
       pd.isna(df_slice['SMA_short'].iloc[-2]) or pd.isna(df_slice['SMA_long'].iloc[-2]):
        return None

    current_sma_short = df_slice['SMA_short'].iloc[-1]
    current_sma_long = df_slice['SMA_long'].iloc[-1]
    prev_sma_short = df_slice['SMA_short'].iloc[-2]
    prev_sma_long = df_slice['SMA_long'].iloc[-2]

    # Signal d'achat (croisement haussier)
    if current_sma_short > current_sma_long and prev_sma_short <= prev_sma_long:
        return 'buy'
    # Signal de vente (croisement baissier)
    elif current_sma_short < current_sma_long and prev_sma_short >= prev_sma_long:
        return 'sell'
    return None

# --- Fonctions de gestion de position (simplifiées pour le backtesting) ---
# Dans le backtesting, nous ne plaçons pas d'ordres réels, nous simulons juste.

# Structure pour suivre les trades dans le backtest
# Chaque trade sera un dictionnaire:
# {'id': unique_id, 'type': 'long'/'short', 'entry_time': datetime, 'entry_price': float, 
#  'amount_btc': float, 'stop_loss': float, 'take_profit': float, 'exit_time': datetime, 
#  'exit_price': float, 'profit_usd': float, 'status': 'open'/'closed_sl'/'closed_tp'}
backtest_trades = []
current_open_position = None # Pour simuler une seule position ouverte à la fois


def run_backtest(df):
    """
    Exécute le backtest sur les données historiques.
    """
    global backtest_trades, current_open_position
    
    backtest_trades = [] # Réinitialiser les trades pour chaque run
    current_open_position = None # Aucune position ouverte au début
    
    current_balance_usdt = INITIAL_BALANCE_USDT
    current_balance_btc = 0 # On commence sans BTC, juste USDT pour acheter

    write_log(f"Démarrage du backtest avec solde initial : {current_balance_usdt:.2f} USDT")

    # Itérer sur chaque bougie du DataFrame
    # Nous commençons à LONG_WINDOW pour avoir suffisamment de données pour les SMA
    for i in range(LONG_WINDOW, len(df)):
        # Simulateurs de temps pour le log
        current_time = df['timestamp'].iloc[i]
        current_price = df['close'].iloc[i]

        # Récupérer la tranche de données nécessaire pour le calcul des indicateurs
        # Il faut au moins LONG_WINDOW bougies pour calculer la SMA_long correctement
        df_slice_for_signal = df.iloc[i-LONG_WINDOW:i+1].copy() # Copie pour éviter SettingWithCopyWarning
        df_slice_for_signal = calculate_moving_averages(df_slice_for_signal)
        
        # Le signal est basé sur le croisement de la bougie précédente et actuelle
        signal = check_signals(df_slice_for_signal, None) # last_signal n'est pas utile ici car on simule pas à pas

        # --- Gestion des positions ouvertes (SL/TP) ---
        if current_open_position:
            position = current_open_position
            
            if position['type'] == 'long': # Position d'achat (On possède du BTC, on veut vendre plus haut)
                if current_price <= position['stop_loss']:
                    profit = (current_price - position['entry_price']) * position['amount_btc']
                    current_balance_usdt += position['amount_btc'] * current_price # Vente des BTC
                    current_balance_btc -= position['amount_btc'] # Décrémente les BTC possédés
                    
                    position.update({
                        'exit_price': current_price,
                        'profit_usd': profit,
                        'exit_time': current_time,
                        'status': 'closed_sl'
                    })
                    backtest_trades.append(position)
                    write_log(f"[{current_time}] SL LONG hit. Sold {position['amount_btc']:.6f} BTC at {current_price:.2f}. Profit: {profit:.2f} USDT. Balance: {current_balance_usdt:.2f} USDT")
                    current_open_position = None # Ferme la position
                elif current_price >= position['take_profit']:
                    profit = (current_price - position['entry_price']) * position['amount_btc']
                    current_balance_usdt += position['amount_btc'] * current_price # Vente des BTC
                    current_balance_btc -= position['amount_btc'] # Décrémente les BTC possédés
                    
                    position.update({
                        'exit_price': current_price,
                        'profit_usd': profit,
                        'exit_time': current_time,
                        'status': 'closed_tp'
                    })
                    backtest_trades.append(position)
                    write_log(f"[{current_time}] TP LONG hit. Sold {position['amount_btc']:.6f} BTC at {current_price:.2f}. Profit: {profit:.2f} USDT. Balance: {current_balance_usdt:.2f} USDT")
                    current_open_position = None # Ferme la position
            
            elif position['type'] == 'short': # Position de vente (On possède des USDT, on veut racheter BTC moins cher)
                # Note: Dans un backtest SPOT, un "short" signifie qu'on a vendu BTC au début
                # et on attend de le racheter. Le profit est basé sur la différence de prix.
                # Conceptuellement, on a converti les BTC en USDT, et on attend de les re-convertir.
                
                if current_price >= position['stop_loss']:
                    profit = (position['entry_price'] - current_price) * position['amount_btc']
                    current_balance_btc += position['amount_btc'] # On rachète le BTC pour couvrir
                    current_balance_usdt -= position['amount_btc'] * current_price # Coût du rachat en USDT
                    
                    position.update({
                        'exit_price': current_price,
                        'profit_usd': profit,
                        'exit_time': current_time,
                        'status': 'closed_sl'
                    })
                    backtest_trades.append(position)
                    write_log(f"[{current_time}] SL SHORT hit. Bought {position['amount_btc']:.6f} BTC at {current_price:.2f}. Profit: {profit:.2f} USDT. Balance: {current_balance_usdt:.2f} USDT")
                    current_open_position = None
                elif current_price <= position['take_profit']:
                    profit = (position['entry_price'] - current_price) * position['amount_btc']
                    current_balance_btc += position['amount_btc'] # On rachète le BTC pour couvrir
                    current_balance_usdt -= position['amount_btc'] * current_price # Coût du rachat en USDT
                    
                    position.update({
                        'exit_price': current_price,
                        'profit_usd': profit,
                        'exit_time': current_time,
                        'status': 'closed_tp'
                    })
                    backtest_trades.append(position)
                    write_log(f"[{current_time}] TP SHORT hit. Bought {position['amount_btc']:.6f} BTC at {current_price:.2f}. Profit: {profit:.2f} USDT. Balance: {current_balance_usdt:.2f} USDT")
                    current_open_position = None

        # --- Décider d'ouvrir une nouvelle position ---
        if not current_open_position: # Seulement si aucune position n'est ouverte
            if signal == 'buy':
                # Calcul de la taille de la position en BTC
                amount_usdt_to_risk = current_balance_usdt * POSITION_SIZING_PCT
                amount_btc_to_buy = amount_usdt_to_risk / current_price
                
                # Assurez-vous que nous avons assez d'USDT pour l'achat
                if current_balance_usdt >= amount_usdt_to_risk:
                    stop_loss = current_price * (1 - STOP_LOSS_PCT)
                    take_profit = current_price * (1 + TAKE_PROFIT_PCT)
                    
                    current_open_position = {
                        'id': len(backtest_trades) + 1, # ID simple pour le backtest
                        'type': 'long',
                        'entry_time': current_time,
                        'entry_price': current_price,
                        'amount_btc': amount_btc_to_buy,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'status': 'open'
                    }
                    current_balance_usdt -= amount_usdt_to_risk # Déduction du solde USDT
                    current_balance_btc += amount_btc_to_buy # Augmentation des BTC possédés
                    write_log(f"[{current_time}] BUY signal. Opened LONG {amount_btc_to_buy:.6f} BTC at {current_price:.2f}. SL: {stop_loss:.2f}, TP: {take_profit:.2f}. Balance: {current_balance_usdt:.2f} USDT")
                else:
                    write_log(f"[{current_time}] BUY signal ignored: Insufficient USDT balance ({current_balance_usdt:.2f}) to open position.")

            elif signal == 'sell':
                # Pour un "short" en backtest spot, on simule une vente de BTC qu'on a déjà
                # et on gagne si le prix baisse. Cela signifie qu'on simule avoir des BTC virtuels
                # pour les vendre, puis les racheter.
                
                # Taille de la position en BTC à "vendre" (en assumant qu'on a le BTC)
                amount_btc_to_sell = current_balance_btc * POSITION_SIZING_PCT
                
                # Simplification: on suppose qu'on a toujours assez de BTC pour "short" avec un certain % du capital BTC
                # (Dans un vrai short, on emprunterait les BTC)
                if current_balance_btc >= amount_btc_to_sell and amount_btc_to_sell > 0: # S'assurer d'avoir des BTC pour vendre
                    stop_loss = current_price * (1 + STOP_LOSS_PCT)
                    take_profit = current_price * (1 - TAKE_PROFIT_PCT)
                    
                    current_open_position = {
                        'id': len(backtest_trades) + 1,
                        'type': 'short',
                        'entry_time': current_time,
                        'entry_price': current_price,
                        'amount_btc': amount_btc_to_sell,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'status': 'open'
                    }
                    current_balance_usdt += amount_btc_to_sell * current_price # Ajout USDT de la vente
                    current_balance_btc -= amount_btc_to_sell # Déduction BTC "vendus"
                    write_log(f"[{current_time}] SELL signal. Opened SHORT {amount_btc_to_sell:.6f} BTC at {current_price:.2f}. SL: {stop_loss:.2f}, TP: {take_profit:.2f}. Balance: {current_balance_usdt:.2f} USDT")
                else:
                    write_log(f"[{current_time}] SELL signal ignored: Insufficient BTC balance ({current_balance_btc:.6f}) to open short position or size too small.")


    # --- Fin du Backtest : Calcul des métriques de performance ---
    write_log("\n--- Backtest terminé ---")
    
    # Traiter toute position encore ouverte à la fin du backtest
    if current_open_position:
        position = current_open_position
        # Fermer la position au dernier prix du dataset (simule une fermeture manuelle)
        last_price = df['close'].iloc[-1]
        
        if position['type'] == 'long':
            profit = (last_price - position['entry_price']) * position['amount_btc']
            current_balance_usdt += position['amount_btc'] * last_price
            current_balance_btc -= position['amount_btc']
        elif position['type'] == 'short':
            profit = (position['entry_price'] - last_price) * position['amount_btc']
            current_balance_btc += position['amount_btc']
            current_balance_usdt -= position['amount_btc'] * last_price
            
        position.update({
            'exit_price': last_price,
            'profit_usd': profit,
            'exit_time': df['timestamp'].iloc[-1],
            'status': 'closed_end_of_test'
        })
        backtest_trades.append(position)
        write_log(f"Position ouverte fermée à la fin du backtest: {position['type']} pour {profit:.2f} USDT.")

    final_total_usdt = current_balance_usdt + (current_balance_btc * df['close'].iloc[-1]) # Solde final converti en USDT
    total_profit = final_total_usdt - INITIAL_BALANCE_USDT
    
    write_log(f"Solde initial: {INITIAL_BALANCE_USDT:.2f} USDT")
    write_log(f"Solde final (incluant BTC): {final_total_usdt:.2f} USDT")
    write_log(f"Profit/Perte net: {total_profit:.2f} USDT ({((total_profit / INITIAL_BALANCE_USDT) * 100):.2f}%)")
    write_log(f"Nombre total de trades fermés: {len(backtest_trades)}")

    # Calcul des statistiques de performance
    if backtest_trades:
        df_trades = pd.DataFrame(backtest_trades)
        wins = df_trades[df_trades['profit_usd'] > 0]
        losses = df_trades[df_trades['profit_usd'] < 0]

        win_count = len(wins)
        loss_count = len(losses)
        
        total_profit_from_trades = wins['profit_usd'].sum()
        total_loss_from_trades = losses['profit_usd'].sum()

        write_log(f"Trades gagnants: {win_count}")
        write_log(f"Trades perdants: {loss_count}")
        write_log(f"Profit total des gagnants: {total_profit_from_trades:.2f} USDT")
        write_log(f"Perte totale des perdants: {total_loss_from_trades:.2f} USDT")

        if loss_count > 0:
            win_rate = (win_count / (win_count + loss_count)) * 100
            avg_win = wins['profit_usd'].mean() if win_count > 0 else 0
            avg_loss = losses['profit_usd'].mean() if loss_count > 0 else 0
            risk_reward_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
            
            write_log(f"Taux de victoire: {win_rate:.2f}%")
            write_log(f"Gain moyen par trade gagnant: {avg_win:.2f} USDT")
            write_log(f"Perte moyenne par trade perdant: {avg_loss:.2f} USDT")
            write_log(f"Ratio Risque/Récompense (Moyenne): {risk_reward_ratio:.2f}")
        else:
            write_log("Aucune perte enregistrée (peut-être pas assez de trades ou stratégie très efficace !)")
            write_log("Taux de victoire: 100%")
            write_log("Ratio Risque/Récompense: Infini")
            
        # Potentiellement retourner le DataFrame des trades pour une analyse plus approfondie
        return df_trades
    else:
        write_log("Aucun trade n'a été exécuté pendant le backtest.")
        return pd.DataFrame()


# --- Exécution principale du backtester ---
if __name__ == "__main__":
    # Nom du fichier de données historiques que data_downloader.py va créer
    # Assurez-vous que ce nom correspond à celui généré par data_downloader.py
    # Vous devrez l'ajuster une fois le téléchargement terminé pour inclure les dates réelles du fichier
    
    # Pour le moment, utilisez un nom générique ou celui que vous attendez du téléchargeur
    # Une fois le téléchargement terminé, copiez le nom exact du fichier CSV généré.
    # Exemple (à ajuster) :
    # historical_data_filename = "historical_data_BTCUSDT_1m_20220701_to_20250630.csv"
    
    # Pour trouver le nom de fichier généré par data_downloader.py :
    # Regardez dans le dossier où vous exécutez data_downloader.py. 
    # Le nom sera quelque chose comme : historical_data_BTCUSDT_1m_YYYYMMDD_to_YYYYMMDD.csv
    # Où YYYYMMDD sont les dates de début et de fin réelles du téléchargement.

    # TEMPORAIRE : Remplacez par le nom réel de votre fichier une fois téléchargé
    historical_data_filename = "historical_data_BTCUSDT_1m_20220701_to_20250630.csv" # Mettez le nom réel ici !

    # Vérifier si le fichier de données existe
    if not os.path.exists(historical_data_filename):
        print(f"ATTENTION: Le fichier de données historiques '{historical_data_filename}' n'existe pas. Veuillez le télécharger avec data_downloader.py d'abord, ou ajustez le nom du fichier.")
    else:
        df_data = load_historical_data(historical_data_filename)
        if not df_data.empty:
            df_results = run_backtest(df_data)
            # Vous pouvez sauvegarder df_results pour une analyse ultérieure si vous voulez
            # df_results.to_csv("backtest_trades_results.csv", index=False)
            # print("Résultats des trades du backtest sauvegardés dans backtest_trades_results.csv")
        else:
            print("Impossible d'exécuter le backtest car aucune donnée historique n'a pu être chargée.")