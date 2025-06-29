import ccxt
from dotenv import load_dotenv
import os

def init_exchange():
    load_dotenv()  # charge les variables depuis le fichier .env
    api_key = os.getenv('API_KEY')
    secret_key = os.getenv('SECRET_KEY')

    if not api_key or not secret_key:
        print("Erreur : API_KEY ou SECRET_KEY non trouvées dans le fichier .env")
        exit(1)

    exchange = ccxt.binance({
        'apiKey': api_key,
        'secret': secret_key,
        'options': {'defaultType': 'spot'},
    })
    exchange.set_sandbox_mode(True)  # mode testnet activé
    return exchange

def print_balance(exchange):
    balance = exchange.fetch_balance()
    print("\n--- Solde Spot ---")
    for coin, info in balance['total'].items():
        if info > 0:
            print(f"{coin}: {info}")
    print("-----------------\n")

def place_order(exchange, symbol, side, amount):
    try:
        order = exchange.create_order(symbol, 'market', side, amount)
        print("\nOrdre passé avec succès :")
        print(f"Type: {order['type']}, Côté: {order['side']}")
        print(f"Montant: {order['amount']}")
        print(f"Prix moyen: {order['average']}")
        print(f"Status: {order['status']}\n")
        return order
    except Exception as e:
        print("Erreur lors du passage de l'ordre :", e)
        return None

def main():
    print("Bienvenue dans ton Trading Bot (testnet spot Binance)\n")
    exchange = init_exchange()

    symbol = "BTC/USDT"  # tu peux changer ici pour la paire que tu veux trader

    while True:
        print("Que veux-tu faire ?")
        print("1 - Voir mon solde")
        print("2 - Passer un ordre d'achat")
        print("3 - Passer un ordre de vente")
        print("4 - Quitter")

        choice = input("Tape le numéro et appuie sur Entrée : ").strip()

        if choice == '1':
            print_balance(exchange)
        elif choice == '2':
            amount = float(input("Combien de BTC veux-tu acheter ? (ex: 0.001) : "))
            place_order(exchange, symbol, 'buy', amount)
        elif choice == '3':
            amount = float(input("Combien de BTC veux-tu vendre ? (ex: 0.001) : "))
            place_order(exchange, symbol, 'sell', amount)
        elif choice == '4':
            print("Au revoir, à bientôt !")
            break
        else:
            print("Choix invalide, recommence.")

if __name__ == "__main__":
    main()
