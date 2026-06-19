# -*- coding: utf-8 -*-
"""
Application N2 / TBDY 2018 -- Methode du deplacement spectral
Annexe 5B du TBDY 2018 — Regle de bilinearisation : secante a 0.6·ay
"""

import importlib, sys
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Force reload of n2_calc so Streamlit always picks up changes to the engine
if "n2_calc" in sys.modules:
    importlib.reload(sys.modules["n2_calc"])

from n2_calc import (
    detect_TB, capacity_to_adrs, compute_performance,
    check_negative_slope, spectrum_to_adrs,
)

st.set_page_config(page_title="N2 / TBDY 2018", layout="wide")


# ---------------------------------------------------------------------------
# File reader — CSV (,  ;  tab) and Excel (.xlsx / .xls)
# ---------------------------------------------------------------------------
def _read_file(src, label: str) -> pd.DataFrame:
    name = getattr(src, "name", str(src))
    ext  = name.rsplit(".", 1)[-1].lower()

    if ext in ("xlsx", "xls"):
        try:
            if hasattr(src, "seek"):
                src.seek(0)
            df = pd.read_excel(src, header=0)
            df.columns = [str(c).strip() for c in df.columns]
            return df
        except Exception as exc:
            st.error(f"Impossible de lire le fichier Excel '{label}' : {exc}")
            st.stop()

    for sep in (",", ";", "\t"):
        for dec in (".", ","):
            try:
                if hasattr(src, "seek"):
                    src.seek(0)
                df = pd.read_csv(src, sep=sep, decimal=dec, engine="python")
                if df.shape[1] >= 2 and not all(df.dtypes == object):
                    df.columns = [str(c).strip() for c in df.columns]
                    return df
            except Exception:
                continue

    st.error(
        f"Impossible de lire '{label}'. "
        "Formats acceptes : CSV (separateurs , ; ou tabulation) et Excel (.xlsx / .xls)."
    )
    st.stop()


