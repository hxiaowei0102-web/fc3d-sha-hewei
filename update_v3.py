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


# 2026-08-22 老板拍板锁 (40,650)：四窗口网格扫描近100/200/500期100%并列(选择偏差饱和)，
# 近1000期96.40%全场最高(超挑选窗=真实区分)破平局；样本外91.35%、验证段91.8%。
LOCKED_PARAMS = {'win': 40, 'k': 650}   # 确定性：首次锁定后永久固定（勿改，除非老板重新拍板）


def _lock_pool_params():
    """把 win/k 锁定参数写入 cache/pool.json 的 locked 字段。
    之后：① 专家池永久固定不再重选  ② Hedge 参数固定不再网格扫描
    → 每天发布的预测 = 开奖完回测表同一期数值（纯确定性函数）。
    幂等：已锁定则跳过；若已锁定值与 LOCKED_PARAMS 不一致则告警（防参数漂移）。
    """
    try:
        p = 'cache/pool.json'
        with open(p, 'r', encoding='utf-8') as f:
            pj = json.load(f)
        if pj.get('locked'):
            cur = pj['locked']
            if cur != LOCKED_PARAMS:
                print(f"  ⚠ 已锁定参数 {cur} ≠ 代码 LOCKED_PARAMS {LOCKED_PARAMS}，请人工核对！")
            return
        pj['locked'] = dict(LOCKED_PARAMS)
        pj['locked_at'] = datetime.now(BJT).strftime('%Y-%m-%d %H:%M:%S')
        pj['lock_note'] = '确定性模式：专家池与win/k永久固定，发布值=回测值（v2.0同款语义）'
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(pj, f, ensure_ascii=False)
        print(f"  ★ 已锁定参数 win={LOCKED_PARAMS['win']} k={LOCKED_PARAMS['k']}（确定性模式）")
    except Exception as e:
        print(f"  ⚠ 锁定参数失败: {str(e)[:80]}")


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
    synced_ok = False
    try:
        import fetch
        next_code, added = fetch.sync_data()
        if added > 0:
            print(f"  ✓ 已追加 {added} 期新数据")
            synced_ok = True
    except Exception as e:
        print(f"  ⚠ 数据同步异常: {str(e)[:100]}")
        print("  ⚠⚠ 若已抓到新开奖但写入失败，本次预测将基于旧数据 —— 终止更新避免发布错误预测")
        sys.exit(1)
    fp2 = current_fingerprint()
    if fp2 != fp:
        fp = fp2
        print(f"  数据已更新 → 指纹 {fp}")

    # ---- [2/5] 专家池：锁定则直接复用（不再穷举重选）----
    print("\n[2/5] 专家池（3931万公式已穷举锁定，固定800专家不再重选）")
    from formulas import FEAT_VERSION, NF
    need_pool = True
    if os.path.exists('cache/pool.json') and not args.force:
        with open('cache/pool.json', 'r', encoding='utf-8') as f:
            pj = json.load(f)
        if pj.get('locked'):
            print(f"  ★ 专家池已锁定（确定性模式，固定 {len(pj.get('pool', []))} 专家）—— 跳过 3931 万穷举")
            need_pool = False
        else:
            pfp = f"{pj['data_info']['n_issues']}_{pj['data_info']['last']}"
            if pfp == fp and pj.get('feat_version') == FEAT_VERSION:
                print(f"  缓存命中（指纹 {fp} v{FEAT_VERSION}），跳过穷举")
                need_pool = False
            elif pfp == fp:
                print(f"  特征体系已升级（{pj.get('feat_version')} → {FEAT_VERSION}），强制重算穷举")
    if need_pool:
        import bruteforce500
        bruteforce500.main()
        # 穷举/复用完成后锁定参数（win=40,k=56 → 与 v2.0 相同"发布=回测"确定性）
        _lock_pool_params()

    # ---- [3/5][4/5] 1000期回测 + 下期预测（锁定参数跳过网格扫描）----
    import hedge_core as _hc
    if os.path.exists('cache/pool.json'):
        with open('cache/pool.json', 'r', encoding='utf-8') as f:
            _pj = json.load(f)
        if _pj.get('locked'):
            print(f"\n[3/5] 参数已锁定 win={_pj['locked']['win']} k={_pj['locked']['k']}（确定性模式，跳过网格扫描）")
        else:
            print(f"\n[3/5] 网格扫描（{len(_hc.WIN_GRID) * len(_hc.K_GRID)}组合 win×K 自动选优）")
    print("[4/5] 1000期 Hedge 逐期真实回测 + 下期预测")
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

    # ---- [4.5/5] v2.0 五专家引擎（双系统B）----
    print("\n[4.5/5] v2.0 五专家引擎（双系统B）")
    import hedge_engine
    hedge_engine.run()

    # ---- [5/5] 生成网页 ----
    print("\n[5/5] 生成静态网页")
    import gen_site
    gen_site.main()

    print(f"\n完成 ✓  总耗时 {time.time()-t0:.1f} 秒")
    print("本地预览: http://127.0.0.1:8000/index.html  (双击 HTML 文件亦可)")


if __name__ == '__main__':
    main()
