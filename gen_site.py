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

    # 本期已发布值（账本保护）仅用于过渡提示；卡片1 直接显示算法预测 Top3
    pub = None
    for r in ledger_records:
        if r.get('issue') == str(n['target_issue']):
            pub = r
            break
    # 卡片1 = 直接显示算法预测票码 Top3（票数前三名）
    show_top3 = list(n['top3_vote'][:3])   # 算法票王 + 票数第2/第3
    trans_note = ""
    if pub and pub.get('kill') != n['kill']:
        trans_note = (
            f'<div style="background:#fff8e6;border:1.5px solid #f0c36d;border-radius:8px;padding:8px 12px;'
            f'margin-top:10px;font-size:12px;color:#7a5a00;line-height:1.6">'
            f'ℹ️ 本期 {n["target_issue"]} 开奖前曾发布<b>杀 {pub["kill"]}</b>（K=56时代，见下方发布记录）；'
            f'上方为 K={n["n_experts"]} 优化后的预测票码 Top3，<b>自下期起以 K={n["n_experts"]} 为准</b>。</div>')

    # 500期回测明细已移除（老板要求只保留实战口径：真实发布记录）

    # ── 1. 本期专家投票（v2.0 exp-row 样式，静态渲染，无展开明细）──
    experts_html = ""
    for i, e in enumerate(n['experts']):
        experts_html += (
            f'<div class="exp-row"><span class="exp-name">#{i+1} {esc(e["name"])}</span>'
            f'<span class="exp-kill">杀 {e["kill"]}</span>'
            f'<span class="exp-w">权重 {e["weight"]:.3f}</span></div>')
    if not experts_html:
        experts_html = '<div style="color:#999;padding:8px">无专家数据</div>'

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

    # ── 2b. 预测票码 Top3 三球（卡片1：三球等宽平均分配，无杂项）──
    ball3_html = "".join(
        f'<div style="flex:1;text-align:center;min-width:0">'
        f'<div class="ball">{c}</div>'
        f'<div class="ball-label">{"杀和尾 " + str(c) if i == 0 else "票码 " + str(c)}</div></div>'
        for i, c in enumerate(show_top3[:3]))

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
  <div class="issue">预测期号 <b style="font-size:34px;letter-spacing:2px">{n['target_issue']}</b> 期</div>
  <div class="pick-card" style="gap:8px">{ball3_html}</div>
</div>

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
  <b>本期专家投票</b> <span style="color:#999;font-size:12px">（{n['n_experts']} 位专家 · 权重=近 {n['win']} 期命中率）</span>
  <div class="tbl-wrap" style="max-height:45vh">{experts_html}</div>
</div>

<div class="card">
  <b>专家级回测</b> <span style="color:#999;font-size:12px">（500期 · 池内 Top10 对照）</span>
  {exp_bt_html}
</div>

<div class="card">
  <b>真实发布记录（逐期）</b> <span style="color:#999;font-size:12px">每一期都是开奖前发布 · 开奖后自动验证 · 近→远 · 手机左右滑动看全</span>
  <div class="dot-row"><span class="dot dot-ok">✓</span><span class="dl">杀对</span><span class="dot dot-bad">✗</span><span class="dl">杀错</span><span class="dl" style="margin-left:8px">⏳待开奖</span></div>
  <div class="tbl-scroll"><div class="tbl-wrap"><table><thead><tr><th>期号</th><th>号码</th><th>和尾</th><th>—</th><th>杀1</th><th>杀1对</th><th>杀2对</th><th>杀2码</th><th>发布时间</th></tr></thead>
  <tbody>{ledger_rows}</tbody></table></div></div>
</div>

<div class="footer">
  <b>说明</b><br>
  ① 杀和尾 = 预测杀掉 0-9 中一个数字，下期<b>和尾</b>不出现即命中，理论随机基线 <b>90%</b>。<br>
  ② 公式池 {pi['pool_size_total']:,} 个（{pi['n_features']} 特征线性组合）在<b>最新500期</b>按命中率选 Top{pi['topk']} 专家池，<b>首次锁定后永久固定</b>；主机制 <b>Hedge 加权投票</b>：每期取近 {n['win']} 期命中率 Top{n['n_experts']} 专家，按命中率加权投票，票王 = 和尾杀码。参数 <b>win={n['win']}/K={n['n_experts']} 已锁定</b>，不再每日重选。<br>
  ③ <b>确定性保证（v2.0 同款语义）</b>：专家池与参数永久固定 → 每天发布的预测 = 开奖后验证的记录，发布值可随时对账（发布时存档、开奖后补标对错）。<br>
  ④ 上方【真实发布记录】为<b>逐期开奖前发布的预测</b>：第 t 期发布时只用第 t-1、t-2 期及更早数据（walk-forward，不偷看未来），发布后存档、开奖后自动补标对错，是<b>唯一实战口径</b>。<br>
  ⑤ <b>选择偏差警示</b>：专家池是在回测的同一段 500 期上按命中率选出的，算法回测数字含轻微选择偏差，样本外会回落；<b>不构成任何购彩建议</b>。<br>
  ⑥ 生成于 <b>{d['generated_at']}</b> · 数据更新后请重新导出。
  {trans_note}
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
