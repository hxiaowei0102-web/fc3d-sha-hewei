# -*- coding: utf-8 -*-
"""
固定专家 Hedge 投票 — 以【近500期】为准的网格扫描自动选优
=============================================================
老板拍板口径：固定 800 专家池，扫描 win×K 网格，
以【最新500期】命中率为第一选优标准（此段是未来预测的最近实战窗口），
并列时以样本外 2000 期打破平局，再并列取 K 大者。

三口径同时输出（透明可查）：
  A. 近500期命中率（主口径，选择偏差段，但代表"最近实战表现"）
  B. 样本外2000期命中率（次级口径，专家未见过的更早数据，真实预期）
  C. 验证段500期命中率（参考，更早再往前，检验稳健性）

已知事实（预检）：K≥200 的组合在近500期全部 100% 饱和 → 必须靠 B 打破平局。
选优规则：(-rate_500, -rate_oos, -k, -win)。
输出：cache/grid_scan_500.json + 终端完整表。
"""
import json
import time

import numpy as np

from engine import load_data
from formulas import feat_list
from hedge_core import hedge_vote, SMOOTH, WINDOW, WIN_MAX, WIN_GRID

CSV = 'fc3d-history.csv'
TRAIN = 500
OOS = 2000
VALID = 500
K_GRID = (100, 200, 300, 400, 500, 600, 700, 800)


def build_oos_matrices(issues, hh, tt, oo, pool, L0, t_end):
    """为 [L0, t_end] 构建 pred/hit 矩阵（含预热）。"""
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


def eval_params(pred, hit, cum, at, L0, t_start, t_end, win, k):
    n = t_end - t_start
    hits = 0
    for t in range(t_start, t_end):
        j = t - L0
        rates = window_rate(cum, j, win)
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

    # 窗口边界
    tr_start = N - TRAIN                # 近500期（主口径）
    oos_start = tr_start - OOS          # 样本外2000期
    v_start = oos_start - VALID         # 验证段500期（参考）
    t_end = N                            # 矩阵覆盖到最后一期（评估近500期需要）
    L0 = v_start - WIN_MAX - 40
    assert L0 >= 2
    print(f"近500期 [{issues[tr_start]}~{issues[N-1]}]（主口径，选优）")
    print(f"样本外2000期 [{issues[oos_start]}~{issues[tr_start-1]}]（次级口径，破平局）")
    print(f"验证段500期 [{issues[v_start]}~{issues[oos_start-1]}]（参考，不参与选优）")

    pred, hit, at = build_oos_matrices(issues, hh, tt, oo, pool, L0, t_end)
    cum = cum_rates(hit)
    print(f"矩阵 {len(pool)}×{hit.shape[1]} 构建完成，用时 {time.time()-t0:.1f}s\n")

    results = []
    for win in WIN_GRID:
        for k in K_GRID:
            h1, n1, r1 = eval_params(pred, hit, cum, at, L0, tr_start, N, win, k)          # 近500期
            h2, n2, r2 = eval_params(pred, hit, cum, at, L0, oos_start, tr_start, win, k)   # 样本外
            h3, n3, r3 = eval_params(pred, hit, cum, at, L0, v_start, oos_start, win, k)    # 验证段
            results.append({'win': win, 'k': k,
                            'r500': r1, 'h500': h1, 'n500': n1,
                            'roos': r2, 'hoos': h2, 'noos': n2,
                            'rvalid': r3, 'hvalid': h3, 'nvalid': n3})
    results.sort(key=lambda r: (-r['r500'], -r['roos'], -r['k'], -r['win']))

    # 完整表
    print("=" * 110)
    print(f"网格 {len(results)} 组合：近500期命中率（主）| 样本外2000期（次）| 验证段500期（参考）")
    print("=" * 110)
    hdr = f"{'win':>4} " + " ".join(f"{'K='+str(k):>13}" for k in K_GRID) + "    ← 每格 = 近500/样本外/验证"
    print(hdr)
    print("-" * 110)
    g = {(r['win'], r['k']): r for r in results}
    for win in WIN_GRID:
        row = f"{win:>4} "
        for k in K_GRID:
            r = g[(win, k)]
            star = "★" if (r['win'], r['k']) == (results[0]['win'], results[0]['k']) else " "
            row += f"{r['r500']:>6.1f}/{r['roos']:>6.1f}/{r['rvalid']:>5.1f}{star}"
        print(row)
    print("-" * 110)

    best = results[0]
    cur = next(r for r in results if r['win'] == 40 and r['k'] == 600)
    print(f"\n✅ 最优：win={best['win']}, K={best['k']}  "
          f"近500期 {best['r500']}%  |  样本外 {best['roos']}%  |  验证段 {best['rvalid']}%")
    print(f"   当前锁定 (40,600)：近500期 {cur['r500']}%  |  样本外 {cur['roos']}%  |  验证段 {cur['rvalid']}%")
    print(f"   当前锁定排名：近500期并列第 {1 + sum(1 for r in results if r['r500'] > cur['r500'])} 位")

    # 近500期非100%的组合（暴露选择偏差范围）
    non100 = [r for r in results if r['r500'] < 100.0]
    print(f"\n近500期 <100% 的组合 {len(non100)} 个（K=100 系列为主，暴露选择偏差）:")
    for r in sorted(non100, key=lambda x: -x['r500'])[:8]:
        print(f"  win={r['win']:>3} K={r['k']:>3}  近500={r['r500']}%  样本外={r['roos']}%")

    out = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'data': {'n_issues': N, 'first': issues[0], 'last': issues[-1]},
        'n_experts': len(pool),
        'windows': {
            'train500': {'first': issues[tr_start], 'last': issues[N-1], 'n': TRAIN, 'role': '主口径(选优)'},
            'oos2000': {'first': issues[oos_start], 'last': issues[tr_start-1], 'n': OOS, 'role': '次级口径(破平局)'},
            'valid500': {'first': issues[v_start], 'last': issues[oos_start-1], 'n': VALID, 'role': '参考'},
        },
        'grid': {'wins': list(WIN_GRID), 'ks': list(K_GRID)},
        'best': best,
        'cur_locked': cur,
        'results': results,
        'note': '选优规则: 近500期命中率→样本外2000期→K大→win大。'
                '近500期K≥200全部100%饱和(选择偏差)，由样本外破平局。',
    }
    with open('cache/grid_scan_500.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已保存 cache/grid_scan_500.json，总用时 {time.time()-t0:.1f}s")


if __name__ == '__main__':
    main()
