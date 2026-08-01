"""
四个创新算法，全部 walk-forward 严格无泄漏
1. 多尺度衰减频率 — 近/中/远三期频率指数衰减加权，杀综合最低频尾
2. 双延迟共识 — 公式(i-1) 与 公式(i-2) 同杀一个尾=高置信，冲突=保守兜底
3. 尾序列KNN — 直接在历史尾序列中找最相似的4尾后缀，看后验分布杀最低频尾
4. 缺口动量 — 每个尾统计「上次出现距今」和「近N期密度」，综合排序杀最"冷"尾
"""
import csv, math
from collections import Counter, defaultdict

rows=list(csv.DictReader(open('fc3d-history.csv',encoding='utf-8')))
tails=[(int(r['hundreds'])+int(r['tens'])+int(r['ones']))%10 for r in rows]
b_arr=[int(r['hundreds']) for r in rows]
s_arr=[int(r['tens']) for r in rows]
g_arr=[int(r['ones']) for r in rows]
T=len(tails); TR=T-500; WARM=200

def h1_span_3(i):
    span=max(b_arr[i-1],s_arr[i-1],g_arr[i-1])-min(b_arr[i-1],s_arr[i-1],g_arr[i-1])
    return (tails[i-1]+span+3)%10

baseline_hits=sum(1 for i in range(TR,T) if tails[i]!=h1_span_3(i))
print(f"基线(h1+span+3) 近500期: {baseline_hits/500*100:.1f}%\n")

# ==== 算法1: 多尺度衰减频率 ====
print("算法1: 多尺度衰减频率")
# 对每个尾, 在近20/50/200窗内加权计数, 指数衰减 α^lag
# score[t] = Σ α^lag * I(tail=t)  across 3 windows with different α
alphas={'s20':0.85,'m50':0.92,'l200':0.97}
h1=0
for i in range(TR,T):
    scores=[0.0]*10
    for label,alpha in alphas.items():
        W=int(label[1:])
        lo=max(0,i-W)
        for j in range(lo,i):
            scores[tails[j]]+=alpha**(i-j)
    best=min(range(10),key=lambda t:scores[t])
    if tails[i]!=best: h1+=1
print(f"  近500期: {h1/5:.1f}%")

# ==== 算法2: 双延迟共识 ====
print("算法2: 双延迟共识(多公式延迟投票)")
# 用4条公式各跑2个延迟, 8票取共识
formulas=[
    lambda i: (9-tails[i-1])%10,                          # A9
    lambda i: h1_span_3(i),                                 # h1+span+3
    lambda i: (tails[i-1]+(b_arr[i-1]+s_arr[i-1]+g_arr[i-1])%10)%10,  # h1+S10
    lambda i: (tails[i-2] if i>=2 else 0),                 # h2
]
h2=0
for i in range(TR,T):
    votes=Counter()
    for fn in formulas:
        votes[fn(i)]+=2           # 当期=权2
        if i>=2: votes[fn(i-1)]+=1  # 延迟1=权1
        if i>=3: votes[fn(i-2)]+=1  # 延迟2=权1
    # 取最低票2个中, 票数最少=最不被看好
    order=sorted(range(10),key=lambda t:votes.get(t,0))
    if tails[i]!=order[0]: h2+=1
print(f"  近500期: {h2/5:.1f}%")

# ==== 算法3: 尾序列KNN ====
print("算法3: 尾序列KNN(匹配最近4尾后缀)")
# 在尾序列中找后缀 (t-4,t-3,t-2,t-1) 最相似的K个历史位置
# 距离=各位置差异的加权(越近权重越大)
MATCH_LEN=4; K=20
h3=0
for i in range(TR,T):
    pattern=tails[i-MATCH_LEN:i]
    dists=[]
    for j in range(WARM,i-MATCH_LEN):
        d=sum((0.5+0.5*k/MATCH_LEN)*abs(tails[j+k]-pattern[k]) for k in range(MATCH_LEN))
        dists.append((d,j+MATCH_LEN))  # j+MATCH_LEN = next position
    dists.sort()
    cnt=Counter()
    for _,pos in dists[:min(K,len(dists))]:
        cnt[tails[pos]]+=1
    best=min(range(10),key=lambda t:cnt.get(t,0))
    if tails[i]!=best: h3+=1
print(f"  近500期: {h3/5:.1f}%")

# ==== 算法4: 缺口动量 ====
print("算法4: 缺口动量(冷尾检测)")
# score[t] = gap_since_last * (1 + short_density_weight)
# gap: 该尾上次出现距今多少期, 越大越冷
# density: 近30期内该尾密度, 越小越冷
h4=0
for i in range(TR,T):
    scores=[0.0]*10
    for t in range(10):
        gap=1
        for j in range(i-1,WARM,-1):
            if tails[j]==t: break
            gap+=1
        den=sum(1 for j in range(max(WARM,i-30),i) if tails[j]==t)/30
        scores[t]=gap*(1+(0.3-den)*5)  # 低密度放大缺口, 高密度缩小缺口
    best=max(range(10),key=lambda t:scores[t])  # 最大分=最冷=最该杀
    if tails[i]!=best: h4+=1
print(f"  近500期: {h4/5:.1f}%")

# ==== 算法5: 混合集成(取4个算法中票数最高的杀) ====
print("\n算法5: 四路集成投票")
h5=0
for i in range(TR,T):
    # 重新计算各算法当期杀码(复用上面逻辑, 这里简化)
    preds=[]
    # algo1
    sc=[0.0]*10
    for label,alpha in alphas.items():
        W=int(label[1:]); lo=max(0,i-W)
        for j in range(lo,i): sc[tails[j]]+=alpha**(i-j)
    preds.append(min(range(10),key=lambda t:sc[t]))
    # algo2 consensus
    votes2=Counter()
    for fn in formulas:
        votes2[fn(i)]+=2
        if i>=2: votes2[fn(i-1)]+=1
    preds.append(sorted(range(10),key=lambda t:votes2.get(t,0))[0])
    # algo4 gap
    gs=[0.0]*10
    for t in range(10):
        gap=1
        for j in range(i-1,WARM,-1):
            if tails[j]==t: break; gap+=1
        den=sum(1 for j in range(max(WARM,i-30),i) if tails[j]==t)/30
        gs[t]=gap*(1+(0.3-den)*5)
    preds.append(max(range(10),key=lambda t:gs[t]))
    # 投票
    v=Counter(preds)
    kill,_=v.most_common(1)[0]
    if tails[i]!=kill: h5+=1
print(f"  近500期: {h5/5:.1f}%")

print(f"\n{'='*45}")
print(f"基线(h1+span+3):      {baseline_hits/5:.1f}%")
print(f"算法1 多尺度衰减频率:  {h1/5:.1f}%")
print(f"算法2 双延迟共识:      {h2/5:.1f}%")
print(f"算法3 尾序列KNN:       {h3/5:.1f}%")
print(f"算法4 缺口动量:        {h4/5:.1f}%")
print(f"算法5 四路集成:        {h5/5:.1f}%")
