# -*- coding: utf-8 -*-
"""
福彩3D 杀和尾 — 联网补抓（多源降级链 + CSV兜底）
=============================================
按降级链逐个尝试抓取最新开奖，抓到比本地CSV新的期号就追加进CSV；
全部失败则不中断，使用现有CSV。所有日期/期号校验严格。
"""
import csv, json, re, os

CSV_PATH = 'fc3d-history.csv'


# ============ HTTP ============
def _http_get(url, referer=None):
    from urllib.request import urlopen, Request
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    if referer:
        headers['Referer'] = referer
    req = Request(url, headers=headers)
    return urlopen(req, timeout=15).read().decode('utf-8', errors='ignore')


# ============ 各源解析（统一返回 [(issue,b,s,g,next_code), ...]） ============
def _parse_huiniao(data):
    return [(it['code'], int(it['one']), int(it['two']), int(it['three']), it.get('next_code'))
            for it in data['data']['data']['list']]


def _parse_apihz(data):
    if data.get('code') != 200:
        return []
    nums = str(data.get('number', '')).split('|')
    if len(nums) != 3:
        return []
    try:
        return [(data['qihao'], int(nums[0]), int(nums[1]), int(nums[2]), None)]
    except (KeyError, ValueError):
        return []


def _parse_17500(raw):
    draws = []
    lines = [l for l in raw.strip().split('\n') if l.strip()]
    for l in lines[-6:]:
        p = l.split()
        if len(p) >= 5 and re.match(r'^20\d{5}$', p[0]):
            draws.append((p[0], int(p[2]), int(p[3]), int(p[4]), None))
    return draws


def _parse_html_3d(raw):
    """通用HTML兜底：抓 20xxxxx 期号 + 紧跟的三个0-9数字"""
    draws = []
    for m in re.finditer(r'(20\d{5})[^\d]{0,30}?(\d)\D+(\d)\D+(\d)', raw):
        issue, b, s, g = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
        if 0 <= b <= 9 and 0 <= s <= 9 and 0 <= g <= 9:
            draws.append((issue, b, s, g, None))
    # 去重保序
    seen, out = set(), []
    for d in draws:
        if d[0] not in seen:
            seen.add(d[0]); out.append(d)
    return out


DATA_SOURCES = [
    {'name': 'huiniao', 'kind': 'json',
     'url': 'https://api.huiniao.top/interface/home/lotteryHistory?type=fcsd&page=1&limit=5',
     'parser': _parse_huiniao},
    {'name': '17500', 'kind': 'txt17500',
     'url': 'https://www.17500.cn/getData/3d.TXT'},
    {'name': 'apihz', 'kind': 'json',
     'url': 'https://cn.apihz.cn/api/caipiao/fucai3d.php?id=88888888&key=88888888',
     'parser': _parse_apihz},
    {'name': 'cwl', 'kind': 'json', 'referer': 'https://www.cwl.gov.cn/',
     'url': 'https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?name=3d&issueCount=5',
     'parser': lambda d: [(it['code'], int(it['red'].split(',')[0]), int(it['red'].split(',')[1]),
                           int(it['red'].split(',')[2]), None) for it in d.get('result', [])]},
    {'name': '55128', 'kind': 'html',
     'url': 'https://www.55128.cn/zous/3d-5.htm'},
    {'name': '8200', 'kind': 'html',
     'url': 'https://3d.8200.cn/'},
]


# ============ 本地CSV ============
def load_existing_rows():
    rows, out_of_order, prev = {}, False, None
    try:
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                iss = row['issue']
                try:
                    b, s, g = int(row['hundreds']), int(row['tens']), int(row['ones'])
                except (KeyError, ValueError):
                    continue
                rows[iss] = (b, s, g)
                if prev is not None and iss < prev:
                    out_of_order = True
                prev = iss
    except FileNotFoundError:
        pass
    return rows, out_of_order


def fetch_latest():
    rows, _ = load_existing_rows()
    local_last = max(rows.keys(), key=int) if rows else None
    if local_last:
        print(f"  本地最新期号: {local_last}")

    for src in DATA_SOURCES:
        try:
            raw = _http_get(src['url'], referer=src.get('referer'))
            if src['kind'] == 'json':
                draws = src['parser'](json.loads(raw))
            elif src['kind'] == 'txt17500':
                draws = _parse_17500(raw)
            elif src['kind'] == 'html':
                draws = _parse_html_3d(raw)
            else:
                draws = []

            if not draws:
                print(f"  [{src['name']}] 无数据, 尝试下一个...")
                continue
            src_latest = max(int(d[0]) for d in draws)
            if local_last and src_latest <= int(local_last):
                print(f"  [{src['name']}] 期号{src_latest}<=本地{local_last}, 无新数据, 跳过")
                continue
            print(f"  [{src['name']}] ✓ 获取{len(draws)}条, 最新{max(d[0] for d in draws)}")
            return {src['name']: draws}
        except Exception as e:
            print(f"  [{src['name']}] ✗ {str(e)[:70]}")
    print("  ❌ 所有数据源均失败或无新数据，使用现有CSV")
    return {}


def append_to_csv(new_draws, local_last=None):
    """只追加比本地最新期号更新的期号，防止乱序/伪造旧期倒灌污染历史"""
    rows, was_oos = load_existing_rows()
    if local_last is None:
        local_last = max(rows.keys(), key=int) if rows else None
    added = 0
    for item in new_draws:
        issue, b, s, g = item[0], item[1], item[2], item[3]
        if not (isinstance(issue, str) and issue.startswith('20') and 7 <= len(issue) <= 8):
            continue
        if not all(isinstance(x, int) and 0 <= x <= 9 for x in [b, s, g]):
            continue
        # 防倒灌：必须严格晚于本地最新期号
        if local_last and int(issue) <= int(local_last):
            continue
        if issue in rows:
            if rows[issue] != (b, s, g):
                print(f"  ⚠ 期号{issue}不一致 {rows[issue]} vs {(b,s,g)}，保留原值")
            continue
        rows[issue] = (b, s, g)
        added += 1
        print(f"  新增: {issue} = {b}{s}{g}")
    if added == 0 and not was_oos:
        return 0
    d = os.path.dirname(CSV_PATH)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(CSV_PATH, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['issue', 'hundreds', 'tens', 'ones'])
        for iss in sorted(rows.keys()):
            b, s, g = rows[iss]
            w.writerow([iss, b, s, g])
    # 写后强校验：确认新增期号真的落盘（防静默丢失，fail fast）
    verify, _ = load_existing_rows()
    missing = [iss for iss in rows if iss not in verify]
    if missing:
        raise IOError(f"CSV写入校验失败，缺失期号: {missing[:5]}...")
    return added


def sync_data():
    """一键：抓数据 → 追加CSV。返回 (next_code, added)"""
    print("[同步] 多源降级抓取最新开奖...")
    rows, _ = load_existing_rows()
    local_last = max(rows.keys(), key=int) if rows else None
    fetched = fetch_latest()
    next_code = None
    added = 0
    if fetched:
        _, draws = list(fetched.items())[0]
        latest_draw = max(draws, key=lambda d: int(d[0]))
        if len(latest_draw) > 4 and latest_draw[4]:
            next_code = str(latest_draw[4])
            print(f"  下期期号(数据源): {next_code}")
        added = append_to_csv(draws, local_last=local_last)
        print(f"  新增{added}期")
    else:
        print("  无新数据，沿用现有CSV")
    return next_code, added


if __name__ == '__main__':
    sync_data()
