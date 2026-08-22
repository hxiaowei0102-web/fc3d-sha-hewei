# -*- coding: utf-8 -*-
"""
固定专家投票 — 参数网格扫描自动选优（样本外口径）
=====================================================
用户需求：专家池固定 800 条不动（cache/pool.json 的 pool 字段），
扫描 win × K 参数网格，在【样本外】数据上逐期 walk-forward 评估，
自动选出最优 (win, K) 写回锁定。

为什么不能用训练窗 500 期选参：
  训练窗 = 专家被选出的同段数据 → 任何 (win,K) 都是 100%（选择偏差假象）。
  选参必须看样本外（专家从未见过的更早数据）→ 真实未来预期。

口径分层（严格防过拟合）：
  A. 扫描段（选优）   = 样本外 2000 期（2019144~2025074）
  B. 验证段（不选优） = 样本外再往前 500 期（更早，专家未见、且不参与选优）
                       → 最优参数在验证段的表现用于判断是否为噪声巧合
  只有 A 段参与选优；B 段仅报告，不参与决策。

网格：win ∈ {40,50,60,70,80,90,100,120,150,180,200,240} × K ∈ {200,300,400,500,600,700,800}
选优 tie-break：样本外命中率 → K 更大 → win 更大（与 hedge_core.grid_scan 一致）。
输出：cache/grid_scan_oos.json + 终端完整表格。
"""
import json
import time

import numpy as np

from engine import load_data
from formulas import feat_list
from hedge_core import hedge_vote, SMOOTH, WINDOW, WIN_MAX, WIN_GRID

CSV = 'fc3d-history.csv'
TRAIN = 500
OOS = 2000            # 扫描段（选优）
VALID = 500           # 验证段（不选优，仅确认）
K_GRID = (200, 300, 400, 500, 600, 700, 800)

# 现有锁定（基准）
CUR_WIN, CUR_K = 40, 600


def build_oos_matrices(issues, hh, tt, oo, pool, L0, t_end):
    """为 [L0, t_end] 构建 pred/hit 矩阵（L0 已含预热）。
    特征：期 t 的特征由 期t-1、期t-2 计算（严格 walk-forward）。
    返回 (pred, hit, at)。at[j] = 期 L0+j 的和尾（用于命中判定）。"""
    F_ext = np.array([
        feat_list(hh[t - 1], tt[t - 1], oo[t - 1],
                  prev=(hh[t - 2], tt[t - 2], oo[t - 2]))
        for t in range(L0, t_end + 1)
    ], dtype=np.int16)                     # (cols, 59)
    at = np.asarray([(hh[i] + tt[i] + oo[i]) % 10 for i in range(t_end + 1)],
                    dtype=np.int16)[L0:t_end + 1]
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
    """hit 的行累计和，用于 O(1) 取任意 [j-win, j) 窗口均值。"""
    return np.cumsum(hit.astype(np.float64), axis=1)


def window_rate(cum, j, win):
    """近 win 期 [j-win, j) 命中率（每专家一行）。j 必须 ≥ win。"""
    return (cum[:, j - 1] - cum[:, j - win - 1]) / win


def eval_params(pred, hit, cum, at, L0, t_start, t_end, win, k):
    """对 [t_start, t_end) 逐期 hedge 投票评估杀1码命中率。"""
    n = t_end - t_start
    hits = 0
    for t in range(t_start, t_end):
        j = t - L0
        rates = window_rate(cum, j, win)
        ti = np.argsort(-rates)[:k]
        w = np.maximum(rates[ti], SMOOTH)
        votes = np.bincount(pred[ti, j], weights=w, minlength=10)
        kill = int(np.argmax(votes))
        if kill != int(at[j]):
            hits += 1
    return hits, n, round(hits / n * 100, 2)


