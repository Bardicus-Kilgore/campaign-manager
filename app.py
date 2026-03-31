"""
app.py — pf2e-baudot Flask application
"""

from flask import Flask, render_template, request, jsonify
import database as db

app = Flask(__name__)


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    stats = db.get_stats()
    return render_template("index.html", stats=stats)


@app.route("/grimoire")
def grimoire():
    tab = request.args.get("tab", "spells")
    conditions = db.get_all_conditions() if tab == "conditions" else []
    return render_template("grimoire.html", tab=tab, conditions=conditions)


@app.route("/bestiary")
def bestiary():
    return render_template("bestiary.html")


# ── API ───────────────────────────────────────────────────────────────────────

@app.route("/api/spells")
def api_spells():
    q          = request.args.get("q", "").strip()
    level      = request.args.get("level") or None
    tradition  = request.args.get("tradition") or None
    spell_type = request.args.get("type") or None
    results    = db.search_spells(q=q, level=level, tradition=tradition,
                                  spell_type=spell_type)
    return jsonify(results)


@app.route("/api/creatures")
def api_creatures():
    q             = request.args.get("q", "").strip()
    level         = request.args.get("level") or None
    creature_type = request.args.get("type") or None
    results       = db.search_creatures(q=q, level=level,
                                        creature_type=creature_type)
    return jsonify(results)


@app.route("/api/feats")
def api_feats():
    q          = request.args.get("q", "").strip()
    level      = request.args.get("level") or None
    feat_class = request.args.get("class") or None
    results    = db.search_feats(q=q, level=level, feat_class=feat_class)
    return jsonify(results)


@app.route("/api/items")
def api_items():
    q      = request.args.get("q", "").strip()
    level  = request.args.get("level") or None
    results = db.search_items(q=q, level=level)
    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
