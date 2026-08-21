# -*- coding: utf-8 -*-
"""
福彩3D 杀和尾 — 生成固定静态网页「index.html」（v2.0 版式复刻）
==================================================================
读 cache/result.json, 输出一个完全自包含的单文件 HTML（纯静态渲染，非 JS 动态）。
版式 100% 复刻 v2.0 时代 index.html（标题 Hedge 单杀、80px 大红球、白卡片、
本期专家投票 / 单杀命中率 / 专家级回测 / 最新500期明细 四卡，浅色移动优先）。
算法数据为当前 v3.1：3931万公式穷举 800 专家池（每日随最新500期重选），
win/k 参数每日网格扫描自动选优，500期回测逐期真实（walk-forward）。
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_JSON = os.path.join(BASE_DIR, 'cache', 'result.json')
OUT_HTML = os.path.join(BASE_DIR, 'index.html')   # 唯一输出: Pages 根路径 = index.html

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
/* ── 手机端优化（2026-08-21）── */
.tbl-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.tbl-scroll table{min-width:580px}
.dot-row{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px;align-items:center}
.dot{width:16px;height:16px;border-radius:50%;font-size:9px;line-height:16px;text-align:center;color:#fff;flex:0 0 auto}
.dot-ok{background:var(--green)}.dot-bad{background:var(--red)}
.dot-row .dl{font-size:11px;color:#999;margin-left:2px}
.pick-card{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.pick-card .ball{width:64px;height:64px;font-size:34px}
@media (max-width:480px){
  body{padding:8px}
  .card{padding:12px;border-radius:10px;margin-bottom:10px}
  h1{font-size:17px}
  .ball{width:68px;height:68px;font-size:36px}
  table{font-size:12px}
  th,td{padding:5px 3px}
  .tbl-scroll table{min-width:560px}
  td.fname{max-width:80px}
}
/* ── v3.1 前瞻焦点重构（2026-08-21）── */
.hero{background:linear-gradient(135deg,#e0453a,#c73a2f);color:#fff;border-radius:14px;padding:20px 16px;margin-bottom:12px;box-shadow:0 4px 14px rgba(224,69,58,.35);text-align:center}
.hero .tag{display:inline-block;background:rgba(255,255,255,.2);border-radius:20px;padding:3px 12px;font-size:12px;margin-bottom:8px}
.hero .big-issue{font-size:15px;opacity:.95}
.hero .big-issue b{font-size:22px;color:#fff}
.hero .big-ball{width:104px;height:104px;border-radius:50%;background:#fff;color:var(--red);font-size:56px;font-weight:800;display:flex;align-items:center;justify-content:center;margin:14px auto;box-shadow:0 6px 18px rgba(0,0,0,.25)}
.hero .big-label{font-size:13px;opacity:.95;margin-top:4px}
.hero .hero-sub{font-size:12px;opacity:.8;margin-top:10px;line-height:1.6}
.hero .hero-sub b{color:#fff}
.hero2{display:flex;gap:8px;margin-top:12px;justify-content:center}
.hero2 .h2ball{width:52px;height:52px;border-radius:50%;background:rgba(255,255,255,.95);color:var(--red);font-size:28px;font-weight:700;display:flex;align-items:center;justify-content:center}
.hero2 .h2label{font-size:11px;opacity:.9;margin-top:3px}
.hero2>div{text-align:center}
details.collapse{border-radius:10px;overflow:hidden}
details.collapse>summary{cursor:pointer;padding:10px 14px;font-size:13px;color:#666;background:#fafbfc;user-select:none;list-style:none;display:flex;justify-content:space-between;align-items:center}
details.collapse>summary::-webkit-details-marker{display:none}
details.collapse>summary .arrow{transition:transform .2s;color:#bbb;font-size:11px}
details.collapse[open]>summary .arrow{transform:rotate(180deg)}
details.collapse[open]>summary{border-bottom:1px solid var(--line)}
details.collapse>.inner{padding:12px}
.collapse{margin-bottom:12px}
.now-card{background:#fff8e6;border:1.5px solid #f0c36d;border-radius:10px;padding:12px 14px;margin-bottom:12px;font-size:13px;color:#7a5a00;line-height:1.7}
.now-card b{color:#a06a00}

"""


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def load_ledger():
    """读取发布账本（逐期真实预测记录）。失败返回空列表。"""
    try:
        import json as _json
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache', 'predictions.json')
        with open(p, 'r', encoding='utf-8') as f:
            return _json.load(f).get('records', [])
    except Exception:
        return []


