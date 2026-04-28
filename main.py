import os
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from Scweet import Scweet

app = Flask(__name__)

AUTH_TOKEN       = os.environ.get("TWITTER_AUTH_TOKEN", "")
MAX_RESULTS_LIMIT = int(os.environ.get("MAX_RESULTS_LIMIT", "200"))

def parse_twitter_date(date_str):
    try:
        return datetime.strptime(date_str, "%a %b %d %H:%M:%S +0000 %Y").replace(tzinfo=timezone.utc)
    except Exception:
        return None

def extract_profile(t):
    user_data = t.get("user", {})
    raw       = t.get("raw", {})
    raw_user  = raw.get("core", {}).get("user_results", {}).get("result", {})
    legacy    = raw_user.get("legacy", {})
    location  = raw_user.get("location", {})
    core      = raw_user.get("core", {})
    dm_perms  = raw_user.get("dm_permissions", {})
    pro       = raw_user.get("professional", None)

    entities_url = legacy.get("entities", {}).get("url", {}).get("urls", [])
    site_web = entities_url[0].get("expanded_url", "") if entities_url else legacy.get("url", "")

    return {
        "username":       user_data.get("screen_name", ""),
        "nom":            user_data.get("name", ""),
        "url_profil":     f"https://twitter.com/{user_data.get('screen_name', '')}",
        "bio":            legacy.get("description", ""),
        "localisation":   location.get("location", ""),
        "site_web":       site_web,
        "date_creation":  core.get("created_at", ""),
        "followers":      legacy.get("followers_count", 0),
        "following":      legacy.get("friends_count", 0),
        "total_tweets":   legacy.get("statuses_count", 0),
        "can_dm":         dm_perms.get("can_dm", False),
        "is_professional": pro is not None,
        "pro_type":       pro.get("professional_type", "") if pro else "",
        "pro_categorie":  pro.get("category", [{}])[0].get("name", "") if pro else "",
        "tweet":          t.get("text", ""),
        "tweet_url":      t.get("tweet_url", ""),
        "tweet_date":     t.get("timestamp", ""),
        "likes":          t.get("likes", 0),
        "retweets":       t.get("retweets", 0),
        "source":         "twitter_scweet",
    }

def get_tweet_entry(t):
    return {
        "texte": t.get("text", ""),
        "url":   t.get("tweet_url", ""),
        "date":  t.get("timestamp", ""),
        "likes": t.get("likes", 0),
    }

@app.route("/health")
def health():
    return jsonify({
        "status":         "ok",
        "auth_token_set": bool(AUTH_TOKEN),
        "max_results":    MAX_RESULTS_LIMIT,
    })

@app.route("/search", methods=["POST"])
def search():
    body = request.get_json(force=True) or {}

    keywords             = body.get("keywords", "")
    count                = min(int(body.get("count", 20)), MAX_RESULTS_LIMIT)
    filtre_localisation  = body.get("localisation", "").strip().lower()
    filtre_jours         = body.get("depuis_jours", None)
    filtre_followers_min = int(body.get("followers_min", 0))
    filtre_can_dm_only   = bool(body.get("can_dm_only", False))

    if not keywords:
        return jsonify({"error": "keywords requis"}), 400
    if not AUTH_TOKEN:
        return jsonify({"error": "TWITTER_AUTH_TOKEN non configuré"}), 500

    try:
        s = Scweet(auth_token=AUTH_TOKEN)

        # On scrape MAX_RESULTS_LIMIT bruts pour avoir assez après filtrage
        tweets = s.search(keywords, limit=MAX_RESULTS_LIMIT)

        now     = datetime.now(timezone.utc)
        results = []
        seen    = {}  # username → index dans results

        for t in tweets:
            try:
                profile  = extract_profile(t)
                username = profile["username"]
                if not username:
                    continue

                # ── Filtre localisation ──────────────────────────────────
                if filtre_localisation:
                    loc = profile["localisation"].lower()
                    if filtre_localisation not in loc:
                        continue

                # ── Filtre plage de dates ────────────────────────────────
                if filtre_jours:
                    tweet_dt = parse_twitter_date(profile["tweet_date"])
                    if tweet_dt and (now - tweet_dt).days > int(filtre_jours):
                        continue

                # ── Filtre followers minimum ─────────────────────────────
                if filtre_followers_min > 0:
                    if profile["followers"] < filtre_followers_min:
                        continue

                # ── Filtre can_dm uniquement ─────────────────────────────
                if filtre_can_dm_only and not profile["can_dm"]:
                    continue

                # ── Regroupement par username (5 derniers tweets max) ────
                tweet_entry = get_tweet_entry(t)

                if username in seen:
                    idx = seen[username]
                    if len(results[idx]["derniers_tweets"]) < 5:
                        results[idx]["derniers_tweets"].append(tweet_entry)
                else:
                    if len(results) >= count:
                        continue
                    profile["derniers_tweets"] = [tweet_entry]
                    results.append(profile)
                    seen[username] = len(results) - 1

            except Exception:
                continue

        return jsonify({
            "count":    len(results),
            "keywords": keywords,
            "filtres_actifs": {
                "localisation":  filtre_localisation or None,
                "depuis_jours":  filtre_jours,
                "followers_min": filtre_followers_min or None,
                "can_dm_only":   filtre_can_dm_only,
            },
            "prospects": results,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
