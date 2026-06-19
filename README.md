# N2 Pushover — TBDY 2018 Annex 5B

A Streamlit application implementing the N2 nonlinear static pushover method for seismic assessment of existing buildings, in strict conformance with **Annex 5B of the Turkish Seismic Building Code (TBDY 2018)**.

---

## Overview

The application determines the **performance point** (target displacement) of a building from its pushover capacity curve V–δ and the elastic response spectrum, following the normative procedure of TBDY 2018 art. 5B.3 (Eq. 5B.12 to 5B.17).

**Features:**
- Transformation of V–δ curve to modal capacity diagram (equivalent SDOF system)
- Elastic spectrum conversion to ADRS format (Eq. 2.5)
- Equal-area bilinearisation with two rules displayed in parallel (secant / initial tangent)
- Iterative computation of C_R for the rigid-structure case T₁ ≤ T_B (art. 5B.3.5b)
- Interactive ADRS plot (Plotly) compliant with Şekil 5B.3 and 5B.4
- Iteration-by-iteration convergence table
- Regulatory alerts per art. 5B.3.6 (near-fault, negative post-yield slope)

---

## Getting Started

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run the application

```bash
streamlit run app.py
```

### 3. Required inputs

| Input | Format | Unit |
|---|---|---|
| Elastic spectrum | CSV `T,Sae` | T in s, Sae in g |
| Capacity curve | CSV `delta,V` | δ in mm, V in kN |
| Γ₁ (modal participation factor) | numeric field | — |
| M₁* (effective modal mass) | numeric field | t |
| φ_top (normalised modal component at roof) | numeric field | — |
| Distance to nearest active fault | numeric field | km |

---

## Project Structure

```
app.py            → Streamlit interface
n2_calc.py        → Calculation engine (pure functions)
_test_calc.py     → Unit tests
requirements.txt  → Python dependencies
```

---

## Normative Compliance

All equations are sourced exclusively from **TBDY 2018**, Annex 5B. No criteria from other standards (Eurocode 8, ATC-40, ASCE 41) are used.

---

## Scope and Limitations

The application outputs the performance point and the target roof displacement δ_target. It does not compute:
- Inter-storey drift ratios
- Plastic hinge acceptance checks (Table 5C.4)

These verifications require floor-level displacements and hinge states from the structural analysis software (SAP2000, Robot Structural Analysis).
