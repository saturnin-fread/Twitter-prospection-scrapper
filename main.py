import os, json, asyncio
from flask import Flask, request, jsonify
from twikit import Client
from twikit.guest import GuestClient

app = Flask(__name__)

COOKIES_JSON = os.environ.get("TWITTER_COOKIES_JSON", "")

def get_event_loop():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

async def build_client():
    if COOKIES_JSON:
        try:
            client = Client("fr-FR")
            cookies = json.loads(COOKIES_JSON)
            # Cookie-Editor exporte une liste, twikit attend un dict
            if isinstance(cookies, list):
                cookies = {c["name"]: c["value"] for c in cookies}
            client.set_cookies(cookies)
            return client
        except Exception as e:
            print(f"[WARN] cookies KO: {e}, fallback guest")
    guest = GuestClient()
    await guest.activate()
    return guest

@app.route("/health")
def health():
    return jsonify({"status": "ok", "cookies_loaded": bool(COOKIES_JSON)})

@app.route("/search", methods=["POST"])
def search():
    body = request.get_json(force=True) or {}
    keywords = body.get("keywords", "")
    count    = int(body.get("count", 20))

    if not keywords:
        return jsonify({"error": "keywords requis"}), 400

    async def _run():
        client = await build_client()
        tweets = await client.search_tweet(keywords, "Latest", count=count)
        results = []
        for t in tweets:
            try:
                u = getattr(t, "user", None)
                results.append({
                    "username":     getattr(u, "screen_name", "") if u else "",
                    "nom":          getattr(u, "name", "") if u else "",
                    "bio":          getattr(u, "description", "") if u else "",
                    "localisation": getattr(u, "location", "") if u else "",
                    "followers":    getattr(u, "followers_count", 0) if u else 0,
                    "url_profil":   f"https://twitter.com/{getattr(u, 'screen_name', '')}" if u else "",
                    "tweet":        getattr(t, "text", ""),
                    "likes":        getattr(t, "favorite_count", 0),
                    "source":       "twitter_twikit",
                })
            except Exception as e:
                results.append({"parse_error": str(e)})
        return results

    try:
        loop = get_event_loop()
        results = loop.run_until_complete(_run())
        return jsonify({"count": len(results), "prospects": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
