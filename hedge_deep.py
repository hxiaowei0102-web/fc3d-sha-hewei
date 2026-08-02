"""
Hedge专家混合深度优化:
扩充专家集(12+独立算法) + 系统调参(权重机制/窗口/平滑)
目标: 在近100/200/500三窗口 + 时段移位检验下稳定超越 h1+span+3 基线
"""
import csv, math
from collections import Counter, defaultdict
import numpy as np

rows = list(csv.DictReader(open(r'D:\福彩3D资料\fc3d-history.csv', encoding='utf-8')))
tails = [(int(r['hundreds']) + int(r['tens']) + int(r['ones'])) % 10 for r in rows]
b_arr = [int(r['hundreds']) for r in rows]
s_arr = [int(r['tens']) for r in rows]
g_arr = [int(r['ones']) for r in rows]
T = len(tails); WARM = 250
TR = T - 500

def span_at(i):
    return max(b_arr[i], s_arr[i], g_arr[i]) - min(b_arr[i], s_arr[i], g_arr[i])

def k_h1s3(i): return (tails[i-1] + span_at(i-1) + 3) % 10
def k_a9(i):   return (9 - tails[i-1]) % 10

# ========== 预计算12个专家的每期杀码 ==========
# E1 A9, E2 h1+span+3, E3 全史低频, E4 近50频, E5 一阶转移, E6 二阶转移
# E7 近10频, E8 和值%10, E9 9-和值, E10 跨度, E11 上期和尾+k动态, E12 冷号缺口
EXPERT_NAMES = ['A9','h1s3','freq_all','freq50','trans1','trans2',
                'freq10','sum10','nsum','span','cold','diffm']
kill_e = {e: [0]*T for e in EXPERT_NAMES}

# 频率类: 全史/近50/近10
def freq_kills(window):
    out = [0]*T
    cnt = Counter()
    for i in range(T):
        if i >= WARM and window == 0:
            cnt[tails[i-1]] += 1
        elif i >= WARM:
            lo = max(WARM, i - window)
            cnt = Counter(tails[lo:i])
        tot = i - (WARM if window == 0 else max(WARM, i-window))
        if tot > 0:
            out[i] = min(range(10), key=lambda t: cnt.get(t,0))
        else:
            out[i] = k_h1s3(i)
    return out
kill_e['freq_all'] = freq_kills(0)
kill_e['freq50'] = freq_kills(50)
kill_e['freq10'] = freq_kills(10)

# 转移表类
def trans_kills(order, win=300):
    out = [0]*T
    for i in range(WARM, T):
        lo = max(WARM, i - win)
        tab = defaultdict(lambda: [0.1]*10)
        for j in range(lo+order, i):
            if order == 1: st = (tails[j-1],)
            else: st = (tails[j-1], tails[j-2])
            tab[st][tails[j]] += 1
        if order == 1: st = (tails[i-1],)
        else: st = (tails[i-1], tails[i-2]) if i >= 2 else (tails[i-1], tails[i-1])
        p = tab[st]; s = sum(p)
        if s == 0: out[i] = k_h1s3(i)
        else:
            probs = [x/s for x in p]
            out[i] = min(range(10), key=lambda t: probs[t])
    return out
kill_e['trans1'] = trans_kills(1)
kill_e['trans2'] = trans_kills(2)

# 简单公式类
for i in range(WARM, T):
    kill_e['A9'][i] = (9 - tails[i-1]) % 10
    kill_e['h1s3'][i] = (tails[i-1] + span_at(i-1) + 3) % 10
    s10 = (b_arr[i-1]+s_arr[i-1]+g_arr[i-1]) % 10
    kill_e['sum10'][i] = s10
    kill_e['nsum'][i] = (9 - s10) % 10
    sp = span_at(i-1)
    kill_e['span'][i] = sp
    # 上期和尾+动态k: 近30窗最优k∈[0,9]
    lo = max(WARM, i-30)
    best_k, best_h = 0, -1
    for kk in range(10):
        h = sum(1 for j in range(lo, i) if tails[j] != (tails[j-1]+kk)%10)
        if h > best_h: best_h, best_k = h, kk
    kill_e['diffm'][i] = (tails[i-1] + best_k) % 10
    # 冷号缺口: 距上次出现最远的尾
    scores = []
    for t in range(10):
        gap = 1
        for j in range(i-1, WARM, -1):
            if tails[j] == t: break
            gap += 1
        scores.append(gap)
    kill_e['cold'][i] = max(range(10), key=lambda t: scores[t])

