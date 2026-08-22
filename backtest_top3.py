# -*- coding: utf-8 -*-
"""
票码1/2/3（杀1/杀2/杀3码）命中率回测
=====================================
口径定义（与页面一致）：
  票码1(杀1码) = 和尾 ∉ {kill}                      基线 90%
  票码2(杀2码) = 和尾 ∉ {kill, 票数第2}              基线 80%
  票码3(杀3码) = 和尾 ∉ {kill, 票数第2, 票数第3}     基线 70%

两个窗口：
  A. 训练窗口 500 期（result.json，专家被选出的同段数据 → 选择偏差口径，仅供对账）
  B. 样本外 2000 期（专家未见过、更早的历史数据 → 真实未来预期），并分 4×500 段看稳定性

严格 walk-forward：预测第 t 期只用 ≤t-1 数据算特征与专家命中率，绝不偷看未来。
"""
import json
import time

import numpy as np

from engine import load_data
from formulas import feat_list
from hedge_core import hedge_vote, SMOOTH, WINDOW, WIN_MAX

CSV = 'fc3d-history.csv'
TRAIN = 500          # 专家训练/回测窗口
OOS = 2000           # 样本外窗口长度


def load_pool():
    with open('cache/pool.json', 'r', encoding='utf-8') as f:
        pj = json.load(f)
    return pj['pool'], pj['locked']


def build_oos_matrices(issues, hh, tt, oo, pool, N, oos_start):
    """为样本外窗口 [oos_start, N-TRAIN) 构建 pred/hit 矩阵。
    L0 取更早，保证样本外每期的近 win 命中窗口也满。
    特征：期 t 的特征由 期t-1、t-2 计算（严格 walk-forward）。
    """
    L0 = oos_start - WIN_MAX - 40          # 再往前留 240+40 期预热
    assert L0 >= 2, f"预热不足：L0={L0}"
    F_ext = np.array([
        feat_list(hh[t - 1], tt[t - 1], oo[t - 1],
                  prev=(hh[t - 2], tt[t - 2], oo[t - 2]))
        for t in range(L0, N - TRAIN + 1)
    ], dtype=np.int16)                     # (cols, 59)
    tail_all = np.asarray([(hh[i] + tt[i] + oo[i]) % 10 for i in range(N)], dtype=np.int16)
    at_ext = tail_all[L0:N - TRAIN + 1]    # 末列对应期 N-TRAIN（样本外最后一天）
    K = len(pool)
    pred = np.zeros((K, F_ext.shape[0]), dtype=np.int16)
    for i, exp in enumerate(pool):
        cols = np.array([idx for _, idx in exp['terms']], dtype=np.intp)
        coeffs = np.array([c for c, _ in exp['terms']], dtype=np.int16)
        if len(cols) == 1:
            pred[i, :] = (F_ext[:, cols[0]] * coeffs[0] + exp['const']) % 10
        else:
            pred[i, :] = ((F_ext[:, cols] * coeffs[None, :]).sum(axis=1) + exp['const']) % 10
    hit = (pred != at_ext[None, :])
    return pred, hit, L0


def stats_window(pred, hit, L0, issues, hh, tt, oo, t_start, t_end, win, k):
    """对 [t_start, t_end) 逐期统计 3 口径命中率 + 连中/连错。"""
    ta = [(hh[i] + tt[i] + oo[i]) % 10 for i in range(len(hh))]
    hits = {'kill': [], 'top2': [], 'top3': []}
    for t in range(t_start, t_end):
        j = t - L0
        kill, ti, w, votes, top_rate = hedge_vote(win, k, SMOOTH, j, hit, pred)
        order = sorted(range(10), key=lambda x: -float(votes[x]))
        c2, c3 = order[1], order[2]
        hits['kill'].append(kill != ta[t])
        hits['top2'].append(ta[t] not in (kill, c2))
        hits['top3'].append(ta[t] not in (kill, c2, c3))
    out = {}
    for name in ('kill', 'top2', 'top3'):
        arr = hits[name]
        n = len(arr)
        h = sum(arr)
        cur_win = 0
        for x in reversed(arr):
            if x:
                cur_win += 1
            else:
                break
        max_lose = cl = 0
        for x in arr:
            cl = cl + 1 if not x else 0
            max_lose = max(max_lose, cl)
        out[name] = {'n': n, 'hit': h, 'rate': round(h / n * 100, 2),
                     'cur_win': cur_win, 'max_lose': max_lose}
    return out


def fmt_row(label, s, baseline):
    return (f"{label:<16} {s['hit']:>5}/{s['n']:<5} {s['rate']:>7.2f}%  "
            f"基线{baseline:>3.0f}%  {s['cur_win']:>4}期连中  最大连错{s['max_lose']}期")


