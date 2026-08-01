"""
福彩3D 杀和尾 — 云端全自动更新（单杀制）
=============================================
6源降级获取 → 追加CSV → 单杀回测 → 生成 JSON + 静态 HTML
GitHub Actions 三重 cron: 北京 22:00 / 23:30 / 01:00
公式: (上期和尾 + 上期跨度 + 3) % 10
"""
import csv, json, os, re, sys
from datetime import datetime, timezone, timedelta
from collections import Counter

TZ = timezone(timedelta(hours=8))
BASE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE, "fc3d-history.csv")
JSON_OUT = os.path.join(BASE, "single_prediction.json")
HTML_OUT = os.path.join(BASE, "index.html")
WARM = 250
BACKTEST_N = 100


# ─── 数据抓取（多源降级）─────────────────────────────────
def http_get(url, timeout=15):
    try:
        import requests
        r = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0"
        }, timeout=timeout)
        if r.status_code == 200:
            r.encoding = "utf-8"
            return r.text
    except Exception: pass
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception: pass
    return None


def fetch_huiniao():
    url = "http://api.huiniao.top/interface/home/lotteryHistory?type=fcsd&page=1&limit=1"
    text = http_get(url)
    if not text: return None
    data = json.loads(text)
    if data.get("code") != 1: return None
    item = data["data"]["data"]["list"][0]
    return {"issue": str(item["code"]), "date": item["day"],
            "b": int(item["one"]), "s": int(item["two"]), "g": int(item["three"])}


def fetch_zhcw():
    url = "https://www.zhcw.com/kjxx/fc3d/"
    text = http_get(url)
    if not text: return None
    m = re.search(r'<em>(\d{7})</em>.*?<em>(\d{4}-\d{2}-\d{2})</em>.*?<i>(\d)</i>\s*<i>(\d)</i>\s*<i>(\d)</i>', text, re.DOTALL)
    if not m:
        m = re.search(r'(\d{7})期.*?(\d{4}-\d{2}-\d{2}).*?(\d)\s*(\d)\s*(\d)', text, re.DOTALL)
    if not m: return None
    return {"issue": m.group(1), "date": m.group(2),
            "b": int(m.group(3)), "s": int(m.group(4)), "g": int(m.group(5))}


def fetch_apihz():
    """apihz JSON API（带key鉴权）"""
    url = "https://api.apihz.cn/api/kaijiang/fc3d/list.php"
    text = http_get(url)
    if not text: return None
    data = json.loads(text)
    if data.get("code") != 1: return None
    item = data["data"][0]
    nums = str(item["code"]).zfill(3)
    return {"issue": str(item["expect"]), "date": item["time"][:10],
            "b": int(nums[0]), "s": int(nums[1]), "g": int(nums[2])}


def fetch_8200():
    """8200 JSON API"""
    url = "https://api.8200.cn/hall/fc3d/getFc3dLotteryList?pageNo=1&pageSize=1"
    text = http_get(url)
    if not text: return None
    data = json.loads(text)
    if data.get("code") != 0: return None
    item = data["data"]["list"][0]
    return {"issue": str(item["lotteryNo"]), "date": item["lotteryTime"][:10],
            "b": int(item["lotteryNumber"][0]), "s": int(item["lotteryNumber"][1]),
            "g": int(item["lotteryNumber"][2])}


def fetch_55128():
    """55128 网页解析"""
    url = "https://www.55128.cn/kjh/fcsd-history-61.htm"
    text = http_get(url)
    if not text: return None
    m = re.search(r'<td>(\d{7})</td>\s*<td>(\d{4}-\d{2}-\d{2})</td>\s*<td[^>]*>\s*(\d)\s*</td>\s*<td[^>]*>\s*(\d)\s*</td>\s*<td[^>]*>\s*(\d)\s*</td>', text)
    if not m:
        m = re.search(r'(\d{7}).*?(\d{4}-\d{2}-\d{2}).*?(\d)\s+(\d)\s+(\d)', text, re.DOTALL)
    if not m: return None
    return {"issue": m.group(1), "date": m.group(2),
            "b": int(m.group(3)), "s": int(m.group(4)), "g": int(m.group(5))}


