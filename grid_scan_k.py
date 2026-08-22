# -*- coding: utf-8 -*-
"""
固定每期参与投票的专家数（K）— 近500期最优网格扫描自动选优
=============================================================
老板口径：固定每期参与投票的专家数 K，以【近500期】最优为准，网格扫描自动选优。
win 沿用当前锁定值 40（参数锁定的一部分），只扫 K ∈ {100..800}（细粒度15档）。

三口径输出：
  A. 近500期命中率（主口径，选择偏差段，代表最近实战）
  B. 样本外2000期命中率（次级口径，破平局）
  C. 验证段500期命中率（参考，更早，检验稳健性）

选优规则：近500期最高 → 并列按样本外最高 → 再并列 K 大。
输出：cache/grid_scan_k.json + 终端表格。
"""
import json
import time

import numpy as np

from engine import load_data
from formulas import feat_list
from hedge_core import SMOOTH, WIN_MAX

CSV = 'fc3d-history.csv'
TRAIN = 500
OOS = 2000
VALID = 500
WIN_FIXED = 40            # 沿用当前锁定 win
K_GRID = (100, 150, 200, 250, 300, 350, 400, 450,
          500, 550, 600, 650, 700, 750, 800)
CUR_K = 600


def build_oos_matrices(issues, hh, tt, oo, pool, L0, t_end):
    F_ext = np.array([
        feat_list(hh[t - 1], tt[t - 1], oo[t - 1],
                  prev=(hh[t - 2], tt[t - 2], oo[t - 2]))
        for t in range(L0, t_end)
    ], dtype=np.int16)
    at = np.asarray([(hh[i] + tt[i] + oo[i]) % 10 for i in range(t_end)],
                    dtype=np.int16)[L0:t_end]
    K = len(pool)
    pred = np.zeros((K, F_ext.shape[0]), dtype=np.int16)
    for i, exp in enumerate(pool):
        cols = np.array([idx for _, idx in exp['terms']], dtype=np.intp)
        coeffs = np.array([c for c, _ in exp['terms']], dtype=np.int16)
        if len(cols) == 1:
            pred[i, :] = (F_ext[:, cols[0]] * coeffs[0] + exp['const']) % 10
        else:
            pred[i, :] = ((F_ext[:, cols] * coeffs[None, :]).sum(axis=1) + exp['const']) % 10
    hit = (pred != at[None, :])
    return pred, hit, at


def cum_rates(hit):
    return np.cumsum(hit.astype(np.float64), axis=1)


def window_rate(cum, j, win):
    return (cum[:, j - 1] - cum[:, j - win - 1]) / win


def eval_params(pred, hit, cum, at, L0, t_start, t_end, k):
    n = t_end - t_start
    hits = 0
    for t in range(t_start, t_end):
        j = t - L0
        rates = window_rate(cum, j, WIN_FIXED)
        ti = np.argsort(-rates)[:k]
        w = np.maximum(rates[ti], SMOOTH)
        votes = np.bincount(pred[ti, j], weights=w, minlength=10)
        if int(np.argmax(votes)) != int(at[j]):
            hits += 1
    return hits, n, round(hits / n * 100, 2)


def main():
    t0 = time.time()
    issues, hh, tt, oo = load_data(CSV)
    N = len(issues)
    with open('cache/pool.json', 'r', encoding='utf-8') as f:
        pj = json.load(f)
    pool = pj['pool']
    print(f"数据 {N} 期：{issues[0]}~{issues[-1]}  固定专家池 {len(pool)} 条")

    tr_start = N - TRAIN
    oos_start = tr_start - OOS
    v_start = oos_start - VALID
    L0 = v_start - WIN_MAX - 40
    pred, hit, at = build_oos_matrices(issues, hh, tt, oo, pool, L0, N)
    cum = cum_rates(hit)
    print(f"矩阵 {len(pool)}×{hit.shape[1]} 完成 | win 固定 {WIN_FIXED} | "
          f"近500[{issues[tr_start]}~{issues[N-1]}] 样本外[{issues[oos_start]}~{issues[tr_start-1]}] "
          f"验证[{issues[v_start]}~{issues[oos_start-1]}]\n")

    results = []
    for k in K_GRID:
        h1, n1, r1 = eval_params(pred, hit, cum, at, L0, tr_start, N, k)
        h2, n2, r2 = eval_params(pred, hit, cum, at, L0, oos_start, tr_start, k)
        h3, n3, r3 = eval_params(pred, hit, cum, at, L0, v_start, oos_start, k)
        results.append({'k': k, 'r500': r1, 'h500': h1, 'n500': n1,
                        'roos': r2, 'hoos': h2, 'noos': n2,
                        'rvalid': r3, 'hvalid': h3, 'nvalid': n3})
    results.sort(key=lambda r: (-r['r500'], -r['roos'], -r['k']))

    print("=" * 64)
    print(f"K 网格扫描（win 固定 {WIN_FIXED}）· 每期参与投票专家数")
    print("=" * 64)
    print(f"{'K':>5}  {'近500期':>10}  {'样本外2000期':>10}  {'验证段500期':>10}")
    print("-" * 64)
    for r in results:
        star = " ★" if r['k'] == results[0]['k'] else ""
        cur = " ◀当前" if r['k'] == CUR_K else ""
        print(f"{r['k']:>5}  {r['r500']:>7.2f}%  {r['roos']:>7.2f}%  {r['rvalid']:>7.2f}%{star}{cur}")
    print("-" * 64)

    best = results[0]
    cur = next(r for r in results if r['k'] == CUR_K)
    print(f"\n✅ 自动选优：K={best['k']}  近500期 {best['r500']}% | 样本外 {best['roos']}% | 验证段 {best['rvalid']}%")
    print(f"   当前 K={CUR_K}：近500期 {cur['r500']}% | 样本外 {cur['roos']}% | 验证段 {cur['rvalid']}%")
    print(f"   近500期并列100%的K: {[r['k'] for r in results if r['r500'] == 100.0]}")

    out = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'data': {'n_issues': N, 'first': issues[0], 'last': issues[-1]},
        'n_experts': len(pool), 'win_fixed': WIN_FIXED, 'cur_k': CUR_K,
        'windows': {'train500': '主口径', 'oos2000': '破平局', 'valid500': '参考'},
        'best': best, 'cur': cur,
        'results': results,
        'note': f'选优规则: 近500期→样本外→K大。win固定{WIN_FIXED}，扫K。近500期K≥200全饱和(选择偏差)。',
    }
    with open('cache/grid_scan_k.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已保存 cache/grid_scan_k.json，总用时 {time.time()-t0:.1f}s")


if __name__ == '__main__':
    main()
