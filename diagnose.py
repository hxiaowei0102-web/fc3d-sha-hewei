"""
双杀机制根因诊断
分析三个关键环节对命中率的影响:
  1. 判定窗口: kill1 三窗加权(50/100/200)是否最优 → 扫单窗/组合
  2. 锁定顺序: kill1 以「单杀命中」选 vs 以「双杀贡献」选, 谁更优
  3. 结算时机: kill2==kill1 时 +1 偏移的损失有多大; 连错聚集分布
"""
import csv
from collections import Counter
from engine import load_tails, KILL1_POOL, select_kill1
from search_kill2 import make_fn

tails=load_tails(); T=len(tails)
kill2_fn=make_fn('h1','span','add',3)
WARM=250

def hit_double(k1,k2,i):
    if k2==k1: k2=(k2+1)%10
    return tails[i]['tail']!=k1 and tails[i]['tail']!=k2

print("="*56)
print("环节1: 判定窗口 — kill1 用哪组窗口选最强?")
print("="*56)
def select_w(tails,i,windows,weights):
    best_s,best_k=-1,None
    for name,fn in KILL1_POOL:
        s=0
        for W,w in zip(windows,weights):
            lo=max(1,i-W)
            if i-lo<10: s+=w*0.9; continue
            s+=w*sum(1 for j in range(lo,i) if tails[j]['tail']!=fn(tails,j))/(i-lo)
        if s>best_s: best_s=s; best_k=fn(tails,i)
    return best_k
for wins,wts,label in [((50,),(1,),'近50'),((100,),(1,),'近100'),
                        ((200,),(1,),'近200'),((50,100,200),(0.5,0.3,0.2),'三窗加权(当前)')]:
    for W in (100,500):
        lo=max(WARM,T-W); h=0
        for i in range(lo,T):
            k1=select_w(tails,i,wins,wts)
            if hit_double(k1,kill2_fn(tails,i),i): h+=1
        print(f"  {label:14} 近{W:3}期 双杀 {h/(T-lo)*100:.2f}%")
    print()

print("="*56)
print("环节2: 锁定顺序 — kill1按单杀命中 vs 按双杀贡献选")
print("="*56)
def select_by_double(tails,i,kill2_fn,W=100):
    best_s,best_k=-1,None
    lo=max(1,i-W)
    for name,fn in KILL1_POOL:
        h=0
        for j in range(lo,i):
            k1=fn(tails,j); k2=kill2_fn(tails,j)
            if k2==k1: k2=(k2+1)%10
            if tails[j]['tail']!=k1 and tails[j]['tail']!=k2: h+=1
        s=h/(i-lo)
        if s>best_s: best_s=s; best_k=fn(tails,i)
    return best_k
for W in (100,500):
    lo=max(WARM,T-W); h1=h2=0
    for i in range(lo,T):
        if hit_double(select_kill1(tails,i)[0],kill2_fn(tails,i),i): h1+=1
        if hit_double(select_by_double(tails,i,kill2_fn),kill2_fn(tails,i),i): h2+=1
    print(f"  近{W:3}期: 单杀目标选kill1={h1/(T-lo)*100:.2f}%  双杀贡献选kill1={h2/(T-lo)*100:.2f}%")

print()
print("="*56)
print("环节3: 结算时机 — kill2==kill1 偏移损失 + 连错分布")
print("="*56)
lo=T-500; clash=0; miss=0; seq=[]
for i in range(lo,T):
    k1=select_kill1(tails,i)[0]; k2=kill2_fn(tails,i)
    raw=k2
    if k2==k1: k2=(k2+1)%10; clash+=1
    ok=tails[i]['tail']!=k1 and tails[i]['tail']!=k2
    if not ok: miss+=1
    seq.append(ok)
print(f"  近500期: kill2==kill1 发生 {clash} 次 ({clash/5:.1f}%), 偏移后仍错 {sum(1 for i in range(lo,T) if kill2_fn(tails,i)==select_kill1(tails,i)[0] and not seq[i-lo])} 次")
# 连错聚集
runs=[]; cur=0
for ok in seq:
    if not ok: cur+=1
    elif cur: runs.append(cur); cur=0
if cur: runs.append(cur)
print(f"  近500期失误 {miss} 期, 连错段数 {len(runs)}, 最长连错 {max(runs) if runs else 0}, 连错分布 {Counter(runs)}")
