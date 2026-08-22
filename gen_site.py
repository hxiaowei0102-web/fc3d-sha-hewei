# -*- coding: utf-8 -*-
"""
福彩3D 杀和尾 — 生成固定静态网页「index.html」（v2.0 版式复刻）
==================================================================
读 cache/result.json, 输出一个完全自包含的单文件 HTML（纯静态渲染，非 JS 动态）。
版式 100% 复刻 v2.0 时代 index.html（标题 Hedge 单杀、80px 大红球、白卡片、
本期专家投票 / 单杀命中率 / 专家级回测 / 最新500期明细 四卡，浅色移动优先）。
算法数据为当前 v3.2 锁定模式：3931万公式穷举 800 专家池【永久固定】，
win/k 参数【锁定】→ 每天发布的预测 = 开奖完回测表同一期数值（确定性，可对账）。
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
.miss-row td{background:#fef2f2}
/* ── 手机端优化（2026-08-21）── */
.tbl-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.tbl-scroll table{min-width:580px}
.pick-card{display:flex;gap:8px;align-items:center;flex-wrap:nowrap}
.pick-card .ball{width:64px;height:64px;font-size:34px}
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


def build_html(d):
    n = d['next']
    s = d['summary']
    di = d['data_info']
    pi = d['pool_info']

    # 卡片1 = 直接显示算法预测票码 Top3（票数前三名）
    show_top3 = list(n['top3_vote'][:3])   # 算法票王 + 票数第2/第3

    # ── 2. 三口径命中率对照（训练窗口 vs 样本外）──
    # 训练窗口（500期，result.json 逐期真实）：专家被选出的同段数据 → 选择偏差，仅供对账
    # 样本外（2000期，2019144~2025074，专家从未见过）：真实未来预期
    rows_all = d['rows']
    _order_tr = [sorted(range(10), key=lambda x: -r['votes'][x]) for r in rows_all]
    _tail_tr = [sum(int(c) for c in r['num']) % 10 for r in rows_all]
    def _cnt3(sel):
        return sum(1 for o, tl in zip(_order_tr, _tail_tr) if tl not in set(o[:sel]))
    top3_hits = _cnt3(3)
    top3_rate = top3_hits / len(rows_all)
    kill_hits = sum(1 for r in rows_all if r['hit'])
    kill_rate = kill_hits / len(rows_all)
    # 近100期
    _o100 = _order_tr[:100]; _t100 = _tail_tr[:100]
    k100 = sum(1 for o, tl in zip(_o100, _t100) if tl not in {o[0]})
    t2_100 = sum(1 for o, tl in zip(_o100, _t100) if tl not in set(o[:2]))
    t3_100 = sum(1 for o, tl in zip(_o100, _t100) if tl not in set(o[:3]))
    # 样本外（top3_backtest.json，缺失时回退为 None → 页面隐藏样本外行）
    try:
        with open(os.path.join(BASE_DIR, 'cache', 'top3_backtest.json'), 'r', encoding='utf-8') as _f:
            _bt = json.load(_f)
        oos = _bt['oos_window']
        oos_ok = True
    except Exception:
        oos, oos_ok = None, False

    # ── 2b. 预测票码 Top3 三球（卡片1：期号 + 三球均分 + 得票数，无标签）──
    _vote_dist = n.get('top3_vote_dist', [0]*10)
    ball3_html = "".join(
        f'<div style="flex:1 1 0;min-width:0;display:flex;flex-direction:column;align-items:center;padding:0 4px">'
        f'<div class="ball">{c}</div>'
        f'<div class="ball-votes">{_vote_dist[c]:.1f} 票</div></div>'
        for c in show_top3[:3])

    # 三口径对照行（训练 vs 样本外）
    def _rate_tr(sel):
        return round(_cnt3(sel) / len(rows_all) * 100, 2)
    if oos_ok:
        _o1 = f'{oos["kill"]["rate"]:.2f}%'
        _o2 = f'{oos["top2"]["rate"]:.2f}%'
        _o3 = f'{oos["top3"]["rate"]:.2f}%'
    else:
        _o1 = _o2 = _o3 = '—'
    _tr_row = (
        f'<tr><td>票码1（杀1码）</td><td>{_rate_tr(1):.2f}%</td><td>基线90%</td>'
        f'<td>{_o1}</td><td>基线90%</td></tr>'
        f'<tr><td>票码2（杀2码）</td><td>{_rate_tr(2):.2f}%</td><td>基线80%</td>'
        f'<td>{_o2}</td><td>基线80%</td></tr>'
        f'<tr><td>票码3（杀3码）</td><td>{_rate_tr(3):.2f}%</td><td>基线70%</td>'
        f'<td>{_o3}</td><td>基线70%</td></tr>'
    )
    if oos_ok:
        _oos_note = f'样本外=2019144~2025074 共 {oos["kill"]["n"]} 期（专家从未见过的历史数据，真实预期）'
    else:
        _oos_note = '样本外数据缺失'
    _note_oos = (
        f'<div style="background:#f2f9f2;border:1px solid #bfe3c4;border-radius:8px;padding:8px 12px;'
        f'margin-top:10px;font-size:12px;color:#1a6b35;line-height:1.6">'
        f'<b>样本外验证</b>：训练窗口500期 100% 是<b>选择偏差</b>（专家池正是从这500期里挑的），'
        f'不可作为未来预期；真实水平看样本外：{_oos_note}。<br>'
        f'票码1 <b>{oos["kill"]["rate"]:.2f}%</b>（基线90%）、'
        f'票码2 <b>{oos["top2"]["rate"]:.2f}%</b>（基线80%）、'
        f'票码3 <b>{oos["top3"]["rate"]:.2f}%</b>（基线70%）——贴近随机基线，无稳定超额。</div>' if oos_ok else '')

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

    # ── 2c. Hedge 加权投票详情卡（10数字得票条形图 + 前5名 + 机制说明）──
    _dist = n.get('top3_vote_dist', [0]*10)
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
    hedge_card_html = (
        f'<div class="card"><b>Hedge 加权投票</b> '
        f'<span style="color:#999;font-size:12px">本期 {n["target_issue"]} · {n["n_experts"]}专家 · 权重=近{n["win"]}期命中率</span>'
        f'<div class="tbl-scroll"><div class="tbl-wrap" style="max-height:38vh"><table>'
        f'<thead><tr><th>数字</th><th>得票（加权合计）</th><th>票数</th><th>名次</th></tr></thead>'
        f'<tbody>{_bar_rows}</tbody></table></div></div>'
        f'<div style="margin-top:10px;font-size:12px;color:#666;line-height:1.7">'
        f'<b style="color:var(--red)">票王 = 杀和尾 {_order[0]}</b>（{_dist[_order[0]]:.1f}票，共识最强）；'
        f'Top3 票码 = {_order[0]}·{_order[1]}·{_order[2]}。'
        f'<br>机制：800 公式专家池按近 {n["win"]} 期命中率排序取 Top{n["n_experts"]}，'
        f'命中率即权重（下限0.02）加权投票，票数最高的数字被「杀掉」。</div></div>')

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>福彩3D 杀和尾 · Hedge 单杀</title>
<style>{CSS_TEXT}</style>
</head>
<body>
<h1>🎯 福彩3D 杀和尾 <span style="font-size:13px;color:#888">Hedge 单杀 v3.2</span></h1>
<div class="sub">数据至 {di['last']} 期（{di['last_draw']}）· 共 {di['n_issues']} 期 · 引擎 v3.2（固定专家 · K={n['n_experts']}）</div>

<div class="card">
  <div class="issue-flex"><span class="issue-pre">预测期号</span><b style="font-size:32px;letter-spacing:1px">{n['target_issue']}</b><span class="issue-post">期</span></div>
  <div class="pick-card" style="gap:8px;margin-top:14px">{ball3_html}</div>
  <div class="formula-info" style="margin-top:14px">Hedge {n['n_experts']}专家加权投票 · win={n['win']} · 参数已锁定 · 票数={n['n_experts']}专家加权合计</div>
</div>

{hedge_card_html}

<div class="card">
  <b>预测票码 Top3 命中率</b> <span style="color:#999;font-size:12px">杀3码（和尾 ∉ Top3 即安全）</span>
  <div class="formula-info">下期 {n['target_issue']} 预测票码：{'、'.join(str(c) for c in show_top3)}（票数前3）</div>
  <div class="tbl-scroll"><div class="tbl-wrap"><table>
    <thead><tr><th>口径</th><th>训练500期</th><th>基线</th><th>样本外2000期</th><th>基线</th></tr></thead>
    <tbody>
      {_tr_row}
    </tbody></table></div></div>
  <div class="stat-row"><span>近100期（训练窗尾段）</span>
    <span class="pct">票1 {k100/100*100:.1f}% · 票2 {t2_100/100*100:.1f}% · 票3 {t3_100/100*100:.1f}%</span></div>
  {_note_oos}
</div>

<div class="card">
  <b>专家级回测</b> <span style="color:#999;font-size:12px">（500期 · 池内 Top10 对照）</span>
  {exp_bt_html}
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
