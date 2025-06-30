import pandas as pd
import requests
import zipfile
import io
import os
from datetime import datetime, timedelta
import time # Assurez-vous que time est importé

def write_log(message):
    """Écrit un message horodaté dans la console."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")

def get_binance_data_url(symbol, timeframe, date_type, date_str):
    """
    Construit l'URL pour télécharger les données historiques de Binance.
    date_type peut être 'monthly' ou 'daily'.
    date_str format: 'YYYY-MM' for monthly, 'YYYY-MM-DD' for daily.
    """
    # Exemple: https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2023-01.zip
    # Exemple: https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2023-01-01.zip
    
    base_url = "https://data.binance.vision/data/spot/"
    return f"{base_url}{date_type}/klines/{symbol.replace('/', '')}/{timeframe}/{symbol.replace('/', '')}-{timeframe}-{date_str}.zip"

def download_and_extract_zip(url, target_dir="temp_data"):
    """
    Télécharge un fichier ZIP et extrait son contenu CSV.
    Retourne le chemin du fichier CSV extrait.
    """
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    write_log(f"Tentative de téléchargement : {url}")
    try:
        response = requests.get(url, stream=True, timeout=30) # Ajout d'un timeout
        response.raise_for_status() # Lève une exception pour les codes d'erreur HTTP (4xx ou 5xx)

        z = zipfile.ZipFile(io.BytesIO(response.content))
        # Binance klines ZIPs usually contain a single CSV file
        csv_filename = z.namelist()[0]
        extracted_path = os.path.join(target_dir, csv_filename)
        z.extractall(target_dir)
        write_log(f"Extrait {csv_filename} dans {target_dir}")
        return extracted_path

    except requests.exceptions.Timeout:
        write_log(f"Erreur: Timeout lors du téléchargement de {url}. Réessayez plus tard.")
        return None
    except requests.exceptions.RequestException as e:
        # 404 Not Found est courant pour les jours sans données ou futures
        if "404 Not Found" in str(e):
            write_log(f"Avertissement: Fichier non trouvé pour {url}. (Probablement pas de données pour ce jour/mois ou URL incorrecte).")
        else:
            write_log(f"Erreur de téléchargement depuis {url}: {e}")
        return None
    except zipfile.BadZipFile:
        write_log(f"Erreur: Le fichier téléchargé depuis {url} n'est pas un ZIP valide ou est corrompu.")
        return None
    except IndexError:
        write_log(f"Erreur: Le fichier ZIP depuis {url} ne contient pas de CSV attendu.")
        return None
    except Exception as e:
        write_log(f"Erreur inattendue lors du traitement de {url}: {e}")
        return None

def fetch_and_process_historical_data(symbol, timeframe, start_date_str, end_date_str, data_granularity='daily'):
    """
    Télécharge et fusionne les données historiques de Binance.
    data_granularity: 'monthly' or 'daily'
    """
    all_dfs = []
    current_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

    write_log(f"Début de la récupération des données pour {symbol} {timeframe} de {start_date_str} à {end_date_str}...")

    while current_date <= end_date:
        date_param = current_date.strftime('%Y-%m-%d')
        write_log(f"Traitement du jour : {date_param}")
        url = get_binance_data_url(symbol, timeframe, 'daily', date_param)
        csv_path = download_and_extract_zip(url)
        
        # Passe au jour suivant
        current_date += timedelta(days=1)

        if csv_path:
            try:
                # Les CSV de Binance ont une structure spécifique
                # ['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume',
                #  'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore']
                df_temp = pd.read_csv(csv_path, header=None, names=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 
                    'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 
                    'taker_buy_quote_asset_volume', 'ignore'
                ])
                # Nous avons besoin de 'timestamp', 'open', 'high', 'low', 'close', 'volume'
                df_temp = df_temp[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                df_temp['timestamp'] = pd.to_datetime(df_temp['timestamp'], unit='ms')
                all_dfs.append(df_temp)
                os.remove(csv_path) # Nettoie le fichier CSV temporaire
            except Exception as e:
                write_log(f"Erreur lors du traitement du CSV {csv_path}: {e}")
        
        # Petite pause pour ne pas surcharger le serveur
        time.sleep(0.5) 

    if not all_dfs:
        write_log("Aucune donnée n'a pu être téléchargée ou traitée pour la période spécifiée.")
        return pd.DataFrame()

    final_df = pd.concat(all_dfs, ignore_index=True)
    # Assurez-vous que les données sont triées chronologiquement et uniques
    final_df = final_df.sort_values('timestamp').drop_duplicates(subset=['timestamp']).reset_index(drop=True)
    write_log(f"Total de {len(final_df)} bougies téléchargées et fusionnées.")
    return final_df

def save_data_to_csv(df, filename):
    """Sauvegarde le DataFrame Pandas dans un fichier CSV."""
    df.to_csv(filename, index=False)
    write_log(f"Données sauvegardées dans {filename}")

if __name__ == "__main__":
    symbol_to_fetch = 'BTC/USDT'
    timeframe_to_fetch = '1m' 

    # --- Configuration pour 3 ans de données ---
    end_date = datetime.now() # Aujourd'hui
    start_date = end_date - timedelta(days=365 * 3) # Les 3 dernières années
    # Note: 365 * 3 est une approximation. Pour être exact, il faudrait compter les années bissextiles.
    # Pour le backtesting, quelques jours de différence ne sont généralement pas critiques.

    # Formatage des dates pour la fonction
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    # Gardons 'daily' pour les 1m, car les fichiers mensuels en 1m sont trop grands
    data_granularity = 'daily' 

    output_filename = f"historical_data_{symbol_to_fetch.replace('/', '')}_{timeframe_to_fetch}_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.csv"
    temp_download_dir = "temp_binance_data" # Répertoire temporaire pour les ZIP et CSV extraits

    if os.path.exists(output_filename):
        write_log(f"Le fichier de données '{output_filename}' existe déjà. Chargement des données existantes.")
        df_historical = pd.read_csv(output_filename)
        df_historical['timestamp'] = pd.to_datetime(df_historical['timestamp'])
    else:
        df_historical = fetch_and_process_historical_data(
            symbol_to_fetch, 
            timeframe_to_fetch, 
            start_date_str, 
            end_date_str, 
            data_granularity=data_granularity
        )
        
        if not df_historical.empty:
            save_data_to_csv(df_historical, output_filename)
        else:
            write_log("Aucune donnée récupérée pour le backtesting. Vérifiez vos paramètres ou la connexion.")

    # Nettoyage du dossier temporaire
    if os.path.exists(temp_download_dir):
        import shutil
        try:
            shutil.rmtree(temp_download_dir)
            write_log(f"Dossier temporaire '{temp_download_dir}' supprimé.")
        except OSError as e:
            write_log(f"Erreur lors de la suppression du dossier temporaire '{temp_download_dir}': {e}")


    if not df_historical.empty:
        write_log(f"Prêt pour le backtesting avec {len(df_historical)} bougies de {symbol_to_fetch} en {timeframe_to_fetch}.")
        write_log(f"Données du {df_historical['timestamp'].min()} au {df_historical['timestamp'].max()}")
    else:
        write_log("Aucune donnée historique n'est disponible pour le backtesting.")