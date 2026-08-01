"""
福彩3D 杀和尾 — 数据抓取模块
多源降级: 灰鸟API(主) → 中彩网(备)
期号严格递增校验, 防缓存/旧数据污染
"""
import csv, json, re, os
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fc3d-history.csv")


def http_get(url, timeout=15):
    try:
        import requests
        r = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }, timeout=timeout)
        if r.status_code == 200:
            r.encoding = "utf-8"
            return r.text
    except Exception:
        pass
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception:
        pass
    return None


def fetch_huiniao():
    url = "http://api.huiniao.top/interface/home/lotteryHistory?type=fcsd&page=1&limit=1"
    text = http_get(url)
    if not text:
        return None
    data = json.loads(text)
    if data.get("code") != 1:
        return None
    item = data["data"]["data"]["list"][0]
    return {"issue": str(item["code"]), "date": item["day"],
            "b": int(item["one"]), "s": int(item["two"]), "g": int(item["three"]),
            "next_issue": item.get("next_code")}


def fetch_zhcw():
    url = "https://www.zhcw.com/kjxx/fc3d/"
    text = http_get(url)
    if not text:
        return None
    m = re.search(r'<em>(\d{7})</em>.*?<em>(\d{4}-\d{2}-\d{2})</em>.*?<i>(\d)</i>\s*<i>(\d)</i>\s*<i>(\d)</i>', text, re.DOTALL)
    if not m:
        m = re.search(r'(\d{7})期.*?(\d{4}-\d{2}-\d{2}).*?(\d)\s*(\d)\s*(\d)', text, re.DOTALL)
    if not m:
        return None
    return {"issue": m.group(1), "date": m.group(2),
            "b": int(m.group(3)), "s": int(m.group(4)), "g": int(m.group(5))}


def load_csv(path=CSV_PATH):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({"issue": r["issue"],
                             "b": int(r["hundreds"]), "s": int(r["tens"]), "g": int(r["ones"])})
            except Exception:
                continue
    return rows


def append_csv(data, path=CSV_PATH):
    existing = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                existing.add(r.get("issue", ""))
    except FileNotFoundError:
        pass
    if str(data["issue"]) in existing:
        return 0
    with open(path, "a", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow([data["issue"], data["b"], data["s"], data["g"]])
    return 1


def next_issue_calc(last_issue):
    """期号跨年回绕: 2026365 -> 2027001"""
    year = int(str(last_issue)[:4])
    num = int(str(last_issue)[4:])
    return f"{year}{num + 1:03d}" if num < 365 else f"{year + 1}001"


def fetch_latest():
    """多源依次尝试, 期号必须 > 本地最新, 否则视为缓存拒绝"""
    sources = [("灰鸟API", fetch_huiniao), ("中彩网", fetch_zhcw)]
    last_issue = None
    try:
        rows = load_csv()
        if rows:
            last_issue = rows[-1]["issue"]
    except Exception:
        pass

    for name, fn in sources:
        try:
            data = fn()
            if not data:
                continue
            if last_issue and str(data["issue"]) <= str(last_issue):
                print(f"  [skip] {name}: 期号{data['issue']}<=本地{last_issue}, 缓存/旧数据")
                continue
            print(f"  [ok] {name}: {data['issue']} ({data.get('date','')}) {data['b']}{data['s']}{data['g']}")
            return data
        except Exception as e:
            print(f"  [warn] {name}: {e}")
    return None


if __name__ == "__main__":
    d = fetch_latest()
    if d:
        n = append_csv(d)
        print(f"追加 {n} 条, 下期预测期号: {d.get('next_issue') or next_issue_calc(d['issue'])}")
    else:
        print("无新数据")
