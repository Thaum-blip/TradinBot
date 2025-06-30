import ccxt
import os
from dotenv import load_dotenv

# Charger les clés API depuis .env
load_dotenv()
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

# Fonction pour afficher le solde
def get_balance():
    balance = exchange.fetch_balance()
    usd_balance = balance['total'].get('USDT', 0)
    btc_balance = balance['total'].get('BTC', 0)
    return usd_balance, btc_balance

# Fonction pour exécuter un ordre
def place_order(symbol, side, amount):
    try:
        order = exchange.create_order(symbol, 'market', side, amount)
        print(f"✅ Ordre {side} exécuté :")
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
        return order
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution de l'ordre : {e}")
        return None

# Nouveauté : afficher les positions ouvertes
def show_positions():
    print("\n📄 Positions ouvertes :")
    try:
        # Récupérer tous les ordres ouverts (le proxy ici pour spot, car ccxt spot ne gère pas margin positions)
        orders = exchange.fetch_open_orders()
        if not orders:
            print("Aucune position/ordre ouvert.")
            return []
        positions = []
        for idx, order in enumerate(orders, start=1):
            symbol = order['symbol']
            side = order['side']
            amount = order['amount']
            price = order['price']
            positions.append(order)
            print(f"{idx} – {symbol} | {side.upper()} | qty: {amount} @ {price}")
        return positions
    except Exception as e:
        print(f"⚠️ Erreur position : {e}")
        return []

# Fermer une position existante
def close_position(positions):
    choix = input("\nTape le numéro de la position à fermer (0 pour annuler) : ")
    if not choix.isdigit() or int(choix) < 0 or int(choix) > len(positions):
        print("Choix invalide.")
        return
    if choix == '0':
        print("Annulé.")
        return
    pos = positions[int(choix) - 1]
    sym = pos['symbol']
    amount = pos['amount']
    side = 'sell' if pos['side'] == 'buy' else 'buy'
    print(f"🔄 Fermeture de {sym} qty {amount} côté {side.upper()}")
    order = place_order(sym, side, amount)
    if order:
        print("✅ Position fermée.")
    else:
        print("❌ Impossible de fermer la position.")

# Menu principal
def main():
    symbol = 'BTC/USDT'
    while True:
        print("\nQue veux-tu faire ?")
        print("1 - Voir mon solde")
        print("2 - Passer un ordre d'achat")
        print("3 - Passer un ordre de vente")
        print("4 - Voir mes positions ouvertes")
        print("5 - Fermer une position ouverte")
        choice = input("Tape le numéro et appuie sur Entrée : ")

        if choice == '1':
            usd_balance, btc_balance = get_balance()
            print(f"Solde disponible : {usd_balance:.2f} USDT, {btc_balance:.6f} BTC")

        elif choice == '2':
            usd_balance, _ = get_balance()
            amount = float(input("Montant en BTC à acheter : "))
            cost_estimate = amount * exchange.fetch_ticker(symbol)['ask']
            if cost_estimate > usd_balance:
                print("Fonds insuffisants pour cet achat.")
            else:
                place_order(symbol, 'buy', amount)
                usd_balance, btc_balance = get_balance()
                print(f"Nouveau solde : {usd_balance:.2f} USDT, {btc_balance:.6f} BTC")

        elif choice == '3':
            _, btc_balance = get_balance()
            amount = float(input("Montant en BTC à vendre : "))
            if amount > btc_balance:
                print("Fonds insuffisants pour cette vente.")
            else:
                place_order(symbol, 'sell', amount)
                usd_balance, btc_balance = get_balance()
                print(f"Nouveau solde : {usd_balance:.2f} USDT, {btc_balance:.6f} BTC")

        elif choice == '4':
            show_positions()

        elif choice == '5':
            positions = show_positions()
            if positions:
                close_position(positions)

        else:
            print("Choix invalide.\nRéessaie.")

if __name__ == "__main__":
    main()
