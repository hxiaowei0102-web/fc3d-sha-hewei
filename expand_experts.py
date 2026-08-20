"""
福彩3D 杀和尾 — 专家扩展实验 (v2.2)
====================================
回答: Hedge 加权投票继续增加专家, 命中率还能提升吗?

实验设计:
1. 基础 5 专家 (A9/h1s3/freq_all/freq50/trans1) — 当前生产配置
2. 构造 7 个新专家候选 (不同窗口频率/公式变体/二阶转移)
3. 从 5 专家开始, 按"全量命中率最优"贪心逐个加入
4. 观察: 近100/500/全量命中率随专家数变化曲线

严格 walk-forward: 只用 <=i-1 数据
"""
import csv
from collections import Counter, defaultdict

BASE = "D:/杀和尾"
CSV_PATH = BASE + "/fc3d-history.csv"
WARM = 250
WINDOW_W = 150
SMOOTH = 0.02

# 基础专家
BASE_EXPERTS = ['A9', 'h1s3', 'freq_all', 'freq50', 'trans1']
# 新专家候选
NEW_EXPERTS = [
    ('freq30',  '近30期低频'),
    ('freq100', '近100期低频'),
    ('freq200', '近200期低频'),
    ('freq500', '近500期低频'),
    ('h1s1',    '公式(h1+span+1)'),
    ('h1s6',    '公式(h1+span+6)'),
    ('trans2',  '二阶转移表'),
]

