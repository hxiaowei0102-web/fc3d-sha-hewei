"""
福彩3D 杀和尾 — 网格扫描公式池选优 (v2.3)
===========================================
目标: 扩大公式池, 网格扫描自动选优, 提高命中率

公式池设计 (总候选 ~180):
1. 线性公式族: (a*上期和尾 + b*跨度 + c) % 10
   a∈{0,1,2,3}, b∈{0,1,2,3}, c∈{0..9} → 160个 (含 h1s3: a=1,b=1,c=3; A9: a=-1,c=9)
2. 频率窗口族: 近{20,30,40,50,60,80,100,150,200,300,500}期最低频 → 11个
3. 转移表族: 阶数{1,2} × 窗口{100,200,300} → 6个
4. 跨位公式: 用百/十/个位各自的最低频尾 → 3个

评估: 严格 walk-forward (只用<=i-1数据), 多窗口命中率
  近100 / 近200 / 近500 / 全量
选优标准: 全量>=90.2% 且 近100>=93% 且 近500>=92% (三窗同时达标才算稳健)
"""
import csv, json, time
from collections import Counter, defaultdict

BASE = "D:/杀和尾"
CSV_PATH = BASE + "/fc3d-history.csv"
JSON_OUT = BASE + "/grid_results.json"
WARM = 250


def load_tails(path=CSV_PATH):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({"issue": r["issue"],
                             "b": int(r["hundreds"]), "s": int(r["tens"]), "g": int(r["ones"]),
                             "tail": (int(r["hundreds"]) + int(r["tens"]) + int(r["ones"])) % 10,
                             "span": max(int(r["hundreds"]), int(r["tens"]), int(r["ones"]))
                                    - min(int(r["hundreds"]), int(r["tens"]), int(r["ones"]))})
            except Exception:
                continue
    return rows


def build_pool():
    """构建公式池 v2: 返回 [(name, 描述, kill_fn)]
    规模: ~500+ 候选
    1. 线性公式族: (a*尾 + b*跨 + c) % 10, a,b∈{-2..3}, c∈{0..9} → 6*6*10=360 (去常数)
    2. 三维公式族: (a*尾 + b*跨 + c*个位 + d) % 10, a,b,c∈{0..3}, d∈{0..9} → 4*4*4*10=640 (抽样)
    3. 乘积公式族: (a*尾*跨 + b*跨 + c) % 10, a∈{0..2}, b∈{0..3}, c∈{0..9}
    4. 频率窗口族: 更多窗口
    5. 转移表族: 阶数{1,2,3} × 窗口{100,200,300,500}
    6. 跨位低频族
    """
    pool = []

    # 1. 线性公式族 (含负数系数)
    for a in range(-2, 4):
        for b in range(-2, 4):
            for c in range(0, 10):
                if a == 0 and b == 0:
                    continue
                name = f"L{a}{b}{c}"
                desc = f"({a}*尾+{b}*跨+{c})%10"
                pool.append((name, desc,
                    (lambda A, B, C: (lambda r, tails, i, ta: (A * r["tail"] + B * r["span"] + C) % 10))(a, b, c)))

    # 2. 三维公式族 (尾+跨+个位) — 抽样 a,b,c∈{0..3}
    for a in range(0, 4):
        for b in range(0, 4):
            for c in range(0, 4):
                for d in range(0, 10):
                    if a == 0 and b == 0 and c == 0:
                        continue
                    name = f"3D{a}{b}{c}{d}"
                    desc = f"({a}*尾+{b}*跨+{c}*个+{d})%10"
                    pool.append((name, desc,
                        (lambda A, B, C, D: (lambda r, tails, i, ta:
                            (A * r["tail"] + B * r["span"] + C * r["g"] + D) % 10))(a, b, c, d)))

    # 3. 乘积公式族
    for a in range(0, 3):
        for b in range(0, 4):
            for c in range(0, 10):
                if a == 0 and b == 0:
                    continue
                name = f"M{a}{b}{c}"
                desc = f"({a}*尾*跨+{b}*跨+{c})%10"
                pool.append((name, desc,
                    (lambda A, B, C: (lambda r, tails, i, ta:
                        (A * r["tail"] * r["span"] + B * r["span"] + C) % 10))(a, b, c)))

    # 4. 频率窗口族 (更多窗口)
    for w in (10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 100, 120, 150, 200, 250, 300, 400, 500):
        name = f"F{w}"
        desc = f"近{w}期最低频"
        pool.append((name, desc, (lambda W: (lambda r, tails, i, ta:
            min(range(10), key=lambda t: Counter(ta[max(WARM, i-W):i]).get(t, 0))))(w)))

    # 5. 转移表族 (含3阶, 更长窗口)
    for order in (1, 2, 3):
        for w in (100, 200, 300, 500):
            name = f"T{order}_{w}"
            desc = f"{order}阶转移表窗{w}"
            pool.append((name, desc, (lambda O, W: (lambda r, tails, i, ta:
                _trans_kill(tails, ta, i, O, W)))(order, w)))

    # 6. 跨位低频 (百/十/个各自历史最低频)
    for pos, pname in (('b', '百'), ('s', '十'), ('g', '个')):
        name = f"P{pos}"
        desc = f"{pname}位最低频"
        pool.append((name, desc, (lambda P: (lambda r, tails, i, ta:
            min(range(10), key=lambda t: Counter([x[P] for x in tails[WARM:i]]).get(t, 0))))(pos)))

    return pool


