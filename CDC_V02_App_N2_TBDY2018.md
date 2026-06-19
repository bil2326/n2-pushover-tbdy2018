# Cahier des charges — Application N2 / TBDY 2018

**Objet** : application Streamlit calculant le point de performance d'un bâtiment par la méthode N2 (poussée progressive), conformément à l'Annexe 5B du TBDY 2018.

**Entrées fournies par l'utilisateur** : le spectre élastique et la courbe de capacité V–δ. L'application réalise la transformation en système à un degré de liberté, la bilinéarisation, le calcul de C_R et la détermination du point de performance.

---

## 1. Périmètre

### 1.1 Ce que l'application fait

- Transformation de la courbe de capacité V–δ en diagramme de capacité modale (a₁–d₁).
- Détection automatique de la période d'angle T_B à partir du spectre saisi.
- Bilinéarisation du diagramme de capacité à aires égales, selon **deux règles affichées en parallèle** pour comparaison.
- Calcul du coefficient de réduction R_y, de la demande de ductilité μ et du coefficient de modification du déplacement C_R, en distinguant les deux cas T₁ > T_B et T₁ ≤ T_B.
- Détermination du déplacement spectral non-linéaire S_d1,max et du déplacement cible réel au sommet δ_cible.
- Tracé interactif (Plotly) du diagramme ADRS avec point de performance.

### 1.2 Ce que l'application ne fait pas (limite actée)

- Pas de calcul de drift inter-étage.
- Pas de vérification des rotules plastiques vis-à-vis du Tableau 5C.4.

> Ces deux vérifications nécessitent les déplacements par niveau et l'état des rotules, qui ne sont pas contenus dans une simple courbe V–δ. L'application s'arrête au point de performance et au déplacement cible.

---

## 2. Entrées

| Entrée | Format | Unité | Source |
|---|---|---|---|
| Spectre élastique | CSV deux colonnes `T,Sae` | T en s, Sae en g | upload |
| Courbe de capacité | CSV deux colonnes `delta,V` | δ sommet en **mm**, V base en kN | upload |
| Γ₁ | champ numérique | — | utilisateur |
| M₁* (masse modale effective) | champ numérique | t | utilisateur |
| φ_sommet (composante modale au sommet, normalisée) | champ numérique | — | utilisateur |
| Distance à la faille active la plus proche | champ numérique | km | utilisateur |

Les entrées sont regroupées dans la barre latérale (sidebar) Streamlit. Le format CSV attendu est documenté à l'écran.

---

## 3. Moteur de calcul

### 3.1 Transformation en système à un degré de liberté

D'après le TBDY 2018 (Éq. 5B.3 et 5B.4) :

- Déplacement modal : `d₁ = (δ_sommet / 1000) / (Γ₁ · φ_sommet)` — δ_sommet lu en mm, converti en m immédiatement à la lecture du CSV. **Tout le moteur de calcul travaille en mètres.**
- Pseudo-accélération modale : `a₁ = V / (M₁* · g)` (résultat en g)

La cohérence des unités est affichée à l'écran pour vérification (point sensible : conversion kN / t / g).

### 3.2 Détection automatique de T_B et conversion du spectre au format ADRS

L'application repère la fin du plateau d'accélération constante du spectre saisi et en déduit T_B. La valeur détectée est affichée et peut être vérifiée visuellement sur le tracé du spectre.

Le spectre est saisi en colonnes `T, Sae` (T en s, Sae en g). La conversion vers le format ADRS (S_de en m, S_ae en g) est effectuée par l'Éq. 2.5 du TBDY 2018 :

```
S_de(T) = S_ae(T) · g · (T / (2π))²      avec g = 9.81 m/s²
```

S_ae reste en g. S_de est en mètres. Cette conversion est appliquée à chaque point du spectre avant tout tracé ou interpolation. L'unité de S_de est affichée à l'écran pour vérification.

### 3.3 Bilinéarisation à aires égales — deux règles

Le diagramme de capacité est converti en diagramme bilinéaire élasto-plastique en respectant l'égalité des aires sous les deux courbes (TBDY art. 5B.3.5b). Deux règles sont calculées et affichées en parallèle :

