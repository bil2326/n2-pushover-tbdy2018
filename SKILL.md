---
name: n2-tbdy2018-pushover
description: "Use this skill for any task involving the N2 method (nonlinear static pushover) under the Turkish seismic code TBDY 2018, Annex 5B. Triggers: pushover analysis, N2 method, ADRS diagram, capacity curve, bilinearisation, C_R coefficient, modal displacement demand, performance point, TBDY 2018 Annex 5B, Sdi, Sde, ay1, Ry, mu, CR, T1 vs TB, drift check, seismic performance assessment of existing buildings under Turkish code. Also use when writing, auditing, or debugging Python/Streamlit code that implements any part of this procedure. Do NOT use for Eurocode 8 pushover, ATC-40 capacity spectrum method, or ASCE 41 — those use different procedures."
license: Internal — bureau d'études usage
---

# N2 Method — TBDY 2018 Annex 5B
## Pushover Analysis of Existing Buildings

---

## 0. Identity and authority

This skill governs every calculation, every line of code, every graphical construction related to the N2 pushover method as defined in **TBDY 2018 Annexe 5B**. The sole normative reference is the TBDY 2018 text available in the project knowledge base (`/mnt/project/TBDY_2018.md`). No other standard (Eurocode 8, ATC-40, FEMA 440, ASCE 41) overrides it — they may inform engineering judgement but never replace a TBDY requirement.

**Before writing any code or formula, search the project knowledge base** for the relevant article. Never cite an equation from memory alone.

---

## 1. The procedure at a glance

The N2 method converts a multi-degree-of-freedom pushover curve into a single-degree-of-freedom (SDOF) modal capacity diagram, then reads the inelastic displacement demand from the elastic response spectrum using a displacement modification factor C_R.

**Five mandatory stages — none is optional, none may be reordered:**

1. Transform V–δ → modal capacity diagram (a₁, d₁) using Éq. 5B.3 and 5B.4.
2. Convert elastic spectrum T–Sae → ADRS format (Sde, Sae) using Éq. 2.5.
3. Bilinearise the capacity diagram at equal areas to obtain (dy, ay1, T₁).
4. Compute R_y, μ, C_R from Éq. 5B.15–5B.17, iterating if T₁ ≤ T_B.
5. Determine Sd1,max = C_R · Sde(T₁) and back-convert to δ_cible.

---

## 2. Equations — exact forms only

These are the only acceptable forms. Any rewriting, simplification, or substitution is an error.

```
Éq. 5B.12 :  d1,max = Sdi(T1)
Éq. 5B.13 :  Sdi(T1) = C_R · Sde(T1)
Éq. 5B.14 :  C_R = μ(Ry, T1) / Ry
Éq. 5B.15 :  Ry = Sae(T1) / ay1          ← both terms in g
Éq. 5B.16a : μ = Ry                        if T1 > T_B
Éq. 5B.16b : μ = 1 + (Ry − 1)·(T_B/T1)   if T1 ≤ T_B
Éq. 5B.17a : C_R = 1                       if T1 > T_B
Éq. 5B.17b : C_R = [1 + (Ry−1)·T_B/T1] / Ry ≥ 1   if T1 ≤ T_B
Éq. 2.5    :  Sde(T) = Sae(T) · g · (T/(2π))²   [g = 9.81 m/s²]
```

**Transformation to SDOF (Éq. 5B.3 / 5B.4):**
```
a1 = V / (M1* · g)          [result in g, V in kN, M1* in t, g = 9.81 m/s²]
d1 = δ_top / (Γ1 · φ_top)   [result in m]
```

**Period from bilinear diagram:**
```
T1 = 2π · √(dy / ay1_ms2)   where ay1_ms2 = ay1[g] · 9.81
```

**Back-conversion to physical displacement:**
```
δ_cible = Sd1,max · Γ1 · φ_top
```

---

## 3. Definitions — no ambiguity tolerated

| Symbol | Exact definition | Common mistake |
|---|---|---|
| `dy` | Abscissa of the yield point on the bilinear diagram (end of elastic branch). **Not** Sde, not d1,max. | Confused with Sde |
| `ay1` | Ordinate of the plateau of the bilinear diagram (yield pseudo-acceleration). | Confused with Sae(T1) |
| `Sde(T1)` | Elastic spectral displacement at T1 from Éq. 2.5. Read at the intersection of the radial line ω1² with the elastic spectrum. | Confused with dy or Sd1,max |
| `Sd1,max` | Inelastic spectral displacement = C_R · Sde(T1). The target displacement of the SDOF system. | Confused with Sde when C_R=1 |
| `T_B` | Corner period of the spectrum (end of constant-acceleration plateau). Detected automatically as the peak of Sae before the descending branch. | Read from code defaults instead of actual spectrum |
| `ω1²` | (2π/T1)² — slope of the elastic radial line in ADRS space. Computed from the bilinear diagram, not from an eigenvalue analysis. | Approximated or omitted |
| `ω_B²` | (2π/T_B)² — threshold slope for the T1 vs T_B condition. | Never computed |

