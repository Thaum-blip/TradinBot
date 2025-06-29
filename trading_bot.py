import ccxt
import time
from dotenv import load_dotenv
import os

# Charger les clés API depuis le fichier .env
load_dotenv()
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")

def init_exchange():
    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'options': {'defaultType': 'spot'},
    })
    exchange.set_sandbox_mode(True)  # Mode test
    return exchange

def afficher_solde(exchange):
    balance = exchange.fetch_balance()
    btc_balance = balance.get('BTC', {'free': 0, 'total': 0})
    usdt_balance = balance.get('USDT', {'free': 0, 'total': 0})
    print("\n=== Solde ===")
    print(f"BTC : Libre : {btc_balance['free']}, Total : {btc_balance['total']}")
    print(f"USDT : Libre : {usdt_balance['free']}, Total : {usdt_balance['total']}")
    print("================\n")

def passer_ordre(exchange, symbole, type_ordre, montant):
    try:
        order = exchange.create_order(
            symbol=symbole,
            type=type_ordre,
            side="buy",
            amount=montant,
        )
        print("\nOrdre passé avec succès :")
        print(order)
        print("=========================\n")
    except Exception as e:
        print(f"\nErreur lors du passage de l'ordre : {e}")
        print("=========================\n")

def main():
    exchange = init_exchange()
    
    while True:
        print("Que veux-tu faire ?")
        print("1 - Voir mon solde")
        print("2 - Passer un ordre d'achat")
        print("3 - Quitter")
        choix = input("Tape le numéro et appuie sur Entrée : ")

        if choix == "1":
            afficher_solde(exchange)
        elif choix == "2":
            symbole = input("Quel symbole veux-tu trader ? (ex : BTC/USDT) : ").upper()
            montant = float(input("Quel montant veux-tu acheter ? (en BTC) : "))
            passer_ordre(exchange, symbole, "market", montant)
        elif choix == "3":
            print("Arrêt du programme.")
            break
        else:
            print("Choix invalide. Réessaie.")

if __name__ == "__main__":
    main()
