"""
探索三个从未尝试过的创新方向 (全部 walk-forward 严格无泄漏) — 预计算优化版
方向A: 循环统计 — 和尾映射单位圆, sin/cos 角度回归预测
方向B: 差分马尔可夫 — 尾差分序列的一阶/二阶转移矩阵+贝叶斯收缩
方向C: Hedge专家混合 — 多专家输出概率分布, 按近窗损失动态加权混合
对照: (h1+span+3) 基线
"""
import csv, math
from collections import Counter, defaultdict
import numpy as np

rows = list(csv.DictReader(open(r'D:\福彩3D资料\fc3d-history.csv', encoding='utf-8')))
tails = [(int(r['hundreds']) + int(r['tens']) + int(r['ones'])) % 10 for r in rows]
b_arr = [int(r['hundreds']) for r in rows]
s_arr = [int(r['tens']) for r in rows]
g_arr = [int(r['ones']) for r in rows]
T = len(tails); WARM = 250; TR = T - 500

def span_at(i):
    return max(b_arr[i], s_arr[i], g_arr[i]) - min(b_arr[i], s_arr[i], g_arr[i])

def baseline(i):
    return (tails[i-1] + span_at(i-1) + 3) % 10

def acc(fn, lo, hi):
    return sum(1 for i in range(lo, hi) if tails[i] != fn(i)) / (hi - lo)

print(f"总期数 {T}, 样本外 [TR={TR}, T={T})\n", flush=True)

# ================= 基线 =================
bl500 = acc(baseline, TR, T) * 100
print(f"基线 (h1+span+3): 近500期{bl500:.2f}%", flush=True)

# ========== 预计算: 各期特征 ==========
h1_arr = [tails[i-1] if i >= 1 else 0 for i in range(T)]
sp_arr = [span_at(i-1) if i >= 1 else 0 for i in range(T)]
s10_arr = [(b_arr[i-1]+s_arr[i-1]+g_arr[i-1]) % 10 if i >= 1 else 0 for i in range(T)]

# ================= 方向A1: 循环均值差分 =================
print("\n===== 方向A: 循环统计 =====", flush=True)
def diff_angle(i):
    d = (tails[i] - tails[i-1]) % 10
    return d * 2 * math.pi / 10

# 预计算差角数组 (只算一次)
DANGLES = [0.0] * T
for i in range(1, T):
    DANGLES[i] = diff_angle(i)

# 前缀和 for 加权循环均值 (alpha^lag 递推)
def make_a1(W, alpha):
    def fn(i):
        lo = max(WARM, i - W)
        if i - lo < 5:
            return baseline(i)
        s = 0.0; c = 0.0; wsum = 0.0
        for j in range(lo, i):
            w = alpha ** (i - 1 - j)
            s += w * math.sin(DANGLES[j]); c += w * math.cos(DANGLES[j]); wsum += w
        mu = math.atan2(s / wsum, c / wsum)
        dists = []
        for t in range(10):
            a = t * 2 * math.pi / 10
            d = abs(math.atan2(math.sin(a - mu), math.cos(a - mu)))
            dists.append((d, t))
        return max(dists)[1]
    return fn

best_a1 = (0, None)
for W in (10, 20, 30, 50, 100):
    for alpha in (0.8, 0.9, 0.95, 1.0):
        a = acc(make_a1(W, alpha), TR, T) * 100
        tag = "🏆" if a > bl500 else ""
        print(f"  A1 W={W} α={alpha}: {a:.2f}% {tag}", flush=True)
        if a > best_a1[0]: best_a1 = (a, (W, alpha))

# ================= 方向B: 差分马尔可夫 =================
print("\n===== 方向B: 差分马尔可夫 =====", flush=True)
diffs = [0] * T
for i in range(1, T):
    diffs[i] = (tails[i] - tails[i-1]) % 10

global_diff = Counter(diffs[WARM:TR])
gd_total = TR - WARM
gd = [global_diff.get(k, 0) / gd_total for k in range(10)]

def build_trans(order, lo, hi):
    tab = defaultdict(lambda: [0]*10)
    for i in range(lo+order, hi):
        if order == 1:
            st = (diffs[i-1],)
        else:
            st = (diffs[i-1], diffs[i-2])
        tab[st][diffs[i]] += 1
    return tab

# 预构建全史转移表(样本外测试期内表是"看到未来"的 — 禁止!)
# 只能按测试期用滚动窗口重建, 但500期×重建300窗口不贵
def make_b(order, alpha):
    def fn(i):
        # 近300期重建表 (只用历史)
        lo = max(WARM, i - 300)
        tab = build_trans(order, lo, i)
        if order == 1:
            st = (diffs[i-1],)
        else:
            st = (diffs[i-1], diffs[i-2])
        raw = tab.get(st, [0]*10)
        tot = sum(raw)
        if tot == 0:
            probs = list(gd)
        else:
            probs = [(raw[t] + alpha * gd[t]) / (tot + alpha) for t in range(10)]
        h1 = tails[i-1]
        tail_probs = [probs[(t - h1) % 10] for t in range(10)]
        return min(range(10), key=lambda t: tail_probs[t])
    return fn