def ledger_rows_html(records, limit=100):
    """账本渲染：逐期真实发布记录（近→远）。含发布时刻列。"""
    rows_html = ""
    for r in records[:limit]:
        hit = r.get('hit')
        kill = r.get('kill')
        tail = r.get('tail')
        if tail is None or hit is None:
            # 未开奖：显示"待开奖"
            cls = ""
            rows_html += (
                f'<tr><td class="iss">{esc(r.get("issue",""))}</td>'
                f'<td class="num">—</td><td class="num">—</td>'
                f'<td class="t3">—</td>'
                f'<td class="num">{kill}</td>'
                f'<td style="color:#bbb">⏳</td>'
                f'<td class="t3">{esc("·".join(str(x) for x in r.get("top2", [])))}</td>'
                f'<td class="t3">{esc(r.get("published_at","")[:16])}</td></tr>')
        else:
            cls = "miss-row" if not hit else ""
            ok2 = tail not in set(r.get("top2", []))
            rows_html += (
                f'<tr class="{cls}"><td class="iss">{esc(r.get("issue",""))}</td>'
                f'<td class="num">{esc(r.get("num",""))}</td>'
                f'<td class="num" style="color:var(--green)">{tail}</td>'
                f'<td class="t3">—</td>'
                f'<td class="{"hit" if hit else "miss"}">{kill}</td>'
                f'<td>{"✅" if hit else "❌"}</td>'
                f'<td class="{"hit" if ok2 else "miss"}">{"✅" if ok2 else "❌"}</td>'
                f'<td class="t3">{esc("·".join(str(x) for x in r.get("top2", [])))}</td>'
                f'<td class="t3">{esc(r.get("published_at","")[:16])}</td></tr>')
    return rows_html


def backtest_rows_html(d, limit=100):
    """500期回测明细（walk-forward 逐期真实，近期在上）。
    注：v3.1 专家池每日重选，本表为当日窗口下的回测（每天可能略有变化）。"""
    rows_html = ""
    for r in d['rows'][:limit]:
        cls = "miss-row" if not r['hit'] else ""
        order = sorted(range(10), key=lambda x: -r['votes'][x])
        tail = sum(int(c) for c in r['num']) % 10
        top3 = "·".join(str(c) for c in order[:3])
        fname = r.get('fname', '')
        fam = r.get('fam', '')
        rows_html += (
            f'<tr class="{cls}"><td class="iss">{esc(r["issue"])}</td>'
            f'<td class="num">{esc(r["num"])}</td>'
            f'<td class="num" style="color:var(--green)">{tail}</td>'
            f'<td class="t3">{r["rate"]*100:.1f}%</td>'
            f'<td class="{"hit" if r["hit"] else "miss"}">{r["kill"]}</td>'
            f'<td>{"✅" if r["hit"] else "❌"}</td>'
            f'<td class="t3">{top3}</td>'
            f'<td class="fname">{esc(fname)}</td></tr>')
    return rows_html


def ledger_stats(records):
    """账本命中率统计（只看已开奖的）"""
    settled = [r for r in records if r.get('hit') is not None]
    if not settled:
        return None
    hits = sum(1 for r in settled if r['hit'])
    top2_hits = sum(1 for r in settled if r.get('tail') not in set(r.get('top2', [])))
    cur = 0
    for r in settled:  # records 近→远
        if r['hit']:
            cur += 1
        else:
            break
    return {'total': len(settled), 'hits': hits, 'rate': hits / len(settled),
            'top2_rate': top2_hits / len(settled), 'cur_win': cur}


