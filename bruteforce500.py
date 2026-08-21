# -*- coding: utf-8 -*-
"""
福彩3D 杀和尾 — 暴力穷举（最新500期，目标=和尾）+ TopK 专家池
=====================================================================
公式池：96特征 × 单/双/三特征线性组合 ≈ 3931万规格（与 formulas.iter_specs 同规则）。
numpy 向量化计算 500 期输出；每族独立小顶堆(pfl=57)在线维护专家池，合并后取 TopK=400。
并列裁决：命中数 → 公式更短 → 字典序（堆内 seq 先到先得近似）。
目标=和尾：命中 = 预测杀码 != 该期和尾 (b+s+g)%10。
walk-forward：第 t 期预测只用 t-1 / t-2 期数据算特征（feat_list 天然满足）。
"""
import json
import os
import time
from heapq import heappush, heappop

import numpy as np

from engine import load_data
from formulas import (feat_list, formula_name, family_of, COEFFS, TRIPLE_COEFFS,
                      NF, B_END, FEAT_VERSION)

CSV = 'fc3d-history.csv'
WINDOW = 500          # 穷举评估窗口 = 最新500期
TOPK = 800            # 专家池规模上限（v3.1: 400→800, 支持更大K）
PFL = 115             # 每族限选上限（7族 × 115 = 805 ≈ TOPK；控制多样性）
POOL_TOTAL = 3840 + 729600 + 38577600   # 单+双+三特征公式总数 = 39,311,040（96特征）


def _update_heap(fam_heaps, fam, hits, terms, const, seq, pfl):
    hp = fam_heaps.get(fam)
    if hp is None:
        hp = fam_heaps[fam] = []
    if len(hp) < pfl:
        heappush(hp, (hits, seq, formula_name(terms, const), terms, const))
    elif hits > hp[0][0]:
        heappop(hp)
        heappush(hp, (hits, seq, formula_name(terms, const), terms, const))


def _fmt_progress(done, total, t0, label):
    el = time.time() - t0
    print(f"  [{label}] {done:,}/{total:,} ({done/total*100:.1f}%) 用时{el:.0f}s", flush=True)


