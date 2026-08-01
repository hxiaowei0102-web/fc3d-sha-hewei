"""
福彩3D 杀和尾 — Flask 面板 :5000
/         面板(预测 + 100期回测近→远 + 基线对照 + 告警)
/refresh  手动抓数重算
"""
import os, json, subprocess, sys
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, jsonify

TZ = timezone(timedelta(hours=8))
BASE = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(BASE, "prediction_data.json")
app = Flask(__name__)


def load_data():
    if not os.path.exists(JSON_PATH):
        return None
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def alert_level(data):
    """滚动100期双杀率跌破基线 → 告警"""
    if not data:
        return "nodata"
    w100 = data["window_stats"].get("100", {}).get("dbl_pct", 0)
    base = data["meta"]["baseline_fixed_26"]
    if w100 < base - 3:
        return "critical"
    if w100 < base:
        return "warn"
    return "ok"


@app.route("/")
def index():
    data = load_data()
    if data is None:
        return "暂无数据, 请先运行 python backtest.py 或访问 /refresh", 503
    return render_template("index.html", d=data, alert=alert_level(data))


@app.route("/refresh")
def refresh():
    """抓新数据 → 重跑回测"""
    log = []
    try:
        r1 = subprocess.run([sys.executable, os.path.join(BASE, "fetch_data.py")],
                            capture_output=True, text=True, timeout=60, cwd=BASE)
        log.append(r1.stdout + r1.stderr)
        r2 = subprocess.run([sys.executable, os.path.join(BASE, "backtest.py")],
                            capture_output=True, text=True, timeout=300, cwd=BASE)
        log.append(r2.stdout + r2.stderr)
    except Exception as e:
        log.append(f"ERROR: {e}")
    data = load_data()
    return jsonify({"ok": data is not None, "log": "\n".join(log),
                    "updated": data["meta"]["updated"] if data else None})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