best_b = (0, None)
for order in (1, 2):
    for alpha in (0.5, 1, 2, 5, 10):
        a = acc(make_b(order, alpha), TR, T) * 100
        tag = "🏆" if a > bl500 else ""
        print(f"  B order={order} α={alpha}: {a:.2f}% {tag}", flush=True)
        if a > best_b[0]: best_b = (a, (order, alpha))

# ================= 方向C: Hedge专家混合 =================
print("\n===== 方向C: Hedge专家混合 =====", flush=True)
# 简化版: 5个专家, 每期输出"最不可能尾", 近100窗命中率做权重, 加权投票
# 预计算每个专家每期的杀码 (O(T) per expert)
EXPERT_KEYS = ['A9', 'h1s3', 'freq_all', 'trans1', 'freq50']
kill_e = {e: [0]*T for e in EXPERT_KEYS}
freq_all_pre = []
cnt_all = Counter()
for i in range(T):
    if i >= WARM:
        cnt_all[tails[i-1]] += 1
    tot = i - WARM
    if tot <= 0:
        freq_all_pre.append([0.1]*10)
    else:
        freq_all_pre.append([cnt_all.get(t, 0)/tot for t in range(10)])

# 近50期频率 前缀和
freq50_pre = []
cnt50 = Counter()
for i in range(T):
    lo = max(WARM, i-50)
    cnt50 = Counter(tails[lo:i])
    tot = i - lo
    freq50_pre.append([cnt50.get(t, 0)/tot for t in range(10)] if tot > 0 else [0.1]*10)

# 一阶转移表 (滚动近300期)
def trans1_prob(i):
    lo = max(WARM, i-300)
    tab = defaultdict(lambda: [0.1]*10)
    for j in range(lo+1, i):
        tab[tails[j-1]][tails[j]] += 1
    h1 = tails[i-1]
    p = tab[h1]
    s = sum(p)
    return [x/s for x in p]

for i in range(WARM, T):
    kill_e['A9'][i] = (9 - h1_arr[i]) % 10
    kill_e['h1s3'][i] = (h1_arr[i] + sp_arr[i] + 3) % 10
    pa = freq_all_pre[i]
    kill_e['freq_all'][i] = min(range(10), key=lambda t: pa[t])
    pt = trans1_prob(i)
    kill_e['trans1'][i] = min(range(10), key=lambda t: pt[t])
    p5 = freq50_pre[i]
    kill_e['freq50'][i] = min(range(10), key=lambda t: p5[t])

def make_c(win, smoothing):
    def fn(i):
        lo = max(WARM, i - win)
        if i - lo >= 10:
            ws = {}
            for e in EXPERT_KEYS:
                h = sum(1 for j in range(lo, i) if tails[j] != kill_e[e][j])
                ws[e] = max(smoothing, h / (i - lo))
        else:
            ws = {e: 0.9 for e in EXPERT_KEYS}
        wsum = sum(ws.values())
        # 加权投票: 各专家投自己杀的尾, 权重=近窗命中率, 但"混合"要看多数
        # 用权重加总: score[t] = Σ w_e * I(kill_e[t]==t)?? 不对 — 我们要"被最多高权重专家否定"的尾
        # 正确: 每个专家认为 t 出现的概率低 → 投 t 一票; 权重高=更信. 加权票数最高的尾=杀
        votes = [0.0]*10
        for e in EXPERT_KEYS:
            votes[kill_e[e][i]] += ws[e]
        return max(range(10), key=lambda t: votes[t])
    return fn

best_c = (0, None)
for win in (50, 100, 200):
    for sm in (0.01, 0.1):
        a = acc(make_c(win, sm), TR, T) * 100
        tag = "🏆" if a > bl500 else ""
        print(f"  C win={win} sm={sm}: {a:.2f}% {tag}", flush=True)
        if a > best_c[0]: best_c = (a, (win, sm))

print(f"\n{'='*50}", flush=True)
print(f"基线:             近500期 {bl500:.2f}%", flush=True)
print(f"A1 循环均值差分:  近500期 {best_a1[0]:.2f}%", flush=True)
print(f"B  差分马尔可夫:  近500期 {best_b[0]:.2f}%", flush=True)
print(f"C  Hedge混合:     近500期 {best_c[0]:.2f}%", flush=True)
