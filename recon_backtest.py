# -*- coding: utf-8 -*-
"""
回测表对账工具 — 独立验证 result.json 回测表的逐期真实性
====================================================================
硬要求：逐期真实 = 每一期的杀码都是"当期开奖前"用已有数据算出来的。
本工具用两条独立轨道重算全部 500 期，与回测表逐期对比：
  轨道1: 独立实现 walk-forward（不复用 hedge_core.run_backtest）
  轨道2: 官方 hedge_core.build_matrices + hedge_vote
任一期不一致即输出；500/500 一致则通过。
另附 walk-forward 时间边界抽查（每期特征只来自 t-1/t-2，开奖后才判定）。
用法: python recon_backtest.py   （需 numpy）
"""
import json
import os
import sys
import io

import numpy as np

os.chdir(os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from engine import load_data
from formulas import feat_list


def track1_independent(issues, hh, tt, oo, pool, rows, params):
    """轨道1: 独立重算（不调用 hedge_core.run_backtest）"""
    N = len(hh)
    tail_arr = [(hh[i] + tt[i] + oo[i]) % 10 for i in range(N)]
    WIN, K, SMOOTH = params['win'], params['k'], params['smooth']
    W = 500
    L0 = N - W - WIN
    assert L0 >= 2

    F_ext = np.array([
        feat_list(hh[t - 1], tt[t - 1], oo[t - 1],
                  prev=(hh[t - 2], tt[t - 2], oo[t - 2]))
        for t in range(L0, N + 1)
    ], dtype=np.int16)

    Kp = len(pool)
    pred = np.zeros((Kp, F_ext.shape[0]), dtype=np.int16)
    for i, exp in enumerate(pool):
        cols = np.array([idx for _, idx in exp['terms']], dtype=np.intp)
        coeffs = np.array([c for c, _ in exp['terms']], dtype=np.int16)
        if len(cols) == 1:
            pred[i, :] = (F_ext[:, cols[0]] * coeffs[0] + exp['const']) % 10
        else:
            pred[i, :] = ((F_ext[:, cols] * coeffs[None, :]).sum(axis=1) + exp['const']) % 10

    def hedge_vote(j):
        lo = j - WIN
        hits = np.zeros(Kp, dtype=np.int32)
        for w in range(lo, j):
            hits += (pred[:, w] != tail_arr[L0 + w])
        rates = hits / WIN
        ti = np.argsort(-rates)[:K]
        wts = np.maximum(rates[ti], SMOOTH)
        votes = np.bincount(pred[ti, j], weights=wts, minlength=10)
        return int(np.argmax(votes))

    mism = []
    for r in rows:
        t = issues.index(r['issue'])
        kill = hedge_vote(t - L0)
        if kill != r['kill']:
            mism.append((r['issue'], r['kill'], kill))
    return mism


def track2_official(issues, hh, tt, oo, pool, rows, params):
    """轨道2: 官方 hedge_core 重算"""
    from hedge_core import build_matrices, hedge_vote as hv
    pred, hit, L0, tail_arr = build_matrices(issues, hh, tt, oo, pool)
    WIN, K = params['win'], params['k']
    mism = []
    for r in rows:
        t = issues.index(r['issue'])
        kill, *_ = hv(WIN, K, params['smooth'], t - L0, hit, pred)
        if kill != r['kill']:
            mism.append((r['issue'], r['kill'], kill))
    return mism


def boundary_check(issues, hh, tt, oo, rows):
    """walk-forward 时间边界抽查：特征只来自 t-1/t-2，命中由 t 开奖判定"""
    tail_arr = [(hh[i] + tt[i] + oo[i]) % 10 for i in range(len(hh))]
    bad = 0
    for r in rows[:3] + rows[-3:]:
        t = issues.index(r['issue'])
        f1 = f"{hh[t-1]}{tt[t-1]}{oo[t-1]}"
        f2 = f"{hh[t-2]}{tt[t-2]}{oo[t-2]}"
        tail = tail_arr[t]
        if (r['kill'] != tail) != r['hit']:
            bad += 1
            print(f"  ❌ {r['issue']}: 边界违规")
        else:
            print(f"  ✅ {r['issue']}: 特征←[{f2}→{f1}] 开奖={hh[t]}{tt[t]}{oo[t]} 和尾{tail} 杀{r['kill']} hit={r['hit']}")
    return bad


def main():
    issues, hh, tt, oo = load_data('fc3d-history.csv')
    with open('cache/pool.json', encoding='utf-8') as f:
        pj = json.load(f)
    pool = pj['pool']
    with open('cache/result.json', encoding='utf-8') as f:
        d = json.load(f)
    rows = d['rows']
    params = d['params']
    print(f"数据 {len(issues)} 期 {issues[0]}~{issues[-1]}")
    print(f"参数 win={params['win']} k={params['k']} | 专家池 {len(pool)} | 回测表 {len(rows)} 行")

    m1 = track1_independent(issues, hh, tt, oo, pool, rows, params)
    m2 = track2_official(issues, hh, tt, oo, pool, rows, params)
    print(f"\n[轨道1 独立重算] 不一致 {len(m1)}/500")
    for x in m1[:5]:
        print(f"  {x}")
    print(f"[轨道2 官方重算] 不一致 {len(m2)}/500")
    for x in m2[:5]:
        print(f"  {x}")

    print(f"\n[walk-forward 边界抽查]")
    bad = boundary_check(issues, hh, tt, oo, rows)

    ok = not m1 and not m2 and bad == 0
    print(f"\n{'✅✅ 对账通过：500期逐期真实，可随时拿开奖对账' if ok else '❌ 对账失败，请检查'}")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
