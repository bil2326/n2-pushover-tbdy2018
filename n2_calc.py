"""
N2 method calculation engine — TBDY 2018 Annex 5B
All displacements in mm, accelerations in g.
"""
import numpy as np

G    = 9.81          # m/s²
G_MM = G * 1000.0    # mm/s²  (= 9810)


# ---------------------------------------------------------------------------
# Spectrum helpers
# ---------------------------------------------------------------------------

def detect_TB(T: np.ndarray, Sae: np.ndarray) -> float:
    """End of constant-acceleration plateau (T_B)."""
    plateau = np.where(Sae >= 0.99 * np.max(Sae))[0]
    if not len(plateau):
        return float(T[np.argmax(Sae)])
    return float(T[plateau[-1]])


def spectrum_to_adrs(T: np.ndarray, Sae: np.ndarray) -> tuple:
    """Eq. 2.5: Sde [mm] = Sae [g] * 9.81 * (T/2pi)^2 * 1000."""
    return Sae * G * (T / (2.0 * np.pi)) ** 2 * 1000.0, Sae


def _sde_mm(T_val: float, T: np.ndarray, Sae: np.ndarray) -> float:
    Sae_val = float(np.interp(T_val, T, Sae))
    return Sae_val * G * (T_val / (2.0 * np.pi)) ** 2 * 1000.0


# ---------------------------------------------------------------------------
# Capacity transformation
# ---------------------------------------------------------------------------

def capacity_to_adrs(
    delta_mm: np.ndarray, V: np.ndarray,
    gamma1: float, phi_top: float, M1eff: float,
) -> tuple:
    """Eq. 5B.3/5B.4  ->  Sd [mm], Sa [g].  delta_mm [mm], V [kN], M1eff [t]."""
    return delta_mm / (gamma1 * phi_top), V / (gamma1 * M1eff * G)


def check_negative_slope(a1: np.ndarray) -> bool:
    return int(np.argmax(a1)) < len(a1) - 1


# ---------------------------------------------------------------------------
# Bilinearization primitives
# ---------------------------------------------------------------------------

def _T_from_bilinear(dy_mm: float, ay_g: float) -> float:
    """T* = 2pi * sqrt(dy[mm] / (ay[g] * 9810))."""
    return 2.0 * np.pi * np.sqrt(dy_mm / (ay_g * G_MM))


def _truncate(d1: np.ndarray, a1: np.ndarray, target: float) -> tuple:
    """Truncate capacity arrays at target [mm], interpolating the endpoint."""
    if target >= float(d1[-1]):
        return d1.copy(), a1.copy()
    i = int(np.searchsorted(d1, target, side="right"))
    d_tr = np.append(d1[:i], target)
    a_tr = np.append(a1[:i], float(np.interp(target, d1, a1)))
    return d_tr, a_tr


def _equal_area_ay(k_init: float, d_max: float, area: float) -> float:
    """Solve equal-area bilinear for ay given fixed initial slope k_init.

    Bilinear area = ay*d_max - ay^2/(2*k_init) = area
    Quadratic: -1/(2k)*ay^2 + d_max*ay - area = 0
    """
    if k_init <= 0 or d_max <= 0:
        return area / d_max if d_max > 0 else 0.0
    A = -1.0 / (2.0 * k_init)
    B, C = d_max, -area
    disc = max(B**2 - 4.0 * A * C, 0.0)
    sd   = np.sqrt(disc)
    bound = 2.0 * area / d_max
    for r in ((-B + sd) / (2.0 * A), (-B - sd) / (2.0 * A)):
        if 0.0 < r <= bound * 1.5:
            return float(r)
    return float(area / d_max)


def _secant_core(d1: np.ndarray, a1: np.ndarray) -> tuple:
    """Secant-at-0.6*ay bilinearization (iterative equal-area).
    Returns (dy, ay, T1, d_bilin, a_bilin).
    """
    area   = float(np.trapezoid(a1, d1))
    d_max  = float(d1[-1])
    i_peak = int(np.argmax(a1))
    a_y    = float(a1[i_peak]) * 0.85
    k      = 1.0
    for _ in range(500):
        p06 = 0.6 * a_y
        ab, db = a1[: i_peak + 1], d1[: i_peak + 1]
        if p06 >= ab[-1]:
            p06 = ab[-1] * 0.99
        d06 = float(np.interp(p06, ab, db))
        if d06 <= 0:
            d06 = d1[1] if len(d1) > 1 else d_max * 0.01
        k       = p06 / d06
        ay_new  = _equal_area_ay(k, d_max, area)
        if abs(ay_new - a_y) < 1e-9:
            a_y = ay_new
            break
        a_y = ay_new
    dy = a_y / k
    T1 = _T_from_bilinear(dy, a_y)
    return float(dy), float(a_y), float(T1), np.array([0.0, dy, d_max]), np.array([0.0, a_y, a_y])


def bilinearize(d1: np.ndarray, a1: np.ndarray, target_mm: float, rule: str) -> tuple:
    """Bilinearize capacity curve up to target_mm.

    rule: 'secant'  (secant at 0.6*ay, TBDY art. 5B.3.5b)
    Returns (dy_mm, ay_g, T1_s, d_bilin, a_bilin).
    """
    target_mm = float(min(target_mm, d1[-1]))
    d_tr, a_tr = _truncate(d1, a1, target_mm)
    return _secant_core(d_tr, a_tr)


# ---------------------------------------------------------------------------
# C_R computation — TBDY 2018 Eq. 5B.16-17
# ---------------------------------------------------------------------------

