# -*- coding: utf-8 -*-
"""
确定性验证 — 发布值 = 回测值（v2.0 同款语义）
====================================================================
铁证测试：2026224 期开奖前发布的是「杀 2」（账本 predictions.json 记录）。
本脚本模拟开奖后（CSV 追加 2026224 开奖号）用【同一固定专家池 + 固定 win/k】
重算 500 期回测表，断言回测表里 2026224 这一行 kill == 2。
若通过 → 每天发布的预测 = 开奖完回测表同一期数值，随时可对账。

用法: python verify_determinism.py
"""
import io
import json
import sys

import numpy as np

if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from engine import load_data, get_next_issue
from formulas import feat_list
from hedge_core import build_matrices, hedge_vote, WINDOW

CSV = 'fc3d-history.csv'
NEXT_ISSUE = '2026224'          # 账本里已真实发布的期号
PUBLISHED_KILL = 2              # 账本发布值（开奖前）
SIM_DRAW = '123'                # 模拟开奖号（仅占位，回测表 kill 不依赖具体开奖号）


def main():
    # 1. 加载真实历史（截至 2026223）
    issues, hh, tt, oo = load_data(CSV)
    assert issues[-1] == '2026223', f"CSV 末期异常: {issues[-1]}"
    assert get_next_issue(issues[-1]) == NEXT_ISSUE

    # 2. 读取锁定后的固定专家池 + 固定参数
    with open('cache/pool.json', encoding='utf-8') as f:
        pj = json.load(f)
    assert pj.get('locked'), 'pool.json 未锁定参数！'
    pool = pj['pool']
    win, k = int(pj['locked']['win']), int(pj['locked']['k'])
    print(f"锁定池 {len(pool)} 专家 | 锁定参数 win={win} k={k}")

    # 3. 模拟开奖后：CSV 追加 2026224 = SIM_DRAW
    issues2 = issues + [NEXT_ISSUE]
    hh2 = hh + [int(SIM_DRAW[0])]
    tt2 = tt + [int(SIM_DRAW[1])]
    oo2 = oo + [int(SIM_DRAW[2])]

    # 4. 用锁定池 + 固定参数重算 500 期回测表（walk-forward，与发布时完全同一套）
    pred, hit, L0, _ = build_matrices(issues2, hh2, tt2, oo2, pool)
    start = len(hh2) - WINDOW
    rows = []
    for t in range(start, len(hh2)):
        j = t - L0
        kill, *_ = hedge_vote(win, k, 0.02, j, hit, pred)
        rows.append({'issue': str(issues2[t]), 'kill': kill})

    # 5. 断言：开奖后回测表最新一行 = 2026224，kill 必须 == 发布值 2
    newest = rows[-1]
    print(f"\n开奖后回测表最新行: {newest['issue']}期 kill={newest['kill']}")
    print(f"账本发布值:        {NEXT_ISSUE}期 杀{PUBLISHED_KILL}")

    if newest['issue'] == NEXT_ISSUE and newest['kill'] == PUBLISHED_KILL:
        print("\n✅✅ 确定性验证通过：开奖前的发布值 = 开奖后的回测表同期待值")
        print("   → 每天发布的预测和开奖完的回测表完全一致，随时可对账（v2.0 同款语义）")
        # 顺便复核 2026223 期（已开奖真实期）：回测表也应与真实结果一致
        r_prev = rows[-2]
        real_tail = (hh2[-2] + tt2[-2] + oo2[-2]) % 10
        print(f"\n参考: 2026223 期回测表 kill={r_prev['kill']}（真实开奖 948，和尾 {real_tail}）")
        return 0
    else:
        print(f"\n❌ 不一致！发布值 {PUBLISHED_KILL} ≠ 回测值 {newest['kill']}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
