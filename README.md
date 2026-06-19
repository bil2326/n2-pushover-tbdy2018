# N2 Pushover — TBDY 2018 Annexe 5B

Application Streamlit implémentant la méthode N2 de poussée progressive pour l'évaluation sismique de bâtiments existants, conformément à l'**Annexe 5B du règlement parasismique turc TBDY 2018**.

---

## Objectif

Déterminer le **point de performance** (déplacement cible) d'un bâtiment à partir de sa courbe de capacité V–δ et du spectre élastique de calcul, selon la procédure normative TBDY 2018 art. 5B.3 (Éq. 5B.12 à 5B.17).

L'application couvre :
- Transformation V–δ → diagramme de capacité modale (système 1 DDL)
- Conversion du spectre au format ADRS (Éq. 2.5)
- Bilinéarisation à aires égales selon deux règles (sécante / tangente initiale)
- Calcul itératif de C_R (cas T₁ ≤ T_B, art. 5B.3.5b)
- Tracé ADRS interactif (Plotly) conforme aux Şekil 5B.3 et 5B.4
- Tableau de convergence passe par passe
- Alertes réglementaires art. 5B.3.6 (faille proche, pente négative)

---

## Utilisation

### 1. Installer les dépendances

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Lancer l'application

```bash
streamlit run app.py
```

### 3. Entrées requises

| Entrée | Format | Unité |
|---|---|---|
| Spectre élastique | CSV `T,Sae` | T en s, Sae en g |
| Courbe de capacité | CSV `delta,V` | δ en mm, V en kN |
| Γ₁ (facteur de participation) | champ numérique | — |
| M₁* (masse modale effective) | champ numérique | t |
| φ_sommet (composante modale) | champ numérique | — |
| Distance faille active | champ numérique | km |

---

## Structure du projet

```
app.py          → interface Streamlit
n2_calc.py      → moteur de calcul (fonctions pures)
_test_calc.py   → tests unitaires
requirements.txt
```

---

## Conformité normative

Toutes les équations sont issues exclusivement du **TBDY 2018**, Annexe 5B. Aucun critère d'un autre référentiel (Eurocode 8, ATC-40, ASCE 41) n'est utilisé.

Niveau de performance cible pour bâtiment acier existant courant (DTS 1–4, BYS ≥ 2) : **KH / LS** sous DD-2 (Tableau 3.4c).

---

## Périmètre et limites

L'application s'arrête au point de performance et au déplacement cible δ_cible. Elle ne calcule pas :
- les drifts inter-étages
- la vérification des rotules plastiques (Tableau 5C.4)

Ces vérifications nécessitent les déplacements par niveau et l'état des rotules issus du logiciel de calcul (SAP2000, Robot Structural Analysis).
