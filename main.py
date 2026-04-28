import os, asyncio
from flask import Flask, request, jsonify
from twikit import Client
from twikit.guest import GuestClient

app = Flask(__name__)

AUTH_TOKEN = os.environ.get("TWITTER_AUTH_TOKEN", "")
CT0        = os.environ.get("TWITTER_CT0", "")

def get_loop():
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
    if AUTH_TOKEN and CT0:
        try:
            client = Client("fr-FR")
            client.set_cookies({
                "auth_token": AUTH_TOKEN,
                "ct0":        CT0,
            })
            return client, "authenticated"
        except Exception as e:
            print(f"[WARN] auth KO: {e}, fallback guest")
    guest = GuestClient()
    await guest.activate()
    return guest, "guest"

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "auth_token_set": bool(AUTH_TOKEN),
        "ct0_set":        bool(CT0),
    })

@app.route("/search", methods=["POST"])
def search():
    body     = request.get_json(force=True) or {}
    keywords = body.get("keywords", "")
    count    = int(body.get("count", 20))

    if not keywords:
        return jsonify({"error": "keywords requis"}), 400

    async def _run():
        client, mode = await build_client()
        tweets = await client.search_tweet(keywords, "Latest", count=count)
        results = []
        for t in tweets:
            try:
                u = getattr(t, "user", None)
                results.append({
                    "username":     getattr(u, "screen_name", ""),
                    "nom":          getattr(u, "name", ""),
                    "bio":          getattr(u, "description", ""),
                    "localisation": getattr(u, "location", ""),
                    "followers":    getattr(u, "followers_count", 0),
                    "url_profil":   f"https://twitter.com/{getattr(u, 'screen_name', '')}",
                    "tweet":        getattr(t, "text", ""),
                    "likes":        getattr(t, "favorite_count", 0),
                    "source":       f"twitter_twikit_{mode}",
                })
            except Exception as e:
                results.append({"parse_error": str(e)})
        return results, mode

    try:
        loop = get_loop()
        results, mode = loop.run_until_complete(_run())
        return jsonify({
            "count":     len(results),
            "mode":      mode,
            "keywords":  keywords,
            "prospects": results,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
