# -*- coding: utf-8 -*-
"""
福彩3D 杀和尾 v3 — 一键更新（3931万公式穷举+Hedge）
===============================
流程：联网补抓最新开奖(多源降级+CSV兜底) → 暴力穷举3931万×500期选专家池 → 网格扫描选Hedge参数
      → 500期逐期真实回测+下期预测 → 生成静态网页
缓存：cache/pool.json、cache/result.json 按 fingerprint 复用（--force 强制重算）
"""
import argparse
import io
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BJT = timezone(timedelta(hours=8))


def current_fingerprint():
    from engine import load_data
    issues, _, _, _ = load_data()
    return f"{len(issues)}_{issues[-1]}"


def main():
    t0 = time.time()
    ap = argparse.ArgumentParser(description='福彩3D 十位杀一码 一键更新')
    ap.add_argument('--force', action='store_true', help='强制重算（忽略缓存）')
    args = ap.parse_args()

    print("=" * 46)
    print("  福彩3D 杀和尾 v3 · 一键更新")
    print(f"  时间(北京): {datetime.now(BJT).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 46)

    fp = current_fingerprint()
    print(f"  数据指纹: {fp}")

    # ---- [1/5] 数据同步 ----
    print("\n[1/5] 同步最新数据（联网补抓 + CSV兜底）")
    try:
        import fetch
        fetch.sync_data()
    except Exception as e:
        print(f"  ⚠ 数据同步异常，沿用现有CSV: {str(e)[:80]}")
    fp2 = current_fingerprint()
    if fp2 != fp:
        fp = fp2
        print(f"  数据已更新 → 指纹 {fp}")

    # ---- [2/5] 暴力穷举（3931万×500期 → 专家池）----
    print("\n[2/5] 暴力穷举（最新500期，3931万公式，按族限选 Top400 专家池）")
    from formulas import FEAT_VERSION, NF
    need_pool = True
    if os.path.exists('cache/pool.json') and not args.force:
        with open('cache/pool.json', 'r', encoding='utf-8') as f:
            pj = json.load(f)
        pfp = f"{pj['data_info']['n_issues']}_{pj['data_info']['last']}"
        if pfp == fp and pj.get('feat_version') == FEAT_VERSION:
            print(f"  缓存命中（指纹 {fp} v{FEAT_VERSION}），跳过穷举")
            need_pool = False
        elif pfp == fp:
            print(f"  特征体系已升级（{pj.get('feat_version')} → {FEAT_VERSION}），强制重算穷举")
    if need_pool:
        import bruteforce500
        bruteforce500.main()

    # ---- [3/5][4/5] 网格扫描 + 500期回测 + 下期预测 ----
    import hedge_core as _hc
    print(f"\n[3/5] 网格扫描（{len(_hc.WIN_GRID) * len(_hc.K_GRID)}组合 win×K 自动选优）")
    print("[4/5] 500期 Hedge 逐期真实回测 + 下期预测")
    need_result = True
    if os.path.exists('cache/result.json') and not args.force:
        with open('cache/result.json', 'r', encoding='utf-8') as f:
            rj = json.load(f)
        if rj.get('fingerprint') == fp and rj.get('pool_info', {}).get('feat_version') == FEAT_VERSION:
            print(f"  回测缓存命中（指纹 {fp} v{FEAT_VERSION}），跳过重算")
            need_result = False
    if need_result:
        import hedge_core
        hedge_core.main()

    # ---- [5/5] 生成网页 ----
    print("\n[5/5] 生成静态网页")
    import gen_site
    gen_site.main()

    print(f"\n完成 ✓  总耗时 {time.time()-t0:.1f} 秒")
    print("本地预览: http://127.0.0.1:8000/index.html  (双击 HTML 文件亦可)")


if __name__ == '__main__':
    main()