---

## 4. The bilinearisation — the most error-prone step

### 4.1 Equal-area rule (art. 5B.3.5b)

The bilinear elastic-perfectly-plastic diagram is constructed so that the area under the bilinear equals the area under the capacity curve **up to the current target displacement** S_di (not Sde). This is the most frequent source of error.

```
Area(bilinear, 0 → S_di) = Area(capacity curve, 0 → S_di)
```

### 4.2 Two initial-stiffness rules (both mandatory, shown in parallel)

1. **Secant at 0.6·ay1** : elastic branch passes through the point (d at a=0.6·ay1, 0.6·ay1).
2. **Initial tangent** : elastic branch slope = slope of the first segment of the capacity curve.

Each rule produces its own (dy, ay1, T1) and its own performance point. Both are displayed; the engineer chooses.

### 4.3 Iteration — the target displacement changes at every pass

This is the critical rule. **Violating it is a calculation error, not a simplification.**

```
Pass 0 :  target = Sde(T1)   [C_R = 1 assumed]  → obtain ay1⁰
Pass n :  compute Ry, μ, C_R
          target = C_R · Sde(T1)                  ← updated every pass
          re-bilinearise up to this new target     → obtain ay1ⁿ
          repeat until |C_R(n) − C_R(n−1)| / C_R(n) < 0.01
```

If the code bilinearises always up to Sde (fixed), the result from pass 1 onward is wrong.

---

## 5. Graphical construction — exact reproduction of Şekil 5B.3 / 5B.4

The ADRS graph is not decorative. It is normative. Every element listed below is **mandatory**.

### 5.1 Elements common to both cases

| Element | How to draw it | What it represents |
|---|---|---|
| Elastic spectrum | (Sde, Sae) from Éq. 2.5, all points of the input CSV | Demand on an elastic SDOF |
| Raw capacity curve | (d1, a1) from stage 1 | Actual pushover result |
| Bilinear diagram | (dy, ay1) plateau | Idealised SDOF |
| Radial line ω1² | From origin (0,0), slope = ω1² = (2π/T1)², extended until it intersects the elastic spectrum | Defines T1 and locates Sde(T1) |
| Point Sde(T1) | Intersection of radial line with elastic spectrum — marked explicitly | Elastic displacement demand |
| Point of performance | On the bilinear diagram at abscissa Sd1,max = C_R·Sde(T1), ordinate ay1 | Inelastic displacement demand |

### 5.2 Case T1 > T_B — Şekil 5B.3

- One bilinear (converged), solid line.
- Performance point = (Sde, ay1) since C_R = 1.
- The radial line touches the spectrum exactly at Sde = Sd1,max.

### 5.3 Case T1 ≤ T_B — Şekil 5B.4

- **Two bilinears** superimposed:
  - Pass-0 bilinear (dashed) = Şekil 5B.4a state.
  - Converged bilinear (solid) = Şekil 5B.4b state.
- Performance point abscissa Sd1,max > Sde.
- Both Sde(T1) and Sd1,max marked on the x-axis.

### 5.4 What is NOT acceptable in the graph

- A radial line that is approximate, omitted, or stops before the spectrum.
- Sde read from a formula without being shown as an intersection.
- A single bilinear when T1 ≤ T_B.
- Performance point placed at the intersection of the two curves (capacity × spectrum) — this is the ATC-40 method, not N2.

---

## 6. Unit discipline — enforced throughout

| Quantity | Unit in code | Notes |
|---|---|---|
| V (base shear) | kN | Input CSV |
| δ_top | m | Input CSV |
| M1* | t | User input |
| g | 9.81 m/s² | Hard-coded constant |
| a1, ay1, Sae | g | Dimensionless acceleration |
| d1, dy, Sde, Sd1,max, δ_cible | m | All displacements |
| T1, T_B | s | — |
| ω1², ω_B² | rad²/s² | Displayed in results table |
| R_y, μ, C_R | — | Dimensionless |

**Critical check** : R_y = Sae(T1) / ay1 is dimensionally correct only if both are in g. If either is in m/s², divide by 9.81 first. Display this check on screen.

---

## 7. Regulatory limits (art. 5B.3.6) — hard stops

Both conditions must be checked before displaying any result. If either is true, the spectral displacement method is **invalid** and a time-history analysis is required.

```
(a) Fault distance < 15 km  →  STOP, time-history required (art. 5B.4)
(b) Post-yield slope of capacity diagram < 0  →  STOP, time-history required
```

Display a blocking warning (Streamlit `st.error`), not just a note.

---

## 8. T_B detection algorithm

T_B is the period at the end of the constant-acceleration plateau. Detection from a discrete spectrum CSV:

1. Find Sae_max = max(Sae array).
2. T_B = last T value where Sae ≥ 0.99 · Sae_max (1 % tolerance on plateau flatness).
3. Display T_B and mark it on the spectrum plot. Allow manual override.
4. If the spectrum has no discernible plateau (monotonically decreasing), signal an error.

