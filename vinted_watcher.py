#!/usr/bin/env python3
"""
Vinted Watcher — surveille une ou plusieurs recherches Vinted
et envoie une notification Discord (via webhook) dès qu'un
nouvel article correspondant apparaît.

Version "single-run" pensée pour tourner via GitHub Actions
(tâche planifiée) : le script fait UNE vérification puis s'arrête.
C'est GitHub Actions qui se charge de le relancer périodiquement.

⚠️ IMPORTANT
- Ce script interroge l'API interne utilisée par le site web de Vinted.
  Elle n'est pas publique/officielle et peut changer sans préavis.
- Ce script ne fait AUCUN achat automatique : il te notifie, tu cliques
  et tu achètes toi-même. C'est volontaire, pour rester dans une zone
  raisonnable vis-à-vis des conditions d'utilisation de Vinted.
- Utilisation strictement personnelle, à tes risques.

Configuration :
- Modifie SEARCHES ci-dessous avec tes propres recherches.
- Le webhook Discord se configure en variable d'environnement
  DISCORD_WEBHOOK_URL (via un secret GitHub Actions), jamais en dur
  dans ce fichier — comme ça tu peux rendre le repo public sans risque.
"""

import json
import os
from pathlib import Path
from datetime import datetime

import requests

# ============== CONFIG ==============

# Une ou plusieurs recherches à surveiller.
SEARCHES = [
    {
        "name": "Nike Tech - jusqu'à 60€",
        "url": "https://www.vinted.fr/catalog?search_text=nke%20tech&catalog[]=2050&size_ids[]=207&size_ids[]=208&brand_ids[]=53&status_ids[]=1&status_ids[]=6&status_ids[]=2&color_ids[]=1&color_ids[]=3&price_from=0&price_to=60&currency=EUR",
    },
    # Ajoute d'autres recherches ici si besoin
]

# Le webhook vient d'une variable d'environnement (secret GitHub),
# jamais écrit en clair ici.
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

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
    trimmed = list(seen)[-2000:]
    SEEN_FILE.write_text(json.dumps(trimmed))


def build_api_url(search_url: str) -> str:
    if "?" in search_url:
        query = search_url.split("?", 1)[1]
    else:
        query = ""
    base = "https://www.vinted.fr/api/v2/catalog/items"
    extra = "order=newest_first"
    if query:
        return f"{base}?{query}&{extra}"
    return f"{base}?{extra}"


def fetch_items(search_url: str):
    api_url = build_api_url(search_url)
    session = requests.Session()
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
    if not DISCORD_WEBHOOK_URL:
        print("⚠️  DISCORD_WEBHOOK_URL n'est pas définie (secret GitHub manquant ?).")
        return

    first_run = not SEEN_FILE.exists()
    seen = load_seen()

    if first_run:
        print("Premier lancement — on mémorise les articles déjà en ligne sans notifier.")

    for search in SEARCHES:
        try:
            items = fetch_items(search["url"])
        except Exception as e:
            print(f"[!] Erreur récupération '{search['name']}': {e}")
            continue

        new_items = [it for it in items if str(it.get("id")) not in seen]

        if first_run:
            for item in new_items:
                seen.add(str(item.get("id")))
            print(f"[i] {len(new_items)} article(s) existants mémorisés pour '{search['name']}' (pas de notif).")
        else:
            for item in reversed(new_items):
                notify_discord(search["name"], item)
                seen.add(str(item.get("id")))
                print(f"[+] Notifié: {item.get('title')}")

        save_seen(seen)

    print("Vérification terminée.")


if __name__ == "__main__":
    main()
