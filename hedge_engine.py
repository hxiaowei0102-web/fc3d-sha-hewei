"""
福彩3D 杀和尾 — Hedge 专家混合引擎 (v2.0 突破版)
==================================================
算法: 5专家动态加权混合
  E1 A9          : (9 - 上期和尾) % 10
  E2 h1s3        : (上期和尾 + 跨度 + 3) % 10   ← 原冠军
  E3 freq_all    : 全史最低频尾
  E4 freq50      : 近50期最低频尾
  E5 trans1      : 一阶尾转移概率表(贝叶斯收缩)
投票: 每个专家近150窗单杀命中率做权重, 加权票数最高的尾 = 最终杀码
      权重下限0.02防止专家"消失"

回测表现 (严格walk-forward, 只用<=i-1数据):
  近100期 98.0%  (+2.0pp vs h1s3)
  近200期 96.5%  (+1.5pp vs h1s3)
  近500期 94.4%  (+0.8pp vs h1s3)
  时段移位 中段+2.2pp / 中后+3.2pp / 尾段+0.8pp  (三段全胜)
"""
import csv, json, os, math
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
BASE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(BASE, "fc3d-history.csv")
OUT = os.path.join(BASE, "hedge_prediction.json")
WARM = 250
WIN = 150        # 权重评估窗口
SMOOTH = 0.02    # 权重下限

EXPERT_KEYS = ['A9', 'h1s3', 'freq_all', 'freq50', 'trans1']


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


# ========== 专家杀码预计算 (全部只用历史) ==========
def compute_expert_kills(tails):
    T = len(tails)
    tails_arr = [t["tail"] for t in tails]
    b_arr = [t["b"] for t in tails]
    s_arr = [t["s"] for t in tails]
    g_arr = [t["g"] for t in tails]

    def span_at(i):
        return max(b_arr[i], s_arr[i], g_arr[i]) - min(b_arr[i], s_arr[i], g_arr[i])

    def h1s3(i):
        return (tails_arr[i - 1] + span_at(i - 1) + 3) % 10

    kills = {e: [0] * T for e in EXPERT_KEYS}

    # 简单公式
    for i in range(WARM, T):
        kills['A9'][i] = (9 - tails_arr[i - 1]) % 10
        kills['h1s3'][i] = h1s3(i)

    # 频率类: freq_all(全史), freq50(近50)
    for e, win in (('freq_all', 0), ('freq50', 50)):
        cnt = Counter()
        for i in range(T):
            if i >= WARM:
                if win == 0:
                    cnt[tails_arr[i - 1]] += 1
                    tot = i - WARM
                else:
                    lo = max(WARM, i - win)
                    cnt = Counter(tails_arr[lo:i])
                    tot = i - lo
                if tot > 0:
                    kills[e][i] = min(range(10), key=lambda t: cnt.get(t, 0))
                else:
                    kills[e][i] = h1s3(i)

    # trans1: 一阶尾转移概率表 (滚动近300期, 拉普拉斯平滑0.1)
    for i in range(WARM, T):
        lo = max(WARM, i - 300)
        tab = defaultdict(lambda: [0.1] * 10)
        for j in range(lo + 1, i):
            tab[tails_arr[j - 1]][tails_arr[j]] += 1
        p = tab[tails_arr[i - 1]]
        s = sum(p)
        kills['trans1'][i] = min(range(10), key=lambda t: p[t]) if s > 0 else h1s3(i)

    return kills, tails_arr, b_arr, s_arr, g_arr


def expert_kill_at(e, i, tails_arr, b_arr, s_arr, g_arr):
    """对任意 i (可为T, 即预测下一期) 计算专家e的杀码, 只用 <=i-1 数据"""
    def span_at(k):
        return max(b_arr[k], s_arr[k], g_arr[k]) - min(b_arr[k], s_arr[k], g_arr[k])

    if e == 'A9':
        return (9 - tails_arr[i - 1]) % 10
    if e == 'h1s3':
        return (tails_arr[i - 1] + span_at(i - 1) + 3) % 10
    if e == 'freq_all':
        cnt = Counter(tails_arr[WARM:i])
        if i - WARM <= 0:
            return (tails_arr[i - 1] + span_at(i - 1) + 3) % 10
        return min(range(10), key=lambda t: cnt.get(t, 0))
    if e == 'freq50':
        lo = max(WARM, i - 50)
        cnt = Counter(tails_arr[lo:i])
        if i - lo <= 0:
            return (tails_arr[i - 1] + span_at(i - 1) + 3) % 10
        return min(range(10), key=lambda t: cnt.get(t, 0))
    if e == 'trans1':
        lo = max(WARM, i - 300)
        tab = defaultdict(lambda: [0.1] * 10)
        for j in range(lo + 1, i):
            tab[tails_arr[j - 1]][tails_arr[j]] += 1
        p = tab[tails_arr[i - 1]]
        s = sum(p)
        if s <= 0:
            return (tails_arr[i - 1] + span_at(i - 1) + 3) % 10
        return min(range(10), key=lambda t: p[t])
    return 0


