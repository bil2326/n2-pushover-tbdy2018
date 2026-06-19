"""Sanity check — tests avec les fichiers reels ET les fichiers de test iteratif."""
import sys, os
base = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base)

import numpy as np
import pandas as pd
from n2_calc import detect_TB, capacity_to_adrs, compute_performance

# ============================================================
# Test 1 : fichiers reels  (cas T1 > T_B attendu)
# ============================================================
spec_path = os.path.join(base, "spectre.xlsx")
cap_path  = next(
    (os.path.join(base, f) for f in os.listdir(base)
     if "capa" in f.lower() and f.endswith(".xlsx")), None
) or os.path.join(base, "capacite.xlsx")

spec = pd.read_excel(spec_path)
cap  = pd.read_excel(cap_path)

T, Sae  = spec["T"].to_numpy(float),     spec["Sae"].to_numpy(float)
delta, V = cap["delta"].to_numpy(float), cap["V"].to_numpy(float)

gamma1, M1eff, phi_top = 1.30, 500.0, 1.0
idx = np.argsort(T);     T, Sae = T[idx], Sae[idx]
idx2 = np.argsort(delta); delta, V = delta[idx2], V[idx2]
mask = delta >= 0;         delta, V = delta[mask], V[mask]
if delta[0] > 0:
    delta = np.concatenate([[0.0], delta])
    V     = np.concatenate([[0.0], V])

d1, a1 = capacity_to_adrs(delta, V, gamma1, phi_top, M1eff)
TB = detect_TB(T, Sae)

Sde_TB = float(np.interp(TB, T, Sae)) * 9.81 * (TB / (2 * np.pi)) ** 2 * 1000.0
print(f"[TEST 1] spectre.xlsx  TB={TB:.3f}s  Sde(TB)={Sde_TB:.4f}mm")
assert abs(Sde_TB - 41.95) < 0.5, f"Sde(TB) incorrect: {Sde_TB}"

r = compute_performance(d1, a1, T, Sae, TB, gamma1, phi_top)
print(f"         T1={r['T1']:.3f}s  CR={r['CR']:.4f}  n_iter={r['n_iter']}  cas={r['case']}")
assert r["case"] == "T1 > T_B", f"Attendu T1>T_B, obtenu {r['case']}"
assert r["n_iter"] == 0, f"T1>T_B doit donner n_iter=0, obtenu {r['n_iter']}"
assert r["CR"] == 1.0
assert len(r["convergence_log"]) == 1
assert r["convergence_log"][0]["converged"] is True

# Pente de la droite radiale : ay/dy == Sae_T1/Sde_T1
slope = r["a_y"] / r["d_y"]
ref   = r["Sae_T1"] / r["Sde_T1"]
assert abs(slope - ref) / ref < 0.01, f"Droite radiale desalignee: {slope:.6f} vs {ref:.6f}"

print("         OK")

# ============================================================
# Test 2 : fichiers de test iteratif  (cas T1 <= T_B attendu)
# ============================================================
spec2 = pd.read_csv(os.path.join(base, "files", "spectre_test.csv"))
cap2  = pd.read_csv(os.path.join(base, "files", "capacite_test.csv"), sep=";", decimal=",")

T2, Sae2   = spec2["T"].to_numpy(float),  spec2["Sae"].to_numpy(float)
d2, V2     = cap2["delta"].to_numpy(float), cap2["V"].to_numpy(float)

TB2 = detect_TB(T2, Sae2)
M1_iter = 2000.0   # masse donnant T1 <= T_B et Ry > 1
d1b, a1b = capacity_to_adrs(d2, V2, 1.30, 1.0, M1_iter)
r2 = compute_performance(d1b, a1b, T2, Sae2, TB2, 1.30, 1.0)

print(f"\n[TEST 2] fichiers_test (M1*={M1_iter}t)  TB={TB2:.3f}s  T1={r2['T1']:.3f}s")
print(f"         CR={r2['CR']:.4f}  n_iter={r2['n_iter']}  cas={r2['case']}")
assert r2["case"] == "T1 <= T_B", f"Attendu T1<=T_B, obtenu {r2['case']}"
assert r2["CR"] > 1.0, f"CR doit etre > 1 : {r2['CR']}"
assert r2["n_iter"] >= 1, f"T1<=T_B doit donner n_iter>=1 : {r2['n_iter']}"
assert len(r2["convergence_log"]) >= 2  # passe 0 + au moins 1 iteration

# Verification log
for entry in r2["convergence_log"]:
    assert entry["CR"] >= 1.0
    assert entry["Ry"] >= 1.0
last = r2["convergence_log"][-1]
assert last["converged"] is True, "Derniere passe doit etre convergee"
assert last["delta_CR_pct"] < 1.0, f"delta_CR trop grand: {last['delta_CR_pct']:.2f}%"

print("  Passe  Sdi_cible    ay_n     dy_n   T1_n    CR_n   dCR    Conv")
for e in r2["convergence_log"]:
    dCR = "  None" if e["delta_CR_pct"] is None else f"{e['delta_CR_pct']:5.2f}%"
    print(f"    {e['n']}   {e['target_mm']:8.2f}  {e['ay']:.4f}  {e['dy']:6.2f}  {e['T1']:.3f}  {e['CR']:.4f}  {dCR}  {'OK' if e['converged'] else ''}")

print("         OK")
print("\nTous les tests passes.")
