"""
福彩3D 杀和尾 — kill2 锚点化穷举
公式池: (op(f1, f2) + c) % 10, 特征取自上期/上上期和尾与结构特征
两阶段筛选:
  阶段1 近500期独立命中率粗筛 (只用 < T 的数据)
  阶段2 top30 与 kill1 联合双杀率, 三窗(100/200/500)一致性门槛
防泄漏: 锚点 T 参数化, 排名仅用 tails[T-500:T], 验证用 tails[T-W:T], 均不碰 >= T
"""
import os, json, itertools
from engine import load_tails, replay_kill1

BASELINE_DOUBLE = 0.8112  # 固定双杀(2,6)全量基线
GATE_PP = 0.01            # 三窗一致性门槛: 均 >= 基线 + 1pp


# ── 特征函数 (只能用 <= i-1 期信息) ────────────────────
def feats(tails, i):
    h1 = tails[i - 1]["tail"]
    h2 = tails[i - 2]["tail"] if i >= 2 else h1
    h3 = tails[i - 3]["tail"] if i >= 3 else h2
    r = tails[i - 1]
    S = r["b"] + r["s"] + r["g"]
    span = max(r["b"], r["s"], r["g"]) - min(r["b"], r["s"], r["g"])
    seg = [t["tail"] for t in tails[max(0, i - 5):i]]
    m5 = round(sum(seg) / len(seg)) % 10 if seg else 0
    return {"h1": h1, "h2": h2, "h3": h3, "S": S, "S10": S % 10,
            "span": span, "m5": m5, "sum_h12": (h1 + h2) % 10}


OPS = {
    "add": lambda a, b: a + b,
    "sub": lambda a, b: a - b,
    "mul": lambda a, b: a * b,
    "xor": lambda a, b: a ^ b,
    "max": lambda a, b: max(a, b),
    "min": lambda a, b: min(a, b),
}


def gen_pool():
    """生成公式池: (fname1, fname2, op, c)"""
    keys = ["h1", "h2", "h3", "S", "S10", "span", "m5", "sum_h12"]
    pool = []
    for f1, f2 in itertools.product(keys, keys):
        for op_name in OPS:
            for c in range(10):
                pool.append((f1, f2, op_name, c))
    return pool


_SYM = {'add': '+', 'sub': '-', 'mul': '*', 'xor': '^', 'max': 'max', 'min': 'min'}

def make_fn(f1, f2, op_name, c):
    op = OPS[op_name]
    desc = f"({f1}{_SYM[op_name]}{f2})+{c}"  # 立即求值, 不用闭包引用循环变量
    def fn(tails, i, f1=f1, f2=f2, op=op, c=c):
        ft = feats(tails, i)
        return (op(ft[f1], ft[f2]) + c) % 10
    fn.desc = desc
    return fn


def independent_hit(tails, fn, lo, hi):
    """fn 在 [lo,hi) 的独立命中率"""
    n = hi - lo
    if n <= 0:
        return 0.0
    return sum(1 for i in range(lo, hi) if tails[i]["tail"] != fn(tails, i)) / n


def joint_hit(tails, kill1_map, fn, lo, hi):
    """与 kill1 联合双杀命中率"""
    n = hi - lo
    if n <= 0:
        return 0.0
    hits = 0
    for i in range(lo, hi):
        k1 = kill1_map.get(i)
        if k1 is None:
            n -= 1
            continue
        k2 = fn(tails, i)
        if k2 == k1:
            k2 = (k2 + 1) % 10
        if tails[i]["tail"] != k1 and tails[i]["tail"] != k2:
            hits += 1
    return hits / n if n > 0 else 0.0


def overlap_rate(tails, kill1_map, fn, lo, hi):
    """kill2 与 kill1 杀码相同率 (独立性约束)"""
    same = tot = 0
    for i in range(lo, hi):
        k1 = kill1_map.get(i)
        if k1 is None:
            continue
        tot += 1
        if fn(tails, i) == k1:
            same += 1
    return same / tot if tot else 1.0


def search(tails, T=None, verbose=True):
    """锚点化穷举。T=评估锚点(默认=末尾)。所有筛选只用 < T 的数据。"""
    if T is None:
        T = len(tails)
    warm = 250
    kill1_map = {i: k for i, (k, _) in replay_kill1(tails, warm).items() if i < T}

    pool = gen_pool()
    if verbose:
        print(f"公式池规模: {len(pool)}, 锚点T={T} (期号{tails[T-1]['issue']})")

    # 阶段1: 近500期独立命中粗筛 (只用 [T-500, T))
    lo1 = max(warm, T - 500)
    stage1 = []
    for (f1, f2, op_name, c) in pool:
        fn = make_fn(f1, f2, op_name, c)
        hit = independent_hit(tails, fn, lo1, T)
        if hit >= 0.895:
            stage1.append((hit, fn, (f1, f2, op_name, c)))
    stage1.sort(key=lambda x: -x[0])
    if verbose:
        print(f"阶段1 粗筛(>=89.5%): {len(stage1)} 条")

    # 阶段2: top30 独立性过滤 + 三窗联合双杀一致性
    results = []
    for hit1, fn, key in stage1[:30]:
        ov = overlap_rate(tails, kill1_map, fn, lo1, T)
        if ov > 0.20:
            continue
        wins = {}
        ok = True
        for W in (100, 200, 500):
            lo = max(warm, T - W)
            jh = joint_hit(tails, kill1_map, fn, lo, T)
            wins[W] = jh
            if jh < BASELINE_DOUBLE + GATE_PP:
                ok = False
        results.append({"desc": fn.desc, "ind500": round(hit1, 4),
                        "overlap": round(ov, 3),
                        "j100": round(wins[100], 4), "j200": round(wins[200], 4),
                        "j500": round(wins[500], 4), "pass": ok,
                        "key": key})
    results.sort(key=lambda r: -(r["j100"] * 0.5 + r["j200"] * 0.3 + r["j500"] * 0.2))
    return results, kill1_map


if __name__ == "__main__":
    tails = load_tails()
    results, _ = search(tails)
    print("\n== top10 候选 ==")
    for r in results[:10]:
        flag = "PASS" if r["pass"] else "----"
        print(f"{flag} {r['desc']:<22} ind500={r['ind500']:.3f} ov={r['overlap']:.2f} "
              f"j100={r['j100']:.3f} j200={r['j200']:.3f} j500={r['j500']:.3f}")
    passing = [r for r in results if r["pass"]]
    print(f"\n三窗一致性通过: {len(passing)} 条")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kill2_candidates.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results[:10], f, ensure_ascii=False, indent=2)
    print(f"已存 {out}")
