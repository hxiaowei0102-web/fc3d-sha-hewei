"""
解剖 (h1+span+3) 的每一次失败 —— 找规律、建补丁
分析维度:
1. 按(h1,span)状态分 — 哪些状态失败率高？
2. 按预测杀码分 — 公式输出哪个数字时容易翻车？
3. 按上期号码结构分 — 豹子/对子/全奇/全偶？
4. 按时间分 — 近期突然恶化的时段？
5. 失败时实际和尾的分布 — 有没有特定尾频繁打破公式？
目标: 找出高风险条件, 在这些条件下切换到备用公式
"""
import csv
from collections import Counter, defaultdict

rows=list(csv.DictReader(open('fc3d-history.csv',encoding='utf-8')))
tails=[(int(r['hundreds'])+int(r['tens'])+int(r['ones']))%10 for r in rows]
b_arr=[int(r['hundreds']) for r in rows]
s_arr=[int(r['tens']) for r in rows]
g_arr=[int(r['ones']) for r in rows]
issues=[r['issue'] for r in rows]
T=len(tails); WARM=250

def pred(i):
    h1=tails[i-1]; sp=max(b_arr[i-1],s_arr[i-1],g_arr[i-1])-min(b_arr[i-1],s_arr[i-1],g_arr[i-1])
    return (h1+sp+3)%10

# 收集所有失败期的详细信息
fails=[]; wins=[]
for i in range(WARM,T):
    k=pred(i); actual=tails[i]
    h1=tails[i-1]; sp=max(b_arr[i-1],s_arr[i-1],g_arr[i-1])-min(b_arr[i-1],s_arr[i-1],g_arr[i-1])
    info={'i':i,'issue':issues[i],'h1':h1,'span':sp,'kill':k,'actual':actual,
          'b':b_arr[i-1],'s':s_arr[i-1],'g':g_arr[i-1],
          'sum':b_arr[i-1]+s_arr[i-1]+g_arr[i-1],
          'pair':b_arr[i-1]==s_arr[i-1] or b_arr[i-1]==g_arr[i-1] or s_arr[i-1]==g_arr[i-1],
          'triple':b_arr[i-1]==s_arr[i-1]==g_arr[i-1],
          'all_odd':b_arr[i-1]%2==1 and s_arr[i-1]%2==1 and g_arr[i-1]%2==1,
          'all_even':b_arr[i-1]%2==0 and s_arr[i-1]%2==0 and g_arr[i-1]%2==0,
          'ok':k!=actual}
    if k==actual: fails.append(info)
    else: wins.append(info)

total=T-WARM; pf=len(fails)/total*100
print(f"全量{WARM}~{T}: 失败{len(fails)}期/{total}期 ({100-pf:.1f}%命中)")
print()

# ==== 维度1: 按(h1,span)状态分 ====
print("="*55)
print("维度1: (h1, span)状态失败率 TOP10")
state_fail=defaultdict(lambda:[0,0])
for f in fails: state=state_fail[(f['h1'],f['span'])]; state[0]+=1
for w in wins: state=state_fail[(w['h1'],w['span'])]; state[1]+=1
ranked=[]
for (h1,sp),(f,w) in state_fail.items():
    tot=f+w
    if tot>=5: ranked.append((f/tot*100,f,w,h1,sp))
ranked.sort(reverse=True)
for pct,f,w,h1,sp in ranked[:10]:
    print(f"  h1={h1} span={sp}: 失败{pct:.0f}% ({f}/{f+w}), 预测杀={pred(WARM+1)}")

# ==== 维度2: 按预测杀码分 ====
print("\n维度2: 公式输出值分布")
kill_cnt=Counter(); kill_fail=Counter()
for f in fails: kill_cnt[f['kill']]+=1; kill_fail[f['kill']]+=1
for w in wins: kill_cnt[w['kill']]+=1
for k in range(10):
    tot=kill_cnt[k]; bad=kill_fail[k]
    if tot>0: print(f"  杀{k}: 输出{tot}次 失败{bad}次={bad/tot*100:.1f}%")

# ==== 维度3: 上期号码结构 ====
print("\n维度3: 上期号码结构")
for label,attr in [('豹子','triple'),('对子','pair'),('全奇','all_odd'),('全偶','all_even')]:
    f_cnt=sum(1 for x in fails if x[attr])
    w_cnt=sum(1 for x in wins if x[attr])
    tot=f_cnt+w_cnt
    if tot>0: print(f"  {label}: {tot}期 失败{f_cnt}次={f_cnt/tot*100:.1f}%")
    else: print(f"  {label}: 0期")

# ==== 维度4: 跨度和值组合 ====
print("\n维度4: 和值范围")
for label,lo,hi in [('小≤11',0,11),('中12-16',12,16),('大≥17',17,30)]:
    f_cnt=sum(1 for x in fails if lo<=x['sum']<=hi)
    w_cnt=sum(1 for x in wins if lo<=x['sum']<=hi)
    tot=f_cnt+w_cnt
    print(f"  {label}: {tot}期 失败{f_cnt}次={f_cnt/tot*100:.1f}%")

print(f"\n维度4b: 跨度范围")
for label,lo,hi in [('≤2',0,2),('3-5',3,5),('6-7',6,7),('8-9',8,9)]:
    f_cnt=sum(1 for x in fails if lo<=x['span']<=hi)
    w_cnt=sum(1 for x in wins if lo<=x['span']<=hi)
    tot=f_cnt+w_cnt
    print(f"  {label}: {tot}期 失败{f_cnt}次={f_cnt/tot*100:.1f}%")

# ==== 维度5: 失败时实际和尾的分布 ====
print("\n维度5: 失败时实际和尾分布 (公式'漏掉'了哪个尾)")
actual_cnt=Counter()
for x in fails: actual_cnt[x['actual']]+=1
for t in range(10):
    print(f"  尾{t}: {actual_cnt[t]}次={actual_cnt[t]/len(fails)*100:.1f}%")