def search_pool(hh, tt, oo, window=WINDOW, topk=TOPK, pfl=PFL, verbose=True):
    """3931万公式 × 最新window期穷举（目标=和尾），按族限选在线维护专家池。

    返回 (pool, fixed_info, stats)
      pool: [{name, family, hits, rate, terms:[[c,idx],...], const}]，按hits降序
      fixed_info: {name, hits, rate} —— 池内第1名（固定公式对照，选择偏差口径）
      stats: {pool_size_total, n_families, window, scan_seconds}
    """
    N = len(hh)
    if N < window + 2:
        raise ValueError(f"数据量不足：仅 {N} 期，至少需要 {window+2} 期。")
    start = N - window
    # 目标 = 和尾 (b+s+g)%10
    tail_arr = [(hh[i] + tt[i] + oo[i]) % 10 for i in range(N)]
    if verbose:
        print(f"穷举窗口: 数据第 {start+1}..{N} 期，共 {window} 期（目标=和尾）")

    # 特征矩阵 (window, 96)，int16 省内存带宽；第k行由 期start+k-1 + 前2期 计算
    rows = [
        feat_list(
            hh[start + k - 1], tt[start + k - 1], oo[start + k - 1],
            prev=(hh[start + k - 2], tt[start + k - 2], oo[start + k - 2]) if start + k - 2 >= 0 else None
        )
        for k in range(window)
    ]
    F = np.array(rows, dtype=np.int16)                 # (500,96)
    ah = np.array(tail_arr[start:start + window], dtype=np.int16)   # 被预测的500个和尾

    fam_heaps = {}
    seq = 0
    t0 = time.time()

    # ---- 单特征: 96×4×10 = 3840 ----
    for idx in range(NF):
        col = F[:, idx]
        for c in COEFFS:
            base = col * c
            for const in range(10):
                out = (base + const) % 10
                hits = int((out != ah).sum())
                _update_heap(fam_heaps, 'A' if idx < 34 else 'B' if idx < B_END else 'C',
                             hits, ((c, idx),), const, seq, pfl)
                seq += 1
    if verbose:
        _fmt_progress(3840, POOL_TOTAL, t0, "单特征")

    # ---- 双特征: C(96,2)×16×10 = 729,600 ----
    done = 3840
    for i in range(NF):
        Fi = F[:, i]
        for j in range(i + 1, NF):
            Fj = F[:, j]
            for c1 in COEFFS:
                p1 = Fi * c1
                for c2 in COEFFS:
                    for const in range(10):
                        out = (p1 + Fj * c2 + const) % 10
                        hits = int((out != ah).sum())
                        _update_heap(fam_heaps, family_of(((c1, i), (c2, j))),
                                     hits, ((c1, i), (c2, j)), const, seq, pfl)
                        seq += 1
            done += 160
    if verbose:
        _fmt_progress(done, POOL_TOTAL, t0, "双特征")

    # ---- 三特征: C(96,3)×27×10 = 38,577,600 ----
    for i in range(NF):
        Fi = F[:, i]
        for j in range(i + 1, NF):
            Fj = F[:, j]
            for k in range(j + 1, NF):
                Fk = F[:, k]
                for c1 in TRIPLE_COEFFS:
                    p1 = Fi * c1
                    for c2 in TRIPLE_COEFFS:
                        p2 = Fj * c2
                        for c3 in TRIPLE_COEFFS:
                            for const in range(10):
                                out = (p1 + p2 + Fk * c3 + const) % 10
                                hits = int((out != ah).sum())
                                _update_heap(fam_heaps, family_of(((c1, i), (c2, j), (c3, k))),
                                             hits, ((c1, i), (c2, j), (c3, k)), const, seq, pfl)
                                seq += 1
            done += 270
            if verbose and done % 1000000 < 270:
                _fmt_progress(done, POOL_TOTAL, t0, "三特征")

    scan_seconds = time.time() - t0
    if verbose:
        _fmt_progress(POOL_TOTAL, POOL_TOTAL, t0, "完成")

    # 合并各族堆，按 hits 降序取 topk
    all_entries = [e for hp in fam_heaps.values() for e in hp]
    all_entries.sort(key=lambda e: (-e[0], e[1]))       # hits 降序, seq 升序
    chosen = all_entries[:topk]
    pool = [{
        'name': e[2], 'family': family_of(e[3]),
        'hits': e[0], 'rate': round(e[0] / window, 4),
        'terms': [[c, idx] for c, idx in e[3]], 'const': e[4],
    } for e in chosen]
    fixed_info = {'name': pool[0]['name'], 'hits': pool[0]['hits'],
                  'rate': pool[0]['rate'], 'terms': pool[0]['terms'],
                  'const': pool[0]['const']} if pool else None
    stats = {'pool_size_total': POOL_TOTAL, 'n_families': len(fam_heaps),
             'window': window, 'scan_seconds': round(scan_seconds, 1)}

    if verbose:
        print(f"  遍历公式规格: {seq:,} 条（应={POOL_TOTAL:,}）")
        print(f"  族数={len(fam_heaps)}, 专家池={len(pool)}（各族限选 pfl={pfl}）")
        print(f"  池内第1名(固定公式对照): {fixed_info['name']}  命中{fixed_info['hits']}/{window} = {fixed_info['rate']*100:.2f}%")
    return pool, fixed_info, stats


def main(verbose=True):
    issues, hh, tt, oo = load_data(CSV)
    N = len(issues)
    print(f"数据 {N} 期：{issues[0]} ~ {issues[-1]}")
    pool, fixed_info, stats = search_pool(hh, tt, oo, verbose=verbose)
    out = {
        'window': WINDOW, 'topk': TOPK, 'pfl': PFL,
        'feat_version': FEAT_VERSION,
        'n_features': NF,
        'data_info': {'n_issues': N, 'first': issues[0], 'last': issues[-1]},
        'stats': stats,
        'fixed': fixed_info,
        'pool': pool,
    }
    os.makedirs('cache', exist_ok=True)
    with open('cache/pool.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"\n已写入 cache/pool.json（专家池 {len(pool)} 条）")
    return pool, fixed_info, stats


if __name__ == '__main__':
    main()
