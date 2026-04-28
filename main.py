import os
import asyncio
from flask import Flask, request, jsonify
from Scweet.scweet import Scweet

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
    count    = int(body.get("count", 20))

    if not keywords:
        return jsonify({"error": "keywords requis"}), 400

    if not AUTH_TOKEN:
        return jsonify({"error": "TWITTER_AUTH_TOKEN non configuré"}), 500

    try:
        s = Scweet(auth_token=AUTH_TOKEN)
        tweets = s.search(keywords, limit=count)

        results = []
        for t in tweets:
            results.append({
                "username":     t.get("UserScreenName", ""),
                "nom":          t.get("UserName", ""),
                "bio":          t.get("UserDescription", ""),
                "localisation": t.get("UserLocation", ""),
                "followers":    t.get("UserFollowers", 0),
                "url_profil":   f"https://twitter.com/{t.get('UserScreenName', '')}",
                "tweet":        t.get("TweetContent", ""),
                "likes":        t.get("Likes", 0),
                "source":       "twitter_scweet",
            })

        return jsonify({
            "count":     len(results),
            "keywords":  keywords,
            "prospects": results,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
