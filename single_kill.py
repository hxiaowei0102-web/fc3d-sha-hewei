"""
福彩3D 杀和尾 — 单杀优化引擎
目标: 每期预测1个不会出现的和尾, 最大化命中率
策略: 超大规模公式池(双特征+线性系数, ~20K条) + per-period自适应最优选择
"""
import csv, itertools, time
from collections import Counter
from engine import load_tails, select_kill1

data=load_tails(); tails=[d['tail'] for d in data]; n=len(data)
T=n; TR=T-500; WARM=250

# 预计算特征 (全部基于上期信息, 严禁当期泄漏)
raw=[(d['b'],d['s'],d['g'],d['tail']) for d in data]
h1_arr=[0]*n; h2_arr=[0]*n; S_arr=[0]*n; sp_arr=[0]*n
m5_arr=[0]*n
for i in range(n):
    if i>=1:
        b,s,g,_=raw[i-1]
        h1_arr[i]=raw[i-1][3]; h2_arr[i]=raw[i-2][3] if i>=2 else h1_arr[i]
        S_arr[i]=b+s+g; sp_arr[i]=max(b,s,g)-min(b,s,g)
for i in range(5,n):
    m5_arr[i]=round(sum(raw[j][3] for j in range(i-5,i))/5)%10

def ft(i,k):
    if k=='h1': return h1_arr[i]
    if k=='h2': return h2_arr[i]
    if k=='S': return S_arr[i]
    if k=='S10': return S_arr[i]%10
    if k=='span': return sp_arr[i]
    if k=='m5': return m5_arr[i]
    return 0

KEYS=['h1','h2','S','S10','span','m5']
OPS={'add':lambda a,b:a+b,'sub':lambda a,b:a-b,'mul':lambda a,b:a*b,
     'max':lambda a,b:max(a,b),'min':lambda a,b:min(a,b)}

# 建公式池: 双特征×5运算×10c + 线性系数
print("建单杀公式池…")
t0=time.time()
pool=[]
seen=set()
for f1,f2 in itertools.product(KEYS,KEYS):
    for op_name in OPS:
        for c in range(10):
            key=(tuple(sorted([f1,f2])) if op_name in('add','mul','max','min') else (f1,f2),op_name,c)
            if key in seen: continue; seen.add(key)
            op=OPS[op_name]
            pool.append(('A',f1,f2,op,op_name,c))
# 线性系数: (a*f1 + c)%10, a∈{1,3,5,7,9}
for f1 in KEYS:
    for a in(1,3,5,7,9):
        for c in range(10):
            key=(f1,a,c)
            if key in seen: continue; seen.add(key)
            pool.append(('L1',f1,a,c))
# 双线性: (a*f1+b*f2+c)%10
for f1,f2 in itertools.product(KEYS,KEYS):
    if f1>=f2: continue
    for a,b in itertools.product((1,3,5,7,9),(1,3,5,7,9)):
        for c in range(10):
            key=(f1,f2,a,b,c)
            if key in seen: continue; seen.add(key)
            pool.append(('L2',f1,f2,a,b,c))
print(f"池: {len(pool)} 条, {time.time()-t0:.1f}s")

def eval_fn(entry,i):
    t=entry[0]
    if t=='A': _,f1,f2,op,op_name,c=entry; return (op(ft(i,f1),ft(i,f2))+c)%10
    elif t=='L1': _,f1,a,c=entry; return (a*ft(i,f1)+c)%10
    else: _,f1,f2,a,b,c=entry; return (a*ft(i,f1)+b*ft(i,f2)+c)%10

# 阶段1: 训练段单杀命中率, 取top100
print("训练段评估单杀命中…")
scored=[]
for entry in pool:
    h=0
    for i in range(WARM,TR):
        if tails[i]!=eval_fn(entry,i): h+=1
    scored.append((h,entry))
scored.sort(key=lambda x:-x[0])
print(f"top5训练段: {[(round(s[0]/(TR-WARM)*100,2),s[1][:3]) for s in scored[:5]]}")
top100=[e for _,e in scored[:100]]

# 阶段2: per-period 动态选最优 (近200窗单杀命中率)
print("样本外per-period自适应(近200窗)…")
hits=0
for i in range(TR,T):
    best_h,best_entry=-1,top100[0]
    lo=max(WARM,i-200)
    if i-lo>=20:
        for entry in top100:
            h=sum(1 for j in range(lo,i) if tails[j]!=eval_fn(entry,j))
            if h>best_h: best_h=h; best_entry=entry
    if tails[i]!=eval_fn(best_entry,i): hits+=1
s1=hits/(T-TR)
print(f"阶段2 样本外: {s1*100:.2f}%")

# 阶段3: 再加一层——per-period 对前10条投票
print("阶段3: 近50窗top3投票…")
h2=0
for i in range(TR,T):
    lo1=max(WARM,i-50)
    if i-lo1<10:
        k=eval_fn(top100[0],i)
    else:
        # 近50窗选top3
        scored_win=[]
        for entry in top100[:30]:
            h=sum(1 for j in range(lo1,i) if tails[j]!=eval_fn(entry,j))
            scored_win.append((h,entry))
        scored_win.sort(key=lambda x:-x[0])
        top3=[e for _,e in scored_win[:3]]
        # 投票: 各出1杀, 取票数最多的
        votes=Counter()
        for entry in top3:
            votes[eval_fn(entry,i)]+=1
        k,vc=votes.most_common(1)[0]
        if vc==1:  # 全分散, 用第1名的
            k=eval_fn(top3[0],i)
    if tails[i]!=k: h2+=1
s2=h2/(T-TR)

# 汇总
from engine import select_kill1
from search_kill2 import make_fn
kill2_fn=make_fn('h1','span','add',3)
# 当前基线
h_k1=h_k2=0
for i in range(TR,T):
    if tails[i]!=select_kill1(data,i)[0]: h_k1+=1
    if tails[i]!=kill2_fn(data,i): h_k2+=1

print(f"\n{'='*50}")
print(f"全量最优固定杀(杀6):    90.77%")
print(f"神谕上限(完美分布):      ~90.8%")
print(f"当前kill1(自适应200窗):  {h_k1/(T-TR)*100:.1f}%  (近500期)")
print(f"当前kill2((h1+span)+3):  {h_k2/(T-TR)*100:.1f}%  (近500期)")
print(f"阶段2 top100动态选:      {s1*100:.2f}%")
print(f"阶段3 top3投票:          {s2*100:.2f}%")
