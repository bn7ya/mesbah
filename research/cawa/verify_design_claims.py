#!/usr/bin/env python3
"""Numerical verification of the mathematical claims in docs/.

Design documents that assert propositions should be able to prove them. This
script checks every load-bearing claim in `docs/01-research-analysis.md` and
`docs/02-math-spec.md` on small synthetic systems where the answer is known.

numpy only -- no torch, no transformers. Runs in a couple of seconds.

    python research/cawa/verify_design_claims.py
"""
from __future__ import annotations

import numpy as np

rng = np.random.default_rng(0)
OK, FAIL = "  ok  ", " FAIL "
results: list[tuple[bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((ok, name))
    print(f"[{OK if ok else FAIL}] {name}" + (f"   {detail}" if detail else ""))


# --------------------------------------------------------------- primitives

def rms(x):
    """Gainless RMSNorm: x * sqrt(d) / ||x||."""
    return x * np.sqrt(x.shape[-1]) / np.linalg.norm(x, axis=-1, keepdims=True)


def silu(x):
    return x / (1.0 + np.exp(-x))


def rope(x, base=10000.0):
    """Rotate pairs (2j, 2j+1) of the head dim by m*theta_j at position m."""
    n, dh = x.shape
    j = np.arange(dh // 2)
    theta = base ** (-2.0 * j / dh)
    ang = np.outer(np.arange(n), theta)
    c, s = np.cos(ang), np.sin(ang)
    xe, xo = x[:, 0::2], x[:, 1::2]
    out = np.empty_like(x)
    out[:, 0::2] = xe * c - xo * s
    out[:, 1::2] = xe * s + xo * c
    return out


class Block:
    """One pre-norm transformer block: RMSNorm -> MHA(RoPE) -> RMSNorm -> SwiGLU."""

    def __init__(self, d, nh, dh, m, use_rope=True):
        self.d, self.nh, self.dh, self.use_rope = d, nh, dh, use_rope
        g = lambda *s: rng.normal(size=s) / np.sqrt(s[0])
        self.Wq = [g(d, dh) for _ in range(nh)]
        self.Wk = [g(d, dh) for _ in range(nh)]
        self.Wv = [g(d, dh) for _ in range(nh)]
        self.Wo = [g(dh, d) for _ in range(nh)]
        self.Wg, self.Wu, self.Wd = g(d, m), g(d, m), g(m, d)

    def __call__(self, H):
        h = rms(H)
        n = h.shape[0]
        mask = np.triu(np.full((n, n), -np.inf), 1)
        acc = np.zeros_like(H)
        for q, k, v, o in zip(self.Wq, self.Wk, self.Wv, self.Wo):
            Q, K, V = h @ q, h @ k, h @ v
            if self.use_rope:
                Q, K = rope(Q), rope(K)
            s = Q @ K.T / np.sqrt(self.dh) + mask
            s = s - s.max(axis=-1, keepdims=True)
            p = np.exp(s)
            p /= p.sum(axis=-1, keepdims=True)
            acc += (p @ V) @ o
        H = H + acc
        h2 = rms(H)
        return H + (silu(h2 @ self.Wg) * (h2 @ self.Wu)) @ self.Wd


def forward(E, blocks, WU, tokens):
    H = E[tokens]
    for b in blocks:
        H = b(H)
    return rms(H) @ WU


D, NH, DH, M, V, N = 16, 2, 8, 24, 40, 12
E0 = rng.normal(size=(V, D))
BLK = [Block(D, NH, DH, M), Block(D, NH, DH, M)]
WU0 = rng.normal(size=(D, V))
TOK = rng.integers(0, V, size=N)
BASE = forward(E0, BLK, WU0, TOK)

print("\n=== Propositions 1-4: the gauge group ===\n")

# --- Prop 1: the residual stream is defined only up to O(d)
Q = np.linalg.qr(rng.normal(size=(D, D)))[0]
rot = []
for b in BLK:
    nb = Block.__new__(Block)
    nb.__dict__.update(b.__dict__)
    nb.Wq = [Q.T @ w for w in b.Wq]
    nb.Wk = [Q.T @ w for w in b.Wk]
    nb.Wv = [Q.T @ w for w in b.Wv]
    nb.Wo = [w @ Q for w in b.Wo]
    nb.Wg, nb.Wu, nb.Wd = Q.T @ b.Wg, Q.T @ b.Wu, b.Wd @ Q
    rot.append(nb)
check("Prop 1  residual stream O(d) gauge is exact (RoPE included)",
      np.allclose(forward(E0 @ Q, rot, Q.T @ WU0, TOK), BASE, atol=1e-9),
      f"max |Δlogit| = {np.abs(forward(E0 @ Q, rot, Q.T @ WU0, TOK) - BASE).max():.2e}")

# --- Prop 2: E_S = E_T pins that gauge to the identity
Qhat = np.linalg.lstsq(E0, E0, rcond=None)[0]
check("Prop 2  E Q = E with rank(E)=d forces Q = I",
      np.allclose(Qhat, np.eye(D), atol=1e-9) and np.linalg.matrix_rank(E0) == D)

# --- Prop 3: OV carries a full GL(d_h) gauge; QK a GL / RoPE-torus gauge
R = rng.normal(size=(DH, DH))
gl = []
for b in BLK:
    nb = Block.__new__(Block); nb.__dict__.update(b.__dict__)
    nb.Wv = [w @ R for w in b.Wv]
    nb.Wo = [np.linalg.solve(R, w) for w in b.Wo]
    gl.append(nb)
check("Prop 3a OV gauge: (W_V R, R⁻¹ W_O) is functionally identical",
      np.allclose(forward(E0, gl, WU0, TOK), BASE, atol=1e-9))

# a *general* GL(d_h) on QK breaks under RoPE, but a per-pair SO(2) does not
phi = rng.uniform(0, 2 * np.pi, DH // 2)
Rt = np.zeros((DH, DH))
for i, a in enumerate(phi):
    Rt[2 * i:2 * i + 2, 2 * i:2 * i + 2] = [[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]]
tor, bad = [], []
for b in BLK:
    nb = Block.__new__(Block); nb.__dict__.update(b.__dict__)
    nb.Wq = [w @ Rt for w in b.Wq]; nb.Wk = [w @ Rt for w in b.Wk]
    tor.append(nb)
    mb = Block.__new__(Block); mb.__dict__.update(b.__dict__)
    mb.Wq = [w @ R for w in b.Wq]
    mb.Wk = [np.linalg.solve(R, w.T).T for w in b.Wk]
    bad.append(mb)
check("Prop 3b QK gauge under RoPE is the ∏SO(2) torus (survives)",
      np.allclose(forward(E0, tor, WU0, TOK), BASE, atol=1e-9))
check("Prop 3b a general GL(d_h) on QK does NOT survive RoPE",
      not np.allclose(forward(E0, bad, WU0, TOK), BASE, atol=1e-6),
      "-- this is why R-4 restricts d_h")

# --- factored circuit traces (never materialise d×d)
s, t = BLK[0], BLK[1]
OVs, OVt = s.Wv[0] @ s.Wo[0], t.Wv[0] @ t.Wo[0]
check("§2.1  ⟨OV_s,OV_t⟩_F computable in factored form",
      np.allclose(np.trace((s.Wv[0].T @ t.Wv[0]) @ (t.Wo[0] @ s.Wo[0].T)),
                  np.sum(OVs * OVt)))

# --- Prop 4: MLP neuron gauge
perm = rng.permutation(M); c = rng.uniform(0.5, 2.0, M)
mlp, badg = [], []
for b in BLK:
    nb = Block.__new__(Block); nb.__dict__.update(b.__dict__)
    nb.Wg = b.Wg[:, perm]
    nb.Wu = (b.Wu * c)[:, perm]
    nb.Wd = (b.Wd / c[:, None])[perm]
    mlp.append(nb)
    gb = Block.__new__(Block); gb.__dict__.update(b.__dict__)
    gb.Wg = b.Wg * c                      # scaling the GATE is not free
    badg.append(gb)
check("Prop 4  neuron gauge P_m ⋉ (ℝ*)^m on (u,o) is exact",
      np.allclose(forward(E0, mlp, WU0, TOK), BASE, atol=1e-9))
check("Prop 4  scaling the gate row is NOT free (SiLU inhomogeneous)",
      not np.allclose(forward(E0, badg, WU0, TOK), BASE, atol=1e-6))
uk, ok_, ul, ol = (rng.normal(size=D) for _ in range(4))
check("§6.1  ⟨u_k o_kᵀ, u_l o_lᵀ⟩_F = (u_k·u_l)(o_k·o_l)",
      np.allclose(np.sum(np.outer(uk, ok_) * np.outer(ul, ol)), (uk @ ul) * (ok_ @ ol)))

print("\n=== Proposition 7: RMSNorm and non-conformal maps ===\n")

dS, dT = 32, 20
X = rng.normal(size=(4000, dS)) * np.exp(rng.normal(scale=1.5, size=dS))   # outlier channels
A = np.linalg.qr(rng.normal(size=(dS, dT)))[0]                              # AᵀA = I_dT
kap = np.linalg.norm(X, axis=1) / np.linalg.norm(X @ A, axis=1)
check("Prop 7  Ñ_{d_T}(xA) = √(d_T/d_S)·κ(x)·Ñ_{d_S}(x)A  exactly",
      np.allclose(rms(X @ A), np.sqrt(dT / dS) * kap[:, None] * (rms(X) @ A)))
rho = np.trace(A @ A.T @ (X.T @ X)) / np.trace(X.T @ X)
w = np.linalg.norm(X, axis=1) ** 2
check("Prop 7  ρ = energy-WEIGHTED mean of κ⁻² (exact)",
      np.allclose(((kap ** -2) * w).sum() / w.sum(), rho),
      f"ρ={rho:.6f}")
check("Prop 7  the UNWEIGHTED mean of κ⁻² is only an approximation",
      abs((kap ** -2).mean() - rho) > 1e-9,
      f"unweighted={(kap**-2).mean():.6f} vs ρ={rho:.6f} -- ratio-of-means ≠ mean-of-ratios")
B = np.linalg.qr(rng.normal(size=(48, dS)))[0].T                            # A Aᵀ = I_dS
check("Prop 7  widening (d_T ≥ d_S) is norm-safe: κ ≡ 1, commutation exact",
      np.allclose(rms(X @ B), np.sqrt(48 / dS) * (rms(X) @ B)))

G = rms(X).T @ rms(X)
Ws = rng.normal(size=(dS, 6))
err = lambda W: np.linalg.norm(rms(X) @ (A @ W - Ws))
plain = err(A.T @ Ws)
wtd = err(np.linalg.solve(A.T @ G @ A, A.T @ G @ Ws))
check("§5.3  activation-weighted conjugation (†) beats naive AᵀW_S",
      wtd < plain, f"{plain:.2f} -> {wtd:.2f}  ({100*(1-wtd/plain):.0f}% better, cond(Ḡ)={np.linalg.cond(G):.0f})")

print("\n=== Propositions 8 and the closed-form transfer solvers ===\n")

n, m, d, mu = 3000, 40, 16, 2.3
Phi = np.linalg.qr(rng.normal(size=(n, m)))[0] * np.sqrt(7.0)     # ΦᵀΦ = 7I
WT, WS = rng.normal(size=(m, d)), rng.normal(size=(m, d))
Wstar = np.linalg.solve(Phi.T @ Phi + mu * np.eye(m), Phi.T @ (Phi @ WS) + mu * WT)
lam = 7.0 / (7.0 + mu)
check("Prop 8  ridge (★) ≡ (1−λ)W_T + λŴ_S  when ΦᵀΦ = cI",
      np.allclose(Wstar, lam * WS + (1 - lam) * WT), f"λ = c/(c+μ) = {lam:.4f}")
# ...and no scalar λ reproduces it once ΦᵀΦ is anisotropic, with μ set by the
# damping rule the spec itself prescribes (μ = α·tr(G)/m).
P2 = rng.normal(size=(n, m)) * np.exp(rng.normal(scale=1.5, size=m))
G2 = P2.T @ P2
mu2 = 0.05 * np.trace(G2) / m
W2 = np.linalg.solve(G2 + mu2 * np.eye(m), G2 @ WS + mu2 * WT)
gap = min(np.linalg.norm(W2 - (l * WS + (1 - l) * WT)) for l in np.linspace(0, 1, 2001))
check("Prop 8  and NO scalar λ reproduces it once ΦᵀΦ is anisotropic",
      gap > 0.1 * np.linalg.norm(W2),
      f"best-λ is {100*gap/np.linalg.norm(W2):.0f}% away, cond(ΦᵀΦ)={np.linalg.cond(G2):.0f}")

# §7.6 reduced-rank ridge vs alternating least squares
n, m, d, r, mu = 800, 12, 9, 3, 0.7
Phi = rng.normal(size=(n, m)) * np.exp(rng.normal(scale=1.2, size=m))
WT, Y = rng.normal(size=(m, d)), rng.normal(size=(n, d))
Gm = Phi.T @ Phi + mu * np.eye(m)
R_ = Y - Phi @ WT
Wf = np.linalg.solve(Gm, Phi.T @ Y + mu * WT)
w, Vg = np.linalg.eigh(Gm)
Gsq, Gis = Vg @ np.diag(np.sqrt(w)) @ Vg.T, Vg @ np.diag(1 / np.sqrt(w)) @ Vg.T
U_, S_, Vt_ = np.linalg.svd(Gsq @ (Wf - WT), full_matrices=False)
Dlt = Gis @ (U_[:, :r] * S_[:r]) @ Vt_[:r]
obj = lambda Dm: np.linalg.norm(Phi @ (WT + Dm) - Y) ** 2 + mu * np.linalg.norm(Dm) ** 2
best = np.inf
for _ in range(25):
    Vv = rng.normal(size=(r, d))
    for _ in range(200):
        Uu = np.linalg.solve(Gm, Phi.T @ R_ @ Vv.T) @ np.linalg.inv(Vv @ Vv.T)
        Vv = np.linalg.solve(Uu.T @ Gm @ Uu, Uu.T @ Phi.T @ R_)
    best = min(best, obj(Uu @ Vv))
check("§7.6  CAWA-LR closed form attains the rank-r ridge optimum",
      obj(Dlt) <= best + 1e-6 * abs(best),
      f"closed form {obj(Dlt):.4f} vs best alternating-LS {best:.4f}")

# §1 streaming CKA identity
Xc = rng.normal(size=(500, 20)); Yc = rng.normal(size=(500, 14)) + Xc[:, :14]
Xc -= Xc.mean(0); Yc -= Yc.mean(0)
K, L = Xc @ Xc.T, Yc @ Yc.T                      # the n×n form we must never build
feat = (np.linalg.norm(Xc.T @ Yc) ** 2
        / (np.linalg.norm(Xc.T @ Xc) * np.linalg.norm(Yc.T @ Yc)))
kern = np.trace(K @ L) / np.sqrt(np.trace(K @ K) * np.trace(L @ L))
check("§1  linear CKA from d×d Gram accumulators ≡ the n×n kernel form",
      np.allclose(feat, kern), f"CKA = {feat:.6f}")

bad_n = sum(1 for ok_f, _ in results if not ok_f)
print(f"\n{len(results) - bad_n}/{len(results)} claims verified"
      + (f"  --  {bad_n} FAILED" if bad_n else ""))
raise SystemExit(1 if bad_n else 0)