1. **Sécante à 0,6·a_y1** (règle FEMA / standard) : la rigidité initiale est la sécante passant par le point situé à 0,6 fois la pseudo-accélération d'écoulement.
2. **Tangente initiale** : la rigidité initiale est la pente initiale de la courbe de capacité.

Chaque règle produit son propre a_y1, sa propre période T₁ et son propre point de performance.

**Définitions strictes (conformes à Şekil 5B.4) :**

- `d_y` : déplacement d'écoulement du diagramme bilinéaire, c'est-à-dire l'abscisse du point de rupture de pente (fin de la branche élastique). Il est distinct de S_de (déplacement cible).
- `a_y1` : pseudo-accélération d'écoulement, ordonnée du plateau horizontal du diagramme bilinéaire.
- La période effective est déduite de la rigidité initiale bilinéarisée : `T₁ = 2π · √(d_y / a_y1)` avec d_y en m et a_y1 en m/s² (= a_y1[g] · 9.81).

**Vérification du cas applicable (art. 5B.3.5a) :**

Conformément au TBDY 2018, la condition `T₁ > T_B` est vérifiée sous sa forme équivalente sur la pente du diagramme :

```
ω₁² = (2π/T₁)²   et   ω_B² = (2π/T_B)²
Condition cas (a) : ω₁² ≤ ω_B²   ↔   T₁ ≥ T_B
```

Les deux valeurs ω₁² et ω_B² sont calculées et affichées. La condition est vérifiée numériquement et indiquée dans le tableau récapitulatif.

**Boucle de convergence — déplacement cible mis à jour à chaque passe (écart #15, critique) :**

La dépendance croisée entre a_y1, l'aire égalisée, C_R et le déplacement cible impose une boucle itérative. La procédure exacte du TBDY (art. 5B.3.5b, Şekil 5B.4) est la suivante :

- **Passe 0** : bilinéariser jusqu'à `S_di = S_de` (C_R = 1). Obtenir `a⁰_y1`.
- **Passe n** : calculer R_y, μ, C_R. Mettre à jour `S_di(T₁) = C_R · S_de`. **Re-bilinéariser jusqu'à ce nouveau déplacement cible `S_di`** (pas jusqu'à S_de fixe) pour obtenir `aⁿ_y1`.
- Répéter jusqu'à convergence : `|C_R(n) − C_R(n−1)| / C_R(n) < 1 %` (convention interne, non contredite par la norme).

> **Attention** : à chaque passe, le déplacement cible de l'égalisation des aires est `S_di = C_R · S_de` et non S_de fixe. Figer le déplacement cible à S_de constitue une erreur de calcul.

Le nombre d'itérations effectuées est affiché dans le tableau récapitulatif.

### 3.4 Coefficient de modification C_R (TBDY art. 5B.3)

**Interpolation de S_ae(T₁)** : T₁ ne coïncide en général pas avec un point du CSV fourni. S_ae(T₁) est obtenu par **interpolation linéaire par morceaux** entre les deux points du spectre encadrant T₁. Aucune extrapolation n'est autorisée ; si T₁ est hors de la plage du spectre fourni, une erreur est signalée.

- Coefficient de réduction : `R_y = S_ae(T₁) / a_y1` (Éq. 5B.15) — les deux termes sont en g.
- Demande de ductilité :
  - cas T₁ > T_B : `μ = R_y` (Éq. 5B.16a)
  - cas T₁ ≤ T_B : `μ = 1 + (R_y − 1)·(T_B / T₁)` (Éq. 5B.16b)
- Coefficient de modification :
  - cas T₁ > T_B : `C_R = 1` (Éq. 5B.17a)
  - cas T₁ ≤ T_B : `C_R = [1 + (R_y − 1)·T_B/T₁] / R_y ≥ 1` (Éq. 5B.17b), calculé par itération

**Vérification d'unités affichée à l'écran** : S_ae(T₁) en g, a_y1 en g, R_y sans dimension. Si S_ae est fourni en m/s², l'application convertit automatiquement en g avant calcul et signale la conversion.

### 3.5 Point de performance

- Déplacement spectral non-linéaire : `S_d1,max = C_R · S_de(T₁)` (Éq. 5B.13)
- Conversion inverse vers le déplacement réel au sommet : `δ_cible = S_d1,max · Γ₁ · φ_sommet`

---

## 4. Sorties

### 4.1 Graphe ADRS interactif (Plotly)

