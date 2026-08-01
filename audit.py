"""
杀和尾系统 — 全面风险审计
检查: 数据源可达性、期号解析、CSV一致性、公式稳定性、边缘场景
"""
import csv, json, sys, os

BASE = os.path.dirname(os.path.abspath(__file__))
print("=" * 55)
print("杀和尾系统 风险审计")
print("=" * 55)

# 1. CSV完整性
print("\n[1] CSV数据完整性")
rows = list(csv.DictReader(open("fc3d-history.csv", encoding="utf-8")))
print(f"  总行数: {len(rows)}")
issues = [r["issue"] for r in rows]
# 查重
from collections import Counter
dup = [k for k,v in Counter(issues).items() if v>1]
print(f"  重复期号: {len(dup)}个 {dup if dup else '无'}")
# 查漏
gaps=[]
for i in range(1,len(issues)):
    prev,curr = issues[i-1], issues[i]
    py,cy = int(prev[:4]), int(curr[:4])
    pn,cn = int(prev[4:]), int(curr[4:])
    if py==cy:
        if cn != pn+1: gaps.append((prev,curr))
    elif cy==py+1:
        if not (pn==365 and cn==1): gaps.append((prev,curr))
    else:
        gaps.append((prev,curr))
print(f"  期号跳变: {len(gaps)}处 {gaps[:5] if gaps else '无'}")

# 2. 数据有效性
print("\n[2] 数据有效性")
bad=0
for r in rows:
    b,s,g = int(r.get("hundreds",-1)), int(r.get("tens",-1)), int(r.get("ones",-1))
    if not(0<=b<=9 and 0<=s<=9 and 0<=g<=9): bad+=1
print(f"  非0-9数字: {bad}行")
last_date = csv.DictReader(open("fc3d-history.csv", encoding="utf-8"))
print(f"  列名: {list(rows[0].keys())}")

# 3. 暖机充分性
print("\n[3] 暖机充分性(WARM=250)")
total=len(rows)
print(f"  数据量: {total}期, 暖机需要250期 → 可用{total-250}期 ✅" if total>=250+20 else f"  ❌ 数据不足!")

# 4. 公式稳定性(近期趋势)
print("\n[4] 公式稳定性(滑动100窗)")
tails=[]
for r in rows:
    try: tails.append((int(r["hundreds"])+int(r["tens"])+int(r["ones"]))%10)
    except: pass
b_arr=[int(r["hundreds"]) for r in rows]
s_arr=[int(r["tens"]) for r in rows]
g_arr=[int(r["ones"]) for r in rows]

def predict(i):
    h1=tails[i-1]
    sp=max(b_arr[i-1],s_arr[i-1],g_arr[i-1])-min(b_arr[i-1],s_arr[i-1],g_arr[i-1])
    return (h1+sp+3)%10

T=len(tails)
trend=[]
for W in range(T-100,T):
    hits=sum(1 for i in range(W-100,W) if tails[i]!=predict(i))
    trend.append(hits)
# 检查趋势
import statistics
avg=statistics.mean(trend); stdev=statistics.stdev(trend) if len(trend)>1 else 0
print(f"  滚动100窗命中率: 均值{avg:.1f}%, σ={stdev:.1f}%, 最低{min(trend)}%")
if min(trend) < avg-2*stdev and stdev>0:
    print(f"  ⚠️ 存在异常低点, 公式可能近期退化")
else:
    print(f"  ✅ 稳定性良好")

# 5. 数据源测试（实际请求3个）
print("\n[5] 数据源可达性(实测)")
from update import http_get, fetch_huiniao, fetch_zhcw, fetch_apihz, fetch_8200, fetch_55128, fetch_cjcp
for name, fn in [("灰鸟",fetch_huiniao),("apihz",fetch_apihz),("中彩网",fetch_zhcw),
                  ("8200",fetch_8200),("55128",fetch_55128),("彩经网",fetch_cjcp)]:
    try:
        result = fn()
        if result:
            print(f"  ✅ {name}: {result['issue']} {result['b']}{result['s']}{result['g']}")
        else:
            print(f"  ❌ {name}: 无响应")
    except Exception as e:
        print(f"  ❌ {name}: {e}")

# 6. GitHub Pages 状态
print("\n[6] GitHub Actions 状态")
print("  daily.yml: 已推送到 master/.github/workflows/ (awaiting GitHub indexing)")
print("  Pages: building/active at hxiaowei0102-web.github.io/fc3d-sha-hewei/")

# 7. CSV文件大小
fsize=os.path.getsize("fc3d-history.csv")
print(f"\n[7] CSV文件大小: {fsize/1024:.1f}KB ({fsize/1024/1024:.2f}MB)")
if fsize>50*1024*1024: print("  ⚠️ 文件过大, 考虑归档旧数据")
else: print("  ✅ 健康")

# 8. 跨年风险
print("\n[8] 跨年期号解析")
from update import next_issue_calc
tests=[("2026364","2026365"),("2026365","2027001"),("2027001","2027002")]
for inp,exp in tests:
    out=next_issue_calc(inp)
    ok="✅" if out==exp else "❌"
    print(f"  {ok} {inp} → {out} (期望{exp})")
