"""
突破口验证:
1. 共识增强 — A9与(h1+span+3)输出同一尾时, 条件命中率是否显著更高?
   → 若是, 构造"共识时杀该尾, 分歧时用近窗优者"的条件策略
2. Hedge混合稳健性 — 近100/200/500三窗口 + 不同时段分割, 检验+0.2pp是否真实
"""
import csv, math
from collections import Counter, defaultdict

rows = list(csv.DictReader(open(r'D:\福彩3D资料\fc3d-history.csv', encoding='utf-8')))
tails = [(int(r['hundreds']) + int(r['tens']) + int(r['ones'])) % 10 for r in rows]
b_arr = [int(r['hundreds']) for r in rows]
s_arr = [int(r['tens']) for r in rows]
g_arr = [int(r['ones']) for r in rows]
T = len(tails); WARM = 250

def span_at(i):
    return max(b_arr[i], s_arr[i], g_arr[i]) - min(b_arr[i], s_arr[i], g_arr[i])

def k_a9(i):  return (9 - tails[i-1]) % 10
def k_h1s3(i): return (tails[i-1] + span_at(i-1) + 3) % 10

# ============ 1. 共识增强 ============
print("="*55)
print("1. 共识增强: A9 与 (h1+span+3) 输出一致时的条件命中率")
print("="*55)
agree_hit = agree_tot = 0
dis_hit_a9 = dis_hit_h = dis_tot = 0
for i in range(WARM, T):
    a9 = k_a9(i); hs = k_h1s3(i)
    actual = tails[i]
    if a9 == hs:
        agree_tot += 1
        if actual != a9: agree_hit += 1
    else:
        dis_tot += 1
        if actual != a9: dis_hit_a9 += 1
        if actual != hs: dis_hit_h += 1

print(f"两公式一致: {agree_tot}期 ({agree_tot/(T-WARM)*100:.1f}%), 命中率 {agree_hit/agree_tot*100:.2f}%" if agree_tot else "无一致")
print(f"两公式分歧: {dis_tot}期, A9命中率 {dis_hit_a9/dis_tot*100:.2f}%, h1s3命中率 {dis_hit_h/dis_tot*100:.2f}%")
print(f"全量A9命中: {sum(1 for i in range(WARM,T) if tails[i]!=k_a9(i))/(T-WARM)*100:.2f}%")
print(f"全量h1s3命中: {sum(1 for i in range(WARM,T) if tails[i]!=k_h1s3(i))/(T-WARM)*100:.2f}%")

# 共识条件策略: 一致→杀该尾; 分歧→近200窗表现更好的那条
print("\n共识条件策略 (一致杀同尾, 分歧用近200窗优者):")
def consensus_200(i):
    a9 = k_a9(i); hs = k_h1s3(i)
    if a9 == hs: return a9
    lo = max(WARM, i-200)
    ha = sum(1 for j in range(lo, i) if tails[j] != k_a9(j))
    hh = sum(1 for j in range(lo, i) if tails[j] != k_h1s3(j))
    return a9 if ha >= hh else hs

for W in (100, 200, 500):
    lo = T - W
    h = sum(1 for i in range(lo, T) if tails[i] != consensus_200(i))
    hb = sum(1 for i in range(lo, T) if tails[i] != k_h1s3(i))
    print(f"  近{W}期: 共识策略 {h/W*100:.2f}%  vs 基线h1s3 {hb/W*100:.2f}%")

# ============ 2. Hedge混合稳健性 ============
print("\n" + "="*55)
print("2. Hedge混合稳健性 (三窗口 + 时段移位)")
print("="*55)
TR = T - 500
h1_arr = [tails[i-1] if i >= 1 else 0 for i in range(T)]
sp_arr = [span_at(i-1) if i >= 1 else 0 for i in range(T)]

# 预计算5专家杀码 (同explore_new优化版)
EXPERT_KEYS = ['A9', 'h1s3', 'freq_all', 'trans1', 'freq50']
kill_e = {e: [0]*T for e in EXPERT_KEYS}
cnt_all = Counter()
freq_all_pre = []
for i in range(T):
    if i >= WARM: cnt_all[tails[i-1]] += 1
    tot = i - WARM
    freq_all_pre.append([cnt_all.get(t,0)/tot for t in range(10)] if tot > 0 else [0.1]*10)