Le graphe reproduit exactement les Şekil 5B.3 et Şekil 5B.4 du TBDY 2018. Il contient les éléments suivants, tous obligatoires :

**Éléments communs aux deux cas (T₁ > T_B et T₁ ≤ T_B) :**

- Spectre élastique au format ADRS : courbe `(S_de, S_ae)` issue de la conversion §3.2.
- Diagramme de capacité modale brut `(d₁, a₁)` tel qu'issu de la transformation §3.1.
- **Droite élastique passant par l'origine**, de pente `ω₁² = (2π/T₁)²` dans le repère (S_de, S_ae). Cette droite est tracée depuis l'origine `(0, 0)` et **prolongée jusqu'à son intersection effective avec le spectre élastique**. Ce point d'intersection donne `S_de(T₁)` graphiquement. La pente de cette droite est `ω₁²` et non une valeur approchée.
- **Point S_de(T₁)** : intersection de la droite élastique avec le spectre. Ce point est marqué explicitement et ses coordonnées sont affichées au survol.
- **Point de performance** : posé sur le diagramme de capacité bilinéarisé à l'abscisse `S_d1,max = C_R · S_de(T₁)`. Marqué avec ses coordonnées `(S_d1,max, a_y1)`.

**Cas T₁ > T_B — Şekil 5B.3 (C_R = 1) :**

- Diagramme bilinéaire convergé (trait plein).
- Le point de performance coïncide avec `(S_de, a_y1)` puisque C_R = 1.

**Cas T₁ ≤ T_B — Şekil 5B.4 (C_R > 1, itération) :**

- **Bilinéaire initiale** (passe 0, C_R = 1) : tracée en tirets, représente l'état `Şekil 5B.4a`.
- **Bilinéaire convergée** (dernière passe) : tracée en trait plein, représente l'état `Şekil 5B.4b`.
- Les deux bilinéaires sont superposées sur le même graphe pour visualiser la convergence.
- Le point de performance est à l'abscisse `S_d1,max = C_R · S_de > S_de`.

**Propriétés du graphe :**

- Survol des coordonnées et zoom (Plotly interactif).
- Légende identifiant chaque courbe.
- Une couleur distincte par règle de bilinéarisation (sécante 0,6 vs tangente initiale).
- Axes : S_de en m (abscisse), S_ae en g (ordonnée).

### 4.2 Tableau récapitulatif

Une colonne par règle de bilinéarisation, avec les grandeurs suivantes dans l'ordre :

| Grandeur | Symbole | Unité |
|---|---|---|
| Période effective | T₁ | s |
| Pente initiale bilinéaire | ω₁² = (2π/T₁)² | rad²/s² |
| Période d'angle du spectre | T_B | s |
| Pente limite | ω_B² = (2π/T_B)² | rad²/s² |
| Cas applicable | T₁ > T_B ou T₁ ≤ T_B | — |
| Déplacement élastique spectral | S_de(T₁) | m |
| Pseudo-accélération élastique | S_ae(T₁) | g |
| Pseudo-accélération d'écoulement | a_y1 | g |
| Déplacement d'écoulement | d_y | m |
| Coefficient de réduction | R_y | — |
| Demande de ductilité | μ | — |
| Coefficient de modification | C_R | — |
| Déplacement spectral non-linéaire | S_d1,max | m |
| Déplacement cible au sommet | δ_cible | m |
| Nombre d'itérations | n_iter | — |

### 4.3 Détail itératif affiché — tableau de convergence (obligatoire)

L'application affiche un **tableau de convergence** déroulant chaque passe de la boucle itérative. Ce tableau est obligatoire pour permettre la vérification indépendante du calcul. Il contient une ligne par itération avec les colonnes suivantes :

