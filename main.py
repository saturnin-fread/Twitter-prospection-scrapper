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
            try:
                user_data = t.get("user", {})
                raw_user  = (
                    t.get("raw", {})
                     .get("core", {})
                     .get("user_results", {})
                     .get("result", {})
                )
                legacy    = raw_user.get("legacy", {})
                location  = raw_user.get("location", {})

                results.append({
                    "username":     user_data.get("screen_name", ""),
                    "nom":          user_data.get("name", ""),
                    "bio":          legacy.get("description", ""),
                    "localisation": location.get("location", ""),
                    "followers":    legacy.get("followers_count", 0),
                    "url_profil":   f"https://twitter.com/{user_data.get('screen_name', '')}",
                    "tweet":        t.get("text", ""),
                    "likes":        t.get("likes", 0),
                    "retweets":     t.get("retweets", 0),
                    "tweet_url":    t.get("tweet_url", ""),
                    "date":         t.get("timestamp", ""),
                    "source":       "twitter_scweet",
                })
            except Exception as e:
                results.append({"parse_error": str(e)})

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
