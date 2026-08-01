"""
双杀命中率提升 — 三管齐下
1. 特征池扩大: 加 h3, 近5期均值尾m5, 振幅|h1-h2|, 和值大小/奇偶, 跨度平方等
2. 公式形式: 双特征四运算 (op(f1,f2)+c)%10 全组合
3. 以「双杀命中率」为唯一直接目标, 贪心选 kill1->kill2
样本外严格切分: 训练[warm,TR), 验证[TR,T)
"""
import csv, itertools
from collections import Counter

def load():
    rows=list(csv.DictReader(open('fc3d-history.csv',encoding='utf-8')))
    return [(int(r['hundreds']),int(r['tens']),int(r['ones']),
             (int(r['hundreds'])+int(r['tens'])+int(r['ones']))%10) for r in rows]

data=load(); tails=[d[3] for d in data]; n=len(tails)

def feats(i):
    b,s,g,_=data[i-1]
    h1=tails[i-1]; h2=tails[i-2] if i>=2 else h1; h3=tails[i-3] if i>=3 else h2
    S=b+s+g; span=max(b,s,g)-min(b,s,g)
    seg=tails[max(0,i-5):i]; m5=round(sum(seg)/len(seg))%10 if seg else 0
    amp=abs(h1-h2)
    return dict(h1=h1,h2=h2,h3=h3,S=S,S10=S%10,span=span,m5=m5,amp=amp,
                sum12=(h1+h2)%10, dif12=(h1-h2)%10, b=b,s=s,g=g,
                span2=span*span%10, Sodd=S%2)

KEYS=list(feats(50).keys())
OPS={'add':lambda a,b:a+b,'sub':lambda a,b:a-b,'mul':lambda a,b:a*b,
     'max':lambda a,b:max(a,b),'min':lambda a,b:min(a,b)}
SYM={'add':'+','sub':'-','mul':'*','max':'max','min':'min'}

def mkfn(f1,f2,op,c):
    o=OPS[op]
    def fn(i,f1=f1,f2=f2,o=o,c=c):
        ft=feats(i); return (o(ft[f1],ft[f2])+c)%10
    fn.desc=f"({f1}{SYM[op]}{f2})+{c}"
    return fn

# 生成池: 双特征×5运算×10常数 + 单特征(视为f1==f2退化)
pool=[]
for f1,f2 in itertools.product(KEYS,KEYS):
    for op in OPS:
        for c in range(10):
            pool.append((f1,f2,op,c))
# 去重: add/mul/max/min 对称, (f1,f2)与(f2,f1)等价
seen=set(); upool=[]
for f1,f2,op,c in pool:
    key=(tuple(sorted([f1,f2])) if op in('add','mul','max','min') else (f1,f2),op,c)
    if key in seen: continue
    seen.add(key); upool.append((f1,f2,op,c))
print(f"公式池(去重后): {len(upool)}")

T=n; TR=n-500; warm=50
# 预计算所有公式在 [warm,T) 的杀码序列
print("预计算杀码序列…")
seqs=[]
for f1,f2,op,c in upool:
    fn=mkfn(f1,f2,op,c)
    seq=[fn(i) for i in range(warm,T)]
    seqs.append((fn.desc, seq))

def dhit(s1,s2,lo,hi):
    h=0
    for i in range(lo,hi):
        k1,k2=s1[i-warm],s2[i-warm]
        if k2==k1: k2=(k2+1)%10
        if tails[i]!=k1 and tails[i]!=k2: h+=1
    return h/(hi-lo)

# 阶段1: 每条在训练段「杀中率」最低的 top80
print("阶段1: 训练段杀中率排序…")
killrate=[]
for desc,seq in seqs:
    cnt=sum(1 for i in range(warm,TR) if tails[i]==seq[i-warm])
    killrate.append((cnt/(TR-warm), desc, seq))
killrate.sort()
top=killrate[:80]
print(f"最优单公式训练杀中率: {top[0][0]*100:.2f}%")

# 阶段2: 贪心 —— 固定top1为kill1, 找最佳kill2; 再全局top对
print("阶段2: 穷举公式对(训练段)…")
best=[]
for a in range(len(top)):
    for b in range(a+1,len(top)):
        d=dhit(top[a][2],top[b][2],warm,TR)
        best.append((d,top[a][1],top[b][1],top[a][2],top[b][2]))
best.sort(reverse=True)

print(f"\n== 训练段 top5 双杀 ==")
for d,n1,n2,_,_ in best[:5]:
    print(f"  {d*100:.2f}%  {n1} + {n2}")

print(f"\n== 样本外(近500期) 真相 ==")
def dh2(s1,s2): return dhit(s1,s2,TR,T)
base=sum(1 for i in range(TR,T) if tails[i] not in(2,6))/(T-TR)
print(f"  固定(2,6)基线: {base*100:.2f}%")
for d,n1,n2,s1,s2 in best[:5]:
    oos=dh2(s1,s2)
    print(f"  {n1}+{n2}\n    样本内{d*100:.2f}% → 样本外{oos*100:.2f}%")