def _normalise_columns(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    lower_map = {k.lower(): v for k, v in mapping.items()}
    rename = {}
    for col in df.columns:
        canonical = lower_map.get(str(col).strip().lower())
        if canonical:
            rename[col] = canonical
    return df.rename(columns=rename)


def _to_float_series(series: pd.Series, col: str) -> pd.Series:
    s = series.astype(str).str.strip().str.replace(",", ".", regex=False)
    s = s[~s.str.lower().isin(["", "nan", "none", "n/a", "-"])]
    s = pd.to_numeric(s, errors="coerce")
    n_bad = int(s.isna().sum())
    if n_bad > 0:
        st.warning(f"Colonne `{col}` : {n_bad} valeur(s) non numerique(s) ignoree(s).")
    return s.dropna().reset_index(drop=True)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Parametres modaux")
    gamma1      = st.number_input("Gamma1 — Facteur de participation modal", value=1.30, format="%.4f")
    M1eff       = st.number_input("M1* — Masse modale effective (t)",         value=500.0, format="%.2f")
    phi_top     = st.number_input("phi_sommet — Composante modale normalisee au sommet", value=1.0, format="%.4f")
    dist_faille = st.number_input("Distance a la faille active la plus proche (km)", value=20.0, format="%.1f")

    st.header("Fichiers d'entree")
    st.caption("**Spectre** : colonnes `T` (s) et `Sae` (g) — CSV ou Excel")
    spectrum_file = st.file_uploader("Spectre elastique", type=["csv", "xlsx", "xls"], key="spec")
    st.caption("**Capacite** : colonnes `delta` (**mm**) et `V` (kN) — CSV ou Excel  \nExport SAP2000 direct accepte.")
    capacity_file = st.file_uploader("Courbe de capacite V-delta", type=["csv", "xlsx", "xls"], key="cap")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
if spectrum_file is None or capacity_file is None:
    st.title("Methode N2 — Point de performance / TBDY 2018 Annexe 5B")
    st.info(
        "Chargez les deux fichiers dans la barre laterale pour lancer le calcul :\n\n"
        "- **Spectre elastique** : colonnes `T` (s) et `Sae` (g)\n"
        "- **Courbe de capacite** : colonnes `delta` (mm) et `V` (kN)"
    )
    st.stop()

spec_df = _read_file(spectrum_file, spectrum_file.name)
cap_df  = _read_file(capacity_file, capacity_file.name)

spec_df = _normalise_columns(spec_df, {"T": "T", "Sae": "Sae", "t": "T", "sae": "Sae"})
cap_df  = _normalise_columns(cap_df,  {"delta": "delta", "V": "V", "v": "V"})

if not {"T", "Sae"}.issubset(spec_df.columns):
    st.error(
        f"Le fichier spectre doit contenir les colonnes `T` et `Sae`. "
        f"Colonnes detectees : {list(spec_df.columns)}."
    )
    st.stop()
if not {"delta", "V"}.issubset(cap_df.columns):
    st.error(
        f"Le fichier courbe doit contenir les colonnes `delta` et `V`. "
        f"Colonnes detectees : {list(cap_df.columns)}."
    )
    st.stop()

T_spec    = _to_float_series(spec_df["T"],    "T").to_numpy()
Sae_spec  = _to_float_series(spec_df["Sae"],  "Sae").to_numpy()
delta_raw = _to_float_series(cap_df["delta"], "delta").to_numpy()
V_raw     = _to_float_series(cap_df["V"],     "V").to_numpy()

_errors = []
if len(T_spec) == 0:    _errors.append("`T` (spectre)")
if len(Sae_spec) == 0:  _errors.append("`Sae` (spectre)")
if len(delta_raw) == 0: _errors.append("`delta` (capacite)")
if len(V_raw) == 0:     _errors.append("`V` (capacite)")
if _errors:
    st.error(f"Aucune valeur numerique trouvee dans : {', '.join(_errors)}.")
    with st.expander("Apercu spectre"):
        st.dataframe(spec_df.head())
    with st.expander("Apercu courbe de capacite"):
        st.dataframe(cap_df.head())
    st.stop()

# Sort + clean
idx_T = np.argsort(T_spec);    T_spec, Sae_spec = T_spec[idx_T], Sae_spec[idx_T]
idx_d = np.argsort(delta_raw); delta_raw, V_raw  = delta_raw[idx_d], V_raw[idx_d]
mask  = delta_raw >= 0
if not np.any(mask):
    st.error("La courbe de capacite ne contient aucun delta >= 0.")
    st.stop()
delta_raw, V_raw = delta_raw[mask], V_raw[mask]
if delta_raw[0] > 0.0:
    delta_raw = np.concatenate([[0.0], delta_raw])
    V_raw     = np.concatenate([[0.0], V_raw])

# ---------------------------------------------------------------------------
# Core calculations — secante a 0.6·ay uniquement
# ---------------------------------------------------------------------------
d1, a1 = capacity_to_adrs(delta_raw, V_raw, gamma1, phi_top, M1eff)
TB      = detect_TB(T_spec, Sae_spec)

res = compute_performance(d1, a1, T_spec, Sae_spec, TB, gamma1, phi_top, "secant")

# ---------------------------------------------------------------------------
# Page header + regulatory checks (TBDY art. 5B.3.6)
# ---------------------------------------------------------------------------
st.title("Methode N2 — Point de performance / TBDY 2018 Annexe 5B")

if dist_faille < 15.0:
    st.error(
        f"**Alerte TBDY art. 5B.3.6** — Distance a la faille ({dist_faille:.1f} km) < 15 km : "
        "une analyse temporelle non-lineaire est requise (art. 5B.4)."
    )
if check_negative_slope(a1):
    st.error(
        "**Alerte TBDY art. 5B.3.6** — La courbe de capacite presente une pente "
        "post-ecoulement negative (effets P-Delta) : "
        "une analyse temporelle non-lineaire est requise."
    )

st.metric("T_B detecte (fin du plateau d'acceleration constante)", f"{TB:.3f} s")

# ---------------------------------------------------------------------------
# Unit check expander
# ---------------------------------------------------------------------------
with st.expander("Verification de coherence des unites et formules appliquees"):
    st.markdown(f"""
**Spectre ADRS** (Sd en mm)
$$S_d(T)\\,[\\text{{mm}}] = S_a(T)\\,[g] \\times 9{{,}}81 \\times \\left(\\frac{{T}}{{2\\pi}}\\right)^2 \\times 1000$$

**Courbe de capacite → ADRS**
$$S_a\\,[g] = \\frac{{V\\,[\\text{{kN}}]}}{{\\Gamma \\cdot m_1^*\\,[\\text{{t}}] \\cdot g}} \\qquad
S_d\\,[\\text{{mm}}] = \\frac{{\\delta\\,[\\text{{mm}}]}}{{\\Gamma \\cdot \\varphi_{{1,\\text{{toit}}}}}}$$

**Periode du systeme equivalent**
$$T^*\\,[\\text{{s}}] = 2\\pi\\sqrt{{\\frac{{S_{{d,y}}\\,[\\text{{mm}}]}}{{S_{{a,y}}\\,[g] \\times 9810}}}}$$

**Point de performance** (Eq. 5B.13)
$$S_{{d1,\\max}} = C_R \\cdot S_{{de}}(T_1) \\qquad \\delta_{{\\text{{cible}}}} = S_{{d1,\\max}} \\cdot \\Gamma_1 \\cdot \\varphi_{{\\text{{toit}}}}$$

| Grandeur | Valeur | Unite |
|---|---|---|
| delta sommet max (SAP2000) | {delta_raw[-1]:.1f} | mm |
| V base max | {V_raw[-1]:.1f} | kN |
| Gamma1 | {gamma1:.4f} | — |
| M1* | {M1eff:.1f} | t |
| Sa max = V/(Gamma·M1*·g) | {a1[-1]:.4f} | g |
| Sd max = delta/(Gamma·phi) | {d1[-1]:.2f} | mm |
""")

# ---------------------------------------------------------------------------
# ADRS figure
# ---------------------------------------------------------------------------
T_fine   = np.linspace(T_spec[0] if T_spec[0] > 0 else T_spec[1], T_spec[-1], 500)
Sae_fine = np.interp(T_fine, T_spec, Sae_spec)
Sde_fine = Sae_fine * 9.81 * (T_fine / (2.0 * np.pi)) ** 2 * 1000.0

Sae_TB = float(np.interp(TB, T_spec, Sae_spec))
Sde_TB = Sae_TB * 9.81 * (TB / (2.0 * np.pi)) ** 2 * 1000.0

x_max = max(
    1.5 * float(d1[-1]),
    1.3 * res["Sd1max"],
    1.3 * res["Sde_T1"],
    Sde_TB * 2.0,
)

T1     = res["T1"]
dy     = res["d_y"]
ay     = res["a_y"]
Sde_T1 = res["Sde_T1"]
Sae_T1 = res["Sae_T1"]
Sd1max = res["Sd1max"]
CR     = res["CR"]

fig = go.Figure()

# Elastic spectrum
fig.add_trace(go.Scatter(
    x=Sde_fine, y=Sae_fine, mode="lines",
    name="Spectre elastique",
    line=dict(color="steelblue", width=2.5),
))

# Raw capacity curve
fig.add_trace(go.Scatter(
    x=d1, y=a1, mode="lines",
    name="Courbe de capacite",
    line=dict(color="gray", width=2),
))

# T_B radial line
fig.add_trace(go.Scatter(
    x=[0.0, Sde_TB], y=[0.0, Sae_TB], mode="lines",
    name=f"Pente T_B={TB:.3f}s",
    line=dict(color="red", width=1.5, dash="dash"),
))
fig.add_trace(go.Scatter(
    x=[Sde_TB], y=[Sae_TB], mode="markers+text",
    marker=dict(size=9, color="red", symbol="diamond"),
    text=[f"T_B={TB:.3f}s<br>Sde={Sde_TB:.1f}mm"],
    textposition="top left",
    showlegend=False,
))

# Pass-0 bilinear (dashed) — only when T1 <= TB
if T1 <= TB:
    fig.add_trace(go.Scatter(
        x=res["d_bilin0"], y=res["a_bilin0"], mode="lines",
        name=f"Bilineaire passe-0  (cible=Sde={Sde_T1:.1f}mm)",
        line=dict(color="darkorange", width=1.5, dash="dash"),
    ))

# Converged bilinear
fig.add_trace(go.Scatter(
    x=res["d_bilin"], y=res["a_bilin"], mode="lines",
    name=f"Bilineaire convergee  ay={ay:.3f}g  dy={dy:.1f}mm  T1={T1:.3f}s",
    line=dict(color="darkorange", width=2.5),
))

# Radial line omega1^2: (0,0) → (dy, ay) → (Sde_T1, Sae_T1)
fig.add_trace(go.Scatter(
    x=[0.0, dy, Sde_T1], y=[0.0, ay, Sae_T1], mode="lines",
    name=f"Droite T1={T1:.3f}s  (pente omega1²)",
    line=dict(color="darkorange", width=1.5, dash="longdash"),
))

# Sde(T1) marker on spectrum
fig.add_trace(go.Scatter(
    x=[Sde_T1], y=[Sae_T1], mode="markers+text",
    marker=dict(size=11, color="darkorange", symbol="circle"),
    text=[f"Sde(T1)={Sde_T1:.1f}mm"],
    textposition="top right",
    name=f"Sde(T1)={Sde_T1:.1f}mm  Sae(T1)={Sae_T1:.3f}g",
))

# Horizontal extension at ay from Sde_T1 to Sd1max (only when CR > 1)
if CR > 1.0 + 1e-4:
    fig.add_trace(go.Scatter(
        x=[Sde_T1, Sd1max], y=[ay, ay], mode="lines",
        line=dict(color="darkorange", width=1.5, dash="dot"),
        showlegend=False,
    ))

# Performance point at (Sd1max, ay) on bilinear plateau
fig.add_trace(go.Scatter(
    x=[Sd1max], y=[ay], mode="markers+text",
    marker=dict(size=16, color="darkorange", symbol="star"),
    text=[f"PP : Sd1max={Sd1max:.1f}mm<br>ay={ay:.3f}g"],
    textposition="top right",
    name=f"Point de performance  Sd1max={Sd1max:.1f}mm  CR={CR:.3f}",
))

fig.update_layout(
    title="Diagramme ADRS — Sa(g) = f(Sd[mm])  —  Methode N2 / TBDY 2018",
    xaxis=dict(title="Deplacement spectral Sd (mm)", range=[0, x_max]),
    yaxis=dict(title="Acceleration spectrale Sa (g)", rangemode="tozero"),
    legend=dict(
        orientation="h",
        yanchor="top", y=-0.12,
        xanchor="center", x=0.5,
        bgcolor="rgba(255,255,255,0.85)",
        font=dict(size=10),
    ),
    margin=dict(b=180),
    hovermode="closest",
    height=650,
)
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Spectrum verification tables
# ---------------------------------------------------------------------------
with st.expander("Verification numerique spectre → ADRS  (Sa·g·(T/2π)²·1000)"):
    sde_check = Sae_spec * 9.81 * (T_spec / (2.0 * np.pi)) ** 2 * 1000.0
    st.dataframe(pd.DataFrame({
        "T (s)":   np.round(T_spec, 4),
        "Sa (g)":  np.round(Sae_spec, 4),
        "Sd (mm)": np.round(sde_check, 3),
    }), use_container_width=True, height=300)
    st.caption(
        f"Exemple : Sd(T_B={TB:.3f}s) = {Sae_TB:.4f} × 9.81 × "
        f"({TB:.3f}/2π)² × 1000 = **{Sde_TB:.2f} mm**"
    )

with st.expander("Spectre Sa = f(T) — verification visuelle de T_B"):
    fig_s = go.Figure()
    fig_s.add_trace(go.Scatter(x=T_spec, y=Sae_spec, mode="lines+markers",
                               name="Sa(T)", line=dict(color="steelblue")))
    fig_s.add_vline(x=TB, line_dash="dash", line_color="red",
                    annotation_text=f"T_B = {TB:.3f} s")
    fig_s.update_layout(xaxis_title="T (s)", yaxis_title="Sa (g)", height=350)
    st.plotly_chart(fig_s, use_container_width=True)

# ---------------------------------------------------------------------------
# Summary table — CDC §4.2 (15 grandeurs)
# ---------------------------------------------------------------------------
st.subheader("Tableau recapitulatif")

omegaBsq = (2.0 * np.pi / TB) ** 2

table_data = {
    "Grandeur": [
        "T1 (s)",
        "omega1² = (2pi/T1)² (rad²/s²)",
        "T_B (s)",
        "omegaB² = (2pi/T_B)² (rad²/s²)",
        "Cas applicable",
        "Sde(T1) (mm)",
        "Sae(T1) (g)",
        "ay1 (g)",
        "dy (mm)",
        "R_y",
        "mu",
        "C_R",
        "Sd1,max (mm)",
        "delta_cible (mm)",
        "Iterations",
    ],
    "Valeur": [
        f"{res['T1']:.3f}",
        f"{res['omega1sq']:.2f}",
        f"{TB:.3f}",
        f"{omegaBsq:.2f}",
        res["case"].replace("<=", "≤"),
        f"{res['Sde_T1']:.2f}",
        f"{res['Sae_T1']:.4f}",
        f"{res['a_y']:.4f}",
        f"{res['d_y']:.2f}",
        f"{res['Ry']:.3f}",
        f"{res['mu']:.3f}",
        f"{res['CR']:.3f}",
        f"{res['Sd1max']:.2f}",
        f"{res['delta_cible']:.2f}",
        str(res["n_iter"]),
    ],
}

st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Convergence detail — CDC §4.3
# ---------------------------------------------------------------------------
log = res["convergence_log"]
case_str = res["case"].replace("<=", "≤")

with st.expander(f"Detail des iterations ({case_str}  —  n_iter = {res['n_iter']})"):
    if res["case"] == "T1 > T_B":
        st.info(
            "T1 > T_B → C_R = 1 par definition (Eq. 5B.17a). "
            "Aucune iteration necessaire, le tableau ci-dessous montre la passe 0 uniquement."
        )
    else:
        st.info(
            f"T1 ≤ T_B → boucle iterative (Eq. 5B.17b). "
            f"Convergence atteinte en **{res['n_iter']}** iteration(s) "
            f"(critere |ΔC_R|/C_R < 1 %)."
        )

    rows_log = []
    for entry in log:
        delta_str = (
            "—" if entry["delta_CR_pct"] is None
            else f"{entry['delta_CR_pct']:.2f} %"
        )
        conv_str = "✅" if entry["converged"] else "⏳"
        rows_log.append({
            "Passe n":           entry["n"],
            "Sdi cible (mm)":   f"{entry['target_mm']:.2f}",
            "ay_n (g)":          f"{entry['ay']:.4f}",
            "dy_n (mm)":         f"{entry['dy']:.2f}",
            "T1_n (s)":          f"{entry['T1']:.3f}",
            "Sae(T1_n) (g)":     f"{entry['Sae_T1']:.4f}",
            "Ry_n":              f"{entry['Ry']:.3f}",
            "mu_n":              f"{entry['mu']:.3f}",
            "CR_n":              f"{entry['CR']:.4f}",
            "|Delta CR| / CR":   delta_str,
            "Conv.":             conv_str,
        })

    df_log = pd.DataFrame(rows_log)
    st.dataframe(df_log, use_container_width=True, hide_index=True)

    st.caption(
        "Colonne **Sdi cible** = C_R(n-1) · Sde(T1) — target de bilinearisation a la passe n.  "
        "Passe 0 : C_R = 1 suppose, cible = Sde(T1_init)."
    )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    "Calculs conformes a **TBDY 2018 Annexe 5B** — "
    "Eq. 5B.3, 5B.4, 5B.12 a 5B.17 et art. 5B.3.6. "
    "Bilinearisation : secante a 0.6·ay, cible = C_R·Sde(T1) iteree. "
    "Limites : pas de calcul de drift inter-etage ; "
    "pas de verification des rotules plastiques (Tableau 5C.4)."
)
