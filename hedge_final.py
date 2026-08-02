"""
最终调优: 5专家Hedge混合精细配置搜索
对比: 全部子集组合 / 投票机制(加权全投 vs top3投) / 权重截断
并在三窗口+时段移位下做最终确认
"""
import csv, math
from collections import Counter, defaultdict
import itertools

rows = list(csv.DictReader(open(r'D:\福彩3D资料\fc3d-history.csv', encoding='utf-8')))
tails = [(int(r['hundreds']) + int(r['tens']) + int(r['ones'])) % 10 for r in rows]
b_arr = [int(r['hundreds']) for r in rows]
s_arr = [int(r['tens']) for r in rows]
g_arr = [int(r['ones']) for r in rows]
T = len(tails); WARM = 250; TR = T - 500

def span_at(i):
    return max(b_arr[i], s_arr[i], g_arr[i]) - min(b_arr[i], s_arr[i], g_arr[i])
def k_h1s3(i): return (tails[i-1] + span_at(i-1) + 3) % 10

# 6个候选专家 (全部只用历史)
EXPERT_NAMES = ['A9','h1s3','freq_all','freq50','trans1','nsum']
kill_e = {e: [0]*T for e in EXPERT_NAMES}

# freq_all / freq50
for e, win in (('freq_all', 0), ('freq50', 50)):
    cnt = Counter()
    for i in range(T):
        if i >= WARM:
            if win == 0:
                cnt[tails[i-1]] += 1
                tot = i - WARM
            else:
                lo = max(WARM, i-win)
                cnt = Counter(tails[lo:i])
                tot = i - lo
            if tot > 0:
                kill_e[e][i] = min(range(10), key=lambda t: cnt.get(t,0))
            else:
                kill_e[e][i] = k_h1s3(i)

# trans1
for i in range(WARM, T):
    lo = max(WARM, i-300)
    tab = defaultdict(lambda: [0.1]*10)
    for j in range(lo+1, i): tab[tails[j-1]][tails[j]] += 1
    p = tab[tails[i-1]]; s = sum(p)
    kill_e['trans1'][i] = min(range(10), key=lambda t: p[t]) if s > 0 else k_h1s3(i)

for i in range(WARM, T):
    kill_e['A9'][i] = (9 - tails[i-1]) % 10
    kill_e['h1s3'][i] = (tails[i-1] + span_at(i-1) + 3) % 10
    kill_e['nsum'][i] = (9 - (b_arr[i-1]+s_arr[i-1]+g_arr[i-1])%10) % 10

# 基础Hedge
def hedge(win, sm, keys):
    def fn(i):
        lo = max(WARM, i - win)
        if i - lo >= 10:
            ws = {e: max(sm, sum(1 for j in range(lo,i) if tails[j]!=kill_e[e][j])/(i-lo)) for e in keys}
        else:
            ws = {e: 0.9 for e in keys}
        votes = [0.0]*10
        for e in keys: votes[kill_e[e][i]] += ws[e]
        return max(range(10), key=lambda t: votes[t])
    return fn

def topk_hedge(win, sm, keys, k=3):
    def fn(i):
        lo = max(WARM, i - win)
        if i - lo >= 10:
            rates = {e: sum(1 for j in range(lo,i) if tails[j]!=kill_e[e][j])/(i-lo) for e in keys}
            top = sorted(keys, key=lambda e: -rates[e])[:k]
            ws = {e: max(sm, rates[e]) for e in top}
        else:
            top = keys[:k]
            ws = {e: 0.9 for e in top}
        votes = [0.0]*10
        for e in top: votes[kill_e[e][i]] += ws[e]
        return max(range(10), key=lambda t: votes[t])
    return fn

def acc(lo, hi, fn):
    return sum(1 for i in range(lo, hi) if tails[i] != fn(i))/(hi-lo)

results = []
# 子集搜索: 必须含h1s3和A9(最强两专家), 从其余4个中任选
base = ['A9','h1s3']
others = [e for e in EXPERT_NAMES if e not in base]
for r in range(0, len(others)+1):
    for combo in itertools.combinations(others, r):
        keys = base + list(combo)
        for win in (50, 100, 150, 200):
            for sm in (0.02, 0.05, 0.1):
                h = acc(TR, T, hedge(win, sm, keys))
                results.append((h*100, keys, win, sm, 'all'))
for k in (2, 3, 4):
    for win in (100, 200):
        h = acc(TR, T, topk_hedge(win, 0.05, EXPERT_NAMES, k))
        results.append((h*100, EXPERT_NAMES, win, 0.05, f'top{k}'))

results.sort(key=lambda x: -x[0])
print("TOP10 配置 (近500期):", flush=True)
for pct, keys, win, sm, mode in results[:10]:
    print(f"  {pct:.2f}%  {mode} keys={keys} win={win} sm={sm}", flush=True)

# 取最优配置做三窗口+时段移位最终确认
best = results[0]
print(f"\n最优配置: {best}", flush=True)
keys, win, sm, mode = best[1], best[2], best[3], best[4]
fn = topk_hedge(win, sm, keys, int(mode[3:])) if mode.startswith('top') else hedge(win, sm, keys)

print("\n最终确认:", flush=True)
for W in (100, 200, 500):
    lo = T - W
    h = acc(lo, T, fn)
    hb = acc(lo, T, lambda i: k_h1s3(i))
    print(f"  近{W}期: 新策略 {h*100:.2f}%  vs 基线 {hb*100:.2f}%  差{(h-hb)*100:+.2f}pp", flush=True)
print("  时段移位:", flush=True)
for label, lo, hi in [("中段", T-1500, T-1000), ("中后", T-1000, T-500), ("尾段", T-500, T)]:
    h = acc(lo, hi, fn)
    hb = acc(lo, hi, lambda i: k_h1s3(i))
    print(f"    {label}[{lo},{hi}): 新策略 {h*100:.2f}%  vs 基线 {hb*100:.2f}%  差{(h-hb)*100:+.2f}pp", flush=True)
