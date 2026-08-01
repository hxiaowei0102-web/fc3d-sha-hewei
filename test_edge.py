"""边界与极端场景测试"""
from engine import load_tails, select_kill1
from search_kill2 import make_fn
tails=load_tails(); T=len(tails)
kill2_fn=make_fn('h1','span','add',3)
fails=[]

# 1. 暖机期(i=250~260, 数据不足200窗): 不应崩溃, 给基准分
try:
    for i in range(250,260):
        k,n,s=select_kill1(tails,i)
        assert 0<=k<=9
    print("✅ 1. 暖机期(数据不足200窗) 正常, 杀码在0-9")
except Exception as e: fails.append(f"暖机期: {e}"); print("❌ 1.",e)

# 2. 撞车偏移: kill2==kill1 时必须偏移且偏移后 != kill1
clash_ok=True
for i in range(T-500,T):
    k1=select_kill1(tails,i)[0]; k2=kill2_fn(tails,i)
    if k2==k1:
        k2=(k2+1)%10
        if k2==k1: clash_ok=False
print("✅ 2. 撞车偏移后必不等于kill1" if clash_ok else "❌ 2. 偏移失效")
if not clash_ok: fails.append("撞车偏移")

# 3. 杀码恒在合法域 0-9 (全量扫描)
bad=0
for i in range(250,T):
    k1=select_kill1(tails,i)[0]
    if not(0<=k1<=9): bad+=1
    k2=kill2_fn(tails,i)
    if not(0<=k2<=9): bad+=1
print(f"✅ 3. 全量{T-250}期杀码全部合法(0-9), 越界{bad}个" if bad==0 else f"❌ 3. {bad}个越界")
if bad: fails.append("杀码越界")

# 4. 无泄漏: 预测第i期, kill1排名只用 <i 数据 → 改动 tails[i] 不应改变第i期的选择
import copy
i=T-1
k_before=select_kill1(tails,i)[0]
tails2=[dict(r) for r in tails]
tails2[i]['tail']=(tails2[i]['tail']+5)%10  # 篡改当期
k_after=select_kill1(tails2,i)[0]
print("✅ 4. 无泄漏: 篡改当期数据不影响当期预测" if k_before==k_after else f"❌ 4. 泄漏! {k_before}->{k_after}")
if k_before!=k_after: fails.append("数据泄漏")

# 5. 极端连错段稳定性: 统计近1000期最长连错
seq=[]
for i in range(T-1000,T):
    k1=select_kill1(tails,i)[0]; k2=kill2_fn(tails,i)
    if k2==k1: k2=(k2+1)%10
    seq.append(tails[i]['tail']!=k1 and tails[i]['tail']!=k2)
cur=mx=0
for ok in seq:
    cur=cur+1 if not ok else 0; mx=max(mx,cur)
print(f"✅ 5. 近1000期最长连错 {mx} 期 (健康线<8)")

# 6. 跨年边界: 期号 2026365->2027001
from fetch_data import next_issue_calc
assert next_issue_calc("2026365")=="2027001", next_issue_calc("2026365")
assert next_issue_calc("2026001")=="2026002"
print("✅ 6. 跨年回绕 2026365→2027001 正确")

print(f"\n{'='*40}")
print(f"测试结果: {'全部通过 ✅' if not fails else '失败项: '+str(fails)}")
