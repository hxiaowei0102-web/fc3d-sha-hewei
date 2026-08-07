"""
福彩3D 杀和尾 — 专家级回测 (v2.1 增强)
=========================================
回答: 本期专家投票 (A9/h1s3/全史低频/近50低频/一阶转移表) 能加入回测吗?

核心设计:
1. 每个专家独立命中率 (近100/200/500/全量) — 看谁最强
2. Hedge 加权投票 vs 各专家 vs 基线(h1s3) — 验证投票组合优势
3. 权重有效性: 高权重专家是否真的命中更高 (近150窗内)
4. 一致性检验: 两专家杀码相同时胜率? 不同时投票是否更优?

严格 walk-forward: 预测第 i 期只用 <=i-1 数据, 无未来泄漏
"""
import csv, json, os
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE, "fc3d-history.csv")
JSON_OUT = os.path.join(BASE, "expert_backtest.json")
WARM = 250
WINDOW_W = 150      # Hedge 权重评估窗口
SMOOTH = 0.02       # 权重下限
EXPERT_KEYS = ['A9', 'h1s3', 'freq_all', 'freq50', 'trans1']
EXPERT_LABELS = {
    'A9': 'A9(9-上期尾)', 'h1s3': '公式(h1+span+3)',
    'freq_all': '全史低频', 'freq50': '近50低频', 'trans1': '一阶转移表',
}


def load_tails(path=CSV_PATH):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({"issue": r["issue"],
                             "b": int(r["hundreds"]), "s": int(r["tens"]), "g": int(r["ones"]),
                             "tail": (int(r["hundreds"]) + int(r["tens"]) + int(r["ones"])) % 10})
            except Exception:
                continue
    return rows


def precompute_kills(tails):
    T = len(tails)
    ta = [t["tail"] for t in tails]
    kills = {e: [0] * (T + 1) for e in EXPERT_KEYS}

    def h1s3(i):
        r = tails[i - 1]
        sp = max(r["b"], r["s"], r["g"]) - min(r["b"], r["s"], r["g"])
        return (r["tail"] + sp + 3) % 10

    for i in range(WARM, T + 1):
        kills['A9'][i] = (9 - tails[i - 1]["tail"]) % 10
        kills['h1s3'][i] = h1s3(i)

    for e, win in (('freq_all', 0), ('freq50', 50)):
        cnt = Counter()
        for i in range(T + 1):
            if i >= WARM:
                if win == 0:
                    cnt[ta[i - 1]] += 1
                    tot = i - WARM
                else:
                    lo = max(WARM, i - win)
                    cnt = Counter(ta[lo:i])
                    tot = i - lo
                if tot > 0:
                    kills[e][i] = min(range(10), key=lambda t: cnt.get(t, 0))
                else:
                    kills[e][i] = h1s3(i)

    for i in range(WARM, T + 1):
        lo = max(WARM, i - 300)
        tab = defaultdict(lambda: [0.1] * 10)
        for j in range(lo + 1, i):
            tab[ta[j - 1]][ta[j]] += 1
        p = tab[tails[i - 1]["tail"]]
        kills['trans1'][i] = min(range(10), key=lambda t: p[t]) if sum(p) > 0 else h1s3(i)

    return kills, ta


def hedge_kill_at(kills, ta, i):
    """第 i 期 Hedge 加权投票杀码 (只用 <=i-1 数据)"""
    lo = max(WARM, i - WINDOW_W)
    if i - lo >= 10:
        ws = {}
        for e in EXPERT_KEYS:
            h = sum(1 for j in range(lo, i) if ta[j] != kills[e][j])
            ws[e] = max(SMOOTH, h / (i - lo))
    else:
        ws = {e: 0.9 for e in EXPERT_KEYS}
    votes = [0.0] * 10
    for e in EXPERT_KEYS:
        votes[kills[e][i]] += ws[e]
    return max(range(10), key=lambda t: votes[t]), ws