def build_html(d):
    n = d['next']
    s = d['summary']
    di = d['data_info']
    pi = d['pool_info']

    # 真实发布记录（账本）
    ledger_records = load_ledger()
    ledger_rows = ledger_rows_html(ledger_records, limit=100)
    ledger_stat = ledger_stats(ledger_records)

    # 500期回测明细（walk-forward 逐期真实）
    backtest_rows = backtest_rows_html(d, limit=100)

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
        f'<span style="color:#999;font-size:12px">网格 {d["scan_count"]} 组合每日选优</span></div>')

    # ── 2b. 杀2码（下期杀2码 = 票数前2）──
    top2_next = n['top3_vote'][:2]          # 下期杀2码 = 票数前2
    balls2 = "".join(
        f'<div style="text-align:center;margin:0 6px"><div class="ball" style="width:56px;height:56px;font-size:30px">{c}</div>'
        f'<div class="ball-label">杀和尾 {c}</div></div>'
        for c in top2_next)

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

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>福彩3D 杀和尾 · Hedge 单杀</title>
<style>{CSS_TEXT}</style>
</head>
<body>
<h1>🎯 福彩3D 杀和尾 <span style="font-size:13px;color:#888">Hedge 单杀 v3.1</span></h1>
<div class="sub">数据至 {di['last']} 期（{di['last_draw']}）· 共 {di['n_issues']} 期 · 每日重选专家池</div>

<!-- ═══ 下一期预测 = 页面唯一焦点（开奖前发布）═══ -->
<div class="hero">
  <div class="tag">🎯 下一期预测 · 开奖前发布</div>
  <div class="big-issue">预测期号 <b>{n['target_issue']}</b> 期</div>
  <div class="big-ball">{n['kill']}</div>
  <div class="big-label">杀和尾 {n['kill']}（杀1码）</div>
  <div class="hero2">
    <div><div class="h2ball">{top2_next[0]}</div><div class="h2label">杀2码</div></div>
    <div><div class="h2ball">{top2_next[1]}</div><div class="h2label">杀2码</div></div>
  </div>
  <div class="hero-sub">Hedge {n['n_experts']}专家加权投票 · win={n['win']} · 每日重选<br>算法回测 {s['rate']*100:.2f}%（500期 · 基线{s['baseline']*100:.0f}%）</div>
</div>

<div class="now-card">
  ⏰ <b>本期杀 {n['kill']}</b>：下一期 {n['target_issue']} 的<b>和尾</b>若等于 {n['kill']} 即杀错，其余 9 个和尾都安全（杀1码）；杀2码 = 和尾不是 {top2_next[0]}、{top2_next[1]} 都安全。<br>
  历史数据只是参考，真正的预测就是上方这个红球。
</div>

<!-- ═══ 历史数据（全部折叠，不影响前瞻焦点）═══ -->
<details class="collapse" open>
  <summary>📊 单杀命中率与投票参数 <span class="arrow">▼</span></summary>
  <div class="inner">{stats_html}</div>
</details>

<details class="collapse">
  <summary>🧪 杀2码专家（Top2）统计 <span class="arrow">▼</span></summary>
  <div class="inner">
    <div class="formula-info">下期 {n['target_issue']} 杀和尾 {top2_next[0]}、{top2_next[1]}（票数前2）</div>
    <div class="stat-row"><span>500期回测命中率</span><span class="pct">{top2_rate*100:.2f}%</span>
      <span style="color:#999;font-size:12px">基线80% ({top2_rate-0.8:+.1%})</span>
      <span style="color:#999;font-size:12px">{top2_hits}/{len(rows_all)}</span></div>
    <div class="stat-row"><span>近100期命中</span><span class="pct">{top2_r100/len(_recent)*100:.1f}%</span>
      <span style="color:#999;font-size:12px">({top2_r100}/{len(_recent)})</span>
      <span style="color:#999;font-size:12px">当前连中 {top2_cur_win} 期</span></div>
    <div class="stat-row"><span>最大连错</span><span class="miss" style="color:var(--red);font-weight:700">{top2_max_lose} 期</span>
      <span style="color:#999;font-size:12px">满额：杀2码上限理论90%</span></div>
  </div>
