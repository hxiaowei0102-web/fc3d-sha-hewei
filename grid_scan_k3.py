# -*- coding: utf-8 -*-
"""
固定每期参与投票专家数 K — 近100/200/500期三窗口最优网格扫描自动选优
=====================================================================
老板口径：固定 K，以近100期、近200期、近500期三个窗口最优为准。
win 沿用锁定值 40；K ∈ {100..800} 细粒度 15 档。

选优规则：近100期最高 → 近200期 → 近500期 → K大（100期最贴近实战，优先破平局）
同时输出样本外2000期 / 验证段500期 供参考（不参与选优）。
输出：cache/grid_scan_k3.json + 终端表格。
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
WIN_FIXED = 40
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

    tr_start = N - TRAIN               # 近500期起点
    oos_start = tr_start - OOS
    v_start = oos_start - VALID
    L0 = v_start - WIN_MAX - 40
    pred, hit, at = build_oos_matrices(issues, hh, tt, oo, pool, L0, N)
    cum = cum_rates(hit)
    print(f"矩阵 {len(pool)}×{hit.shape[1]} 完成 | win={WIN_FIXED}\n")

    # 近100/200期起点
    s100 = N - 100
    s200 = N - 200

    results = []
    for k in K_GRID:
        h1, n1, r1 = eval_params(pred, hit, cum, at, L0, s100, N, k)      # 近100
        h2, n2, r2 = eval_params(pred, hit, cum, at, L0, s200, N, k)      # 近200
        h3, n3, r3 = eval_params(pred, hit, cum, at, L0, tr_start, N, k)  # 近500
        h4, n4, r4 = eval_params(pred, hit, cum, at, L0, oos_start, tr_start, k)  # 样本外
        h5, n5, r5 = eval_params(pred, hit, cum, at, L0, v_start, oos_start, k)   # 验证
        results.append({'k': k,
                        'r100': r1, 'h100': h1, 'n100': n1,
                        'r200': r2, 'h200': h2, 'n200': n2,
                        'r500': r3, 'h500': h3, 'n500': n3,
                        'roos': r4, 'hoos': h4, 'noos': n4,
                        'rvalid': r5, 'hvalid': h5, 'nvalid': n5})
    # 选优：近100 → 近200 → 近500 → K大
    results.sort(key=lambda r: (-r['r100'], -r['r200'], -r['r500'], -r['k']))

    print("=" * 86)
    print(f"K 网格扫描（win={WIN_FIXED}）· 固定每期参与投票专家数 · 三窗口选优")
    print("=" * 86)
    print(f"{'K':>5}  {'近100':>8}  {'近200':>8}  {'近500':>8}  {'样本外':>8}  {'验证段':>8}")
    print("-" * 86)
    for r in results:
        star = " ★" if r['k'] == results[0]['k'] else ""
        cur = " ◀当前" if r['k'] == CUR_K else ""
        print(f"{r['k']:>5}  {r['r100']:>6.2f}%  {r['r200']:>6.2f}%  {r['r500']:>6.2f}%  "
              f"{r['roos']:>6.2f}%  {r['rvalid']:>6.2f}%{star}{cur}")
    print("-" * 86)

    best = results[0]
    cur = next(r for r in results if r['k'] == CUR_K)
    print(f"\n✅ 自动选优：K={best['k']}  近100={best['r100']}% 近200={best['r200']}% "
          f"近500={best['r500']}% | 样本外{best['roos']}% 验证段{best['rvalid']}%")
    print(f"   当前 K={CUR_K}：近100={cur['r100']}% 近200={cur['r200']}% 近500={cur['r500']}% | "
          f"样本外{cur['roos']}% 验证段{cur['rvalid']}%")
    print(f"   近100期并列100%: {[r['k'] for r in results if r['r100'] == 100.0]}")
    print(f"   近200期并列100%: {[r['k'] for r in results if r['r200'] == 100.0]}")
    print(f"   近500期并列100%: {[r['k'] for r in results if r['r500'] == 100.0]}")

    out = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'data': {'n_issues': N, 'first': issues[0], 'last': issues[-1]},
        'n_experts': len(pool), 'win_fixed': WIN_FIXED, 'cur_k': CUR_K,
        'windows': {'r100': '近100期(主)', 'r200': '近200期(次)', 'r500': '近500期(次)',
                    'roos': '样本外2000(参考)', 'rvalid': '验证段500(参考)'},
        'best': best, 'cur': cur,
        'results': results,
        'note': '选优规则: 近100期→近200期→近500期→K大。win固定40，扫K。',
    }
    with open('cache/grid_scan_k3.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已保存 cache/grid_scan_k3.json，总用时 {time.time()-t0:.1f}s")


if __name__ == '__main__':
    main()
