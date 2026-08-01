"""
福彩3D 杀和尾 — 单杀引擎（一杀制）
公式: kill = (上一期和尾 + 上一期跨度 + 3) % 10
全量命中率 ~91.7%, 近500期 ~93.6%
"""
import csv, json, os
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
BASE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(BASE, "fc3d-history.csv")
OUT = os.path.join(BASE, "single_prediction.json")
WARM = 250


def load():
    rows = []
    with open(CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                b, s, g = int(r["hundreds"]), int(r["tens"]), int(r["ones"])
                rows.append({"issue": r["issue"], "b": b, "s": s, "g": g,
                             "tail": (b + s + g) % 10})
            except Exception:
                continue
    return rows


def predict(i, tails):
    """单杀公式: (上一期和尾 + 上一期跨度 + 3) % 10"""
    r = tails[i - 1]
    h1 = r["tail"]
    span = max(r["b"], r["s"], r["g"]) - min(r["b"], r["s"], r["g"])
    return (h1 + span + 3) % 10


def next_issue_calc(last):
    if not last:
        return "?"
    year = int(str(last)[:4])
    num = int(str(last)[4:])
    return f"{year}{num + 1:03d}" if num < 365 else f"{year + 1}001"


def run():
    tails = load()
    T = len(tails)

    # 预测
    k_next = predict(T, tails)
    next_issue = next_issue_calc(tails[-1]["issue"])

    # 多窗口命中率
    win = {}
    for W in (100, 200, 500, 1000):
        lo = max(WARM, T - W)
        n = T - lo
        hits = sum(1 for i in range(lo, T) if tails[i]["tail"] != predict(i, tails))
        win[W] = {"n": n, "hit": hits, "pct": round(hits / n * 100, 2)}

    # 100期明细 (近→远)
    details = []
    for i in range(T - 1, max(WARM, T - 100) - 1, -1):
        k = predict(i, tails)
        ok = tails[i]["tail"] != k
        details.append({
            "issue": tails[i]["issue"],
            "number": f"{tails[i]['b']}{tails[i]['s']}{tails[i]['g']}",
            "tail": tails[i]["tail"], "kill": k, "hit": ok,
        })

    data = {
        "meta": {
            "updated": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"),
            "total": T,
            "latest_issue": tails[-1]["issue"],
            "latest_number": f"{tails[-1]['b']}{tails[-1]['s']}{tails[-1]['g']}",
            "formula": "(上期和尾 + 跨度 + 3) % 10",
            "full_hit": round(sum(1 for i in range(WARM, T)
                                   if tails[i]["tail"] != predict(i, tails)) / (T - WARM) * 100, 2),
        },
        "prediction": {
            "next_issue": next_issue,
            "kill": k_next,
        },
        "window_stats": win,
        "details": details,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"单杀命中率:")
    for W in (100, 200, 500, 1000):
        print(f"  近{W:>4}期 {win[W]['pct']}%")
    print(f"  全量(WARM~今) {data['meta']['full_hit']}%")
    print(f"\n预测 {next_issue} 期: 杀和尾 {k_next}")
    print(f"公式: {data['meta']['formula']}")
    print(f"已输出 {OUT}")
    return data


if __name__ == "__main__":
    run()
