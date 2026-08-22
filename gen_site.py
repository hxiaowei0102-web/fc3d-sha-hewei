# -*- coding: utf-8 -*-
"""
福彩3D 杀和尾 — 生成固定静态网页「index.html」（v2.0 版式复刻）
==================================================================
读 cache/result.json, 输出一个完全自包含的单文件 HTML（纯静态渲染，非 JS 动态）。
当前版式：卡片1(期号+三球+得票数) + Hedge 加权投票详情卡，浅色移动优先。
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
/* ── 手机端优化（2026-08-21）── */
.tbl-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.tbl-scroll table{min-width:580px}
.dot{width:16px;height:16px;border-radius:50%;font-size:9px;line-height:16px;text-align:center;color:#fff;flex:0 0 auto}
.dot-ok{background:var(--green)}.dot-bad{background:var(--red)}
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

    # 卡片1 = 只显示票王（杀和尾）1 个红球
    king = int(n['kill'])                # 票王 = 杀和尾
    _vote_dist = n.get('top3_vote_dist', [0]*10)
    ball1_html = (
        f'<div style="display:flex;justify-content:center;align-items:center;margin:16px 0">'
        f'<div style="display:flex;flex-direction:column;align-items:center">'
        f'<div class="ball">{king}</div>'
        f'<div class="ball-votes">{_vote_dist[king]:.1f} 票</div></div></div>')

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

    # ── 2d. 1000期回测表（近期→远期 · 逐期真实预测记录）──
    bt_rows_html = ""
    for r in d['rows'][:1000]:
        tail = sum(int(c) for c in r['num']) % 10
        top3 = r['top3']
        # 只把杀错的那一格数字变红：每格独立判断，和尾恰好=该数字才标红；
        # 和尾=杀2 只红杀2格，杀1格不受影响（不做累积判断）
        def _cell(code):
            if code == tail:
                return f'<td class="miss" style="font-weight:700">{code}</td>'
            return f'<td style="font-weight:700">{code}</td>'
        cells = "".join(_cell(top3[i]) for i in range(3))
        bt_rows_html += (
            f'<tr><td class="iss">{esc(r["issue"])}</td>'
            f'<td class="num">{r["num"]}</td>'
            f'<td class="num" style="color:var(--green)">{tail}</td>'
            f'{cells}</tr>')
    bt_total = len(d['rows'])
    bt_hits = sum(1 for r in d['rows'] if r['hit'])
    bt_card_html = (
        f'<div class="card"><b>1000期回测表</b> '
        f'<span style="color:#999;font-size:12px">近→远 · 逐期真实预测记录（walk-forward，不偷看未来）</span>'
        f'<div class="stat-row"><span>杀1命中（1000期）</span>'
        f'<span class="pct">{bt_hits}/{bt_total} = {bt_hits/bt_total*100:.2f}%</span></div>'
        f'<div style="margin-top:8px;font-size:12px;color:#999;line-height:1.8">'
        f'<span class="miss">🔴 红字 = 该数字杀错（和尾恰好=此数）</span>；其余为默认色 = 杀对。</div>'
        f'<div class="tbl-scroll"><div class="tbl-wrap"><table>'
        f'<thead><tr><th>期号</th><th>号码</th><th>和尾</th><th>杀1</th><th>杀2</th><th>杀3</th></tr></thead>'
        f'<tbody>{bt_rows_html}</tbody></table></div></div>'
        f'<div style="margin-top:10px;font-size:12px;color:#999;line-height:1.6">'
        f'第 t 期预测只用 ≤ t-1 期数据；固定800专家 + 固定机制(win=40,K=650) 确定性重算 → 逐期真实预测记录。</div></div>')

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
  <div style="margin-top:14px">{ball1_html}</div>
  <div class="formula-info" style="margin-top:14px">Hedge {n['n_experts']}专家加权投票 · win={n['win']} · 参数已锁定 · 票数={n['n_experts']}专家加权合计</div>
</div>

{hedge_card_html}

{bt_card_html}
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
