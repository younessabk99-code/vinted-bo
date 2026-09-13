#!/usr/bin/env python3
"""
Vinted Watcher — surveille une ou plusieurs recherches Vinted
et envoie une notification Discord (via webhook) dès qu'un
nouvel article correspondant apparaît.

⚠️ IMPORTANT
- Ce script interroge l'API interne utilisée par le site web de Vinted.
  Elle n'est pas publique/officielle et peut changer sans préavis.
- Reste raisonnable sur POLL_INTERVAL (30-60s minimum) pour éviter
  d'être bloqué (rate limit / ban IP).
- Ce script ne fait AUCUN achat automatique : il te notifie, tu cliques
  et tu achètes toi-même. C'est volontaire, pour rester dans une zone
  raisonnable vis-à-vis des conditions d'utilisation de Vinted.
- Utilisation strictement personnelle, à tes risques.

Installation :
    pip install requests --break-system-packages

Configuration : modifie la section CONFIG ci-dessous.
"""

import json
import time
import random
from pathlib import Path
from datetime import datetime

import requests

# ============== CONFIG ==============

# Une ou plusieurs recherches à surveiller.
# `url` = l'URL de recherche Vinted (copie-colle depuis ton navigateur
# après avoir appliqué tes filtres marque/taille/prix/etc.)
SEARCHES = [
    {
        "name": "Nike Tech - jusqu'à 60€",
        "url": "https://www.vinted.fr/catalog?search_text=nke%20tech&catalog[]=2050&size_ids[]=207&size_ids[]=208&brand_ids[]=53&status_ids[]=1&status_ids[]=6&status_ids[]=2&color_ids[]=1&color_ids[]=3&price_from=0&price_to=60&currency=EUR",
    },
    # Ajoute d'autres recherches ici si besoin
]

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1548760593622769710/4yD8TaS6XkzzpvtzmRmf-dMOXW8iehpqEJMcKY-OjuWs5kGOlG2rCUU-Gd9rIQnFybKO"

POLL_INTERVAL_SECONDS = 45  # ne descends pas trop bas (risque de blocage)
SEEN_FILE = Path(__file__).parent / "seen_items.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}

# =====================================


def load_seen():
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen):
    # on garde seulement les 2000 derniers ids pour ne pas grossir à l'infini
    trimmed = list(seen)[-2000:]
    SEEN_FILE.write_text(json.dumps(trimmed))


def build_api_url(search_url: str) -> str:
    """
    Transforme une URL de recherche Vinted (catalog?...) en URL d'API
    interne (api/v2/catalog/items?...). Les paramètres de filtre restent
    les mêmes après le '?'.
    """
    if "?" in search_url:
        query = search_url.split("?", 1)[1]
    else:
        query = ""
    base = "https://www.vinted.fr/api/v2/catalog/items"
    sep = "&" if "order=" in query else ("&" if query else "")
    extra = "order=newest_first"
    if query:
        return f"{base}?{query}&{extra}"
    return f"{base}?{extra}"


def fetch_items(search_url: str):
    api_url = build_api_url(search_url)
    session = requests.Session()
    # Vinted exige un cookie de session valide pour l'API ; on récupère
    # d'abord la page classique pour obtenir les cookies nécessaires.
    session.get("https://www.vinted.fr/", headers=HEADERS, timeout=15)
    resp = session.get(api_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("items", [])


def notify_discord(search_name: str, item: dict):
    title = item.get("title", "Article Vinted")
    price = item.get("price", {})
    price_str = f"{price.get('amount', '?')} {price.get('currency_code', '')}"
    url = item.get("url", "")
    photo = (item.get("photo") or {}).get("url")

    embed = {
        "title": title,
        "url": url,
        "description": f"💶 {price_str}",
        "footer": {"text": f"Recherche : {search_name}"},
        "timestamp": datetime.utcnow().isoformat(),
    }
    if photo:
        embed["thumbnail"] = {"url": photo}

    payload = {"embeds": [embed]}
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"[!] Erreur envoi Discord: {e}")


def main():
    if "COLLE_TON_WEBHOOK" in DISCORD_WEBHOOK_URL:
        print("⚠️  Configure d'abord DISCORD_WEBHOOK_URL dans le script.")
        return

    seen = load_seen()
    print(f"Démarrage — {len(SEARCHES)} recherche(s), poll toutes les {POLL_INTERVAL_SECONDS}s.")

    while True:
        for search in SEARCHES:
            try:
                items = fetch_items(search["url"])
            except Exception as e:
                print(f"[!] Erreur récupération '{search['name']}': {e}")
                continue

            new_items = [it for it in items if str(it.get("id")) not in seen]

            for item in reversed(new_items):  # du plus ancien au plus récent
                notify_discord(search["name"], item)
                seen.add(str(item.get("id")))
                print(f"[+] Notifié: {item.get('title')}")

            save_seen(seen)

        # petit jitter pour ne pas être trop prévisible
        time.sleep(POLL_INTERVAL_SECONDS + random.uniform(0, 5))


if __name__ == "__main__":
    main()
