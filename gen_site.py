# -*- coding: utf-8 -*-
"""
福彩3D 杀和尾 — 生成固定静态网页「index.html」（v2.0 版式复刻）
==================================================================
读 cache/result.json, 输出一个完全自包含的单文件 HTML（纯静态渲染，非 JS 动态）。
当前版式：卡片1(期号+三球+得票数) + Hedge 加权投票详情卡，浅色移动优先。
算法数据为当前 v3 锁定模式：3931万公式穷举 800 专家池【永久固定】，
win/k 参数【锁定】→ 每天发布的预测 = 开奖完回测表同一期数值（确定性，可对账）。
"""
import json
import os
import sys

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
.ball-votes{text-align:center;font-size:13px;color:#999;margin-top:8px;white-space:nowrap;line-height:1.3}
.ball-label{text-align:center;font-size:13px;color:#666;margin-top:4px}
.issue{text-align:center;font-size:15px}.issue b{color:var(--red);font-size:20px}
.issue-flex{display:grid;grid-template-columns:1fr auto 1fr;align-items:baseline;gap:10px;text-align:center}
.issue-flex b{color:var(--red);line-height:1.15;margin-right:-2px;justify-self:center}
.issue-pre{color:#444;font-size:14px;white-space:nowrap;justify-self:end}
.issue-post{color:#444;font-size:14px;white-space:nowrap;justify-self:start}
@media (max-width:480px){
  .issue-flex{flex-wrap:nowrap}
  .issue-flex b{font-size:28px !important}
}.formula-info{text-align:center;font-size:12px;color:#888;margin:8px 0}
.stat-row{display:flex;justify-content:space-between;align-items:center;padding:9px 2px;border-bottom:1px solid var(--line);font-size:15px}
.stat-row:last-child{border-bottom:none}.pct{font-weight:700;color:var(--green)}
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
/* ── 手机端优化（2026-08-21）── */
.tbl-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.tbl-scroll table{min-width:580px}
.dot{width:16px;height:16px;border-radius:50%;font-size:9px;line-height:16px;text-align:center;color:#fff;flex:0 0 auto}
.dot-ok{background:var(--green)}.dot-bad{background:var(--red)}
.pick-card{display:flex;gap:8px;align-items:center;flex-wrap:nowrap}
.pick-card .ball{width:64px;height:64px;font-size:34px}
/* ── 双系统切换（2026-08-22）── */
.sys-switch{display:flex;gap:10px;justify-content:center;margin:12px 0 4px}
.sys-btn{border:1.5px solid var(--line);background:var(--card);color:#555;border-radius:20px;padding:7px 18px;font-size:14px;font-weight:600;cursor:pointer;transition:all .15s}
.sys-btn.active{background:var(--red);border-color:var(--red);color:#fff}
.sys-panel{display:none}
.sys-panel.on{display:block}
.sys-badge{display:inline-block;font-size:11px;color:#fff;background:var(--red);border-radius:9px;padding:1px 7px;margin-left:6px;vertical-align:2px}
.sys-btn.active .sys-badge{background:#fff;color:var(--red)}
.sys-badge.gray{background:#999}
/* ── 回测表窗口切换（2026-08-22）── */
.win-switch{display:flex;gap:8px;margin:10px 0 6px;flex-wrap:wrap}
.win-btn{border:1px solid var(--line);background:var(--card);color:#666;border-radius:14px;padding:4px 13px;font-size:12.5px;font-weight:600;cursor:pointer;transition:all .15s}
.win-btn.active{background:var(--green);border-color:var(--green);color:#fff}
@media (max-width:480px){.win-btn{font-size:12px;padding:3px 10px}}
@media (max-width:480px){
  body{padding:8px}
  .card{padding:12px;border-radius:10px;margin-bottom:10px}
  h1{font-size:17px}
  .ball{width:56px;height:56px;font-size:30px}
  .ball-votes{font-size:12px;margin-top:6px}
  .ball-label{font-size:12px}
  .issue b{font-size:30px !important}
  table{font-size:12px}
  th,td{padding:5px 3px}
  .tbl-scroll table{min-width:560px}
  td.fname{max-width:80px}
}
"""


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# ─────────────────────────── 系统A：当前800专家 ───────────────────────────
def render_sysA(d):
    n = d['next']
    s = d['summary']
    di = d['data_info']

    # 预测球（票王1个红球）
    king = int(n['kill'])
    _dist = n.get('top3_vote_dist', [0]*10)
    ball_html = (
        f'<div style="display:flex;justify-content:center;align-items:center;margin:16px 0">'
        f'<div style="display:flex;flex-direction:column;align-items:center">'
        f'<div class="ball">{king}</div>'
        f'<div class="ball-votes">{_dist[king]:.1f} 票</div></div></div>')

    # Hedge 加权投票详情卡
    _maxv = max(_dist) if max(_dist) > 0 else 1
    _order = sorted(range(10), key=lambda x: -_dist[x])
    _medals = {0: '🥇', 1: '🥈', 2: '🥉', 3: '4', 4: '5'}
    _bar_rows = ""
    for _r, _c in enumerate(_order):
        _w = max(int(_dist[_c] / _maxv * 100), 2)
        _is_king = _r == 0
        _row_bg = 'style="background:#fff5f5"' if _is_king else ''
        _rank_txt = f'<b style="color:var(--red)">票王</b>' if _is_king else f'第{_medals.get(_r, str(_r+1))}名'
        _bar_rows += (
            f'<tr {_row_bg}><td style="width:34px;font-weight:700">{_c}</td>'
            f'<td style="width:44%;position:relative"><div style="height:18px;border-radius:4px;'
            f'background:{"var(--red)" if _is_king else "#f0d9d7"};width:{_w}%"></div></td>'
            f'<td style="width:70px;font-weight:700">{_dist[_c]:.1f}</td>'
            f'<td style="width:70px">{_rank_txt}</td></tr>')
    hedge_card = (
        f'<div class="card"><b>Hedge 加权投票</b> '
        f'<span style="color:#999;font-size:12px">本期 {n["target_issue"]} · {n["n_experts"]}专家 · 权重=近{n["win"]}期命中率</span>'
        f'<div class="tbl-scroll"><div class="tbl-wrap" style="max-height:38vh"><table>'
        f'<thead><tr><th>数字</th><th>得票（加权合计）</th><th>票数</th><th>名次</th></tr></thead>'
        f'<tbody>{_bar_rows}</tbody></table></div></div>'
        f'<div style="margin-top:10px;font-size:12px;color:#666;line-height:1.7">'
        f'<b style="color:var(--red)">票王 = 杀和尾 {_order[0]}</b>（{_dist[_order[0]]:.1f}票，共识最强）；'
        f'Top3 票码 = {_order[0]}·{_order[1]}·{_order[2]}。'
        f'<br>机制：3931万公式穷举 800 专家池（按近 {n["win"]} 期命中率取 Top{n["n_experts"]}），'
        f'命中率即权重（下限0.02）加权投票，票数最高的数字被「杀掉」。</div></div>')

    # 预测笔记（真实发布台账：每天开奖前发布的预测 + 开奖后自动核对 + 累计命中率）
    try:
        import ledger as _ledger
        _recs = _ledger.get_records()
        _st = _ledger.get_stats()
        _note_rows = ""
        for _r in _recs[:60]:
            _issue = _r.get('issue', '?')
            _kill = _r.get('kill', '?')
            _hit = _r.get('hit')
            _num = _r.get('num') or '待开奖'
            _tail = _r.get('tail')
            if _hit is True:
                _cell = f'<td class="ok" style="font-weight:700;color:var(--green)">✓ 杀对</td>'
            elif _hit is False:
                _cell = f'<td class="miss" style="font-weight:700;color:var(--red)">✗ 杀错(和尾{_tail})</td>'
            else:
                _cell = f'<td style="color:#999">待开奖</td>'
            _note_rows += (
                f'<tr><td class="iss">{_issue}</td>'
                f'<td style="font-weight:700">{_num}</td>'
                f'<td style="font-weight:700">{_tail if _tail is not None else "-"}</td>'
                f'<td style="font-weight:700">{_kill}</td>{_cell}</tr>')
        _note_html = (
            f'<div class="card"><b>预测笔记</b> '
            f'<span style="color:#999;font-size:12px">800专家 · 每日开奖前真实发布 · 开奖后自动核对（近期在上）</span>'
            f'<div class="stat-row"><span>累计命中率（已核对{_st["settled"]}期）</span>'
            f'<span class="pct" style="color:var(--red)">杀1 {_st["rate"]:.2f}%'
            f'<span style="color:#999;font-size:12px">（{_st["hits"]}对/{_st["misses"]}错 · 共发布{_st["total"]}条 · {_st["pending"]}期待开奖）</span></span></div>'
            f'<div class="tbl-scroll"><div class="tbl-wrap" style="max-height:38vh"><table>'
            f'<thead><tr><th>预测期号</th><th>开奖号码</th><th>和尾</th><th>杀1</th><th>核对</th></tr></thead>'
            f'<tbody>{_note_rows}</tbody></table></div></div>'
            f'<div style="margin-top:10px;font-size:12px;color:#999;line-height:1.6">'
            f'每条记录 = 开奖前真实发布的预测（非回测）。开奖后自动补标 ✓/✗，累计命中率持续跟踪。'
            f'数据源更新后本表自动累积，可对账。</div></div>')
    except Exception as _e:
        _note_html = f'<div class="card"><b>预测笔记</b> <span style="color:#999;font-size:12px">账本未初始化，待首次发布后生成</span></div>'
    bt_card = _note_html

    # 预测卡
    pred_card = (
        f'<div class="card">'
        f'<div class="issue-flex"><span class="issue-pre">预测期号</span><b style="font-size:32px;letter-spacing:1px">{n["target_issue"]}</b><span class="issue-post">期</span></div>'
        f'<div style="margin-top:14px">{ball_html}</div>'
        f'<div class="formula-info" style="margin-top:14px">Hedge {n["n_experts"]}专家加权投票 · win={n["win"]} · 参数已锁定 · 票数={n["n_experts"]}专家加权合计</div>'
        f'</div>')
    return pred_card + hedge_card + bt_card


# ─────────────────────────── 系统B：v2.0 五专家 ───────────────────────────
def render_sysB(db):
    pred = db['prediction']
    meta = db['meta']
    ws = db['window_stats']
    rows = db['rows']

    # 预测球
    king = int(pred['kill'])
    _dist = pred.get('votes', [0]*10)
    ball_html = (
        f'<div style="display:flex;justify-content:center;align-items:center;margin:16px 0">'
        f'<div style="display:flex;flex-direction:column;align-items:center">'
        f'<div class="ball">{king}</div>'
        f'<div class="ball-votes">{_dist[king]:.1f} 票</div></div></div>')

    # 5专家加权投票详情卡
    _maxv = max(_dist) if max(_dist) > 0 else 1
    _order = sorted(range(10), key=lambda x: -_dist[x])
    _medals = {0: '🥇', 1: '🥈', 2: '🥉', 3: '4', 4: '5'}
    _bar_rows = ""
    for _r, _c in enumerate(_order):
        _w = max(int(_dist[_c] / _maxv * 100), 2)
        _is_king = _r == 0
        _row_bg = 'style="background:#fff5f5"' if _is_king else ''
        _rank_txt = f'<b style="color:var(--red)">票王</b>' if _is_king else f'第{_medals.get(_r, str(_r+1))}名'
        _bar_rows += (
            f'<tr {_row_bg}><td style="width:34px;font-weight:700">{_c}</td>'
            f'<td style="width:44%;position:relative"><div style="height:18px;border-radius:4px;'
            f'background:{"var(--red)" if _is_king else "#f0d9d7"};width:{_w}%"></div></td>'
            f'<td style="width:70px;font-weight:700">{_dist[_c]:.1f}</td>'
            f'<td style="width:70px">{_rank_txt}</td></tr>')
    # 各专家本期杀码
    exp_txt = " · ".join(f"{k}={v}" for k, v in pred.get('experts', {}).items())
    hedge_card = (
        f'<div class="card"><b>Hedge 加权投票</b> '
        f'<span style="color:#999;font-size:12px">本期 {pred["target_issue"]} · 5专家 · 权重=近{meta["window"]}期命中率</span>'
        f'<div class="tbl-scroll"><div class="tbl-wrap" style="max-height:38vh"><table>'
        f'<thead><tr><th>数字</th><th>得票（加权合计）</th><th>票数</th><th>名次</th></tr></thead>'
        f'<tbody>{_bar_rows}</tbody></table></div></div>'
        f'<div style="margin-top:10px;font-size:12px;color:#666;line-height:1.7">'
        f'<b style="color:var(--red)">票王 = 杀和尾 {_order[0]}</b>（{_dist[_order[0]]:.1f}票，共识最强）；'
        f'Top3 票码 = {_order[0]}·{_order[1]}·{_order[2]}。'
        f'<br>机制：5个手挑公式专家（A9+h1s3+全史频+近50频+转移表），近{meta["window"]}期命中率做权重'
        f'（下限0.02）加权投票，票数最高的数字被「杀掉」。<br>'
        f'本期各专家杀码：{exp_txt}</div></div>')

    # 回测表（含100/200/500/1000期窗口切换）
    bt_card = _render_bt_card('B', rows, '5专家',
        f'第 t 期预测只用 ≤ t-1 期数据；固定5专家 + 固定机制(win={meta["window"]}) 确定性重算 → 逐期真实预测记录。')

    # 命中率汇总（多窗口）
    stat_rows = ""
    for W in (100, 200, 500, 1000):
        w = ws.get(str(W), {})
        if not w:
            continue
        stat_rows += (
            f'<div class="stat-row"><span>近{W}期</span>'
            f'<span class="pct">{w["pct"]}% <span style="color:#999;font-size:12px">(基线{w["base_pct"]}%)</span></span></div>')
    stats_card = (
        f'<div class="card"><b>多窗口命中率</b> <span style="color:#999;font-size:12px">v2.0五专家 · 全量{meta["full_hit"]}%（基线{meta["full_base"]}%）</span>'
        f'{stat_rows}</div>')

    # 预测卡
    pred_card = (
        f'<div class="card">'
        f'<div class="issue-flex"><span class="issue-pre">预测期号</span><b style="font-size:32px;letter-spacing:1px">{pred["target_issue"]}</b><span class="issue-post">期</span></div>'
        f'<div style="margin-top:14px">{ball_html}</div>'
        f'<div class="formula-info" style="margin-top:14px">Hedge 5专家加权投票 · win={meta["window"]} · 参数已锁定 · 票数=5专家加权合计</div>'
        f'</div>')
    return pred_card + hedge_card + stats_card + bt_card


def _render_bt_card(sys_id, rows, sys_name, note, title='回测表', sub_note='逐期真实预测记录（walk-forward，不偷看未来）', issue_head='期号'):
    """回测记录卡片：顶部 100/200/500/1000期 切换按钮 + 杀1命中率联动 + 四个窗口表格。
    sys_id ∈ {'A','B'} 用于区分两套独立切换（localStorage 各自记忆）。
    命中率口径：杀1 = 和尾不在top3[0]（票王命中）。
    title: 卡片标题（A系统=实战记录，B系统=回测表）
    issue_head: 表头第一列（A系统=预测期号，B系统=期号）
    """
    wins = [100, 200, 500, 1000]
    # 命中率：从近到远取窗口（rows 已是近→远）
    rate_html = ""
    for W in wins:
        seg = rows[:W]
        n = len(seg)
        h1 = sum(1 for r in seg if not _tail_in_top3(r))
        p1 = h1 / n * 100 if n else 0
        rate_html += (
            f'<div class="stat-row" id="bt-rate-{sys_id}-{W}" style="display:none">'
            f'<span>命中率（近{W}期）</span>'
            f'<span class="pct">杀1 {p1:.2f}%'
            f'<span style="color:#999;font-size:12px">（{h1}/{n}）</span></span></div>')
    # 四个窗口的表格容器（默认1000期显示）
    tbl_html = ""
    for W in wins:
        seg = rows[:W]
        rows_html = _render_bt_rows(seg)
        disp = 'style="display:block"' if W == 1000 else 'style="display:none"'
        tbl_html += (
            f'<div id="bt-tbl-{sys_id}-{W}" class="bt-win-tbl" {disp}>'
            f'<div class="tbl-scroll"><div class="tbl-wrap"><table>'
            f'<thead><tr><th>{issue_head}</th><th>号码</th><th>和尾</th><th>杀1</th></tr></thead>'
            f'<tbody>{rows_html}</tbody></table></div></div></div>')
    # 窗口切换按钮（默认1000 active）
    btns = ""
    for W in wins:
        active = 'active' if W == 1000 else ''
        btns += (
            f'<button class="win-btn {active}" data-sys="{sys_id}" data-w="{W}" '
            f'onclick="switchBtWin(\'{sys_id}\', {W})">{W}期</button>')
    return (
        f'<div class="card"><b>{title}</b> '
        f'<span style="color:#999;font-size:12px">{sys_name} · 近→远 · {sub_note}</span>'
        f'<div class="win-switch">{btns}</div>'
        f'{rate_html}'
        f'<div style="margin-top:8px;font-size:12px;color:#999;line-height:1.8">'
        f'<span class="miss">🔴 红字 = 该数字杀错（和尾恰好=此数）</span>；其余为默认色 = 杀对。</div>'
        f'{tbl_html}'
        f'<div style="margin-top:10px;font-size:12px;color:#999;line-height:1.6">{note}</div></div>')


def _tail_in_top3(r):
    """和尾是否等于该期杀码 top3[0]（票王）。杀1命中 = 和尾不在 top3[0]。"""
    tail = sum(int(c) for c in r['num']) % 10
    return tail == r['top3'][0]


def _render_bt_rows(rows):
    """两系统共用的回测表行渲染：只显示杀1（票王），杀错变红（独立判断）。"""
    out = ""
    for r in rows:
        tail = sum(int(c) for c in r['num']) % 10
        kill1 = r['top3'][0]
        cell = f'<td class="miss" style="font-weight:700">{kill1}</td>' if kill1 == tail else f'<td style="font-weight:700">{kill1}</td>'
        out += (
            f'<tr><td class="iss">{esc(r["issue"])}</td>'
            f'<td class="num">{r["num"]}</td>'
            f'<td class="num" style="color:var(--green)">{tail}</td>'
            f'{cell}</tr>')
    return out


def build_html(d, db):
    n = d['next']
    di = d['data_info']
    db_pred = db['prediction']

    sysA_html = render_sysA(d)
    sysB_html = render_sysB(db)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>福彩3D 杀和尾 · Hedge 双系统</title>
<style>{CSS_TEXT}</style>
</head>
<body>
<h1>🎯 福彩3D 杀和尾 <span style="font-size:13px;color:#888">Hedge 双系统</span></h1>
<div class="sub">数据至 {di['last']} 期（{di['last_draw']}）· 共 {di['n_issues']} 期 · 两套引擎共用同一份数据</div>

<div class="sys-switch">
  <button class="sys-btn active" data-sys="A" onclick="switchSys('A')">800专家 <span class="sys-badge">v3</span></button>
  <button class="sys-btn" data-sys="B" onclick="switchSys('B')">5专家 <span class="sys-badge gray">v2.0</span></button>
</div>

<div id="sysA" class="sys-panel on">{sysA_html}</div>
<div id="sysB" class="sys-panel">{sysB_html}</div>

<script>
function switchSys(s){{
  document.querySelectorAll('.sys-btn').forEach(b=>b.classList.toggle('active', b.dataset.sys===s));
  document.getElementById('sysA').classList.toggle('on', s==='A');
  document.getElementById('sysB').classList.toggle('on', s==='B');
  try{{localStorage.setItem('sha_hewei_sys', s)}}catch(e){{}}
}}
function switchBtWin(sys, w){{
  document.querySelectorAll('.win-btn[data-sys="'+sys+'"]').forEach(b=>b.classList.toggle('active', +b.dataset.w===w));
  [100,200,500,1000].forEach(x=>{{
    var t=document.getElementById('bt-tbl-'+sys+'-'+x), r=document.getElementById('bt-rate-'+sys+'-'+x);
    if(t) t.style.display = (x===w)?'block':'none';
    if(r) r.style.display = (x===w)?'block':'none';
  }});
  try{{localStorage.setItem('sha_hewei_bt_'+sys, w)}}catch(e){{}}
}}
(function(){{
  try{{
    var s = localStorage.getItem('sha_hewei_sys');
    if(s === 'B') switchSys('B');
    ['A','B'].forEach(function(sys){{
      var w = localStorage.getItem('sha_hewei_bt_'+sys);
      if(w && [100,200,500,1000].indexOf(+w)>=0) switchBtWin(sys, +w);
    }});
  }}catch(e){{}}
}})();
</script>
</body>
</html>
"""


def main():
    # 系统A：当前800专家（cache/result.json）
    with open(CACHE_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data['scan_count'] = len(data.get('scan', [])) if isinstance(data.get('scan'), list) else 72
    # 系统B：v2.0 五专家（hedge_prediction.json）
    bpath = os.path.join(BASE_DIR, 'hedge_prediction.json')
    with open(bpath, 'r', encoding='utf-8') as f:
        db = json.load(f)
    html = build_html(data, db)
    with open(OUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    n = data['next']
    s = data['summary']
    bp = db['prediction']
    print(f"已生成固定网页: {OUT_HTML}")
    print(f"数据至 {data['data_info']['last']} 期 | 公式池 {data['pool_info']['pool_size_total']:,} | 专家池 {data['pool_info']['topk']}")
    print(f"[800专家] Hedge(K={n['n_experts']},win={n['win']}) | 回测 {s['hit']}/{s['total']} = {s['rate']*100:.2f}% (基线90%)")
    print(f"[800专家] 下一期 {n['target_issue']} 杀和尾 {n['kill']}")
    print(f"[5专家]   Hedge(win={db['meta']['window']}) | 全量 {db['meta']['full_hit']}% (基线{db['meta']['full_base']}%)")
    print(f"[5专家]   下一期 {bp['target_issue']} 杀和尾 {bp['kill']} (Top3 {bp['top3']})")
    print("双击打开即可浏览，或传到手机查看。")


if __name__ == '__main__':
    main()
