"""
暴力穷举双杀公式 — 冲98%实证 + 过拟合拆解
策略: 穷举 (kill1, kill2) 公式对, 直接最大化双杀命中率
关键: 在 [0,T-500] 上选公式, 在 [T-500,T] 上样本外验证
若样本内98% 样本外跌回81%, 即证明98%是过拟合幻觉
"""
import csv, itertools, random
from collections import Counter

def load():
    rows=list(csv.DictReader(open('fc3d-history.csv',encoding='utf-8')))
    return [(int(r['hundreds']),int(r['tens']),int(r['ones']),
             (int(r['hundreds'])+int(r['tens'])+int(r['ones']))%10) for r in rows]

data=load()
tails=[d[3] for d in data]
n=len(tails)

def feats(i):
    b,s,g,_=data[i-1]
    h1=tails[i-1]; h2=tails[i-2] if i>=2 else h1
    S=b+s+g; span=max(b,s,g)-min(b,s,g)
    return dict(h1=h1,h2=h2,S=S,S10=S%10,span=span,b=b,s=s,g=g)

# 单特征线性公式池: (coef*f + c) % 10, coef∈{1..9}, c∈{0..9}
KEYS=['h1','h2','S','S10','span','b','s','g']
pool=[]
for k in KEYS:
    for coef in range(1,10):
        for c in range(10):
            pool.append((k,coef,c))
def mkfn(k,coef,c):
    def fn(i,k=k,coef=coef,c=c):
        return (coef*feats(i)[k]+c)%10
    return fn
FUNCS=[(f"{coef}*{k}+{c}", mkfn(k,coef,c)) for k,coef,c in pool]
print(f"单公式池: {len(FUNCS)} 条")

T=n          # 总锚点
TR=n-500     # 训练/筛选截止: [warm, TR), 样本外: [TR, T)
warm=50

# 阶段1: 每条单公式在训练段 [warm,TR) 的双杀贡献 = 杀中率低
def killrate(fn, lo, hi):
    cnt=0; tot=0
    for i in range(lo,hi):
        if tails[i]==fn(i): cnt+=1
        tot+=1
    return cnt/tot  # 越低越好(杀得准=杀的尾很少真的出现)

print("阶段1: 训练段筛选低杀中率公式…")
scored=[(killrate(fn,warm,TR), name, fn) for name,fn in FUNCS]
scored.sort()
top=scored[:60]   # 取训练段杀中率最低的60条
print(f"训练段最优单公式杀中率: {top[0][0]*100:.2f}% (越低越好, 随机=10%)")

# 阶段2: C(60,2)=1770 对, 训练段双杀命中率
def dh(fn1,fn2,lo,hi):
    h=0;t=0
    for i in range(lo,hi):
        k1,k2=fn1(i),fn2(i)
        if k2==k1: k2=(k2+1)%10
        if tails[i]!=k1 and tails[i]!=k2: h+=1
        t+=1
    return h/t

print("阶段2: 穷举公式对…")
pairs=[]
for a,b in itertools.combinations(top,2):
    d=dh(a[2],b[2],warm,TR)
    pairs.append((d,a[1],b[1],a[2],b[2]))
pairs.sort(reverse=True)
print(f"\n== 训练段(warm~{TR}) top5 双杀命中 ==")
for d,n1,n2,_,_ in pairs[:5]:
    print(f"  {d*100:.2f}%  [{n1}] + [{n2}]")

# 阶段3: 样本外验证 [TR, T) —— 这才是真相
print(f"\n== 同一批公式 样本外({TR}~{T}, 近500期) ==")
base=dh(lambda i:2, lambda i:6, TR, T)
print(f"  固定(2,6)基线: {base*100:.2f}%")
for d,n1,n2,f1,f2 in pairs[:5]:
    oos=dh(f1,f2,TR,T)
    print(f"  {n1}+{n2}: 样本内{d*100:.2f}% → 样本外{oos*100:.2f}%  (Δ{(d-oos)*100:+.1f}pp)")
print(f"\n结论: 样本内>98%的公式对, 样本外若跌回~81-84%, 即证明98%是过拟合")