def compute_CR(Ry: float, TB: float, T1: float) -> tuple:
    """Returns (mu, CR)."""
    if T1 > TB:
        return float(Ry), 1.0
    mu = 1.0 + (Ry - 1.0) * (TB / T1)
    return float(mu), float(max(mu / Ry, 1.0))


# ---------------------------------------------------------------------------
# Iterative performance point — TBDY 2018 art. 5B.3.5b
# ---------------------------------------------------------------------------

def compute_performance(
    d1: np.ndarray, a1: np.ndarray,
    T: np.ndarray, Sae: np.ndarray,
    TB: float,
    gamma1: float, phi_top: float,
    rule: str = "secant",
    max_iter: int = 50,
    tol: float = 0.01,
) -> dict:
    """Full iterative N2 performance point per TBDY 2018 Annex 5B art. 5B.3.5b.

    Pass 0 : bilinearize to Sde(T1_init)  [C_R = 1 assumed]
    Pass n : target = C_R(n-1) * Sde(T1)  ->  re-bilinearize
             until |C_R(n) - C_R(n-1)| / C_R(n) < tol (1 %)

    For T1 > T_B: C_R = 1 by definition, no iteration (n_iter = 0).
    For T1 <= T_B: n_iter >= 1.

    Returns dict with:
      T1, Sae_T1, Sde_T1, a_y, d_y, Ry, mu, CR, Sd1max, delta_cible,
      n_iter, case, omega1sq, omegaBsq,
      d_bilin0/a_bilin0  (pass-0 bilinear),
      d_bilin/a_bilin    (converged bilinear),
      convergence_log    (list of dicts, one per pass).
    """
    # --- Initial bilinear to full d_max to bootstrap T1 estimate ---
    dy_i, _, T1_i, _, _ = bilinearize(d1, a1, float(d1[-1]), rule)
    Sde_i = _sde_mm(T1_i, T, Sae)

    # --- Pass 0: bilinearize to Sde(T1_init) ---
    target0 = float(min(max(Sde_i, dy_i * 1.05), d1[-1]))
    dy, ay, T1, d_bil0, a_bil0 = bilinearize(d1, a1, target0, rule)
    Sde    = _sde_mm(T1, T, Sae)
    Sae_T1 = float(np.interp(T1, T, Sae))
    Ry     = max(Sae_T1 / ay, 1.0)
    mu, CR = compute_CR(Ry, TB, T1)

    log = [{
        "n":            0,
        "target_mm":    target0,
        "ay":           ay,
        "dy":           dy,
        "T1":           T1,
        "Sae_T1":       Sae_T1,
        "Ry":           Ry,
        "mu":           mu,
        "CR":           CR,
        "delta_CR_pct": None,
        "converged":    T1 > TB,   # converged at pass 0 iff T1 > T_B
    }]

    d_bilc, a_bilc = d_bil0.copy(), a_bil0.copy()
    n_iter = 0

    if T1 <= TB:
        # --- Iterative loop (only when T1 <= T_B) ---
        CR_prev = CR
        for n in range(1, max_iter + 1):
            target_n = float(min(max(CR_prev * Sde, dy * 1.05), d1[-1]))
            dy, ay, T1, d_bilc, a_bilc = bilinearize(d1, a1, target_n, rule)
            Sde    = _sde_mm(T1, T, Sae)
            Sae_T1 = float(np.interp(T1, T, Sae))
            Ry     = max(Sae_T1 / ay, 1.0)
            mu, CR = compute_CR(Ry, TB, T1)
            delta_pct = abs(CR - CR_prev) / max(CR, 1e-9) * 100.0
            converged = delta_pct < tol * 100.0
            log.append({
                "n":            n,
                "target_mm":    target_n,
                "ay":           ay,
                "dy":           dy,
                "T1":           T1,
                "Sae_T1":       Sae_T1,
                "Ry":           Ry,
                "mu":           mu,
                "CR":           CR,
                "delta_CR_pct": delta_pct,
                "converged":    converged,
            })
            n_iter = n
            if converged:
                break
            CR_prev = CR

    # --- Final values ---
    Ry     = max(Sae_T1 / ay, 1.0)
    mu, CR = compute_CR(Ry, TB, T1)
    Sd1max      = CR * Sde
    delta_cible = Sd1max * gamma1 * phi_top
    omega1sq    = (2.0 * np.pi / T1) ** 2
    omegaBsq    = (2.0 * np.pi / TB) ** 2

    # Extend converged bilinear plateau to Sd1max for clean display
    d_bilc = d_bilc.copy()
    a_bilc = a_bilc.copy()
    if d_bilc[-1] < Sd1max:
        d_bilc[-1] = Sd1max

    return {
        "T1":               T1,
        "Sae_T1":           Sae_T1,
        "Sde_T1":           Sde,
        "a_y":              ay,
        "d_y":              dy,
        "Ry":               Ry,
        "mu":               mu,
        "CR":               CR,
        "Sd1max":           Sd1max,
        "delta_cible":      delta_cible,
        "n_iter":           n_iter,
        "case":             "T1 > T_B" if T1 > TB else "T1 <= T_B",
        "omega1sq":         omega1sq,
        "omegaBsq":         omegaBsq,
        "d_bilin0":         d_bil0,
        "a_bilin0":         a_bil0,
        "d_bilin":          d_bilc,
        "a_bilin":          a_bilc,
        "convergence_log":  log,
    }
