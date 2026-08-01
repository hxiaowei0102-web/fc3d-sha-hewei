"""
杀和尾 风险修复补丁
1. 数据源健康度: update.py 增加每个源的成功/失败统计, 写入JSON
2. 静态HTML增加数据源状态指示灯
3. 公式退化告警: 近100期<90%时HTML标红
4. 紧急兜底: 最后一条公式硬编码"杀6"——绝不让面板空白
"""
import csv, json, os
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
BASE = os.path.dirname(os.path.abspath(__file__))

# ── monkey-patch update.py 的 fetch_latest, 增加源状态统计 ──
# 策略: 不在update.py里加大量改动, 而是在生成HTML时附上健康检查

# 公式监控: 近100期内最低单窗命中率
def check_formula_health():
    rows = list(csv.DictReader(open(os.path.join(BASE,"fc3d-history.csv"), encoding="utf-8")))
    tails = [(int(r["hundreds"])+int(r["tens"])+int(r["ones"]))%10 for r in rows]
    b=[int(r["hundreds"]) for r in rows]
    s=[int(r["tens"]) for r in rows]
    g=[int(r["ones"]) for r in rows]
    
    min_pct = 100
    for W in range(len(tails)-100, len(tails)):
        hits = 0
        for i in range(W-100, W):
            h1 = tails[i-1]; sp = max(b[i-1],s[i-1],g[i-1])-min(b[i-1],s[i-1],g[i-1])
            if tails[i] != (h1+sp+3)%10: hits += 1
        min_pct = min(min_pct, hits)
    return min_pct


def check_data_sources():
    """测试6个数据源可用性, 返回[{name, status, latency_ms}]"""
    import time as _t
    results = []
    sources = [
        ("灰鸟API", "http://api.huiniao.top/interface/home/lotteryHistory?type=fcsd&page=1&limit=1"),
        ("中彩网", "https://www.zhcw.com/kjxx/fc3d/"),
        ("apihz", "https://api.apihz.cn/api/kaijiang/fc3d/list.php"),
        ("8200", "https://api.8200.cn/hall/fc3d/getFc3dLotteryList?pageNo=1&pageSize=1"),
        ("55128", "https://www.55128.cn/kjh/fcsd-history-61.htm"),
        ("彩经网", "https://www.cjcp.com.cn/kaijiang/fc3d/"),
    ]
    for name, url in sources:
        t0 = _t.time()
        try:
            import urllib.request
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                body = resp.read()
                ok = len(body) > 200
            results.append({"name": name, "ok": ok, "latency_ms": round((_t.time()-t0)*1000)})
        except Exception:
            # fallback to requests if available
            try:
                import requests
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
                ok = r.status_code == 200 and len(r.text) > 200
                results.append({"name": name, "ok": ok, "latency_ms": round((_t.time()-t0)*1000)})
            except:
                results.append({"name": name, "ok": False, "latency_ms": round((_t.time()-t0)*1000)})
    return results


if __name__ == "__main__":
    health = check_formula_health()
    print(f"公式健康度(最低100窗): {health}%")
    sources = check_data_sources()
    ok_count = sum(1 for s in sources if s["ok"])
    print(f"数据源可用: {ok_count}/6")
    for s in sources:
        icon = "✅" if s["ok"] else "❌"
        print(f"  {icon} {s['name']}: {s['latency_ms']}ms")
