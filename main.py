import os
import re
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify
from Scweet import Scweet

app = Flask(__name__)

AUTH_TOKEN = os.environ.get("TWITTER_AUTH_TOKEN", "")

def parse_twitter_date(date_str):
    try:
        return datetime.strptime(date_str, "%a %b %d %H:%M:%S +0000 %Y").replace(tzinfo=timezone.utc)
    except:
        return None

def extract_profile(t):
    raw_user = (
        t.get("raw", {})
         .get("core", {})
         .get("user_results", {})
         .get("result", {})
    )
    legacy       = raw_user.get("legacy", {})
    location     = raw_user.get("location", {})
    dm_perms     = raw_user.get("dm_permissions", {})
    professional = raw_user.get("professional", {})
    user_data    = t.get("user", {})

    # Site web
    site_web = ""
    url_entities = legacy.get("entities", {}).get("url", {}).get("urls", [])
    if url_entities:
        site_web = url_entities[0].get("expanded_url", "")

    # Catégorie professionnelle
    pro_category = ""
    pro_type = professional.get("professional_type", "")
    categories = professional.get("category", [])
    if categories:
        pro_category = categories[0].get("name", "")

    return {
        "username":        user_data.get("screen_name", ""),
        "nom":             user_data.get("name", ""),
        "bio":             legacy.get("description", ""),
        "localisation":    location.get("location", ""),
        "followers":       legacy.get("followers_count", 0),
        "following":       legacy.get("friends_count", 0),
        "total_tweets":    legacy.get("statuses_count", 0),
        "site_web":        site_web,
        "can_dm":          dm_perms.get("can_dm", False),
        "compte_pro":      bool(professional),
        "type_pro":        pro_type,
        "categorie_pro":   pro_category,
        "date_creation":   raw_user.get("core", {}).get("created_at", ""),
        "url_profil":      f"https://twitter.com/{user_data.get('screen_name', '')}",
        "tweet":           t.get("text", ""),
        "tweet_url":       t.get("tweet_url", ""),
        "tweet_date":      t.get("timestamp", ""),
        "likes":           t.get("likes", 0),
        "retweets":        t.get("retweets", 0),
        "source":          "twitter_scweet",
    }

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

    # ── Filtres ──────────────────────────────────────────────
    filtre_localisation  = body.get("localisation", "")        # ex: "France", "Paris"
    filtre_jours         = body.get("depuis_jours", None)      # ex: 30 → tweets des 30 derniers jours
    filtre_followers_min = int(body.get("followers_min", 0))   # ex: 100
    filtre_can_dm_only   = bool(body.get("can_dm_only", False))# ex: true

    if not keywords:
        return jsonify({"error": "keywords requis"}), 400
    if not AUTH_TOKEN:
        return jsonify({"error": "TWITTER_AUTH_TOKEN non configuré"}), 500

    try:
        s = Scweet(auth_token=AUTH_TOKEN)
        tweets = s.search(keywords, limit=count)

        results = []
        now = datetime.now(timezone.utc)

        for t in tweets:
            try:
                prospect = extract_profile(t)

                # ── Filtre localisation ───────────────────────
                if filtre_localisation:
                    loc = prospect["localisation"].lower()
                    if filtre_localisation.lower() not in loc:
                        continue

                # ── Filtre plage de dates ─────────────────────
                if filtre_jours:
                    tweet_date = parse_twitter_date(prospect["tweet_date"])
                    if tweet_date:
                        delta = now - tweet_date
                        if delta.days > int(filtre_jours):
                            continue

                # ── Filtre followers minimum ──────────────────
                if filtre_followers_min > 0:
                    if prospect["followers"] < filtre_followers_min:
                        continue

                # ── Filtre can_dm uniquement ──────────────────
                if filtre_can_dm_only and not prospect["can_dm"]:
                    continue

                results.append(prospect)

            except Exception as e:
                results.append({"parse_error": str(e)})

        return jsonify({
            "count":    len(results),
            "keywords": keywords,
            "filtres_appliques": {
                "localisation":  filtre_localisation or "aucun",
                "depuis_jours":  filtre_jours or "aucun",
                "followers_min": filtre_followers_min,
                "can_dm_only":   filtre_can_dm_only,
            },
            "prospects": results,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/profile", methods=["POST"])
def profile():
    """
    Récupère le profil complet + 5 derniers tweets d'un username.
    Body: { "username": "Batiweb" }
    """
    body     = request.get_json(force=True) or {}
    username = body.get("username", "").strip().lstrip("@")

    if not username:
        return jsonify({"error": "username requis"}), 400
    if not AUTH_TOKEN:
        return jsonify({"error": "TWITTER_AUTH_TOKEN non configuré"}), 500

    try:
        s = Scweet(auth_token=AUTH_TOKEN)

        # Récupère les 5 derniers tweets du profil
        recent = s.get_profile_tweets([username], limit=5)
        last_tweets = []
        profil_data = {}

        for t in recent:
            if not profil_data:
                profil_data = extract_profile(t)
            last_tweets.append({
                "text":      t.get("text", ""),
                "date":      t.get("timestamp", ""),
                "likes":     t.get("likes", 0),
                "retweets":  t.get("retweets", 0),
                "tweet_url": t.get("tweet_url", ""),
            })

        profil_data["derniers_tweets"] = last_tweets

        return jsonify(profil_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