</details>

<details class="collapse">
  <summary>👨‍🔬 本期专家投票（Top{n['n_experts']}） <span class="arrow">▼</span></summary>
  <div class="inner"><div class="tbl-wrap" style="max-height:45vh">{experts_html}</div></div>
</details>

<details class="collapse">
  <summary>🏆 专家级回测（500期 Top10） <span class="arrow">▼</span></summary>
  <div class="inner">{exp_bt_html}</div>
</details>

<details class="collapse">
  <summary>📜 最新 500 期回测表（walk-forward 逐期真实） <span class="arrow">▼</span></summary>
  <div class="inner">
    <div class="dot-row"><span class="dot dot-ok">✓</span><span class="dl">杀对</span><span class="dot dot-bad">✗</span><span class="dl">杀错</span><span class="dl" style="margin-left:8px">专家池平均命中率</span></div>
    <div class="tbl-scroll"><div class="tbl-wrap"><table><thead><tr><th>期号</th><th>号码</th><th>和尾</th><th>专家均</th><th>杀1</th><th>对错</th><th>票码Top3</th><th>主投专家</th></tr></thead>
    <tbody>{backtest_rows}</tbody></table></div></div>
  </div>
</details>

<details class="collapse">
  <summary>📝 真实发布记录（逐期开奖前发布） <span class="arrow">▼</span></summary>
  <div class="inner">
    <div class="dot-row"><span class="dot dot-ok">✓</span><span class="dl">杀对</span><span class="dot dot-bad">✗</span><span class="dl">杀错</span><span class="dl" style="margin-left:8px">⏳待开奖</span></div>
    <div class="tbl-scroll"><div class="tbl-wrap"><table><thead><tr><th>期号</th><th>号码</th><th>和尾</th><th>—</th><th>杀1</th><th>杀1对</th><th>杀2对</th><th>杀2码</th><th>发布时间</th></tr></thead>
    <tbody>{ledger_rows}</tbody></table></div></div>
  </div>
</details>

<div class="footer">
  <b>说明</b><br>
  ① 杀和尾 = 预测杀掉 0-9 中一个数字，下期<b>和尾</b>不出现即命中，理论随机基线 <b>90%</b>。<br>
  ② 公式池 {pi['pool_size_total']:,} 个（{pi['n_features']} 特征线性组合）在<b>最新500期</b>按命中率选 Top{pi['topk']} 专家池（<b>每日随窗口重选</b>）；主机制 <b>Hedge 加权投票</b>：每期取近 {n['win']} 期命中率 Top{n['n_experts']} 专家，按命中率加权投票，票王 = 和尾杀码。参数 win={n['win']}/K={n['n_experts']} 经 {d['scan_count']} 组合网格扫描<b>每日自动选优</b>。<br>
  ③ 上方【真实发布记录】为<b>逐期开奖前发布的预测</b>：第 t 期发布时只用第 t-1、t-2 期及更早数据（walk-forward，不偷看未来），发布后存档、开奖后自动补标对错。<br>
  ④ <b>选择偏差警示</b>：专家池是在回测的同一段 500 期上按命中率选出的，算法回测数字含轻微选择偏差，样本外会回落；<b>不构成任何购彩建议</b>。<br>
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
    n = data['next']
    s = data['summary']
    print(f"已生成固定网页: {OUT_HTML}")
    print(f"数据至 {data['data_info']['last']} 期 | 公式池 {data['pool_info']['pool_size_total']:,} | 专家池 {data['pool_info']['topk']}")
    print(f"机制: Hedge(K={n['n_experts']},win={n['win']}) | 回测 {s['hit']}/{s['total']} = {s['rate']*100:.2f}% (基线90%)")
    print(f"下一期 {n['target_issue']} 杀和尾 {n['kill']}")
    print("双击打开即可浏览，或传到手机查看。")


if __name__ == '__main__':
    main()