def main():
    t0 = time.time()
    issues, hh, tt, oo = load_data(CSV)
    N = len(issues)
    pool, locked = load_pool()
    win, k = int(locked['win']), int(locked['k'])
    print(f"数据 {N} 期：{issues[0]}~{issues[-1]}  专家池 {len(pool)}  锁定 win={win}, K={k}")
    print(f"方案: 固定{len(pool)}专家 + win={win} + K={k}（锁定确定性模式）\n")

    # ── A. 训练窗口 500 期（选择偏差口径，与页面回测表对账）──
    res = json.load(open('cache/result.json', encoding='utf-8'))
    rows = res['rows']                     # 近期→远期
    ta_tr = []
    for r in rows:
        tail = (int(r['num'][0]) + int(r['num'][1]) + int(r['num'][2])) % 10
        top3 = r['top3']
        ta_tr.append(tail)
        r['_h1'] = r['kill'] != tail
        r['_h2'] = tail not in (top3[0], top3[1])
        r['_h3'] = tail not in set(top3)
    A = {}
    for name, key, base in (('kill', '_h1', 90), ('top2', '_h2', 80), ('top3', '_h3', 70)):
        arr = [r[key] for r in rows]
        cur_win = 0
        for x in arr:                      # 近期在上，从头数连中
            if x:
                cur_win += 1
            else:
                break
        max_lose = cl = 0
        for x in reversed(arr):
            cl = cl + 1 if not x else 0
            max_lose = max(max_lose, cl)
        A[name] = {'n': len(arr), 'hit': sum(arr), 'rate': round(sum(arr) / len(arr) * 100, 2),
                   'cur_win': cur_win, 'max_lose': max_lose, 'base': base}

    print("=" * 78)
    print("A. 训练窗口 500 期（专家被选出的同段数据 → 选择偏差口径，仅供对账，不可作未来预期）")
    print("=" * 78)
    for name, lab, base in (('kill', '票码1(杀1码)', 90), ('top2', '票码2(杀2码)', 80), ('top3', '票码3(杀3码)', 70)):
        print(fmt_row(lab, A[name], base))
    print(f"  注: 100% 因为专家池正是从这500期里挑选的 → 过拟合于本段, 真实水平看 B")

    # ── B. 样本外 2000 期（真实预期）──
    oos_start = N - TRAIN - OOS           # 样本外起点
    print("\n" + "=" * 78)
    print(f"B. 样本外 {OOS} 期（{issues[oos_start]}~{issues[oos_start+OOS-1]}，专家从未见过 → 真实未来预期）")
    print("=" * 78)
    pred, hit, L0 = build_oos_matrices(issues, hh, tt, oo, pool, N, oos_start)
    print(f"  矩阵构建完成 ({len(pool)}×{hit.shape[1]})，L0={L0}，用时 {time.time()-t0:.1f}s")

    B = stats_window(pred, hit, L0, issues, hh, tt, oo,
                     oos_start, oos_start + OOS, win, k)
    for name, lab, base in (('kill', '票码1(杀1码)', 90), ('top2', '票码2(杀2码)', 80), ('top3', '票码3(杀3码)', 70)):
        print(fmt_row(lab, B[name], base))

    # ── B2. 样本外分 4×500 段看稳定性 ──
    print("\n  样本外分 4×500 段（检验稳定性）:")
    segs = []
    for si in range(4):
        s0 = oos_start + si * 500
        seg = stats_window(pred, hit, L0, issues, hh, tt, oo, s0, s0 + 500, win, k)
        segs.append(seg)
        print(f"    {issues[s0]}~{issues[s0+499]}  "
              f"票1 {seg['kill']['rate']:5.2f}%  票2 {seg['top2']['rate']:5.2f}%  票3 {seg['top3']['rate']:5.2f}%")
    print(f"    平均           "
          f"票1 {np.mean([s['kill']['rate'] for s in segs]):5.2f}%  "
          f"票2 {np.mean([s['top2']['rate'] for s in segs]):5.2f}%  "
          f"票3 {np.mean([s['top3']['rate'] for s in segs]):5.2f}%")

    # 保存
    out = {
        'params': {'win': win, 'k': k, 'n_experts': len(pool), 'locked': locked},
        'data': {'n_issues': N, 'first': issues[0], 'last': issues[-1]},
        'train_window': {name: A[name] for name in ('kill', 'top2', 'top3')},
        'oos_window': {name: B[name] for name in ('kill', 'top2', 'top3')},
        'oos_segments': [{'first': issues[s0], 'last': issues[s0+499],
                          'kill': segs[si]['kill']['rate'],
                          'top2': segs[si]['top2']['rate'],
                          'top3': segs[si]['top3']['rate']} for si, s0 in enumerate(range(oos_start, oos_start + OOS, 500))],
        'note': 'train=选择偏差(专家被选出的同段数据)，oos=专家未见过的更早2000期(真实预期)',
    }
    with open('cache/top3_backtest.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 结果已保存 cache/top3_backtest.json，总用时 {time.time()-t0:.1f}s")


if __name__ == '__main__':
    main()
