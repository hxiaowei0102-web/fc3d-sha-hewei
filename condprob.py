"""
逼近神谕上限的正路: 条件概率表直接预测下期和尾
对每个「条件状态」, 用历史统计下期和尾分布, 杀概率最低的2个
状态设计(只用 <= i-1 信息): 上期和尾h1 / (h1,h2) / (h1,和值大小) / (h1,跨度档)
拉普拉斯平滑防小样本过拟合; 多状态投票
严格样本外: 状态表在 [warm,TR) 建, 在 [TR,T) 验证
"""
import csv
from collections import defaultdict, Counter

def load():
    rows=list(csv.DictReader(open('fc3d-history.csv',encoding='utf-8')))
    return [(int(r['hundreds']),int(r['tens']),int(r['ones']),
             (int(r['hundreds'])+int(r['tens'])+int(r['ones']))%10) for r in rows]
data=load(); tails=[d[3] for d in data]; n=len(tails)

def state(i, kind):
    b,s,g,_=data[i-1]
    h1=tails[i-1]; h2=tails[i-2] if i>=2 else h1
    S=b+s+g; span=max(b,s,g)-min(b,s,g)
    if kind=='h1': return (h1,)
    if kind=='h1h2': return (h1,h2)
    if kind=='h1S': return (h1, 0 if S<=12 else (2 if S>=15 else 1))
    if kind=='h1span': return (h1, 0 if span<=3 else (2 if span>=7 else 1))
    if kind=='h1h2span': return (h1,h2,0 if span<=3 else 1)

T=n; TR=n-500; warm=50
KINDS=['h1','h1h2','h1S','h1span','h1h2span']

# 建条件概率表 (训练段)
def build_table(kind, alpha=1.0):
    tab=defaultdict(lambda:[alpha]*10)  # 拉普拉斯平滑
    for i in range(warm,TR):
        st=state(i,kind)
        tab[st][tails[i]]+=1
    return tab

def kill2_from(tab, st):
    probs=tab.get(st)
    if probs is None: return None
    tot=sum(probs)
    order=sorted(range(10), key=lambda t: probs[t]/tot)
    return order[0], order[1]  # 概率最低的2个尾

def dhit_kills(getkills, lo, hi):
    h=0
    for i in range(lo,hi):
        kk=getkills(i)
        if kk is None: continue
        if tails[i]!=kk[0] and tails[i]!=kk[1]: h+=1
    return h/(hi-lo)

print("== 单状态条件概率表 双杀命中 ==")
results={}
for kind in KINDS:
    tab=build_table(kind)
    # 样本内
    ins=dhit_kills(lambda i,k=kind,t=tab: kill2_from(t,state(i,k)), warm, TR)
    # 样本外
    oos=dhit_kills(lambda i,k=kind,t=tab: kill2_from(t,state(i,k)), TR, T)
    nstates=len(tab)
    results[kind]=(ins,oos)
    print(f"  {kind:10} 状态数{nstates:3} | 样本内{ins*100:.2f}% 样本外{oos*100:.2f}%")

# 多状态投票: 5个表各出2杀, 取被「判低概率」次数最多的2个尾
def vote_kills(i, tabs):
    cnt=Counter()
    for kind in KINDS:
        kk=kill2_from(tabs[kind], state(i,kind))
        if kk: cnt[kk[0]]+=2; cnt[kk[1]]+=1  # 最低概率权重2
    top2=[t for t,_ in cnt.most_common(2)]
    return tuple(top2) if len(top2)==2 else None

tabs={k:build_table(k) for k in KINDS}
vins=dhit_kills(vote_kills and (lambda i: vote_kills(i,tabs)), warm, TR)
voos=dhit_kills(lambda i: vote_kills(i,tabs), TR, T)
base=sum(1 for i in range(TR,T) if tails[i] not in(2,6))/(T-TR)
print(f"\n== 五状态投票 ==")
print(f"  样本内{vins*100:.2f}%  样本外{voos*100:.2f}%")
print(f"  固定(2,6)基线样本外: {base*100:.2f}%")
print(f"\n神谕上限参考: 87.5% | 当前最佳样本外即真实可达水平")