print(f"12专家预计算完成", flush=True)

def baseline_acc(lo, hi):
    return sum(1 for i in range(lo, hi) if tails[i] != k_h1s3(i))/(hi-lo)

# ========== Hedge 混合 ==========
def hedge(win=100, sm=0.05, subset=None, weight_mode='rate'):
    keys = subset if subset else EXPERT_NAMES
    def fn(i):
        lo = max(WARM, i - win)
        if i - lo >= 10:
            ws = {}
            for e in keys:
                h = sum(1 for j in range(lo, i) if tails[j] != kill_e[e][j])
                ws[e] = max(sm, h/(i-lo))
        else:
            ws = {e: 0.9 for e in keys}
        votes = [0.0]*10
        for e in keys: votes[kill_e[e][i]] += ws[e]
        return max(range(10), key=lambda t: votes[t])
    return fn

# 先看每个专家单飞的表现
print("\n单个专家样本外表现 (近500期):", flush=True)
for e in EXPERT_NAMES:
    h = sum(1 for i in range(TR, T) if tails[i] != kill_e[e][i])
    tag = "🏆" if h/500*100 > 93.6 else ""
    print(f"  {e:8}: {h/500*100:.2f}% {tag}", flush=True)

# 全12专家混合
print(f"\n基线 h1s3: {baseline_acc(TR,T)*100:.2f}%", flush=True)
for win in (50, 100, 200):
    for sm in (0.01, 0.05, 0.1):
        h = sum(1 for i in range(TR, T) if tails[i] != hedge(win, sm)(i))
        print(f"  全12专家 win={win} sm={sm}: {h/500*100:.2f}%", flush=True)

# 去掉弱专家(单飞<90%的)试
print("\n只用强专家 (单飞≥91%):", flush=True)
strong = [e for e in EXPERT_NAMES if sum(1 for i in range(TR,T) if tails[i]!=kill_e[e][i])/500*100 >= 91]
print(f"  强专家集: {strong}", flush=True)
for win in (100, 200):
    h = sum(1 for i in range(TR, T) if tails[i] != hedge(win, 0.05, strong)(i))
    print(f"  强专家 win={win}: {h/500*100:.2f}%", flush=True)

# 排名权重: 不用命中率, 用近窗排名
def hedge_rank(win=100, sm=0.05, keys=None):
    keys = keys or EXPERT_NAMES
    def fn(i):
        lo = max(WARM, i - win)
        if i - lo >= 10:
            rates = {}
            for e in keys:
                rates[e] = sum(1 for j in range(lo, i) if tails[j] != kill_e[e][j])/(i-lo)
            rank = sorted(keys, key=lambda e: -rates[e])
            # 权重线性递减: 第1名=1.0, 第k名=1/(1+k)
            ws = {e: max(sm, 1.0/(1+rank.index(e))) for e in keys}
        else:
            ws = {e: 0.9 for e in keys}
        votes = [0.0]*10
        for e in keys: votes[kill_e[e][i]] += ws[e]
        return max(range(10), key=lambda t: votes[t])
    return fn

print("\n排名权重版:", flush=True)
for win in (50, 100, 200):
    h = sum(1 for i in range(TR, T) if tails[i] != hedge_rank(win)(i))
    print(f"  全专家 rank win={win}: {h/500*100:.2f}%", flush=True)
for win in (50, 100, 200):
    h = sum(1 for i in range(TR, T) if tails[i] != hedge_rank(win, 0.05, strong)(i))
    print(f"  强专家 rank win={win}: {h/500*100:.2f}%", flush=True)
