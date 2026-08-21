# -*- coding: utf-8 -*-
"""
福彩3D 杀和尾 — 生成固定静态网页「杀和尾v3.html」（v2 风格样式）
=========================================================
读 cache/result.json, 输出一个完全自包含的单文件 HTML:
数据以 window.__DATA__ 内联 JSON 嵌入, 双击即开, 零后端, 可传手机浏览。
样式复刻 v2 的 index.html（浅色移动优先、大红色杀码球、白卡片、逐期表近期在上）。
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_JSON = os.path.join(BASE_DIR, 'cache', 'result.json')
OUT_HTML = os.path.join(BASE_DIR, '杀和尾v3.html')

# 内置样式（复刻 v2 index.html 风格）
CSS_TEXT = """
:root{--red:#e0453a;--green:#1a9e54;--bg:#f4f6f9;--card:#fff;--line:#e6e9ef}
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:#222;max-width:640px;margin:0 auto;padding:12px;padding-bottom:40px}
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
.miss-row td{background:#fef2f2}
td.fname{font-size:11px;color:#999;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
td.iss{color:#999;font-size:11.5px;font-family:ui-monospace,Consolas,monospace}
td.num{font-weight:700;letter-spacing:1px}
td.t3{font-size:11px;color:#999;font-family:ui-monospace,Consolas,monospace}
td.t3 b{color:var(--red)}
.warn{background:#fef3c7;border:1px solid #f59e0b;color:#92400e;border-radius:8px;padding:8px 11px;font-size:11.5px;margin-top:10px;line-height:1.6}
.footer{margin-top:16px;padding:12px;background:#fff;border-radius:12px;font-size:11px;color:#999;line-height:1.7}
.footer b{color:#666}
"""

BODY_TEMPLATE = """
<div class="card">
  <div class="issue">预测期号 <b id="nextIssue">-</b> 期</div>
  <div class="ball-wrap"><div><div class="ball" id="killNum">-</div><div class="ball-label" id="killLabel">杀和尾 -</div></div></div>
  <div class="formula-info" id="killFormula">-</div>
</div>

<div class="card">
  <b>本期专家投票</b> <span style="color:#999;font-size:12px">（Top <span id="pK">-</span> 专家加权 · 近<span id="pWin">-</span>期命中率）</span>
  <div id="expBody"></div>
</div>

<div class="card">
  <b>500期回测命中率</b>
  <div class="stat-row"><span>回测命中率</span><span class="pct" id="stRate">-</span><span style="color:#999;font-size:12px" id="stHit">-</span></div>
  <div class="stat-row"><span>最大连中</span><span class="pct" id="stMaxWin">-</span><span style="color:#999;font-size:12px">连错阈值参考</span></div>
  <div class="stat-row"><span>最大连错</span><span class="miss" id="stMaxLose">-</span><span style="color:#999;font-size:12px" id="stCur">-</span></div>
  <div class="warn" id="warnSel"></div>
</div>

<div class="card">
  <b>最新 100 期明细</b> <span style="color:#999;font-size:12px">（近 → 远）</span>
  <div class="tbl-wrap"><table><thead><tr><th>期号</th><th>号码</th><th>票码Top3</th><th>杀</th><th>结果</th><th>首席专家</th></tr></thead>
  <tbody id="tbBody"></tbody></table></div>
</div>

<div class="footer">
  <b>说明</b><br>
  ① 杀和尾 = 预测杀掉 0-9 中一个数字，下期<b>和尾</b>不出现即命中，理论随机基线 <b>90%</b>。<br>
  ② 公式池 <b id="fc">-</b> 个暴力穷举算法（<span id="nfeat">-</span>特征线性组合），在<b>最新500期</b>按命中率选 Top<span id="fTopk">-</span> 专家池，主机制 <b>Hedge 加权投票</b>：每期取近 <span id="pWin2">-</span> 期命中率 Top<span id="pK2">-</span> 专家，按命中率加权投票，票王 = 和尾杀码。参数经 <span id="pScan">-</span> 组合网格扫描自动选优。<br>
  ③ 回测为<b>逐期真实预测记录</b>：第 t 期预测只用第 t-1、t-2 期数据（walk-forward，不偷看未来）。<br>
  ④ <b>选择偏差警示</b>：专家池是在回测的同一段 500 期上按命中率选出的，回测数字含轻微选择偏差，样本外会回落；<b>不构成任何购彩建议</b>。<br>
  ⑤ <b>固定快照</b>：本页为数据快照（生成于 <span id="genTime">-</span>），数据更新后请重新导出。
</div>
"""


def build_html(data):
    payload = json.dumps(data, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>福彩3D 杀和尾 · Hedge穷举</title>
<style>{CSS_TEXT}</style>
</head>
<body>
<h1>🎯 福彩3D 杀和尾 <span style="font-size:13px;color:#888">Hedge 穷举 v3</span></h1>
<div class="sub" id="dataInfo">数据加载中...</div>
{BODY_TEMPLATE}
<script>
window.__DATA__ = {payload};
</script>
<script>
var DATA = window.__DATA__;
var $ = function(id){{ return document.getElementById(id); }};
function fmtPct(x){{ return (x*100).toFixed(2)+"%"; }}
function render(d){{
  DATA = d;
  var n = d.next, s = d.summary, di = d.data_info, pi = d.pool_info;
  $("dataInfo").textContent = "更新于 " + d.generated_at + " · 共 " + di.n_issues + " 期 · 最新 " + di.last + " (" + di.last_draw + ")";
  $("nextIssue").textContent = n.target_issue;
  $("killNum").textContent = n.kill;
  $("killLabel").textContent = "杀和尾 " + n.kill;
  $("killFormula").textContent = "算法：Hedge " + n.n_experts + "专家加权投票 (win=" + n.win + ") · " + pi.pool_size_total.toLocaleString() + "公式穷举";
  $("pK").textContent = n.n_experts; $("pWin").textContent = n.win;
  $("pK2").textContent = n.n_experts; $("pWin2").textContent = n.win;
  $("pScan").textContent = d.scan.length;
  $("fTopk").textContent = pi.topk;
  $("fc").textContent = pi.pool_size_total.toLocaleString();
  $("nfeat").textContent = pi.n_features;
  // 专家投票
  var ex = "";
  (n.experts || []).forEach(function(e){{
    ex += '<div class="exp-row"><span class="exp-name">' + e.name + '</span>' +
          '<span class="exp-kill">杀 ' + e.kill + '</span>' +
          '<span class="exp-w">权重 ' + e.weight.toFixed(3) + '</span></div>';
  }});
  $("expBody").innerHTML = ex || "无数据";
  // 回测汇总
  $("stRate").textContent = fmtPct(s.rate);
  $("stHit").textContent = s.hit + "/" + s.total + " (基线 90%)";
  $("stMaxWin").textContent = s.max_win + " 期";
  $("stMaxLose").textContent = s.max_lose + " 期";
  if(s.cur_lose > 0){{ $("stCur").textContent = "当前连错 " + s.cur_lose; $("stCur").style.color = "var(--red)"; }}
  else {{ $("stCur").textContent = "当前连中 " + s.cur_win; $("stCur").style.color = "var(--green)"; }}
  var diff = (s.rate - s.baseline) * 100;
  if (Math.abs(diff) > 6) {{
    $("warnSel").textContent = "⚠ 回测率与90%基线偏离 " + diff.toFixed(1) + "pp，疑含过拟合，请谨慎参考。";
  }} else {{
    $("warnSel").textContent = "⚠ 专家池在回测的同一段500期上选出，回测含轻微选择偏差，样本外会回落。";
  }}
  // 100期明细（近期在上）
  var html = "";
  d.rows.slice(0, 100).forEach(function(r){{
    var cls = r.hit ? "hit" : "miss";
    var t3 = (r.top3 || [r.kill]).map(function(c, i){{ return i === 0 ? '<b>' + c + '</b>' : c; }}).join("·");
    html += '<tr class="' + (r.hit ? "" : "miss-row") + '">' +
      '<td class="iss">' + r.issue + '</td>' +
      '<td class="num">' + r.num + '</td>' +
      '<td class="t3">' + t3 + '</td>' +
      '<td class="' + cls + '">' + r.kill + '</td>' +
      '<td>' + (r.hit ? "✅" : "❌") + '</td>' +
      '<td class="fname" title="' + r.fname + '">' + r.fname + '</td></tr>';
  }});
  $("tbBody").innerHTML = html;
  $("genTime").textContent = d.generated_at;
}}
render(DATA);
</script>
</body>
</html>
"""


def main():
    with open(CACHE_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
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