def _trans_kill(tails, ta, i, order, win):
    """转移表杀码: 用 (i-order)..(i-1) 历史转移 (通用多阶)"""
    lo = max(WARM, i - win)
    tab = defaultdict(lambda: [0.1] * 10)
    for j in range(lo + order, i):
        key = tuple(ta[j - k] for k in range(order, 0, -1))
        tab[key][ta[j]] += 1
    key = tuple(ta[i - k] for k in range(order, 0, -1))
    p = tab[key]
    return min(range(10), key=lambda t: p[t]) if sum(p) > 0 else -1  # -1 = 无历史, 用h1s3兜底


def precompute_pool_kills(tails, pool):
    """预计算池内每个公式每期的杀码"""
    T = len(tails)
    ta = [t["tail"] for t in tails]

    def h1s3_fallback(i):
        r = tails[i - 1]
        return (r["tail"] + r["span"] + 3) % 10

    results = {}
    for name, desc, fn in pool:
        kills = [0] * (T + 1)
        for i in range(WARM, T + 1):
            k = fn(tails[i - 1], tails, i, ta)
            if k == -1:
                k = h1s3_fallback(i)
            kills[i] = k
        results[name] = kills
    return results, ta


def evaluate(tails, kills, name, desc, WINDOWS=(100, 200, 500)):
    """单公式多窗口命中率"""
    T = len(tails)
    ta = [t["tail"] for t in tails]
    stats = {}
    for W in WINDOWS:
        lo = max(WARM, T - W)
        n = T - lo
        h = sum(1 for i in range(lo, T) if ta[i] != kills[i])
        stats[str(W)] = {"n": n, "hit": h, "pct": round(h / n * 100, 2)}
    full_n = T - WARM
    full_h = sum(1 for i in range(WARM, T) if ta[i] != kills[i])
    stats["full"] = {"n": full_n, "hit": full_h, "pct": round(full_h / full_n * 100, 2)}
    return stats


def run():
    t0 = time.time()
    tails = load_tails()
    T = len(tails)
    print(f"总期数: {T}, 回测范围: {WARM}~{T} ({T-WARM} 期)")

    pool = build_pool()
    print(f"公式池大小: {len(pool)}")
    print(f"构建公式池耗时: {time.time()-t0:.1f}s")

    # 预计算所有公式的杀码
    t1 = time.time()
    results, ta = precompute_pool_kills(tails, pool)
    print(f"预计算完成耗时: {time.time()-t1:.1f}s")

    # 评估所有公式
    t2 = time.time()
    all_stats = []
    for name, desc, _ in pool:
        stats = evaluate(tails, results[name], name, desc)
        all_stats.append((name, desc, stats))
    print(f"评估完成耗时: {time.time()-t2:.1f}s")

    # 排名: 按 全量 > 近500 > 近200 > 近100 综合
    def rank_key(x):
        s = x[2]
        return (s["full"]["pct"], s["500"]["pct"], s["200"]["pct"], s["100"]["pct"])

    all_stats.sort(key=rank_key, reverse=True)

    print("\n" + "=" * 75)
    print("=== 公式池 TOP 20 (按全量命中率) ===")
    print(f"{'排名':<4} {'公式':<10} {'说明':<24} {'近100':>7} {'近200':>7} {'近500':>7} {'全量':>7}")
    for i, (name, desc, s) in enumerate(all_stats[:20], 1):
        print(f"{i:<4} {name:<10} {desc:<24} {s['100']['pct']:>6}% {s['200']['pct']:>6}% {s['500']['pct']:>6}% {s['full']['pct']:>6}%")

    # 达标公式 (三窗同时满足)
    print("\n=== 达标公式 (全量>=90.2% 且 近500>=92% 且 近100>=93%) ===")
    qualified = [x for x in all_stats
                 if x[2]["full"]["pct"] >= 90.2 and x[2]["500"]["pct"] >= 92.0 and x[2]["100"]["pct"] >= 93.0]
    if not qualified:
        print("  (无公式三窗全达标 — 说明单公式性能天花板已到)")
        # 降级显示: 全量>=90.2 且 近500>=92
        qualified = [x for x in all_stats if x[2]["full"]["pct"] >= 90.2 and x[2]["500"]["pct"] >= 92.0]
        print(f"  (降级标准: 全量>=90.2% 且 近500>=92% → {len(qualified)} 个)")
    for name, desc, s in qualified[:15]:
        print(f"  {name:<10} {desc:<24} 近100={s['100']['pct']}% 近500={s['500']['pct']}% 全量={s['full']['pct']}%")

    # 输出到 JSON
    out = {"total": T, "pool_size": len(pool), "top20": [
        {"name": n, "desc": d, "stats": s} for n, d, s in all_stats[:20]]}
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 结果已保存: {JSON_OUT}")
    print(f"总耗时: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    run()