| Colonne | Symbole | Unité | Description |
|---|---|---|---|
| Numéro de passe | n | — | 0 = initialisation |
| Cible de bilinéarisation | S_di_cible | mm | = C_R(n−1)·S_de à la passe n, = S_de à la passe 0 |
| Pseudo-accél. d'écoulement | aⁿ_y1 | g | Issue de la bilinéarisation à aires égales à la cible S_di_cible |
| Déplacement d'écoulement | dⁿ_y | mm | Abscisse du point de rupture de pente |
| Période effective | T₁ⁿ | s | 2π·√(dⁿ_y / aⁿ_y1·g) |
| Accél. spectrale élastique | S_ae(T₁ⁿ) | g | Interpolation linéaire sur le spectre |
| Coefficient de réduction | Rⁿ_y | — | S_ae(T₁ⁿ) / aⁿ_y1 |
| Demande de ductilité | μⁿ | — | Éq. 5B.16a ou 5B.16b selon le cas |
| Coefficient de modification | Cⁿ_R | — | Éq. 5B.17a ou 5B.17b |
| Variation C_R | ΔC_R | % | \|Cⁿ_R − Cⁿ⁻¹_R\| / Cⁿ_R |
| Convergence | — | — | ✅ si ΔC_R < 1 %, ⏳ sinon |

Ce tableau permet à l'ingénieur de vérifier la convergence passe par passe. Il est affiché sous le graphe ADRS, dans un expander Streamlit intitulé **"Détail des itérations"**.

> **Règle de cohérence** : si n_iter = 1, cela signifie que le critère de convergence est satisfait dès la passe 0 → cas T₁ > T_B uniquement (C_R = 1 par définition, pas d'itération). Si T₁ ≤ T_B et n_iter = 1, c'est un bug — la boucle ne s'est pas exécutée correctement.

### 4.4 Alertes réglementaires (TBDY art. 5B.3.6)

La méthode du déplacement spectral n'est pas valable dans deux cas, signalés par une alerte :

- **Faille proche** : distance à la faille < 15 km → analyse temporelle non-linéaire requise (art. 5B.4).
- **Pente post-écoulement négative** (effets P-Δ) → analyse temporelle non-linéaire requise.

---

## 5. Point d'attention (non bloquant)

L'affichage des deux règles de bilinéarisation peut donner deux points de performance sensiblement différents lorsque la transition élasto-plastique de la courbe est molle (cas fréquent en charpente métallique avec flambement progressif des diagonales). Ce n'est pas une anomalie mais la sensibilité réelle de la méthode au choix de bilinéarisation. L'application affiche cet écart honnêtement ; le choix de la règle retenue relève du jugement de l'ingénieur.

---

## 6. Stack technique

- **Streamlit** (interface) ;
- **numpy** (calcul) ;
- **plotly** (graphe interactif) ;
- **pandas** (lecture CSV, tableau).

Lancement : `streamlit run app.py`. Deux fichiers CSV d'exemple sont fournis pour test immédiat.

---

## 7. Conformité réglementaire

Toutes les équations et critères s'appuient exclusivement sur le **TBDY 2018**, Annexe 5B (Éq. 5B.3, 5B.4, 5B.12 à 5B.17) et art. 5B.3.6. Aucun critère de performance n'est emprunté à un autre référentiel.

**Corrections apportées à la v1 du CDC suite à l'audit de conformité :**

| # | Écart corrigé | Section modifiée |
|---|---|---|
| 15 | Déplacement cible de la bilinéarisation mis à jour à `C_R·S_de` à chaque passe (pas S_de fixe) — erreur de calcul directe | §3.3 |
| 13 | Droite élastique de pente `ω₁²` obligatoire, prolongée jusqu'à son intersection avec le spectre pour lire S_de | §4.1 |
| 14 | Deux états bilinéaires affichés dans le cas T₁ ≤ T_B (Şekil 5B.4a et 5B.4b) | §4.1 |
| 12 | Vérification de la condition normative sous forme `ω₁² ≤ ω_B²` en plus de `T₁ > T_B` | §3.3, §4.2 |
| 16 | Définition explicite de d_y (déplacement d'écoulement ≠ S_de) | §3.3 |
| 17 | Interpolation linéaire par morceaux de S_ae(T₁) spécifiée | §3.4 |
| 19 | Vérification d'unités S_ae / a_y1 (tous deux en g) explicite | §3.4 |
| 20 | Conversion T → S_de via Éq. 2.5 du TBDY explicite | §3.2 |
| 21 | Unité entrée δ : mm (pas m) + conversion mm→m immédiate en §3.1 | §2, §3.1 |
| 22 | Tableau de convergence itératif obligatoire (détail passe par passe) | §4.3 |
| 23 | Règle de cohérence n_iter=1 : valide seulement si T₁ > T_B | §4.3 |
