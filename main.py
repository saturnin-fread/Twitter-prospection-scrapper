import os
from flask import Flask, request, jsonify
from Scweet import Scweet

app = Flask(__name__)

AUTH_TOKEN = os.environ.get("TWITTER_AUTH_TOKEN", "")

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "auth_token_set": bool(AUTH_TOKEN)
    })

@app.route("/search", methods=["POST"])
def search():
    body     = request.get_json(force=True) or {}
    keywords = body.get("keywords", "")
    count    = int(body.get("count", 5))

    if not keywords:
        return jsonify({"error": "keywords requis"}), 400

    try:
        s = Scweet(auth_token=AUTH_TOKEN)
        tweets = s.search(keywords, limit=count)

        # Retourne les données BRUTES pour voir les vraies clés
        raw = []
        for t in tweets:
            if isinstance(t, dict):
                raw.append(t)
            else:
                raw.append(vars(t) if hasattr(t, '__dict__') else str(t))

        return jsonify({
            "count": len(raw),
            "raw_keys": list(raw[0].keys()) if raw else [],
            "first_item": raw[0] if raw else {},
            "all": raw,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
