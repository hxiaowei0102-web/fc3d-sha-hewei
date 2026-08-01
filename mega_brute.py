"""
三板斧冲双杀 — numpy 向量化极速版
斧1: 动态k2池(per-period选最优双杀伙伴)
斧2: KNN特征匹配 
斧3: 集成投票
全部严格样本外 T=8710, 训练[250,8210), 测试[8210,8710)
"""
import csv, itertools, time
import numpy as np
from collections import Counter
from engine import load_tails, select_kill1

# ── 数据准备 ──
engine_tails=load_tails()
rows=list(csv.DictReader(open('fc3d-history.csv',encoding='utf-8')))
B=np.array([int(r['hundreds']) for r in rows],dtype=np.int32)
S=np.array([int(r['tens']) for r in rows],dtype=np.int32)
G=np.array([int(r['ones']) for r in rows],dtype=np.int32)
tail=(B+S+G)%10
n=len(tail); T=n; TR=T-500; WARM=250

# 预计算特征矩阵 (n×15) —— 全部基于上期(i-1)信息, 严禁当期泄漏
h1=np.roll(tail,1); h1[0]=0
h2=np.roll(tail,2); h2[:2]=h1[:2]
h3=np.roll(tail,3); h3[:3]=h2[:3]
# 关键: 所有B/S/G/span/total 必须用上期 = shift(1)
total_lag=np.roll(B+S+G,1); total_lag[0]=0
span_lag=np.roll(np.maximum(np.maximum(B,S),G)-np.minimum(np.minimum(B,S),G),1); span_lag[0]=0
B_lag=np.roll(B,1); B_lag[0]=0
S_lag=np.roll(S,1); S_lag[0]=0
G_lag=np.roll(G,1); G_lag[0]=0
m5=np.zeros(n,dtype=np.int32)
for i in range(5,n): m5[i]=round(np.mean(tail[i-5:i]))%10
amp=np.abs(h1-h2)
par=total_lag%2
sz=np.select([total_lag<=11,total_lag>=16],[0,2],default=1)
sb=np.select([span_lag<=2,span_lag>=6],[0,2],default=1)

FEAT={'h1':h1,'h2':h2,'h3':h3,'S':total_lag,'S10':total_lag%10,'span':span_lag,
      'm5':m5,'amp':amp,'sum12':(h1+h2)%10,'dif12':(h1-h2)%10,
      'b':B_lag,'s':S_lag,'g':G_lag,'parity':par,'sz':sz,'sb':sb}
FKEYS=list(FEAT.keys())

# ── 斧1: 公式池向量化 ──
print("斧1: 建超大规模公式池(向量化)…")
t0=time.time()

# 快速筛选: 只用训练段单杀命中率筛 top500 公式, 再样本外 per-period 动态选
def build_kills(f1,f2,op,c):
    a=FEAT[f1]; b=FEAT[f2]
    if op=='add': raw=a+b
    elif op=='sub': raw=a-b
    elif op=='mul': raw=a*b
    elif op=='max': raw=np.maximum(a,b)
    elif op=='min': raw=np.minimum(a,b)
    else: raw=np.abs(a-b)
    return (raw+c)%10

OPS={'add':'+','sub':'-','mul':'*','max':'max','min':'min'}
# 只评估 双特征×5op×10c ≈ 7K条(去重后), 用numpy向量化快速算训练段独立命中
seen=set()
pool_data=[]  # (kills_array, desc)
for f1,f2 in itertools.product(FKEYS,FKEYS):
    for op in OPS:
        for c in range(10):
            key=(tuple(sorted([f1,f2])) if op in('add','mul','max','min') else (f1,f2),op,c)
            if key in seen: continue; seen.add(key)
            kills=build_kills(f1,f2,op,c)
            ind_hit=np.mean((kills[WARM:TR]!=tail[WARM:TR]).astype(float))
            if ind_hit>=0.895:
                pool_data.append((kills, f"({f1}{OPS[op]}{f2})+{c}", ind_hit))
print(f"粗筛后: {len(pool_data)} 条 (独立命中≥89.5%), 建池{time.time()-t0:.1f}s")

# 训练段评估双杀贡献(配自适应kill1), 取top80
print("训练段双杀贡献排序(配自适应kill1)…")
t1=time.time()
# 先预跑kill1序列
k1_seq=np.zeros(n-WARM,dtype=np.int32)
for i in range(WARM,n):
    k1_seq[i-WARM]=select_kill1(engine_tails,i)[0]
kill1_train=k1_seq[:TR-WARM]

scored_dh=[]
for kills,desc,inh in pool_data:
    k2_seq=kills[WARM:TR]
    # 偏移
    clash=k2_seq==kill1_train
    k2_seq[clash]=(k2_seq[clash]+1)%10
    dh=np.mean((kill1_train!=tail[WARM:TR])&(k2_seq!=tail[WARM:TR]))
    scored_dh.append((dh,desc,kills,inh))
scored_dh.sort(key=lambda x:-x[0])
print(f"top5训练段双杀: {[(round(d*100,2),n) for d,n,_,_ in scored_dh[:5]]}")

