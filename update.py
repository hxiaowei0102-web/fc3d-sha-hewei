"""
福彩3D 杀和尾 — 云端全自动更新（单杀制）
=============================================
6源降级获取 → 追加CSV → 单杀回测 → 生成 JSON + 静态 HTML
GitHub Actions 三重 cron: 北京 22:00 / 23:30 / 01:00
公式: (上期和尾 + 上期跨度 + 3) % 10
"""
import csv, json, os, re, sys
from datetime import datetime, timezone, timedelta
from collections import Counter, defaultdict

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
    """① 灰鸟API (JSON) — 带 next_code, 跨年安全"""
    url = "http://api.huiniao.top/interface/home/lotteryHistory?type=fcsd&page=1&limit=1"
    text = http_get(url)
    if not text: return None
    data = json.loads(text)
    if data.get("code") != 1: return None
    item = data["data"]["data"]["list"][0]
    return {"issue": str(item["code"]), "date": item["day"],
            "b": int(item["one"]), "s": int(item["two"]), "g": int(item["three"]),
            "next_code": str(item.get("next_code") or "")}


def fetch_17500():
    """② 17500.cn 官方级全量TXT (2002至今) — 取最新一行(文件末尾)
    格式: 期号 日期 百 十 个 ... | GBK 编码 | 仅 http"""
    url = "http://www.17500.cn/getData/3d.TXT"
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("gbk", errors="ignore")
        last = None
        for line in raw.splitlines():
            line = line.strip()
            if not line: continue
            p = line.split()
            if len(p) >= 5 and len(p[0]) == 7 and p[0].isdigit():
                last = {"issue": p[0], "date": p[1],
                        "b": int(p[2]), "s": int(p[3]), "g": int(p[4])}
        return last
    except Exception:
        return None


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
    """③ apihz JSON API（公共key, JSON单期）"""
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
    """多源降级: ①灰鸟(JSON+next_code) → ②17500(官方全量TXT,新增) → ③apihz(JSON)
       → ④8200/55128/彩经网(历史备份) → 中彩网(缓存页,基本只剩理论存在,最后兜底)"""
    sources = [
        ("灰鸟API", fetch_huiniao),
        ("17500",   fetch_17500),
        ("apihz",   fetch_apihz),
        ("8200",    fetch_8200),
        ("55128",   fetch_55128),
        ("彩经网",  fetch_cjcp),
        ("中彩网",  fetch_zhcw),
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


# ─── 单杀引擎 (Hedge 6专家加权混合 v2.4) ─────────────────
WINDOW_W = 150    # Hedge权重评估窗口
SMOOTH = 0.02     # 权重下限
# v2.4: 网格扫描4轮选优(以近500最优为准) - 去freq_all 加LS212 → 近500=94.4%
EXPERT_KEYS = ['h1s3', 'trans1', 'L038', 'L-222', 'X2015', 'LS212']
EXPERT_LABELS = {
    'h1s3': '公式(h1+span+3)', 'trans1': '一阶转移表',
    'L038': '公式(3*跨+8)', 'L-222': '公式(-2尾+2跨+2)',
    'X2015': '公式(2尾+十+5)', 'LS212': '公式(2十+跨+2)',
}


def precompute_kills(tails):
    """预计算每个专家每期的杀码数组 (全部只用历史)
    数组长度 T+1, kills[e][T] 即下一期预测 (用 tails[T-1] 信息, 无泄漏)"""
    T = len(tails)
    ta = [t["tail"] for t in tails]
    kills = {e: [0] * (T + 1) for e in EXPERT_KEYS}

    def h1s3(i):
        r = tails[i - 1]
        sp = max(r["b"], r["s"], r["g"]) - min(r["b"], r["s"], r["g"])
        return (r["tail"] + sp + 3) % 10

    # 简单公式
    for i in range(WARM, T + 1):
        kills['h1s3'][i] = h1s3(i)
        r = tails[i - 1]
        sp = max(r["b"], r["s"], r["g"]) - min(r["b"], r["s"], r["g"])
        kills['L038'][i] = (3 * sp + 8) % 10      # 网格扫描: (0*尾+3*跨+8)%10
        kills['L-222'][i] = (-2 * r["tail"] + 2 * sp + 2) % 10  # 网格扫描: (-2*尾+2*跨+2)%10
        kills['X2015'][i] = (2 * r["tail"] + r["s"] + 5) % 10   # 网格扫描: (2*尾+十+5)%10
        kills['LS212'][i] = (2 * r["s"] + sp + 2) % 10  # 网格扫描: (2*十+跨+2)%10

    # trans1 一阶转移表 (滚动近300期)
    for i in range(WARM, T + 1):
        lo = max(WARM, i - 300)
        tab = defaultdict(lambda: [0.1] * 10)
        for j in range(lo + 1, i):
            tab[ta[j - 1]][ta[j]] += 1
        p = tab[tails[i - 1]["tail"]]
        kills['trans1'][i] = min(range(10), key=lambda t: p[t]) if sum(p) > 0 else h1s3(i)

    return kills, ta


def hedge_kill_from(kills, ta, i):
    """第 i 期 Hedge 混合杀码 (只用 <=i-1 数据)"""
    lo = max(WARM, i - WINDOW_W)
    if i - lo >= 10:
        ws = {}
        for e in EXPERT_KEYS:
            h = sum(1 for j in range(lo, i) if ta[j] != kills[e][j])
            ws[e] = max(SMOOTH, h / (i - lo))
    else:
        ws = {e: 0.9 for e in EXPERT_KEYS}
    votes = [0.0] * 10
    for e in EXPERT_KEYS:
        votes[kills[e][i]] += ws[e]
    return max(range(10), key=lambda t: votes[t]), ws


def predict(i, tails):
    """兼容旧接口: 单杀公式 (h1+span+3) — 仅用于对照"""
    r = tails[i - 1]
    h1 = r["tail"]
    span = max(r["b"], r["s"], r["g"]) - min(r["b"], r["s"], r["g"])
    return (h1 + span + 3) % 10


def next_issue_calc(last):
    """期号跨年回绕: 每年最多359期, 2026360+ -> 2027001
    保守处理: 当前年末尾期号>=357 时进位到下一年001"""
    if not last: return "?"
    year = int(last[:4]); num = int(last[4:])
    if num >= 357:
        return f"{year+1}001"
    return f"{year}{num+1:03d}"


def compute(tails, next_code=None):
    T = len(tails)
    kills, ta = precompute_kills(tails)

    # 预测下一期 (i=T)
    lo = max(WARM, T - WINDOW_W)
    ws = {}
    for e in EXPERT_KEYS:
        h = sum(1 for j in range(lo, T) if ta[j] != kills[e][j])
        ws[e] = max(SMOOTH, h / (T - lo))
    votes = [0.0] * 10
    for e in EXPERT_KEYS:
        votes[kills[e][T]] += ws[e]
    k_next = max(range(10), key=lambda t: votes[t])
    exp_next = {e: kills[e][T] for e in EXPERT_KEYS}
    # 优先用源提供的 next_code (跨年安全), 否则按序号推算
    next_issue = str(next_code) if next_code else next_issue_calc(tails[-1]["issue"])

    # 多窗口命中率 (Hedge vs 基线 h1s3)
    win = {}
    for W in (100, 200, 500, 1000):
        lo = max(WARM, T - W)
        n = T - lo
        hits = 0; hits_base = 0
        for i in range(lo, T):
            if ta[i] != hedge_kill_from(kills, ta, i)[0]: hits += 1
            if ta[i] != predict(i, tails): hits_base += 1
        win[W] = {"n": n, "hit": hits, "pct": round(hits / n * 100, 2),
                  "base_pct": round(hits_base / n * 100, 2),
                  "diff": round((hits - hits_base) / n * 100, 2)}

    # 100期明细（近→远）+ 各专家杀码
    details = []
    for i in range(T - 1, max(WARM, T - BACKTEST_N) - 1, -1):
        k = hedge_kill_from(kills, ta, i)[0]
        ok = ta[i] != k
        details.append({
            "issue": tails[i]["issue"],
            "number": f"{tails[i]['b']}{tails[i]['s']}{tails[i]['g']}",
            "tail": ta[i], "kill": k, "hit": ok,
            "experts": {e: kills[e][i] for e in EXPERT_KEYS},
        })

    full_hits = sum(1 for i in range(WARM, T) if ta[i] != hedge_kill_from(kills, ta, i)[0])
    full_base = sum(1 for i in range(WARM, T) if ta[i] != predict(i, tails))

    # ── 专家级回测: 各专家独立命中率 + 投票组合优势 ──
    expert_stats = {}
    for e in EXPERT_KEYS:
        s = {}
        for W in (100, 200, 500):
            lo = max(WARM, T - W)
            n = T - lo
            h = sum(1 for i in range(lo, T) if ta[i] != kills[e][i])
            s[str(W)] = {"n": n, "hit": h, "pct": round(h / n * 100, 2)}
        fn = T - WARM
        fh = sum(1 for i in range(WARM, T) if ta[i] != kills[e][i])
        s["full"] = {"n": fn, "hit": fh, "pct": round(fh / fn * 100, 2)}
        expert_stats[e] = s
    best_e = max(EXPERT_KEYS, key=lambda e: expert_stats[e]["full"]["pct"])

    data = {
        "meta": {
            "updated": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"),
            "total": T, "latest_issue": tails[-1]["issue"],
            "latest_number": f"{tails[-1]['b']}{tails[-1]['s']}{tails[-1]['g']}",
            "formula": "Hedge 6专家加权混合 (h1s3+转移表+3跨8+-2尾2跨2+2尾十5+2十跨2)",
            "window": WINDOW_W,
            "full_hit": round(full_hits / (T - WARM) * 100, 2),
            "full_base": round(full_base / (T - WARM) * 100, 2),
        },
        "prediction": {"next_issue": next_issue, "kill": k_next,
                       "experts": exp_next,
                       "weights": {e: round(ws[e], 3) for e in EXPERT_KEYS}},
        "window_stats": win,
        "expert_stats": expert_stats,
        "best_single": {"expert": best_e, "label": EXPERT_LABELS.get(best_e, best_e),
                        "pct": expert_stats[best_e]["full"]["pct"]},
        "details": details,
    }

    # 输出 JSON
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 生成静态 HTML（内嵌 JSON，无需服务器）
    html = build_html(data)
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n  Hedge单杀命中: 近100={win[100]['pct']}% (基{win[100]['base_pct']}%) 近500={win[500]['pct']}% (基{win[500]['base_pct']}%)")
    print(f"  预测 {next_issue} 期: 杀和尾 {k_next} | 专家票 {exp_next}")
    return data


def build_html(d):
    """内嵌数据的静态 HTML"""
    def expert_label(e):
        return {'h1s3': '公式(h1+span+3)', 'trans1': '一阶转移表',
                'L038': '公式(3*跨+8)', 'L-222': '公式(-2尾+2跨+2)',
                'X2015': '公式(2尾+十+5)', 'LS212': '公式(2十+跨+2)'}[e]
    # 每个专家的近100期回测明细 (details 已按 近→远 排列)
    def expert_detail_rows(e):
        rows = []
        for r in d['details']:
            k = r['experts'].get(e)
            if k is None:
                continue
            ok = r['tail'] != k
            rows.append(
                f'<tr><td>{r["issue"]}</td><td>{r["number"]}</td><td>{r["tail"]}</td>'
                f'<td class="{"hit" if ok else "miss"}">{k}</td>'
                f'<td>{"✅" if ok else "❌"}</td></tr>')
        return "".join(rows)

    def expert_card_html(e):
        detail_rows = expert_detail_rows(e)
        exp100 = d.get('expert_stats', {}).get(e, {}).get('100', {})
        pct = f'{exp100["pct"]}%' if exp100 else '—'
        hits = f'{exp100["hit"]}/{exp100["n"]}' if exp100 else ''
        return (
            f'<details class="exp-detail">'
            f'<summary class="exp-row">'
            f'<span class="exp-name">{expert_label(e)}</span>'
            f'<span class="exp-kill">杀 {d["prediction"]["experts"][e]}</span>'
            f'<span class="exp-w">近100回测 {pct} {hits}</span>'
            f'<span class="exp-toggle">▸</span>'
            f'</summary>'
            f'<div class="tbl-wrap" style="max-height:40vh">'
            f'<table><thead><tr><th>期号</th><th>号码</th><th>和尾</th><th>{expert_label(e)}杀</th><th>结果</th></tr></thead>'
            f'<tbody>{detail_rows}</tbody></table>'
            f'</div></details>')

    experts_html = "".join(expert_card_html(e) for e in d['prediction']['experts'])
    stats_html = "".join(
        f'<div class="stat-row"><span>近 {w} 期</span>'
        f'<span class="pct">{s["pct"]}%</span>'
        f'<span style="color:#999;font-size:12px">基线{s["base_pct"]}% ({s["diff"]:+.1f}pp)</span>'
        f'<span style="color:#999;font-size:12px">{s["hit"]}/{s["n"]}</span></div>'
        for w, s in sorted(d['window_stats'].items()))
    rows_html = "".join(
        f'<tr><td>{r["issue"]}</td><td>{r["number"]}</td><td>{r["tail"]}</td>'
        f'<td class="{"hit" if r["hit"] else "miss"}">{r["kill"]}</td>'
        f'<td>{"✅" if r["hit"] else "❌"}</td></tr>' for r in d['details'])
    # 专家回测表格
    exp_bt_rows = ""
    if d.get('expert_stats'):
        exp_bt_rows = "".join(
            f'<tr><td style="text-align:left">{EXPERT_LABELS.get(e, e)}</td>'
            f'<td>{d["expert_stats"][e]["100"]["pct"]}%</td>'
            f'<td>{d["expert_stats"][e]["200"]["pct"]}%</td>'
            f'<td>{d["expert_stats"][e]["500"]["pct"]}%</td>'
            f'<td>{d["expert_stats"][e]["full"]["pct"]}%</td></tr>'
            for e in EXPERT_KEYS)
        exp_bt_rows += (
            f'<tr style="font-weight:700;color:var(--green)"><td style="text-align:left">Hedge 加权投票</td>'
            f'<td>{d["window_stats"][100]["pct"]}%</td>'
            f'<td>{d["window_stats"][200]["pct"]}%</td>'
            f'<td>{d["window_stats"][500]["pct"]}%</td>'
            f'<td>{d["meta"]["full_hit"]}%</td></tr>')
        if d.get('best_single'):
            exp_bt_rows += (
                f'<tr style="color:#999"><td style="text-align:left">最优单专家 {d["best_single"]["label"]}</td>'
                f'<td colspan="4">全量 {d["best_single"]["pct"]}% (Hedge vs 最优: '
                f'{round(d["meta"]["full_hit"] - d["best_single"]["pct"], 2):+.2f}pp)</td></tr>')
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>福彩3D 杀和尾 · Hedge单杀</title>
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
.stat-row{{display:flex;justify-content:space-between;align-items:center;padding:9px 2px;border-bottom:1px solid var(--line);font-size:15px}}
.stat-row:last-child{{border-bottom:none}}.pct{{font-weight:700;color:var(--green)}}
.exp-row{{display:flex;justify-content:space-between;align-items:center;padding:8px 2px;border-bottom:1px solid var(--line);font-size:14px;cursor:pointer;list-style:none}}
.exp-row:last-child{{border-bottom:none}}
.exp-name{{color:#444}}.exp-kill{{font-weight:700;color:var(--red)}}
.exp-w{{color:#999;font-size:12px}}
.exp-detail{{display:block;border-bottom:1px solid var(--line)}}
.exp-detail:last-child{{border-bottom:none}}
.exp-detail summary::-webkit-details-marker{{display:none}}
.exp-toggle{{color:#bbb;font-size:12px;transition:transform .2s;margin-left:8px}}
.exp-detail[open] .exp-toggle{{transform:rotate(90deg)}}
.exp-detail .tbl-wrap{{border-top:1px dashed var(--line);padding-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{padding:6px 3px;text-align:center;border-bottom:1px solid var(--line)}}
thead th{{position:sticky;top:0;background:#fafbfc;font-size:12px;color:#666;z-index:1}}
.tbl-wrap{{max-height:60vh;overflow-y:auto}}
.hit{{color:var(--green);font-weight:700}}.miss{{color:var(--red);font-weight:700}}
</style>
</head>
<body>
<h1>🎯 福彩3D 杀和尾 <span style="font-size:13px;color:#888">Hedge 单杀 v2.4</span></h1>
<div class="sub">更新于 {d['meta']['updated']} · 共 {d['meta']['total']} 期 · 最新 {d['meta']['latest_issue']} ({d['meta']['latest_number']})</div>
<div class="card">
  <div class="issue">预测期号 <b>{d['prediction']['next_issue']}</b> 期</div>
  <div class="ball-wrap"><div><div class="ball">{d['prediction']['kill']}</div><div class="ball-label">杀和尾 {d['prediction']['kill']}</div></div></div>
  <div class="formula-info">算法：{d['meta']['formula']}</div>
</div>
<div class="card">
  <b>本期专家投票</b> <span style="color:#999;font-size:12px">（点击专家行展开近100期回测，近→远）</span>
  {experts_html}
</div>
<div class="card">
  <b>单杀命中率</b>
  {stats_html}
  <div class="stat-row" style="border-top:1px solid var(--line);margin-top:4px;padding-top:10px">
    <span>全量(暖机后)</span><span class="pct">{d['meta']['full_hit']}%</span>
    <span style="color:#999;font-size:12px">基线{d['meta']['full_base']}%</span>
    <span style="color:#999;font-size:12px">{d['meta']['total']-250} 期</span>
  </div>
</div>
<div class="card">
  <b>专家级回测</b> <span style="color:#999;font-size:12px">（各专家独立命中率 vs 加权投票）</span>
  <div class="tbl-wrap"><table>
    <thead><tr><th style="text-align:left">专家</th><th>近100</th><th>近200</th><th>近500</th><th>全量</th></tr></thead>
    <tbody>
    {exp_bt_rows}
    </tbody>
  </table></div>
</div>
<div class="card">
  <b>最新 100 期明细</b> <span style="color:#999;font-size:12px">（近 → 远）</span>
  <div class="tbl-wrap"><table><thead><tr><th>期号</th><th>号码</th><th>和尾</th><th>杀</th><th>结果</th></tr></thead><tbody>
  {rows_html}
  </tbody></table></div>
</div>
</body></html>"""


# ─── Main ──────────────────────────────────────────────
if __name__ == "__main__":
    print(f"🕐 {datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')} 杀和尾单杀更新")
    # 0. 双向同步: 先拉取云端最新数据(兼容本地/云端统一更新)
    try:
        import subprocess
        r = subprocess.run(["git", "pull", "--ff-only"], capture_output=True, text=True, timeout=15, cwd=BASE)
        if "Already up to date" in r.stdout:
            print("  🔄 本地已是最新")
        elif r.returncode == 0:
            print(f"  🔄 同步云端: {r.stdout.strip().split(chr(10))[0]}")
    except Exception:
        pass  # 没有git或网络不可用, 继续用本地数据

    # 1. 抓新数据
    new = fetch_latest()
    next_code = None
    if new:
        next_code = new.get("next_code")
        append_csv(new)

    # 2. 载入全量
    tails = load_csv()
    if not tails:
        print("  ❌ CSV 无数据或已损坏, 中止 (避免 IndexError)")
        sys.exit(1)
    print(f"  📊 总期数: {len(tails)} | 首期 {tails[0]['issue']} | 末期 {tails[-1]['issue']}")

    # 3. 回测+预测+生成HTML (优先用源提供的 next_code, 跨年安全)
    compute(tails, next_code)
    print(f"  ✅ 完成 | 预测期号: {next_code or next_issue_calc(tails[-1]['issue'])} | JSON: {JSON_OUT} | HTML: {HTML_OUT}")
