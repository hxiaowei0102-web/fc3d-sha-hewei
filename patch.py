"""
补丁引擎: 对高危(h1,span)状态用条件最优替代, 其余保持原公式
高危定义: 训练段该状态失败率>15% 且样本≥30
替代: 该状态下历史实际和尾分布中最低频尾(≠原公式输出)
"""
import csv
from collections import Counter, defaultdict

rows=list(csv.DictReader(open('fc3d-history.csv',encoding='utf-8')))
tails=[(int(r['hundreds'])+int(r['tens'])+int(r['ones']))%10 for r in rows]
b=[int(r['hundreds']) for r in rows]; s=[int(r['tens']) for r in rows]
g=[int(r['ones']) for r in rows]
T=len(tails); TR=T-500; WARM=250

def formula(h1,sp):
    return (h1+sp+3)%10

# 训练段: 统计每个(h1,span)的公式表现
state_data=defaultdict(lambda: {'fails':0,'total':0,'actuals':Counter()})
for i in range(WARM,TR):
    h1=tails[i-1]; sp=max(b[i-1],s[i-1],g[i-1])-min(b[i-1],s[i-1],g[i-1])
    k=formula(h1,sp); actual=tails[i]
    state_data[(h1,sp)]['total']+=1
    state_data[(h1,sp)]['actuals'][actual]+=1
    if k==actual:
        state_data[(h1,sp)]['fails']+=1

# 识别高危状态 + 生成替代杀码
patches={}
for (h1,sp),d in state_data.items():
    if d['total']<30: continue
    fr=d['fails']/d['total']
    if fr<0.12: continue  # 失败率<12%不做补丁
    # 替代: 排除原公式杀码, 选历史最低频尾
    orig=formula(h1,sp)
    alt=sorted(range(10),key=lambda t: d['actuals'][t] if t!=orig else 999)[0]
    patches[(h1,sp)]=alt

print(f"补丁状态数: {len(patches)}")
for (h1,sp),alt in sorted(patches.items()):
    d=state_data[(h1,sp)]
    orig=formula(h1,sp)
    print(f"  h1={h1} span={sp}: 原杀{orig}失败{d['fails']/d['total']*100:.0f}%({d['fails']}/{d['total']}) → 改杀{alt}")

# 样本外评估
base_hit=0; patch_hit=0; patch_use=0
for i in range(TR,T):
    h1=tails[i-1]; sp=max(b[i-1],s[i-1],g[i-1])-min(b[i-1],s[i-1],g[i-1])
    # 原公式
    k_orig=formula(h1,sp)
    if tails[i]!=k_orig: base_hit+=1
    # 补丁公式
    if (h1,sp) in patches:
        patch_use+=1
        k_patch=patches[(h1,sp)]
    else:
        k_patch=k_orig
    if tails[i]!=k_patch: patch_hit+=1

n_test=T-TR
print(f"\n样本外(近500期):")
print(f"  原公式命中: {base_hit/n_test*100:.1f}%")
print(f"  补丁命中:   {patch_hit/n_test*100:.1f}%")
print(f"  触发补丁:   {patch_use}次/{n_test}期")
if patch_use>0:
    # 补丁期内表现
    p_base=p_alt=0
    for i in range(TR,T):
        h1=tails[i-1]; sp=max(b[i-1],s[i-1],g[i-1])-min(b[i-1],s[i-1],g[i-1])
        if (h1,sp) not in patches: continue
        if tails[i]!=formula(h1,sp): p_base+=1
        if tails[i]!=patches[(h1,sp)]: p_alt+=1
    print(f"  补丁期内: 原公式{p_base/patch_use*100:.1f}% → 替代{p_alt/patch_use*100:.1f}%")

# 扩展: 尝试不同阈值
print(f"\n阈值扫描:")
for th in (0.10,0.11,0.12,0.13,0.14,0.15):
    patches2={}
    for (h1,sp),d in state_data.items():
        if d['total']<30: continue
        if d['fails']/d['total']<th: continue
        orig=formula(h1,sp)
        alt=sorted(range(10),key=lambda t: d['actuals'][t] if t!=orig else 999)[0]
        if alt!=orig: patches2[(h1,sp)]=alt
    h2=0
    for i in range(TR,T):
        h1=tails[i-1]; sp=max(b[i-1],s[i-1],g[i-1])-min(b[i-1],s[i-1],g[i-1])
        k=patches2.get((h1,sp),formula(h1,sp))
        if tails[i]!=k: h2+=1
    on=sum(1 for i in range(TR,T) if (tails[i-1],max(b[i-1],s[i-1],g[i-1])-min(b[i-1],s[i-1],g[i-1])) in patches2)
    print(f"  th={th:.0%}: 补丁{len(patches2)}状态 触发{on}次 → {h2/n_test*100:.1f}%")
