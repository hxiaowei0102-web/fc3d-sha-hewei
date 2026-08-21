# -*- coding: utf-8 -*-
"""
福彩3D 十位杀一码 — 特征引擎 + 公式库（v5 扩展版）
=============================================
特征 v1(34单期) + v2单期派生9 + v3单期派生8 + v2跨期16 + v3跨期14 + v4单期派生8 + v4跨期7 = 96 特征。
系数 (1,2,3,5) × 常数0-9，单/双/三特征线性组合 ≈ 3931万规格。
所有特征均由「上期」「上上期」计算，第i期预测只用第i-1期及更早数据，不偷看未来。
"""
from engine import load_data

FEAT_VERSION = 'v5_96'     # 特征体系版本（用于缓存指纹，特征变更必须升级）

FEAT_NAMES = [
    # ===== v1 单期特征（34个，上期三码 b,s,g）=====
    'b', 's', 'g',
    'b2', 's2', 'g2',
    'b3', 's3', 'g3',
    'S', 'S10', 'P', 'mx', 'mn', 'md',
    'd1', 'd2', 'd3',
    'bs', 'bg', 'sg', 'bsg',
    'S2', 'P2',
    'sum2', 'sum3', 'sum4',
    'bp', 'gp', 'sp',
    'bo', 'so', 'go', 'So',
    # ===== v2 单期派生（9个）=====
    'd12', 'd13', 'd23',      # 跨度两两乘积尾
    'mxmn', 'mxmd', 'mnmd',   # 大×小 / 大+中 / 小+中
    'S3',                     # 和值³尾
    'dsum',                   # 三差值和
    'bsg2',                   # 两两积之和尾
    # ===== v3 单期派生（8个，新增）=====
    'oddn',                   # 奇码数 0-3
    'bign',                   # 大码数(>=5) 0-3
    'Sm3',                    # 和值模3
    'Pm3',                    # 跨度模3
    'mdmn',                   # 中-小
    'mx_md',                  # 大-中（v3，原名mxmd与v2冲突已改）
    'SP10',                   # (和值+跨度)尾
    'N9',                     # 和尾补9 (9-S10)%10
    # ===== v2 跨期特征（16个，前2期 bL,sL,gL）=====
    'bL', 'sL', 'gL',         # 前2期三码
    'SL', 'S10L', 'PL',       # 前2期和值 / 和尾 / 跨度
    'db', 'ds', 'dg',         # 各位较前2期差分(mod)
    'dS',                     # 和值较前2期差分(mod)
    'bh', 'sh', 'gh',         # 近2期各位之和尾
    'bpr', 'spr', 'gpr',      # 近2期各位之积尾
    # ===== v3 跨期特征（14个，新增）=====
    'dbA', 'dsA', 'dgA',      # 各位跨期差绝对值 |b-bL| 等
    'dSA',                    # 和值跨期差绝对值 |S-SL|
    'bsgL10',                 # 前2期三码积尾
    'mxmnL',                  # 前2期大×小尾
    'dsumL',                  # 前2期三差值和尾
    'SPL10',                  # 前2期(和值+跨度)尾
    'bsL10', 'bgL10',         # 百×前2十/个 尾
    'sbL10', 'sgL10',         # 十×前2百/个 尾
    'gbL10', 'gsL10',         # 个×前2百/十 尾
    # ===== v4 单期派生（8个，新增）=====
    'consec',                 # 连号对数 0-3
    'isZ3',                   # 组三标志（恰一对相同）
    'isBao',                  # 豹子标志
    'S9',                     # 和值补9 (9-S10)%10
    'P9',                     # 跨度补9
    'mxmn_s',                 # 大+小尾
    'SxP',                    # 和值×跨度尾
    'ss_gg',                  # 十²+个²尾
    # ===== v4 跨期特征（7个，新增）=====
    'SL_s10',                 # 前2期和值+十位 尾
    's_gL10',                 # 十+前2个 尾
    'dS2',                    # 和值跨期差平方尾
    'sdsA',                   # 十×|十-前2十| 尾
    'd1d1L',                  # 百十差-前2百十差(mod10)
    'bL_s10',                 # 前2百+十 尾
    'dbA_s',                  # |百-前2百|+十 尾
]
_IDX = {n: i for i, n in enumerate(FEAT_NAMES)}
NF = len(FEAT_NAMES)

