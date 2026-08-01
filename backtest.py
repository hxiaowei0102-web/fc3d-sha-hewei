"""
福彩3D 杀和尾 — 回测与产物输出
100期明细(近→远)、双杀命中率、基线对照, 输出 prediction_data.json
"""
import os, json
from datetime import datetime, timezone, timedelta
from engine import load_tails, select_kill1, replay_kill1
from search_kill2 import search, make_fn, BASELINE_DOUBLE
from fetch_data import next_issue_calc

TZ = timezone(timedelta(hours=8))
BASE = os.path.dirname(os.path.abspath(__file__))
JSON_OUT = os.path.join(BASE, "prediction_data.json")
WARM = 250


def run():
    tails = load_tails()
    T = len(tails)

    # 1. 穷举 kill2 (锚点=T, 严格无泄漏); kill1_map 一次性重放, 与穷举共享
    results, kill1_map = search(tails, T=T, verbose=True)
    passing = [r for r in results if r["pass"]]
    chosen = passing[0] if passing else (results[0] if results else None)
    if chosen is None:
        raise RuntimeError("穷举无候选")
    f1, f2, op_name, c = chosen["key"]
    kill2_fn = make_fn(f1, f2, op_name, c)
    print(f"\n选定 kill2: {chosen['desc']} (三窗通过={chosen['pass']})")

    def pair_at(i):
        v = kill1_map.get(i)
        k1 = v[0] if isinstance(v, tuple) else v  # replay_kill1 返回 (kill, name)
        if k1 is None:
            k1 = select_kill1(tails, i)[0]
        k2 = kill2_fn(tails, i)
        if k2 == k1:
            k2 = (k2 + 1) % 10
        return k1, k2

    # 2. 明日预测 (第 T 期, 用 <= T-1 期信息)
    k1_next, k1_name, k1_score = select_kill1(tails, T)
    k2_next = kill2_fn(tails, T)
    if k2_next == k1_next:
        k2_next = (k2_next + 1) % 10
    next_issue = next_issue_calc(tails[-1]["issue"])

    # 3. 近100期明细 (近→远), 复用 kill1_map
    details = []
    for i in range(T - 1, max(WARM, T - 100) - 1, -1):
        k1, k2 = pair_at(i)
        actual = tails[i]["tail"]
        hit1, hit2 = actual != k1, actual != k2
        details.append({
            "issue": tails[i]["issue"],
            "number": f"{tails[i]['b']}{tails[i]['s']}{tails[i]['g']}",
            "tail": actual, "kill1": k1, "kill2": k2,
            "hit1": hit1, "hit2": hit2, "hit": hit1 and hit2,
        })

    # 4. 多窗口命中率(双杀 + 单独) + 基线固定(2,6)对照
    win_stats, base = {}, {}
    for W in (100, 200, 500, 1000):
        lo = max(WARM, T - W)
        n = T - lo
        dbl = h1 = h2 = 0
        for i in range(lo, T):
            k1, k2 = pair_at(i)
            if tails[i]["tail"] != k1: h1 += 1
            if tails[i]["tail"] != k2: h2 += 1
            if tails[i]["tail"] != k1 and tails[i]["tail"] != k2: dbl += 1
        win_stats[W] = {"n": n,
                        "dbl_hit": dbl, "dbl_pct": round(dbl / n * 100, 2),
                        "k1_hit": h1, "k1_pct": round(h1 / n * 100, 2),
                        "k2_hit": h2, "k2_pct": round(h2 / n * 100, 2)}
        bhits = sum(1 for i in range(lo, T) if tails[i]["tail"] not in (2, 6))
        base[W] = round(bhits / n * 100, 2)

    data = {
        "meta": {
            "updated": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"),
            "total_issues": T,
            "latest_issue": tails[-1]["issue"],
            "latest_number": f"{tails[-1]['b']}{tails[-1]['s']}{tails[-1]['g']}",
            "baseline_fixed_26": round(BASELINE_DOUBLE * 100, 2),
        },
        "prediction": {
            "next_issue": next_issue,
            "kill1": k1_next, "kill1_name": k1_name, "kill1_score": round(k1_score, 4),
            "kill2": k2_next, "kill2_desc": chosen["desc"],
            "kills": sorted([k1_next, k2_next]),
        },
        "kill2_eval": {k: chosen[k] for k in ("desc", "ind500", "overlap", "j100", "j200", "j500", "pass")},
        "window_stats": win_stats,
        "baseline_fixed26": base,
        "candidates_top5": [{k: r[k] for k in ("desc", "j100", "j200", "j500", "pass")} for r in results[:5]],
        "details": details,
    }
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n== 回测报告 ==")
    for W in (100, 200, 500, 1000):
        s = win_stats[W]
        print(f"近{W:>4}期 双杀{s['dbl_pct']}% | kill1单独{s['k1_pct']}% kill2单独{s['k2_pct']}% | 基线{base[W]}%")
    print(f"\n预测 {next_issue} 期: 杀 {k1_next}({k1_name}) + {k2_next}({chosen['desc']})")
    print(f"已输出 {JSON_OUT}")
    return data


if __name__ == "__main__":
    run()
