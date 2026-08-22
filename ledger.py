# -*- coding: utf-8 -*-
"""
发布账本 — 逐期真实预测记录
====================================================================
核心目标：页面回测表必须是「逐期真实预测记录」——每一期的杀码都是
「当期开奖前」用已有数据算出来并【真实发布】过的，而不是事后重算。

机制：
  1. hedge_core 每次跑完把「下期预测」交给本模块记账（predictions.json）
  2. 账本按 target_issue 去重：同一期只保留第一条（即开奖前发布的那次）
  3. 数据更新后（某期开奖了），自动补标该期 hit/miss
  4. 账本持续累积，页面回测表直接从账本渲染 → 全部是真实发布记录

数据文件：cache/predictions.json
  结构: {"records": [ {issue, kill, top2, published_at, data_last, hit, num, tail}, ... ]}
"""
import json
import os
import time
from datetime import datetime, timezone, timedelta

LEDGER_PATH = os.path.join('cache', 'predictions.json')
BJT = timezone(timedelta(hours=8))


def _load():
    try:
        with open(LEDGER_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {'records': []}


def _save(ledger):
    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
    with open(LEDGER_PATH, 'w', encoding='utf-8') as f:
        json.dump(ledger, f, ensure_ascii=False, indent=1)


def record_publication(nxt, data_last):
    """记录一次真实发布（开奖前调用）。同期只保留第一条 = 开奖前那次发布。"""
    ledger = _load()
    issue = str(nxt['target_issue'])
    exists = [r for r in ledger['records'] if r['issue'] == issue]
    if exists:
        e = exists[0]
        print(f"[账本] {issue}期已有发布记录(杀{e['kill']})，保持开奖前发布值不变（去重保护）")
        return e
    rec = {
        'issue': issue,
        'kill': nxt['kill'],
        'top3': nxt.get('top3_vote', [])[:3],
        'top2': nxt.get('top3_vote', [])[:2],   # 兼容旧渲染/旧记录
        'published_at': datetime.now(BJT).strftime('%Y-%m-%d %H:%M:%S'),
        'data_last': data_last,
        'hit': None,      # 开奖后补标
        'num': None,
        'tail': None,
    }
    ledger['records'].append(rec)
    ledger['records'].sort(key=lambda r: r['issue'])
    _save(ledger)
    print(f"[账本] 记录发布: {issue}期 杀{rec['kill']} Top2={rec['top2']} (数据至{data_last})")
    return rec


def settle_past(issues, hh, tt, oo):
    """数据更新后，把账本里已开奖的期号补标对错（hit/num/tail）。"""
    ledger = _load()
    tail_of = {}
    for i, iss in enumerate(issues):
        tail_of[iss] = (hh[i] + tt[i] + oo[i]) % 10
    changed = 0
    for rec in ledger['records']:
        if rec['issue'] not in tail_of:
            continue
        rec['tail'] = tail_of[rec['issue']]
        rec['num'] = f"{hh[issues.index(rec['issue'])]}{tt[issues.index(rec['issue'])]}{oo[issues.index(rec['issue'])]}"
        # 杀1命中 = 和尾 != 票王; 杀2/杀3 命中 = 和尾 != 该码（各自独立核对）
        rec['hit'] = bool(rec['kill'] != rec['tail'])
        _top3 = rec.get('top3') or rec.get('top2') or []
        rec['hit2'] = bool(len(_top3) > 1 and _top3[1] != rec['tail'])
        rec['hit3'] = bool(len(_top3) > 2 and _top3[2] != rec['tail'])
        changed += 1
    if changed:
        _save(ledger)
        print(f"[账本] 补标 {changed} 期开奖结果")
    return changed


def get_records():
    """返回全部发布记录（近期在上）"""
    ledger = _load()
    return list(reversed(ledger['records']))


def get_stats():
    """累计命中率统计：settled=已开奖核对数, hits=杀1对数, hits2/3=杀2/3对数,
    rate=杀1累计命中率, rate2/3=杀2/3累计命中率, pending=待开奖数"""
    recs = get_records()
    settled = [r for r in recs if r.get('hit') is not None]
    hits = sum(1 for r in settled if r['hit'])
    hits2 = sum(1 for r in settled if r.get('hit2'))
    hits3 = sum(1 for r in settled if r.get('hit3'))
    n = len(settled)
    return {
        'total': len(recs),          # 总发布数（含待开奖）
        'settled': n,                # 已核对数
        'hits': hits,                # 杀1对数
        'misses': n - hits,          # 杀1错数
        'rate': round(hits / n * 100, 2) if n else 0.0,   # 杀1累计命中率
        'hits2': hits2,              # 杀2对数
        'misses2': n - hits2,        # 杀2错数
        'rate2': round(hits2 / n * 100, 2) if n else 0.0,  # 杀2累计命中率
        'hits3': hits3,              # 杀3对数
        'misses3': n - hits3,        # 杀3错数
        'rate3': round(hits3 / n * 100, 2) if n else 0.0,  # 杀3累计命中率
        'pending': len(recs) - n,    # 待开奖数
    }


if __name__ == '__main__':
    from engine import load_data
    issues, hh, tt, oo = load_data('fc3d-history.csv')
    n = settle_past(issues, hh, tt, oo)
    stats = get_stats()
    print(f"账本共 {stats['total']} 条发布记录, 补标 {n} 期, 累计命中率 {stats['rate']}% ({stats['hits']}/{stats['settled']})")
    for r in get_records()[:10]:
        print(f"  {r['issue']}期 杀{r['kill']} Top2={r['top2']} hit={r['hit']} 开奖={r['num']} 和尾={r['tail']}")