# 族块边界：A=单期基础(0-33) / B=单期派生(34..B_END-1) / C=跨期(>=B_END)
B_END = 89

# 系数集（v2 扩展）
COEFFS = (1, 2, 3, 5)


def feat_list(b, s, g, prev=None):
    """特征向量。prev=(bL,sL,gL) 为前2期三码，缺省时跨期特征用0（安全退化）"""
    if prev is None:
        bL = sL = gL = 0
    else:
        bL, sL, gL = prev
    mx = max(b, s, g); mn = min(b, s, g); md = b + s + g - mx - mn
    S = b + s + g; P = mx - mn
    SL = bL + sL + gL; PL = max(bL, sL, gL) - min(bL, sL, gL)
    d1 = abs(b - s); d2 = abs(b - g); d3 = abs(s - g)
    d1L = abs(bL - sL); d2L = abs(bL - gL); d3L = abs(sL - gL)
    mxL = max(bL, sL, gL); mnL = min(bL, sL, gL)
    return [
        # v1
        b, s, g,
        b * b % 10, s * s % 10, g * g % 10,
        b * b * b % 10, s * s * s % 10, g * g * g % 10,
        S, S % 10, P, mx, mn, md,
        d1, d2, d3,
        b * s % 10, b * g % 10, s * g % 10, b * s * g % 10,
        S * S % 10, P * P % 10,
        (b + s) % 10, (s + g) % 10, (b + g) % 10,
        (1 if g == 0 else b ** g) % 10, (1 if b == 0 else g ** b) % 10, (1 if g == 0 else s ** g) % 10,
        b % 2, s % 2, g % 2, S % 2,
        # v2 单期派生
        (d1 * d2) % 10, (d1 * d3) % 10, (d2 * d3) % 10,
        (mx * mn) % 10, (mx + md) % 10, (mn + md) % 10,
        (S * S * S) % 10,
        (d1 + d2 + d3) % 10,
        (b * s + s * g + g * b) % 10,
        # v3 单期派生
        b % 2 + s % 2 + g % 2,            # oddn 奇码数
        (b >= 5) + (s >= 5) + (g >= 5),  # bign 大码数
        S % 3,                            # Sm3
        P % 3,                            # Pm3
        md - mn,                          # mdmn
        mx - md,                          # mx_md
        (S + P) % 10,                     # SP10
        (9 - S % 10) % 10,                # N9
        # v2 跨期
        bL, sL, gL,
        SL, SL % 10, PL,
        (b - bL) % 10, (s - sL) % 10, (g - gL) % 10,
        (S - SL) % 10,
        (b + bL) % 10, (s + sL) % 10, (g + gL) % 10,
        (b * bL) % 10, (s * sL) % 10, (g * gL) % 10,
        # v3 跨期
        abs(b - bL), abs(s - sL), abs(g - gL),
        abs(S - SL),
        (bL * sL * gL) % 10,
        (mxL * mnL) % 10,
        (d1L + d2L + d3L) % 10,
        (SL + PL) % 10,
        (b * sL) % 10, (b * gL) % 10,
        (s * bL) % 10, (s * gL) % 10,
        (g * bL) % 10, (g * sL) % 10,
        # v4 单期派生
        (abs(b - s) == 1) + (abs(s - g) == 1) + (abs(b - g) == 1),  # consec 连号对数
        1 if (b == s) + (s == g) + (b == g) == 1 else 0,             # isZ3 组三
        1 if b == s == g else 0,                                     # isBao 豹子
        (9 - S % 10) % 10,                                           # S9
        (9 - P) % 10,                                                # P9
        (mx + mn) % 10,                                              # mxmn_s
        (S * P) % 10,                                                # SxP
        (s * s + g * g) % 10,                                        # ss_gg
        # v4 跨期
        (SL + s) % 10,                                               # SL_s10
        (s + gL) % 10,                                               # s_gL10
        (((S - SL) % 10) ** 2) % 10,                                 # dS2
        (s * abs(s - sL)) % 10,                                      # sdsA
        (d1 - d1L) % 10,                                             # d1d1L
        (bL + s) % 10,                                               # bL_s10
        (abs(b - bL) + s) % 10,                                      # dbA_s
    ]


