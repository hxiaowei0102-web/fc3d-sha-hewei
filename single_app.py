"""
福彩3D 杀和尾 — 单杀面板 :5001
公式: (上期和尾 + 跨度 + 3) % 10
"""
import os, json
from flask import Flask, render_template

BASE = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(BASE, "single_prediction.json")
app = Flask(__name__)


@app.route("/")
def index():
    if not os.path.exists(JSON_PATH):
        return "暂无数据, 请先运行 python single_backtest.py", 503
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    w100 = data["window_stats"]["100"]["pct"]
    if w100 >= 93:
        alert = "ok"
    elif w100 >= 91:
        alert = "warn"
    else:
        alert = "critical"
    return render_template("single.html", d=data, alert=alert)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