freq50_pre = []
for i in range(T):
    lo = max(WARM, i-50)
    cnt50 = Counter(tails[lo:i]); tot = i-lo
    freq50_pre.append([cnt50.get(t,0)/tot for t in range(10)] if tot > 0 else [0.1]*10)

def trans1_prob(i):
    lo = max(WARM, i-300)
    tab = defaultdict(lambda: [0.1]*10)
    for j in range(lo+1, i): tab[tails[j-1]][tails[j]] += 1
    p = tab[tails[i-1]]; s = sum(p)
    return [x/s for x in p]

for i in range(WARM, T):
    kill_e['A9'][i] = (9 - h1_arr[i]) % 10
    kill_e['h1s3'][i] = (h1_arr[i] + sp_arr[i] + 3) % 10
    pa = freq_all_pre[i]; kill_e['freq_all'][i] = min(range(10), key=lambda t: pa[t])
    pt = trans1_prob(i); kill_e['trans1'][i] = min(range(10), key=lambda t: pt[t])
    p5 = freq50_pre[i]; kill_e['freq50'][i] = min(range(10), key=lambda t: p5[t])

def hedge_kill(i, win=100, sm=0.05):
    lo = max(WARM, i - win)
    if i - lo >= 10:
        ws = {e: max(sm, sum(1 for j in range(lo, i) if tails[j] != kill_e[e][j])/(i-lo)) for e in EXPERT_KEYS}
    else:
        ws = {e: 0.9 for e in EXPERT_KEYS}
    votes = [0.0]*10
    for e in EXPERT_KEYS: votes[kill_e[e][i]] += ws[e]
    return max(range(10), key=lambda t: votes[t])

print(f"标准配置(win=100):")
for W in (100, 200, 500):
    lo = T - W
    hh = sum(1 for i in range(lo, T) if tails[i] != hedge_kill(i))
    hb = sum(1 for i in range(lo, T) if tails[i] != k_h1s3(i))
    print(f"  近{W}期: Hedge {hh/W*100:.2f}%  vs 基线 {hb/W*100:.2f}%  差{(hh-hb)/W*100:+.2f}pp")

# 时段移位检验: 前500期 vs 中500期 vs 最后500期
print("\n时段移位 (每段500期, Hedge vs 基线):")
for label, lo, hi in [("中段", T-1500, T-1000), ("中后", T-1000, T-500), ("尾段", T-500, T)]:
    hh = sum(1 for i in range(lo, hi) if tails[i] != hedge_kill(i))
    hb = sum(1 for i in range(lo, hi) if tails[i] != k_h1s3(i))
    print(f"  {label}[{lo},{hi}): Hedge {hh/500*100:.2f}%  vs 基线 {hb/500*100:.2f}%  差{(hh-hb)/5:+.2f}pp")

# ============ 3. 三公式共识 (A9 + h1s3 + Hedge) ============
print("\n" + "="*55)
print("3. 三路共识: A9/h1s3/Hedge 全一致才高置信, 否则Hedge兜底")
print("="*55)
def triple(i):
    a9 = k_a9(i); hs = k_h1s3(i); hd = hedge_kill(i)
    if a9 == hs == hd: return a9, 'triple'
    return hd, 'hedge'
for W in (100, 200, 500):
    lo = T - W
    h = 0; tri_tot = 0; tri_hit = 0
    for i in range(lo, T):
        k, tag = triple(i)
        if tag == 'triple': tri_tot += 1
        if tails[i] != k: h += 1
        if tag == 'triple' and tails[i] != k: tri_hit += 1
    hb = sum(1 for i in range(lo, T) if tails[i] != k_h1s3(i))
    print(f"  近{W}期: 三路策略 {h/W*100:.2f}%  vs 基线 {hb/W*100:.2f}%  (三一致{tri_tot}期, 其中命中{tri_hit}期={tri_hit/tri_tot*100:.1f}%' if tri_tot else 0)")
