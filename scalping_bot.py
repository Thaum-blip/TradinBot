import ccxt
import time
from dotenv import load_dotenv
import os

# Charger les variables d'environnement
load_dotenv()

API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")

# Initialisation de l'exchange
def init_exchange():
    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'options': {'defaultType': 'spot'},
    })
    exchange.set_sandbox_mode(True)  # Utiliser le mode sandbox pour éviter les risques
    return exchange

# Afficher les détails de l'ordre
def afficher_details_ordre(order):
    try:
        symbole = order.get('symbol', 'N/A')
        type_ordre = order.get('type', 'N/A')
        montant = order.get('amount', 'N/A')
        prix_moyen = order.get('average', 'N/A')
        cout_total = order.get('cost', 'N/A')
        statut = order.get('status', 'N/A')
        commission = order.get('fee', {}).get('cost', 0.0)
        commission_devise = order.get('fee', {}).get('currency', 'N/A')

        print("\n=== Détails de l'ordre ===")
        print(f"Symbole : {symbole}")
        print(f"Type d'ordre : {type_ordre}")
        print(f"Montant : {montant}")
        print(f"Prix moyen : {prix_moyen} USDT")
        print(f"Coût total : {cout_total} USDT")
        print(f"Commission : {commission} {commission_devise}")
        print(f"Statut : {statut}")
        print("==========================\n")

    except Exception as e:
        print(f"Erreur lors de l'affichage des détails de l'ordre : {e}")

# Fonction principale du bot de scalping
def scalping_bot(exchange, symbole, montant, prix_achat_cible, prix_vente_cible):
    while True:
        try:
            ticker = exchange.fetch_ticker(symbole)
            prix_actuel = ticker['last']
            print(f"Prix actuel : {prix_actuel} USDT")

            if prix_actuel <= prix_achat_cible:
                print("Prix cible d'achat atteint ! Passons un ordre d'achat.")
                order = exchange.create_order(
                    symbol=symbole,
                    type="market",
                    side="buy",
                    amount=montant,
                )
                afficher_details_ordre(order)
                print("Achat effectué, en attente du prix de vente cible...\n")

                while True:
                    ticker = exchange.fetch_ticker(symbole)
                    prix_actuel = ticker['last']
                    print(f"Prix actuel : {prix_actuel} USDT")

                    if prix_actuel >= prix_vente_cible:
                        print("Prix cible de vente atteint ! Passons un ordre de vente.")
                        order = exchange.create_order(
                            symbol=symbole,
                            type="market",
                            side="sell",
                            amount=montant,
                        )
                        afficher_details_ordre(order)
                        print("Vente effectuée. Prêt pour une nouvelle opportunité.\n")
                        break

                    time.sleep(2)

            time.sleep(2)

        except Exception as e:
            print(f"Erreur dans le bot : {e}")
            time.sleep(5)

# Lancer le bot
if __name__ == "__main__":
    exchange = init_exchange()
    symbole = "BTC/USDT"
    montant = 0.001  # Quantité de BTC à acheter/vendre
    prix_achat_cible = 108000  # Modifier selon tes critères
    prix_vente_cible = 109000  # Modifier selon tes critères

    print("Bot de scalping démarré !")
    scalping_bot(exchange, symbole, montant, prix_achat_cible, prix_vente_cible)