top_pool=[(kills,desc) for _,desc,kills,_ in scored_dh[:80]]
print(f"top80池 建池+评估+排序: {time.time()-t1:.1f}s")

# 样本外 per-period 动态选最优 k2
print("样本外 per-period 动态选k2…")
k1_oos=k1_seq[TR-WARM:TR-WARM+(T-TR)]
h1t=0
for idx in range(T-TR):
    i=TR+idx; k1=k1_oos[idx]
    best_j,best_k=-1,None
    lo=max(0,i-WARM-200)  # 近200窗在k1_seq中的位置
    for kills,desc in top_pool:
        k2_win=kills[max(WARM,i-200):i]
        k1_win=k1_seq[lo:idx+(TR-WARM)]
        clash=(k2_win==k1_win)
        k2_win=np.where(clash,(k2_win+1)%10,k2_win)
        jh=np.mean((k1_win!=tail[max(WARM,i-200):i])&(k2_win!=tail[max(WARM,i-200):i]))
        if jh>best_j: best_j=jh; best_k=kills[i]
    if best_k is None: best_k=top_pool[0][0][i]
    if best_k==k1: best_k=(best_k+1)%10
    if tail[i]!=k1 and tail[i]!=best_k: h1t+=1
axe1=h1t/(T-TR)
print(f"斧1 样本外: {axe1*100:.2f}%")

# ── 斧2: KNN 向量化 ──
print("\n斧2: KNN特征匹配(向量化)…")
FN=np.column_stack([h1/10,h2/10,h3/10,total_lag/27,(total_lag%10)/10,
                     span_lag/10,m5/10,amp/10,par,sz/2,sb/2])
F_mean=FN[WARM:TR].mean(axis=0); F_std=FN[WARM:TR].std(axis=0)+1e-8
FN_norm=(FN-F_mean)/F_std

# 训练段选K
bestK,bestH=20,0
for K in(15,20,25,30,40,50,65,80,100):
    h=0
    for i in range(WARM+50,TR):
        v=FN_norm[i]
        dists=np.sum((FN_norm[WARM:i]-v)**2,axis=1)
        if len(dists)>0:
            top_idx=np.argsort(dists)[:min(K,len(dists))]
            cnt=np.bincount(tail[WARM:][top_idx],minlength=10)
            order=np.argsort(cnt)[:2]
            if tail[i]!=order[0] and tail[i]!=order[1]: h+=1
    print(f"K={K}: {h/(TR-WARM-50)*100:.2f}%")
    if h>bestH: bestH=h; bestK=K
print(f"最优K={bestK}")

h2t=0; knn_preds=[]
for i in range(TR,T):
    v=FN_norm[i]
    dists=np.sum((FN_norm[WARM:i]-v)**2,axis=1)
    top_idx=np.argsort(dists)[:min(bestK,len(dists))]
    cnt=np.bincount(tail[WARM:][top_idx],minlength=10)
    order=np.argsort(cnt)
    knn_preds.append((order[0],order[1]))
    if tail[i]!=order[0] and tail[i]!=order[1]: h2t+=1
axe2=h2t/(T-TR)
print(f"斧2 样本外: {axe2*100:.2f}%")

# ── 斧3: 集成 ──
print("\n斧3: 两路集成投票…")
h3t=0
for idx in range(T-TR):
    i=TR+idx; k1=k1_oos[idx]
    # 斧1预测
    best_j,best_k2=-1,None
    lo=max(0,i-WARM-200)
    for kills,desc in top_pool:
        k2_win=kills[max(WARM,i-200):i]
        k1_win=k1_seq[lo:idx+(TR-WARM)]
        clash=(k2_win==k1_win)
        k2_win=np.where(clash,(k2_win+1)%10,k2_win)
        jh=np.mean((k1_win!=tail[max(WARM,i-200):i])&(k2_win!=tail[max(WARM,i-200):i]))
        if jh>best_j: best_j=jh; best_k2=kills[i]
    if best_k2 is None: best_k2=top_pool[0][0][i]
    if best_k2==k1: best_k2=(best_k2+1)%10
    # 斧2预测
    ko1,ko2=knn_preds[idx]
    # 加权投票: 斧1权3,斧2权2
    votes=Counter(); votes[k1]+=3; votes[best_k2]+=2; votes[ko1]+=3; votes[ko2]+=2
    top2=[t for t,_ in votes.most_common(2)]
    if tail[i]!=top2[0] and tail[i]!=top2[1]: h3t+=1
axe3=h3t/(T-TR)

# ── 汇总 ──
base=np.mean([1 if tail[i] not in(2,6) else 0 for i in range(TR,T)])
print(f"\n{'='*45}")
print(f"固定(2,6)基线:      {base*100:.2f}%")
print(f"当前引擎(单200窗):   84.4% (近500)")
print(f"斧1 动态k2池:       {axe1*100:.2f}%")
print(f"斧2 KNN(K={bestK}):        {axe2*100:.2f}%")
print(f"斧3 集成投票:        {axe3*100:.2f}%")
best=max(axe1,axe2,axe3)
print(f"\n🏆 冠军: {best*100:.2f}% | 神谕上限: 87.51% | 差距: {87.51-best*100:.2f}pp")
print(f"总耗时: {time.time()-t0:.1f}s")