def main():
    t0 = time.time()
    issues, hh, tt, oo = load_data(CSV)
    N = len(issues)
    with open('cache/pool.json', 'r', encoding='utf-8') as f:
        pj = json.load(f)
    pool = pj['pool']
    print(f"数据 {N} 期：{issues[0]}~{issues[-1]}  固定专家池 {len(pool)} 条  "
          f"当前锁定 (win={CUR_WIN}, K={CUR_K})")

    # 窗口边界
    oos_start = N - TRAIN - OOS            # 扫描段起点 = 样本外 2000 期起点
    v_start = oos_start - VALID            # 验证段起点（更早 500 期）
    t_end = N - TRAIN                      # 矩阵末列对应期 = 训练窗第一天
    L0 = v_start - WIN_MAX - 40            # 预热：WIN_MAX+40 期
    assert L0 >= 2, f"预热不足 L0={L0}"
    print(f"窗口：验证段 [{issues[v_start]}~{issues[oos_start-1]}] {VALID}期"
          f"（仅确认，不选优）")
    print(f"      扫描段 [{issues[oos_start]}~{issues[oos_start+OOS-1]}] {OOS}期（选优）")
    print(f"      L0={L0}（含 {WIN_MAX+40} 期预热）\n")

    # 构建矩阵（覆盖验证段+扫描段）
    pred, hit, at = build_oos_matrices(issues, hh, tt, oo, pool, L0, t_end)
    cum = cum_rates(hit)
    print(f"矩阵构建完成 {len(pool)}×{hit.shape[1]}，用时 {time.time()-t0:.1f}s")

    # 基准：当前锁定 (40,600)
    bh, bn, br = eval_params(pred, hit, cum, at, L0, oos_start, oos_start + OOS, CUR_WIN, CUR_K)
    print(f"基准 当前锁定 (win={CUR_WIN}, K={CUR_K}) → 扫描段 {bh}/{bn} = {br}%\n")

    # 网格扫描
    results = []
    for win in WIN_GRID:
        for k in K_GRID:
            h, n, r = eval_params(pred, hit, cum, at, L0, oos_start, oos_start + OOS, win, k)
            results.append({'win': win, 'k': k, 'hits': h, 'total': n, 'rate': r})
    # 选优 tie-break：命中率 → K 大 → win 大
    results.sort(key=lambda r: (-r['rate'], -r['k'], -r['win']))

    # 打印完整表
    print("=" * 88)
    print(f"网格扫描 {len(results)} 组合（扫描段 {OOS} 期，样本外选优口径）")
    print("=" * 88)
    header = f"{'win':>4} " + " ".join(f"K{k:>4}" for k in K_GRID) + "      ← K 列"
    print(header)
    print("-" * 88)
    grid_map = {(r['win'], r['k']): r['rate'] for r in results}
    for win in WIN_GRID:
        row = f"{win:>4} "
        for k in K_GRID:
            r = grid_map[(win, k)]
            mark = " ★" if (win, k) == (results[0]['win'], results[0]['k']) else ""
            row += f"{r:>7.2f}{mark}"
        print(row)
    print("-" * 88)

    # 汇总统计
    rates_all = [r['rate'] for r in results]
    best = results[0]
    print(f"\n✅ 最优：win={best['win']}, K={best['k']} → {best['hits']}/{best['total']} = {best['rate']}%")
    print(f"   全网格均值 {np.mean(rates_all):.2f}% | 中位 {np.median(rates_all):.2f}% | "
          f"最高 {max(rates_all):.2f}% | 最低 {min(rates_all):.2f}% | 极差 {max(rates_all)-min(rates_all):.2f}pp")
    print(f"   当前锁定 (40,600) 排名第 {1 + results.index({'win': CUR_WIN, 'k': CUR_K, 'hits': bh, 'total': bn, 'rate': br})} 位")

    # 验证段确认（最优 + 当前锁定 + 网格均值参考）
    print("\n验证段确认（更早 500 期，不参与选优，仅检验稳健性）：")
    for label, (win, k) in (('最优参数', (best['win'], best['k'])),
                            ('当前锁定', (CUR_WIN, CUR_K))):
        h, n, r = eval_params(pred, hit, cum, at, L0, v_start, oos_start, win, k)
        print(f"  {label:<8} (win={win:>3}, K={k:>3}) → {h}/{n} = {r}%  (基线90%)")
    # 每个 win 最优 k 组合的验证段平均（噪声参考）
    v_rates = []
    for r in results[:15]:
        h, n, vr = eval_params(pred, hit, cum, at, L0, v_start, oos_start, r['win'], r['k'])
        v_rates.append(vr)
    print(f"  扫描段 Top15 组合在验证段的平均 {np.mean(v_rates):.2f}% "
          f"(若≈基线90%说明样本外优势在验证段不可复制)")

    # 保存
    out = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'data': {'n_issues': N, 'first': issues[0], 'last': issues[-1]},
        'n_experts': len(pool),
        'windows': {
            'scan': {'first': issues[oos_start], 'last': issues[oos_start + OOS - 1],
                     'n': OOS, 'role': '选优'},
            'valid': {'first': issues[v_start], 'last': issues[oos_start - 1],
                      'n': VALID, 'role': '仅确认，不选优'},
        },
        'grid': {'wins': list(WIN_GRID), 'ks': list(K_GRID)},
        'baseline_cur': {'win': CUR_WIN, 'k': CUR_K, 'rate': br},
        'best': best,
        'grid_stats': {'mean': round(float(np.mean(rates_all)), 2),
                       'median': round(float(np.median(rates_all)), 2),
                       'max': max(rates_all), 'min': min(rates_all),
                       'range_pp': round(max(rates_all) - min(rates_all), 2)},
        'valid_best': None, 'valid_cur': None,
        'results': results,
        'note': '选优口径=样本外2000期(专家未见)。训练窗100%为选择偏差，不可用于选参。'
                '验证段500期不参与选优，仅检验最优参数稳健性。',
    }
    vb = eval_params(pred, hit, cum, at, L0, v_start, oos_start, best['win'], best['k'])
    vc = eval_params(pred, hit, cum, at, L0, v_start, oos_start, CUR_WIN, CUR_K)
    out['valid_best'] = {'win': best['win'], 'k': best['k'], 'hits': vb[0], 'total': vb[1], 'rate': vb[2]}
    out['valid_cur'] = {'win': CUR_WIN, 'k': CUR_K, 'hits': vc[0], 'total': vc[1], 'rate': vc[2]}

    with open('cache/grid_scan_oos.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 结果已保存 cache/grid_scan_oos.json，总用时 {time.time()-t0:.1f}s")


if __name__ == '__main__':
    main()