def run():
    tails = load_tails()
    T = len(tails)
    kills, ta = precompute_kills(tails)
    print(f"总期数: {T}, 回测范围: {WARM}~{T} ({T-WARM} 期)")

    # ── 1. 各专家独立命中率 + 基线 ──
    print("\n=== 1. 各专家独立命中率 (单杀正确率) ===")
    expert_stats = {}
    for e in EXPERT_KEYS:
        s = {}
        for W in (100, 200, 500):
            lo = max(WARM, T - W)
            n = T - lo
            h = sum(1 for i in range(lo, T) if ta[i] != kills[e][i])
            s[f"{W}"] = {"n": n, "hit": h, "pct": round(h / n * 100, 2)}
        full_n = T - WARM
        full_h = sum(1 for i in range(WARM, T) if ta[i] != kills[e][i])
        s["full"] = {"n": full_n, "hit": full_h, "pct": round(full_h / full_n * 100, 2)}
        expert_stats[e] = s
        print(f"  {EXPERT_LABELS[e]:<16} 近100={s['100']['pct']}%  近200={s['200']['pct']}%  "
              f"近500={s['500']['pct']}%  全量={s['full']['pct']}%")

    # 基线 h1s3 与 A9 一致, 加 random 理论基线 90%
    print(f"  {'随机基线(理论)':<16} 90.00% (10选1必然中约90%)")

    # ── 2. Hedge 加权投票 vs 各专家 ──
    print("\n=== 2. Hedge 加权投票 vs 各专家 ===")
    hedge_stats = {}
    for W in (100, 200, 500):
        lo = max(WARM, T - W)
        n = T - lo
        h = sum(1 for i in range(lo, T) if ta[i] != hedge_kill_at(kills, ta, i)[0])
        hedge_stats[f"{W}"] = {"n": n, "hit": h, "pct": round(h / n * 100, 2)}
    full_n = T - WARM
    full_h = sum(1 for i in range(WARM, T) if ta[i] != hedge_kill_at(kills, ta, i)[0])
    hedge_stats["full"] = {"n": full_n, "hit": full_h, "pct": round(full_h / full_n * 100, 2)}
    print(f"  Hedge加权投票   近100={hedge_stats['100']['pct']}%  近200={hedge_stats['200']['pct']}%  "
          f"近500={hedge_stats['500']['pct']}%  全量={hedge_stats['full']['pct']}%")

    # 对比最优单专家
    best_e = max(EXPERT_KEYS, key=lambda e: expert_stats[e]["full"]["pct"])
    best_pct = expert_stats[best_e]["full"]["pct"]
    hedge_pct = hedge_stats["full"]["pct"]
    print(f"  最优单专家: {EXPERT_LABELS[best_e]} 全量={best_pct}%")
    print(f"  Hedge 提升: {hedge_pct - best_pct:+.2f}pp (vs 最优单专家)")

    # ── 3. 权重有效性: 近150窗内高权重专家是否更高命中 ──
    print("\n=== 3. 权重有效性检验 (近150窗) ===")
    lo = max(WARM, T - WINDOW_W)
    for e in EXPERT_KEYS:
        h = sum(1 for j in range(lo, T) if ta[j] != kills[e][j])
        w = max(SMOOTH, h / (T - lo))
        print(f"  {EXPERT_LABELS[e]:<16} 近150窗命中={h}/{T-lo} = {w*100:.1f}%")

    # ── 4. 一致性分析: 专家投票一致 vs 分歧 ──
    print("\n=== 4. 专家一致性分析 (全量) ===")
    agree_cnt, agree_hit = 0, 0
    diff_cnt, diff_hit = 0, 0
    vote_cnt = Counter()   # 最高票数分布
    for i in range(WARM, T):
        k, ws = hedge_kill_at(kills, ta, i)
        votes = [0.0] * 10
        for e in EXPERT_KEYS:
            votes[kills[e][i]] += ws[e]
        vmax = max(votes)
        n_agree = sum(1 for v in votes if v >= vmax - 1e-9)
        vote_cnt[n_agree] += 1
        if n_agree >= 3:  # 3+ 专家一致
            agree_cnt += 1
            if ta[i] != k:
                agree_hit += 1
        else:
            diff_cnt += 1
            if ta[i] != k:
                diff_hit += 1
    print(f"  3+专家一致杀码: {agree_cnt} 期, 命中率 {agree_hit/agree_cnt*100:.2f}%" if agree_cnt else "  3+专家一致: 无")
    print(f"  专家分歧(<3一致): {diff_cnt} 期, 命中率 {diff_hit/diff_cnt*100:.2f}%" if diff_cnt else "")
    print(f"  最高票分布: {dict(sorted(vote_cnt.items()))}")

    # 汇总输出
    data = {
        "meta": {
            "total": T, "warm": WARM, "window": WINDOW_W,
            "note": "专家级回测: 每专家独立命中率 + Hedge投票优势 + 权重有效性",
        },
        "expert_stats": expert_stats,
        "hedge_stats": hedge_stats,
        "best_single": {"expert": best_e, "label": EXPERT_LABELS[best_e], "pct": best_pct},
        "hedge_vs_best": round(hedge_pct - best_pct, 2),
        "consistency": {
            "agree_3plus": {"n": agree_cnt, "hit": agree_hit, "pct": round(agree_hit / agree_cnt * 100, 2) if agree_cnt else 0},
            "diff": {"n": diff_cnt, "hit": diff_hit, "pct": round(diff_hit / diff_cnt * 100, 2) if diff_cnt else 0},
            "top_vote_dist": dict(sorted(vote_cnt.items())),
        },
    }
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 结果已保存: {JSON_OUT}")
    return data


if __name__ == "__main__":
    run()