def family_of(terms):
    """公式所属族：按特征来源块分段（idx<34 单期基础A / idx<B_END 单期派生B / 其余跨期C），
    族 = 出现块的字母集排序拼接，共 7 族（A/B/C/AB/AC/BC/ABC）。用于专家池按族限选控制多样性。"""
    blocks = sorted({'A' if idx < 34 else 'B' if idx < B_END else 'C' for _, idx in terms})
    return ''.join(blocks)


def eval_linear(feats, terms, const):
    v = const
    for c, idx in terms:
        v += c * feats[idx]
    return v % 10


def formula_name(terms, const):
    return '+'.join(f'{c}*{FEAT_NAMES[idx]}' for c, idx in terms) + f'+{const}'


def parse_linear(name):
    terms = []
    const = 0
    for part in name.split('+'):
        part = part.strip()
        if '*' in part:
            c_str, feat = part.split('*', 1)
            terms.append((int(c_str), _IDX[feat]))
        elif part.isdigit():
            const += int(part)
        else:
            terms.append((1, _IDX[part]))
    return terms, const


def build_linear_specs(include_pair=True, include_single=True):
    """生成 (terms, const) 规格列表（未去重，v2 双特征规模）"""
    specs = []
    if include_single:
        for idx in range(NF):
            for c in COEFFS:
                for const in range(10):
                    specs.append((((c, idx),), const))
    if include_pair:
        for i in range(NF):
            for j in range(i + 1, NF):
                for c1 in COEFFS:
                    for c2 in COEFFS:
                        for const in range(10):
                            specs.append((((c1, i), (c2, j)), const))
    return specs


# 三特征组合系数（小子集控规模：C(59,3)×27×10 ≈ 878万）
TRIPLE_COEFFS = (1, 2, 3)


def iter_specs(include_single=True, include_pair=True, include_triple=True):
    """流式生成全部规格（单/双/三特征），不占内存。总量约1001万。"""
    if include_single:
        for idx in range(NF):
            for c in COEFFS:
                for const in range(10):
                    yield (((c, idx),), const)
    if include_pair:
        for i in range(NF):
            for j in range(i + 1, NF):
                for c1 in COEFFS:
                    for c2 in COEFFS:
                        for const in range(10):
                            yield (((c1, i), (c2, j)), const)
    if include_triple:
        for i in range(NF):
            for j in range(i + 1, NF):
                for k in range(j + 1, NF):
                    for c1 in TRIPLE_COEFFS:
                        for c2 in TRIPLE_COEFFS:
                            for c3 in TRIPLE_COEFFS:
                                for const in range(10):
                                    yield (((c1, i), (c2, j), (c3, k)), const)


def make_predictor(name):
    """把公式名编译为 (b,s,g,prev)->int 的可调用函数，用于回测与预测"""
    terms, const = parse_linear(name)

    def fn(b, s, g, prev=None, terms=terms, const=const):
        return eval_linear(feat_list(b, s, g, prev), terms, const)
    return fn


if __name__ == '__main__':
    issues, h, t, o = load_data()
    N = len(issues)
    print(f"特征数: {NF}")
    specs = build_linear_specs()
    print(f"公式规格数(去重前): {len(specs)}")
    # 验证示例
    f = make_predictor('1*bL+2*dg+3')
    print(f"示例: 1*bL+2*dg+3 对(上期2,9,6, 前2期3,7,3) = {f(2,9,6,(3,7,3))}")
