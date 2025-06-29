import os
from dotenv import load_dotenv
import ccxt

load_dotenv()  # charge les variables depuis .env et c'est sécurisé ducoup

def init_exchange(api_key, secret_key):
    api_key = os.getenv("API_KEY")
    secret_key = os.getenv("API_SECRET")

    exchange = ccxt.binance({
        'apiKey': api_key,
        'secret': secret_key,
        'options': {'defaultType': 'spot'},
    })
    exchange.set_sandbox_mode(True)
    return exchange

def get_balance(exchange):
    balance = exchange.fetch_balance()
    print("Solde disponible (uniquement > 0) :")
    for currency, amount in balance['total'].items():
        if amount > 0:
            print(f"{currency}: {amount}")

def place_order(exchange, symbol, order_type, side, amount, price=None):
    try:
        if order_type == 'limit':
            order = exchange.create_order(symbol, order_type, side, amount, price)
        elif order_type == 'market':
            order = exchange.create_order(symbol, order_type, side, amount)
        else:
            print("Type d'ordre non supporté.")
            return None
        print("Ordre passé avec succès :")
        print(order)
        return order
    except Exception as e:
        print("Erreur lors du passage de l'ordre :", e)
        return None

def print_order_summary(order):
    info = order.get('info', {})
    print("=== Récapitulatif de l'ordre ===")
    print(f"ID de l'ordre : {info.get('orderId', 'N/A')}")
    print(f"Type d'ordre : {order.get('type', 'N/A')}")
    print(f"Côté : {order.get('side', 'N/A')}")
    print(f"Symbole : {order.get('symbol', 'N/A')}")
    print(f"Statut : {order.get('status', 'N/A')}")
    print(f"Quantité demandée : {order.get('amount', 'N/A')}")
    print(f"Quantité exécutée : {order.get('filled', 'N/A')}")
    print(f"Prix moyen : {order.get('average', 'N/A')}")
    print(f"Coût total (quote asset) : {order.get('cost', 'N/A')}")
    fee = order.get('fee', {})
    print(f"Frais : {fee.get('cost', 0)} {fee.get('currency', '')}")
    print("===============================")

def main():
    api_key = "TA_CLE_API"
    secret_key = "TON_SECRET_KEY"
    exchange = init_exchange(api_key, secret_key)

    print("Que veux-tu faire ?")
    print("1 - Voir mon solde")
    print("2 - Passer un ordre d'achat")
    print("3 - Passer un ordre de vente")

    choix = input("Tape le numéro et appuie sur Entrée : ")

    if choix == '1':
        get_balance(exchange)
    elif choix == '2':
        place_order(exchange, 'BTC/USDT', 'market', 'buy', 0.001)
        if order:
            print_order_summary(order)
    elif choix == '3':
        place_order(exchange, 'BTC/USDT', 'market', 'sell', 0.001)
        if order:
            print_order_summary(order)
    else:
        print("Choix non reconnu.")

if __name__ == "__main__":
    main()