def build_hedge_kill_fn(kills, tails_arr, b_arr, s_arr, g_arr, T):
    """返回 kill(i): 第i期的Hedge混合杀码 (只用 <=i-1 数据)
    i ∈ [WARM, T], 其中 i=T 表示预测下一期 (该期专家杀码现算)"""
    def kill(i):
        lo = max(WARM, i - WIN)
        if i - lo >= 10:
            ws = {}
            for e in EXPERT_KEYS:
                h = sum(1 for j in range(lo, i) if tails_arr[j] != kills[e][j])
                ws[e] = max(SMOOTH, h / (i - lo))
        else:
            ws = {e: 0.9 for e in EXPERT_KEYS}
        votes = [0.0] * 10
        for e in EXPERT_KEYS:
            if i < T:
                k = kills[e][i]
            else:
                k = expert_kill_at(e, i, tails_arr, b_arr, s_arr, g_arr)
            votes[k] += ws[e]
        return max(range(10), key=lambda t: votes[t])
    return kill


def next_issue_calc(last):
    if not last:
        return "?"
    year = int(str(last)[:4])
    num = int(str(last)[4:])
    return f"{year}{num + 1:03d}" if num < 365 else f"{year + 1}001"


def run():
    tails = load()
    T = len(tails)
    kills, tails_arr, b_arr, s_arr, g_arr = compute_expert_kills(tails)
    kill = build_hedge_kill_fn(kills, tails_arr, b_arr, s_arr, g_arr, T)

    # 对照基线 h1s3
    def span_at(i):
        return max(b_arr[i], s_arr[i], g_arr[i]) - min(b_arr[i], s_arr[i], g_arr[i])

    def h1s3_pred(i):
        return (tails_arr[i - 1] + span_at(i - 1) + 3) % 10

    # 预测下一期
    k_next = kill(T)
    next_issue = next_issue_calc(tails[-1]["issue"])

    # 多窗口命中率 (Hedge vs 基线)
    win = {}
    for W in (100, 200, 500, 1000):
        lo = max(WARM, T - W)
        n = T - lo
        hits = sum(1 for i in range(lo, T) if tails_arr[i] != kill(i))
        hits_base = sum(1 for i in range(lo, T) if tails_arr[i] != h1s3_pred(i))
        win[W] = {"n": n, "hit": hits, "pct": round(hits / n * 100, 2),
                  "base_pct": round(hits_base / n * 100, 2),
                  "diff": round((hits - hits_base) / n * 100, 2)}

    # 全量
    full_hits = sum(1 for i in range(WARM, T) if tails_arr[i] != kill(i))
    full_base = sum(1 for i in range(WARM, T) if tails_arr[i] != h1s3_pred(i))

    # 100期明细 (近→远) + 各专家当期杀码
    details = []
    for i in range(T - 1, max(WARM, T - 100) - 1, -1):
        k = kill(i)
        exp = {e: kills[e][i] for e in EXPERT_KEYS}
        ok = tails_arr[i] != k
        details.append({
            "issue": tails[i]["issue"],
            "number": f"{tails[i]['b']}{tails[i]['s']}{tails[i]['g']}",
            "tail": tails_arr[i], "kill": k, "hit": ok, "experts": exp,
        })

    data = {
        "meta": {
            "updated": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"),
            "total": T,
            "latest_issue": tails[-1]["issue"],
            "latest_number": f"{tails[-1]['b']}{tails[-1]['s']}{tails[-1]['g']}",
            "algorithm": "Hedge 5专家加权混合 (A9+h1s3+全史频+近50频+转移表)",
            "window": WIN,
            "full_hit": round(full_hits / (T - WARM) * 100, 2),
            "full_base": round(full_base / (T - WARM) * 100, 2),
        },
        "prediction": {
            "next_issue": next_issue,
            "kill": k_next,
            "experts": {e: expert_kill_at(e, T, tails_arr, b_arr, s_arr, g_arr) for e in EXPERT_KEYS},
        },
        "window_stats": win,
        "details": details,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Hedge 专家混合引擎 (v2.0):")
    print(f"  算法: {data['meta']['algorithm']}")
    print(f"  权重窗 {WIN}, 平滑 {SMOOTH}")
    print(f"\n命中率 (Hedge vs 基线h1s3):")
    for W in (100, 200, 500, 1000):
        w = win[W]
        print(f"  近{W:>4}期 {w['pct']}%  (基线{w['base_pct']}%, 差{w['diff']:+.2f}pp)")
    print(f"  全量   {data['meta']['full_hit']}%  (基线{data['meta']['full_base']}%)")
    print(f"\n预测 {next_issue} 期: 杀和尾 {k_next}")
    print(f"  专家投票: {data['prediction']['experts']}")
    print(f"已输出 {OUT}")
    return data


if __name__ == "__main__":
    run()
