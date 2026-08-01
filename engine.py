"""
福彩3D 杀和尾 — 核心引擎
和尾 = (百+十+个) % 10
双杀制: kill1 + kill2 独立算法, 下期和尾同时 != 两者 = 命中

防泄漏核心设计:
  回测第 i 期时, kill1 候选池排名只用 tails[i-W : i] (即 <= i-1 期实际值),
  评估只发生在第 i 期本身, 筛选区/评估区零重叠、零未来。
"""
import csv, os

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fc3d-history.csv")


# ── 数据加载 ─────────────────────────────────────────
def load_tails(path=CSV_PATH):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                b, s, g = int(r["hundreds"]), int(r["tens"]), int(r["ones"])
                rows.append({"issue": r["issue"], "b": b, "s": s, "g": g,
                             "tail": (b + s + g) % 10})
            except Exception:
                continue
    return rows


# ── kill1 候选池 (~60条) ─────────────────────────────
# 每条: (名称, 函数 tails, i -> 杀码), 只能用 tails[0..i-1] 的信息
def _h1(tails, i):
    return tails[i - 1]["tail"] if i >= 1 else 0

def _h2(tails, i):
    return tails[i - 2]["tail"] if i >= 2 else 0

def _sum1(tails, i):
    r = tails[i - 1]
    return r["b"] + r["s"] + r["g"]

def _span1(tails, i):
    r = tails[i - 1]
    return max(r["b"], r["s"], r["g"]) - min(r["b"], r["s"], r["g"])

def _mean5(tails, i):
    seg = [t["tail"] for t in tails[max(0, i - 5):i]]
    return round(sum(seg) / len(seg)) % 10 if seg else 0


def build_kill1_pool():
    pool = []
    # 1. 固定杀 0-9
    for t in range(10):
        pool.append((f"固定杀{t}", lambda tails, i, t=t: t))
    # 2. 上期和尾变换
    pool.append(("A9(9-上期和尾)", lambda tails, i: (9 - _h1(tails, i)) % 10))
    pool.append(("10-上期和尾", lambda tails, i: (10 - _h1(tails, i)) % 10))
    pool.append(("上期和尾同尾", lambda tails, i: _h1(tails, i)))
    for k in range(1, 10):
        pool.append((f"上期和尾+{k}", lambda tails, i, k=k: (_h1(tails, i) + k) % 10))
    # 3. 上上期
    pool.append(("9-上上期和尾", lambda tails, i: (9 - _h2(tails, i)) % 10))
    pool.append(("上上期和尾", lambda tails, i: _h2(tails, i)))
    pool.append(("h1+h2", lambda tails, i: (_h1(tails, i) + _h2(tails, i)) % 10))
    pool.append(("h1-h2", lambda tails, i: (_h1(tails, i) - _h2(tails, i)) % 10))
    # 4. 和值/跨度结构
    pool.append(("和值%10", lambda tails, i: _sum1(tails, i) % 10))
    pool.append(("9-和值%10", lambda tails, i: (9 - _sum1(tails, i) % 10) % 10))
    pool.append(("跨度", lambda tails, i: _span1(tails, i) % 10))
    pool.append(("9-跨度", lambda tails, i: (9 - _span1(tails, i)) % 10))
    pool.append(("和值+跨度", lambda tails, i: (_sum1(tails, i) + _span1(tails, i)) % 10))
    # 5. 均值尾
    pool.append(("近5期均值尾", lambda tails, i: _mean5(tails, i)))
    pool.append(("9-近5期均值尾", lambda tails, i: (9 - _mean5(tails, i)) % 10))
    # 6. 条件分支 (和值奇偶/大小)
    pool.append(("和值奇→A9,偶→杀6", lambda tails, i: (9 - _h1(tails, i)) % 10 if _sum1(tails, i) % 2 == 1 else 6))
    pool.append(("和值>13→杀6,否则A9", lambda tails, i: 6 if _sum1(tails, i) > 13 else (9 - _h1(tails, i)) % 10))
    pool.append(("跨度>=6→杀6,否则杀2", lambda tails, i: 6 if _span1(tails, i) >= 6 else 2))
    return pool


KILL1_POOL = build_kill1_pool()


def select_kill1(tails, i, windows=(200,), weights=(1.0,)):
    """选当期 kill1。排名只用 tails[i-W:i] (历史), 不碰 tails[i]。
    诊断结论(2026-08-01): 单窗近200期(84.4%) > 三窗加权(83.8%),
    50期短窗引入噪声稀释稳定信号, 故默认改单窗200。"""
    best_name, best_score, best_kill = None, -1.0, None
    for name, fn in KILL1_POOL:
        score = 0.0
        for W, w in zip(windows, weights):
            lo = max(1, i - W)  # 需要 i-1 存在
            if i - lo < 10:
                score += w * 0.9  # 数据不足给基准分
                continue
            hits = sum(1 for j in range(lo, i) if tails[j]["tail"] != fn(tails, j))
            score += w * hits / (i - lo)
        if score > best_score:
            best_name, best_score = name, score
            best_kill = fn(tails, i)
    return best_kill, best_name, best_score


def replay_kill1(tails, start=250):
    """全量 walk-forward 重放 kill1。返回 {i: (kill, name)}。前 start 期用于暖机。"""
    out = {}
    for i in range(start, len(tails)):
        k, name, _ = select_kill1(tails, i)
        out[i] = (k, name)
    return out


if __name__ == "__main__":
    tails = load_tails()
    print(f"总期数: {len(tails)}")
    # 快速验证: 近500期 kill1 自适应 vs A9 vs 固定杀6
    N = 500
    lo = len(tails) - N
    hits_ad = sum(1 for i in range(lo, len(tails))
                  if tails[i]["tail"] != select_kill1(tails, i)[0])
    hits_a9 = sum(1 for i in range(lo, len(tails))
                  if tails[i]["tail"] != (9 - tails[i - 1]["tail"]) % 10)
    hits_f6 = sum(1 for i in range(lo, len(tails)) if tails[i]["tail"] != 6)
    print(f"近{N}期 单杀命中: 自适应={hits_ad / N * 100:.2f}%  A9={hits_a9 / N * 100:.2f}%  固定6={hits_f6 / N * 100:.2f}%")