---

## 9. Interpolation rule

S_ae(T1) is obtained by **piecewise linear interpolation** between the two CSV points bracketing T1. No spline, no polynomial, no extrapolation.

```python
Sae_T1 = np.interp(T1, T_array, Sae_array)  # numpy linear interpolation
```

If T1 < T_array[0] or T1 > T_array[-1], raise a ValueError and display an error in the UI.

---

## 10. Output table — mandatory columns

| Column | Symbol | Unit |
|---|---|---|
| Effective period | T1 | s |
| Initial stiffness | ω1² | rad²/s² |
| Corner period | T_B | s |
| Threshold stiffness | ω_B² | rad²/s² |
| Applicable case | T1 > T_B or T1 ≤ T_B | — |
| Elastic spectral displacement | Sde(T1) | m |
| Elastic spectral acceleration | Sae(T1) | g |
| Yield pseudo-acceleration | ay1 | g |
| Yield displacement | dy | m |
| Strength reduction factor | Ry | — |
| Ductility demand | μ | — |
| Displacement modification | C_R | — |
| Inelastic spectral displacement | Sd1,max | m |
| Target roof displacement | δ_cible | m |
| Iterations | n_iter | — |

---

## 11. Code architecture (Streamlit app)

```
app.py
├── sidebar_inputs()         → returns dict: Γ1, M1*, φ_top, fault_dist, CSV data
├── transform_to_sdof()      → V,δ → a1,d1 using Éq.5B.3/5B.4
├── convert_spectrum_adrs()  → T,Sae → Sde,Sae using Éq.2.5
├── detect_TB()              → returns T_B from spectrum array
├── bilinearise()            → (capacity, target, rule) → (dy, ay1, T1)
│     rules: 'secant06' | 'initial_tangent'
├── compute_CR()             → full iteration loop, returns (Ry, μ, CR, Sdi, n_iter)
│     calls bilinearise() at every pass with updated target = CR·Sde
├── check_limits_5B36()      → returns (fault_ok, slope_ok) with st.error if False
├── build_adrs_figure()      → returns plotly Figure with all mandatory elements
└── results_table()          → returns pd.DataFrame with all mandatory columns
```

Every function is **pure** (no side effects, no global state). Tests can call them directly without Streamlit.

---

## 12. Known pitfalls — do not repeat

| Pitfall | Consequence | Guard |
|---|---|---|
| Bilinearise always up to Sde (fixed) | ay1 wrong from pass 1, C_R wrong | Target = C_R·Sde, updated every pass |
| Performance point = intersection of capacity × spectrum curves | Wrong method (ATC-40 not N2) | Point is on capacity curve at abscissa Sd1,max |
| Radial line omitted or approximate | Sde unverifiable graphically | Draw from (0,0) with exact slope ω1², extend to spectrum |
| Sae and ay1 in different units for Ry | Ry dimensionally wrong (factor ~9.81) | Assert both in g before division |
| T_B from default or hard-coded value | Wrong case detection | Always detect from actual spectrum |
| One bilinear shown when T1 ≤ T_B | Convergence invisible | Show pass-0 (dashed) and converged (solid) |
| dy confused with Sde | T1 wrong | dy = yield abscissa on bilinear ≠ Sde |
| Extrapolation of spectrum for T1 outside range | Silent wrong Sae | Raise ValueError if T1 out of bounds |

---

## 13. Pre-code checklist — run before writing any function

- [ ] Éq. 5B.3/5B.4 : units V in kN, M1* in t, g = 9.81 → a1 in g ?
- [ ] Éq. 2.5 : Sde in m, Sae in g, g = 9.81 applied ?
- [ ] T_B detected from actual spectrum, not hard-coded ?
- [ ] bilinearise() target = C_R·Sde at every pass (not fixed Sde) ?
- [ ] Two rules (secant-0.6 and initial-tangent) both implemented ?
- [ ] Interpolation np.interp (linear), no extrapolation ?
- [ ] Éq. 5B.17b : C_R ≥ 1 enforced ?
- [ ] Convergence criterion |ΔC_R|/C_R < 0.01, max 50 iterations ?
- [ ] Graph: radial line from (0,0), slope ω1², extended to spectrum ?
- [ ] Graph: Sde(T1) marked as explicit intersection point ?
- [ ] Graph: two bilinears when T1 ≤ T_B ?
- [ ] Graph: performance point on capacity curve at Sd1,max, not on spectrum ?
- [ ] art. 5B.3.6 : fault distance and negative slope both checked before output ?
- [ ] Output table: all 15 columns present ?

---

## 14. Audit trail

| Version | Date | Change |
|---|---|---|
| v1 | 2026-06-18 | Initial — from CDC v1 (pre-audit) |
| v2 | 2026-06-18 | Corrections from conformity audit : bilinearisation target, radial line, two bilinears, unit checks, interpolation, d_y definition |