def fetch_cjcp():
    """彩经网 网页解析"""
    url = "https://www.cjcp.com.cn/kaijiang/fc3d/"
    text = http_get(url)
    if not text: return None
    m = re.search(r'(\d{7})\s*期.*?(\d{4}-\d{2}-\d{2}).*?(\d)\s*(\d)\s*(\d)', text, re.DOTALL)
    if not m:
        m = re.search(r'<td>(\d{7})</td>.*?<td>(\d{4}-\d{2}-\d{2})</td>.*?<td>(\d)</td>.*?<td>(\d)</td>.*?<td>(\d)</td>', text, re.DOTALL)
    if not m: return None
    return {"issue": m.group(1), "date": m.group(2),
            "b": int(m.group(3)), "s": int(m.group(4)), "g": int(m.group(5))}


# ─── CSV 操作 ──────────────────────────────────────────
def load_csv(path=CSV_PATH):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({"issue": r["issue"],
                             "b": int(r["hundreds"]), "s": int(r["tens"]), "g": int(r["ones"]),
                             "tail": (int(r["hundreds"]) + int(r["tens"]) + int(r["ones"])) % 10})
            except Exception: continue
    return rows


def append_csv(data, path=CSV_PATH):
    existing = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f): existing.add(r.get("issue", ""))
    except FileNotFoundError: pass
    if str(data["issue"]) in existing: return 0
    with open(path, "a", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow([data["issue"], data["b"], data["s"], data["g"]])
    print(f"  ✅ 新数据: {data['issue']} ({data['date']}) {data['b']}{data['s']}{data['g']}")
    return 1


def fetch_latest():
    sources = [
        ("灰鸟API", fetch_huiniao),
        ("apihz",   fetch_apihz),
        ("中彩网",  fetch_zhcw),
        ("8200",    fetch_8200),
        ("55128",   fetch_55128),
        ("彩经网",  fetch_cjcp),
    ]
    last_issue = None
    try:
        rows = load_csv()
        if rows: last_issue = rows[-1]["issue"]
    except Exception: pass
    for name, fn in sources:
        try:
            data = fn()
            if not data: continue
            if last_issue and str(data["issue"]) <= str(last_issue):
                print(f"  ⏭️ {name}: 期号{data['issue']}<=本地{last_issue}, 跳过")
                continue
            print(f"  📡 {name}: {data['issue']} ({data['date']}) {data['b']}{data['s']}{data['g']}")
            return data
        except Exception as e:
            print(f"  ⚠️ {name}: {e}")
    return None


# ─── 单杀引擎 ──────────────────────────────────────────
def predict(i, tails):
    r = tails[i - 1]
    h1 = r["tail"]
    span = max(r["b"], r["s"], r["g"]) - min(r["b"], r["s"], r["g"])
    return (h1 + span + 3) % 10


def next_issue_calc(last):
    if not last: return "?"
    year = int(last[:4]); num = int(last[4:])
    return f"{year}{num+1:03d}" if num < 365 else f"{year+1}001"


def compute(tails):
    T = len(tails)
    k_next = predict(T, tails)
    next_issue = next_issue_calc(tails[-1]["issue"])

    # 多窗口命中率
    win = {}
    for W in (100, 200, 500, 1000):
        lo = max(WARM, T - W)
        n = T - lo
        hits = sum(1 for i in range(lo, T) if tails[i]["tail"] != predict(i, tails))
        win[W] = {"n": n, "hit": hits, "pct": round(hits / n * 100, 2)}

    # 100期明细（近→远）
    details = []
    for i in range(T - 1, max(WARM, T - BACKTEST_N) - 1, -1):
        k = predict(i, tails)
        ok = tails[i]["tail"] != k
        details.append({
            "issue": tails[i]["issue"],
            "number": f"{tails[i]['b']}{tails[i]['s']}{tails[i]['g']}",
            "tail": tails[i]["tail"], "kill": k, "hit": ok,
        })

    data = {
        "meta": {
            "updated": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"),
            "total": T, "latest_issue": tails[-1]["issue"],
            "latest_number": f"{tails[-1]['b']}{tails[-1]['s']}{tails[-1]['g']}",
            "formula": "(上期和尾 + 跨度 + 3) % 10",
            "full_hit": round(sum(1 for i in range(WARM, T)
                                   if tails[i]["tail"] != predict(i, tails)) / (T - WARM) * 100, 2),
        },
        "prediction": {"next_issue": next_issue, "kill": k_next},
        "window_stats": win,
        "details": details,
    }

    # 输出 JSON
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 生成静态 HTML（内嵌 JSON，无需服务器）
    html = build_html(data)
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n  单杀命中: 近100={win[100]['pct']}% 近500={win[500]['pct']}%")
    print(f"  预测 {next_issue} 期: 杀和尾 {k_next}")
    return data


def build_html(d):
    """内嵌数据的静态 HTML"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>福彩3D 杀和尾 · 单杀</title>
<style>
:root{{--red:#e0453a;--green:#1a9e54;--bg:#f4f6f9;--card:#fff;--line:#e6e9ef}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:#222;max-width:640px;margin:0 auto;padding:12px}}
.card{{background:var(--card);border-radius:12px;padding:16px;margin-bottom:12px;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
h1{{font-size:19px}}.sub{{color:#888;font-size:12px;margin-top:4px}}
.ball-wrap{{display:flex;justify-content:center;margin:16px 0}}
.ball{{width:80px;height:80px;border-radius:50%;background:var(--red);color:#fff;font-size:42px;font-weight:700;display:flex;align-items:center;justify-content:center;box-shadow:0 3px 10px rgba(224,69,58,.4)}}
.ball-label{{text-align:center;font-size:13px;color:#666;margin-top:6px}}
.issue{{text-align:center;font-size:15px}}.issue b{{color:var(--red);font-size:20px}}
.formula-info{{text-align:center;font-size:12px;color:#888;margin:8px 0}}
.stat-row{{display:flex;justify-content:space-between;padding:9px 2px;border-bottom:1px solid var(--line);font-size:15px}}
.stat-row:last-child{{border-bottom:none}}.pct{{font-weight:700}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{padding:6px 3px;text-align:center;border-bottom:1px solid var(--line)}}
thead th{{position:sticky;top:0;background:#fafbfc;font-size:12px;color:#666;z-index:1}}
.tbl-wrap{{max-height:60vh;overflow-y:auto}}
.hit{{color:var(--green);font-weight:700}}.miss{{color:var(--red);font-weight:700}}
</style>
</head>
<body>
<h1>🎯 福彩3D 杀和尾 <span style="font-size:13px;color:#888">单杀制</span></h1>
<div class="sub">更新于 {d['meta']['updated']} · 共 {d['meta']['total']} 期 · 最新 {d['meta']['latest_issue']} ({d['meta']['latest_number']})</div>
<div class="card">
  <div class="issue">预测期号 <b>{d['prediction']['next_issue']}</b> 期</div>
  <div class="ball-wrap"><div><div class="ball">{d['prediction']['kill']}</div><div class="ball-label">杀和尾</div></div></div>
  <div class="formula-info">公式：{d['meta']['formula']}</div>
</div>
<div class="card">
  <b>单杀命中率</b>
  {"".join(f'<div class="stat-row"><span>近 {w} 期</span><span class="pct">{s["pct"]}%</span><span style="color:#999;font-size:12px">{s["hit"]}/{s["n"]}</span></div>' for w,s in d['window_stats'].items())}
  <div class="stat-row" style="border-top:1px solid var(--line);margin-top:4px;padding-top:10px"><span>全量(暖机后)</span><span class="pct">{d['meta']['full_hit']}%</span><span style="color:#999;font-size:12px">{d['meta']['total']-250} 期</span></div>
</div>
<div class="card">
  <b>最新 100 期明细</b> <span style="color:#999;font-size:12px">（近 → 远）</span>
  <div class="tbl-wrap"><table><thead><tr><th>期号</th><th>号码</th><th>和尾</th><th>杀</th><th>结果</th></tr></thead><tbody>
  {"".join(f'<tr><td>{r["issue"]}</td><td>{r["number"]}</td><td>{r["tail"]}</td><td class="{"hit" if r["hit"] else "miss"}">{r["kill"]}</td><td>{"✅" if r["hit"] else "❌"}</td></tr>' for r in d['details'])}
  </tbody></table></div>
</div>
</body></html>"""


# ─── Main ──────────────────────────────────────────────
if __name__ == "__main__":
    print(f"🕐 {datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')} 杀和尾单杀更新")
    # 1. 抓新数据
    new = fetch_latest()
    if new:
        append_csv(new)

    # 2. 载入全量
    tails = load_csv()
    print(f"  📊 总期数: {len(tails)} | 首期 {tails[0]['issue']} | 末期 {tails[-1]['issue']}")

    # 3. 回测+预测+生成HTML
    compute(tails)
    print(f"  ✅ 完成 | 预测期号: {next_issue_calc(tails[-1]['issue'])} | JSON: {JSON_OUT} | HTML: {HTML_OUT}")