EXPERT_LABELS = {
    'A9': 'A9(9-上期尾)', 'h1s3': '公式(h1+span+3)',
    'freq_all': '全史低频', 'freq50': '近50低频', 'trans1': '一阶转移表',
    'freq30': '近30期低频', 'freq100': '近100期低频', 'freq200': '近200期低频',
    'freq500': '近500期低频', 'h1s1': '公式(h1+span+1)', 'h1s6': '公式(h1+span+6)',
    'trans2': '二阶转移表',
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
    """计算所有专家 (5基础 + 7新) 的杀码"""
    T = len(tails)
    ta = [t["tail"] for t in tails]
    all_keys = BASE_EXPERTS + [e for e, _ in NEW_EXPERTS]
    kills = {e: [0] * (T + 1) for e in all_keys}

    def h1s3(i):
        r = tails[i - 1]
        sp = max(r["b"], r["s"], r["g"]) - min(r["b"], r["s"], r["g"])
        return (r["tail"] + sp + 3) % 10

    def h1sK(i, k):
        r = tails[i - 1]
        sp = max(r["b"], r["s"], r["g"]) - min(r["b"], r["s"], r["g"])
        return (r["tail"] + sp + k) % 10

    for i in range(WARM, T + 1):
        kills['A9'][i] = (9 - tails[i - 1]["tail"]) % 10
        kills['h1s3'][i] = h1s3(i)
        kills['h1s1'][i] = h1sK(i, 1)
        kills['h1s6'][i] = h1sK(i, 6)

    # 频率类 (不同窗口)
    for e, win in [('freq_all', 0), ('freq50', 50), ('freq30', 30),
                   ('freq100', 100), ('freq200', 200), ('freq500', 500)]:
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

    # 转移表 (一阶/二阶)
    for e, order in [('trans1', 1), ('trans2', 2)]:
        for i in range(WARM, T + 1):
            lo = max(WARM, i - 300)
            tab = defaultdict(lambda: [0.1] * 10)
            for j in range(lo + order, i):
                key = tuple(ta[j - k] for k in range(order, 0, -1))
                tab[key][ta[j]] += 1
            if order == 1:
                key = (tails[i - 1]["tail"],)
            else:
                key = (tails[i - 2]["tail"], tails[i - 1]["tail"])
            p = tab[key]
            kills[e][i] = min(range(10), key=lambda t: p[t]) if sum(p) > 0 else h1s3(i)

    return kills, ta


def hedge_kill_at(kills, ta, i, experts):
    """第 i 期 Hedge 加权投票 (专家子集)"""
    lo = max(WARM, i - WINDOW_W)
    if i - lo >= 10:
        ws = {}
        for e in experts:
            h = sum(1 for j in range(lo, i) if ta[j] != kills[e][j])
            ws[e] = max(SMOOTH, h / (i - lo))
    else:
        ws = {e: 0.9 for e in experts}
    votes = [0.0] * 10
    for e in experts:
        votes[kills[e][i]] += ws[e]
    return max(range(10), key=lambda t: votes[t])


def hit_rate(kills, ta, experts, W):
    """专家子集在近 W 期的命中率"""
    T = len(ta)
    lo = max(WARM, T - W)
    n = T - lo
    h = sum(1 for i in range(lo, T) if ta[i] != hedge_kill_at(kills, ta, i, experts))
    return round(h / n * 100, 2), h, n


def run():
    tails = load_tails()
    T = len(tails)
    print(f"总期数: {T}, 回测范围: {WARM}~{T} ({T-WARM} 期)")
    print("=" * 70)

    kills, ta = precompute_kills(tails)

    # 1. 单专家独立命中率 (全量)
    print("\n=== 1. 各专家独立命中率 (全量, 含新候选) ===")
    full_n = T - WARM
    indep = {}
    for e in BASE_EXPERTS + [x for x, _ in NEW_EXPERTS]:
        fh = sum(1 for i in range(WARM, T) if ta[i] != kills[e][i])
        indep[e] = round(fh / full_n * 100, 2)
        tag = "" if e in BASE_EXPERTS else " [新]"
        print(f"  {EXPERT_LABELS[e]:<16} {indep[e]:>6.2f}%{tag}")

    # 2. 贪心扩展实验
    print("\n=== 2. 专家数扩展实验 (贪心: 每次加入全量命中率最优的新专家) ===")
    print(f"{'专家集合':<60} {'近100':>7} {'近500':>7} {'全量':>7}")
    current = list(BASE_EXPERTS)
    remaining = [e for e, _ in NEW_EXPERTS]
    # 记录基线
    p100, _, _ = hit_rate(kills, ta, current, 100)
    p500, _, _ = hit_rate(kills, ta, current, 500)
    pfull, _, _ = hit_rate(kills, ta, current, full_n)
    print(f"  {'+'.join(current):<60} {p100:>6}% {p500:>6}% {pfull:>6}%")
    print(f"  {'[当前生产配置]':<60}")

    while remaining:
        # 试每个剩余专家, 选全量命中率最优的
        best_e, best_rate, best_p = None, -1, None
        for e in remaining:
            trial = current + [e]
            pr, _, _ = hit_rate(kills, ta, trial, full_n)
            if pr > best_rate:
                best_rate, best_e, best_p = pr, e, trial
        if best_e is None:
            break
        current = best_p
        remaining.remove(best_e)
        p100, _, _ = hit_rate(kills, ta, current, 100)
        p500, _, _ = hit_rate(kills, ta, current, 500)
        pfull, _, _ = hit_rate(kills, ta, current, full_n)
        mark = " ← 加入" if best_rate > pfull else ""
        print(f"  +{EXPERT_LABELS[best_e]:<14} {p100:>6}% {p500:>6}% {pfull:>6}%{mark}")
        if best_rate <= pfull:
            print(f"  ⚠️ 加入 {best_e} 后全量不升反降, 继续实验(观察曲线)")

    # 3. 相关性分析
    print("\n=== 3. 专家间一致性 (新专家 vs 现有专家) ===")
    for e in [x for x, _ in NEW_EXPERTS]:
        agree = sum(1 for i in range(WARM, T) if kills[e][i] == kills['h1s3'][i])
        agree2 = sum(1 for i in range(WARM, T) if kills[e][i] == kills['freq50'][i])
        print(f"  {EXPERT_LABELS[e]:<16} 与h1s3一致率 {agree/full_n*100:>5.1f}% | 与freq50一致率 {agree2/full_n*100:>5.1f}%")

    # 4. 结论
    print("\n=== 4. 结论 ===")
    print("  看近100/近500/全量三个窗口随专家数变化:")
    print("  - 若全量基本持平(±0.3pp内) → 增加专家无实质提升 (投票被稀释)")
    print("  - 若某窗口明显下降 → 新增专家有副作用")
    print("  - 只有三个窗口全部稳定提升才是真提升")


if __name__ == "__main__":
    run()
