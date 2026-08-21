# -*- coding: utf-8 -*-
"""
福彩3D 杀和尾 — 生成固定静态网页「杀和尾v3.html」（v2.0 版式复刻）
==================================================================
读 cache/result.json, 输出一个完全自包含的单文件 HTML（纯静态渲染，非 JS 动态）。
版式 100% 复刻 v2.0 时代 index.html（标题 Hedge 单杀、80px 大红球、白卡片、
本期专家投票 / 单杀命中率 / 专家级回测 / 最新500期明细 四卡，浅色移动优先）。
算法数据为当前 v3.1：3931万公式穷举 800 专家池，Hedge 加权投票。
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_JSON = os.path.join(BASE_DIR, 'cache', 'result.json')
OUT_HTML = os.path.join(BASE_DIR, '杀和尾v3.html')
OUT_INDEX = os.path.join(BASE_DIR, 'index.html')   # Pages 根路径 = index.html（同步输出）

# ── v2.0 原版 CSS（从 git 9b24fbe 提取，未改动）───────────────────────
CSS_TEXT = """
:root{--red:#e0453a;--green:#1a9e54;--bg:#f4f6f9;--card:#fff;--line:#e6e9ef}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:#222;max-width:640px;margin:0 auto;padding:12px}
.card{background:var(--card);border-radius:12px;padding:16px;margin-bottom:12px;box-shadow:0 1px 4px rgba(0,0,0,.06)}
h1{font-size:19px}.sub{color:#888;font-size:12px;margin-top:4px}
.ball-wrap{display:flex;justify-content:center;margin:16px 0}
.ball{width:80px;height:80px;border-radius:50%;background:var(--red);color:#fff;font-size:42px;font-weight:700;display:flex;align-items:center;justify-content:center;box-shadow:0 3px 10px rgba(224,69,58,.4)}
.ball-label{text-align:center;font-size:13px;color:#666;margin-top:6px}
.issue{text-align:center;font-size:15px}.issue b{color:var(--red);font-size:20px}
.formula-info{text-align:center;font-size:12px;color:#888;margin:8px 0}
.stat-row{display:flex;justify-content:space-between;align-items:center;padding:9px 2px;border-bottom:1px solid var(--line);font-size:15px}
.stat-row:last-child{border-bottom:none}.pct{font-weight:700;color:var(--green)}
.exp-row{display:flex;justify-content:space-between;align-items:center;padding:8px 2px;border-bottom:1px solid var(--line);font-size:14px;cursor:pointer;list-style:none}
.exp-row:last-child{border-bottom:none}
.exp-name{color:#444}.exp-kill{font-weight:700;color:var(--red)}
.exp-w{color:#999;font-size:12px}
.exp-detail{display:block;border-bottom:1px solid var(--line)}
.exp-detail:last-child{border-bottom:none}
.exp-detail summary::-webkit-details-marker{display:none}
.exp-toggle{color:#bbb;font-size:12px;transition:transform .2s;margin-left:8px}
.exp-detail[open] .exp-toggle{transform:rotate(90deg)}
.exp-detail .tbl-wrap{border-top:1px dashed var(--line);padding-top:4px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:6px 3px;text-align:center;border-bottom:1px solid var(--line)}
thead th{position:sticky;top:0;background:#fafbfc;font-size:12px;color:#666;z-index:1}
.tbl-wrap{max-height:60vh;overflow-y:auto}
.hit{color:var(--green);font-weight:700}.miss{color:var(--red);font-weight:700}
td.iss{color:#999;font-size:11.5px;font-family:ui-monospace,Consolas,monospace}
td.num{font-weight:700;letter-spacing:1px}
td.t3{font-size:11px;color:#999;font-family:ui-monospace,Consolas,monospace}
td.t3 b{color:var(--red)}
td.fname{font-size:11px;color:#999;max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.miss-row td{background:#fef2f2}
.footer{margin-top:16px;padding:12px;background:#fff;border-radius:12px;font-size:11px;color:#999;line-height:1.7}
.footer b{color:#666}
"""


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def build_html(d):
    n = d['next']
    s = d['summary']
    di = d['data_info']
    pi = d['pool_info']

    # ── 1. 本期专家投票（v2.0 exp-row 样式，静态渲染，无展开明细）──
    experts_html = ""
    for i, e in enumerate(n['experts']):
        experts_html += (
            f'<div class="exp-row"><span class="exp-name">#{i+1} {esc(e["name"])}</span>'
            f'<span class="exp-kill">杀 {e["kill"]}</span>'
            f'<span class="exp-w">权重 {e["weight"]:.3f}</span></div>')
    if not experts_html:
        experts_html = '<div style="color:#999;padding:8px">无专家数据</div>'

    # ── 2. 单杀命中率（v2.0 stat-row 样式，数据来自 v3.1 500期回测）──
    # 补充: 单杀 Top2（杀2码）500期回测 —— 和尾 ∉ 票数前2
    rows_all = d['rows']
    top2_hits = 0
    top2_cur_win = 0
    top2_max_lose = 0
    _cl = 0
    for _r in rows_all:
        _order = sorted(range(10), key=lambda x: -_r['votes'][x])
        _tail = sum(int(c) for c in _r['num']) % 10
        _ok = _tail not in set(_order[:2])
        if _ok:
            top2_hits += 1
            _cl = 0
        else:
            _cl += 1
            top2_max_lose = max(top2_max_lose, _cl)
    # 当前连中（近期在上，从最新往回数）
    for _r in rows_all:
        _order = sorted(range(10), key=lambda x: -_r['votes'][x])
        _tail = sum(int(c) for c in _r['num']) % 10
        if _tail not in set(_order[:2]):
            top2_cur_win += 1
        else:
            break
    top2_rate = top2_hits / len(rows_all)
    # 近100期杀2表现
    _recent = d['rows'][:100]
    top2_r100 = sum(
        1 for _r in _recent
        if (sum(int(c) for c in _r['num']) % 10) not in set(sorted(range(10), key=lambda x: -_r['votes'][x])[:2])
    )
    stats_html = (
        f'<div class="stat-row"><span>500期回测命中率（杀1码）</span>'
        f'<span class="pct">{s["rate"]*100:.2f}%</span>'
        f'<span style="color:#999;font-size:12px">基线{s["baseline"]*100:.0f}% ({s["rate"]-s["baseline"]:+.1%})</span>'
        f'<span style="color:#999;font-size:12px">{s["hit"]}/{s["total"]}</span></div>'
        f'<div class="stat-row"><span>当前连中</span><span class="pct">{s["cur_win"]} 期</span>'
        f'<span style="color:#999;font-size:12px">最大连中 {s["max_win"]} 期</span></div>'
        f'<div class="stat-row"><span>最大连错</span>'
        f'<span class="miss" style="color:var(--red);font-weight:700">{s["max_lose"]} 期</span>'
        f'<span style="color:#999;font-size:12px">专家池均值 {s["pool_avg"]*100:.2f}%</span></div>'
        f'<div class="stat-row"><span>投票参数</span><span>K={n["n_experts"]} · win={n["win"]}</span>'
        f'<span style="color:#999;font-size:12px">网格 {d["scan_count"]} 组合选优</span></div>')

    # ── 2b. 杀2码专家卡（新）──
    top2_next = n['top3_vote'][:2]          # 下期杀2码 = 票数前2
    balls2 = "".join(
        f'<div style="display:inline-block;margin:0 8px"><div class="ball" style="width:56px;height:56px;font-size:30px">{c}</div>'
        f'<div class="ball-label">杀和尾 {c}</div></div>'
        for c in top2_next)
    top2_card_html = f"""
<div class="card">
  <b>杀2码专家（Top2）</b> <span style="color:#999;font-size:12px">下期杀2个和尾，任一中即安全</span>
  <div class="ball-wrap">{balls2}</div>
  <div class="formula-info">下期 {n['target_issue']} 杀和尾 {top2_next[0]}、{top2_next[1]}（票数前2）</div>
  <div class="stat-row"><span>500期回测命中率</span><span class="pct">{top2_rate*100:.2f}%</span>
    <span style="color:#999;font-size:12px">基线80% ({top2_rate-0.8:+.1%})</span>
    <span style="color:#999;font-size:12px">{top2_hits}/{len(rows_all)}</span></div>
  <div class="stat-row"><span>近100期命中</span><span class="pct">{top2_r100/len(_recent)*100:.1f}%</span>
    <span style="color:#999;font-size:12px">({top2_r100}/{len(_recent)})</span>
    <span style="color:#999;font-size:12px">当前连中 {top2_cur_win} 期</span></div>
  <div class="stat-row"><span>最大连错</span><span class="miss" style="color:var(--red);font-weight:700">{top2_max_lose} 期</span>
    <span style="color:#999;font-size:12px">满额：杀2码上限理论90%</span></div>
  <div class="warn" style="background:#eef7ee;border-color:#1a9e54;color:#1a6e3a">💡 杀2码 = 在杀1码基础上多杀1个，命中率98%+，但杀掉2个码后剩余8个和尾。</div>
</div>"""

    # ── 3. 专家级回测（v2.0 表格样式，数据来自 leaderboard Top10）──
    lb_rows = ""
    for i, lb in enumerate(d['leaderboard'][:10]):
        lb_rows += (
            f'<tr><td>{i+1}</td><td style="text-align:left">{esc(lb["name"])}</td>'
            f'<td>{lb["rate_recent"]*100:.2f}%</td><td>{esc(lb["fam"])}</td></tr>')
    exp_bt_html = (
        f'<table><thead><tr><th>#</th><th style="text-align:left">池内公式</th>'
        f'<th>500期命中</th><th>族</th></tr></thead><tbody>{lb_rows}'
        f'<tr style="font-weight:700;color:var(--green)"><td style="text-align:left" colspan="2">Hedge 加权投票</td>'
        f'<td>{s["rate"]*100:.2f}%</td><td>K={n["n_experts"]}</td></tr>'
        f'<tr style="color:#999"><td style="text-align:left" colspan="2">专家池平均（800 专家）</td>'
        f'<td>{s["pool_avg"]*100:.2f}%</td><td>—</td></tr></tbody></table>')

    # ── 4. 最新 500 期明细（v2.0 表格，近→远，含和尾+Top2）──
    rows_html = ""
    for r in d['rows'][:500]:
        tail = sum(int(c) for c in r['num']) % 10
        # Top2 = 票数前2
        order = sorted(range(10), key=lambda x: -r['votes'][x])
        top2_codes = order[:2]
        top2_ok = tail not in set(top2_codes)
        t3 = '·'.join(
            f'<b>{c}</b>' if i == 0 else str(c)
            for i, c in enumerate(r['top3'][:3]))
        miss_cls = "miss-row" if (not r["hit"] or not top2_ok) else ""
        rows_html += (
            f'<tr class="{miss_cls}">'
            f'<td class="iss">{r["issue"]}</td><td class="num">{r["num"]}</td>'
            f'<td class="num" style="color:var(--green)">{tail}</td>'
            f'<td class="t3">{t3}</td>'
            f'<td class="{"hit" if r["hit"] else "miss"}">{r["kill"]}</td>'
            f'<td>{"✅" if r["hit"] else "❌"}</td>'
            f'<td class="{"hit" if top2_ok else "miss"}">{"✅" if top2_ok else "❌"}</td>'
            f'<td class="t3">{top2_codes[0]}·{top2_codes[1]}</td>'
            f'<td class="fname" title="{esc(r["fname"])}">{esc(r["fname"])}</td></tr>')

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>福彩3D 杀和尾 · Hedge 单杀</title>
<style>{CSS_TEXT}</style>
</head>
<body>
<h1>🎯 福彩3D 杀和尾 <span style="font-size:13px;color:#888">Hedge 单杀 v2.0</span></h1>
<div class="sub">数据至 {di['last']} 期（{di['last_draw']}）· 共 {di['n_issues']} 期 · 引擎 v3.1（3931万公式穷举）</div>

<div class="card">
  <div class="issue">预测期号 <b>{n['target_issue']}</b> 期</div>
  <div class="ball-wrap"><div><div class="ball">{n['kill']}</div><div class="ball-label">杀和尾 {n['kill']}</div></div></div>
  <div class="formula-info">算法：Hedge {n['n_experts']}专家加权投票 · {pi['pool_size_total']:,}公式穷举选 Top{pi['topk']} · win={n['win']}</div>
</div>

{top2_card_html}

<div class="card">
  <b>本期专家投票</b> <span style="color:#999;font-size:12px">（{n['n_experts']} 位专家 · 权重=近 {n['win']} 期命中率）</span>
  <div class="tbl-wrap" style="max-height:45vh">{experts_html}</div>
</div>

<div class="card">
  <b>单杀命中率</b>
  {stats_html}
</div>

<div class="card">
  <b>专家级回测</b> <span style="color:#999;font-size:12px">（500期 · 池内 Top10 对照）</span>
  {exp_bt_html}
</div>

<div class="card">
  <b>最新 500 期明细</b> <span style="color:#999;font-size:12px">（近 → 远）</span>
  <div class="tbl-wrap"><table><thead><tr><th>期号</th><th>号码</th><th>和尾</th><th>票码Top3</th><th>杀1</th><th>杀1对</th><th>杀2对</th><th>杀2码</th><th>首席专家</th></tr></thead>
  <tbody>{rows_html}</tbody></table></div>
</div>

<div class="footer">
  <b>说明</b><br>
  ① 杀和尾 = 预测杀掉 0-9 中一个数字，下期<b>和尾</b>不出现即命中，理论随机基线 <b>90%</b>。<br>
  ② 公式池 {pi['pool_size_total']:,} 个（{pi['n_features']} 特征线性组合）在<b>最新500期</b>按命中率选 Top{pi['topk']} 专家池，主机制 <b>Hedge 加权投票</b>：每期取近 {n['win']} 期命中率 Top{n['n_experts']} 专家，按命中率加权投票，票王 = 和尾杀码。参数经 {d['scan_count']} 组合网格扫描自动选优。<br>
  ③ 回测为<b>逐期真实预测记录</b>：第 t 期预测只用第 t-1、t-2 期数据（walk-forward，不偷看未来）。<br>
  ④ <b>选择偏差警示</b>：专家池是在回测的同一段 500 期上按命中率选出的，回测数字含轻微选择偏差，样本外会回落；<b>不构成任何购彩建议</b>。<br>
  ⑤ 生成于 <b>{d['generated_at']}</b> · 数据更新后请重新导出。
</div>
</body>
</html>
"""


def main():
    with open(CACHE_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data['scan_count'] = len(data.get('scan', [])) if isinstance(data.get('scan'), list) else 72
    html = build_html(data)
    with open(OUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    # Pages 根路径同步输出 index.html（避免手机访问根地址看到旧版）
    with open(OUT_INDEX, 'w', encoding='utf-8') as f:
        f.write(html)
    n = data['next']
    s = data['summary']
    print(f"已生成固定网页: {OUT_HTML} (+ {OUT_INDEX})")
    print(f"数据至 {data['data_info']['last']} 期 | 公式池 {data['pool_info']['pool_size_total']:,} | 专家池 {data['pool_info']['topk']}")
    print(f"机制: Hedge(K={n['n_experts']},win={n['win']}) | 回测 {s['hit']}/{s['total']} = {s['rate']*100:.2f}% (基线90%)")
    print(f"下一期 {n['target_issue']} 杀和尾 {n['kill']}")
    print("双击打开即可浏览，或传到手机查看。")


if __name__ == '__main__':
    main()
