# -*- coding: utf-8 -*-
"""
福彩3D 杀和尾 — 一键更新（5专家 Hedge v2.0 单系统）
=====================================================
流程：联网补抓最新开奖(多源降级+CSV兜底) → v2.0 五专家引擎 Hedge 加权投票
      → 预测笔记账本（真实发布记录） → 生成静态网页
数据：fc3d-history.csv（云端每晚自动更新，本地 CSV 滞后）
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
    ap = argparse.ArgumentParser(description='福彩3D 杀和尾 一键更新')
    ap.add_argument('--force', action='store_true', help='强制重算（忽略缓存）')
    args = ap.parse_args()

    print("=" * 46)
    print("  福彩3D 杀和尾 · 一键更新（5专家 Hedge v2.0）")
    print(f"  时间(北京): {datetime.now(BJT).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 46)

    fp = current_fingerprint()
    print(f"  数据指纹: {fp}")

    # ---- [1/4] 数据同步 ----
    print("\n[1/4] 同步最新数据（联网补抓 + CSV兜底）")
    try:
        import fetch
        next_code, added = fetch.sync_data()
        if added > 0:
            print(f"  ✓ 已追加 {added} 期新数据")
    except Exception as e:
        print(f"  ⚠ 数据同步异常: {str(e)[:100]}")
        print("  ⚠⚠ 若已抓到新开奖但写入失败，本次预测将基于旧数据 —— 终止更新避免发布错误预测")
        sys.exit(1)
    fp2 = current_fingerprint()
    if fp2 != fp:
        fp = fp2
        print(f"  数据已更新 → 指纹 {fp}")

    # ---- [2/4] v2.0 五专家引擎（Hedge 加权投票）----
    print("\n[2/4] v2.0 五专家引擎（Hedge 加权投票）")
    import hedge_engine
    data = hedge_engine.run()

    # ---- [3/4] 预测笔记（账本）：补标旧记录 + 记录本次真实发布 ----
    print("\n[3/4] 预测笔记（账本）")
    try:
        import ledger
        from engine import load_data as _ld
        _issues, _hh, _tt, _oo = _ld('fc3d-history.csv')
        n_settled = ledger.settle_past(_issues, _hh, _tt, _oo)
        pred = data['prediction']
        # 账本记录 B 系统(5专家)的发布：补 top3_vote 别名兼容 ledger
        nxt = {
            'target_issue': pred['target_issue'],
            'kill': pred['kill'],
            'top3_vote': pred['top3'],
        }
        ledger.record_publication(nxt, data['meta']['latest_issue'])
        _stats = ledger.get_stats()
        print(f"  [账本] 共 {_stats['total']} 条发布记录 | 已核对 {_stats['settled']} | 累计命中率 {_stats['rate']}% ({_stats['hits']}/{_stats['settled']}) | 待开奖 {_stats['pending']}")
    except Exception as _e:
        print(f"  ⚠ 账本异常（不影响主流程）: {_e}")

    # ---- [4/4] 生成网页 ----
    print("\n[4/4] 生成静态网页")
    import gen_site
    gen_site.main()

    print(f"\n完成 ✓  总耗时 {time.time()-t0:.1f} 秒")
    print("本地预览: http://127.0.0.1:8000/index.html  (双击 HTML 文件亦可)")


if __name__ == '__main__':
    main()
