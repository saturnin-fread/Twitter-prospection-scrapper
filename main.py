import os, json, asyncio
from flask import Flask, request, jsonify
from twikit import Client
from twikit.guest import GuestClient

app = Flask(__name__)

# ── auth via cookies stockés en Variable Railway ──────────────────────────────
COOKIES_JSON = os.environ.get("TWITTER_COOKIES_JSON", "")  # Variable Railway

async def get_client():
    """Retourne un client authentifié si cookies dispos, sinon guest."""
    if COOKIES_JSON:
        client = Client("fr-FR")
        cookies = json.loads(COOKIES_JSON)
        client.set_cookies(cookies)
        return client
    else:
        guest = GuestClient()
        await guest.activate()
        return guest

# ── endpoints ─────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/search", methods=["POST"])
def search():
    body = request.get_json(force=True) or {}
    keywords = body.get("keywords", "")
    count    = int(body.get("count", 20))
    if not keywords:
        return jsonify({"error": "keywords requis"}), 400

    async def _run():
        client = await get_client()
        tweets = await client.search_tweet(keywords, "Latest", count=count)
        results = []
        for t in tweets:
            u = t.user
            results.append({
                "username":    u.screen_name if u else "",
                "nom":         u.name if u else "",
                "bio":         u.description if u else "",
                "localisation": u.location if u else "",
                "followers":   u.followers_count if u else 0,
                "url_profil":  f"https://twitter.com/{u.screen_name}" if u else "",
                "tweet":       t.text,
                "source":      "twitter_twikit",
            })
        return results

    try:
        results = asyncio.run(_run())
        return jsonify({"count": len(results), "prospects": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
