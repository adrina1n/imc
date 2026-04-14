# IMC Prosperity 4 — Tutorial Round : Évolution de la stratégie

**Round :** Tutorial (Round 0)
**Produits :** EMERALDS, TOMATOES
**Versions :** v1 → v2 → v3 → v4

---

## Vue d'ensemble

Le but du tutorial round est simple : faire du market making sur deux produits.
EMERALDS est stationnaire — son prix tourne autour de 10 000 en permanence.
TOMATOES est non-stationnaire — son prix dérive, monte, descend, sans revenir à une moyenne fixe.

La stratégie repose sur trois piliers qui restent les mêmes dans toutes les versions :

1. **Estimer un fair value** — le prix "juste" du produit à un instant donné
2. **Prendre** les ordres dans le book qui battent ce fair value (taking)
3. **Poster** des ordres autour de ce fair value pour capturer le spread (market making)

Ce qui change entre les versions, c'est la qualité de l'estimation du fair value et la gestion de l'inventaire.

---

## v1 — La base

### Ce qu'on fait

Pour EMERALDS : fair value constant à 10 000, penny jumping sur le meilleur bid/ask, et position-reducing à fair value.

Pour TOMATOES : on calcule le **Wall Mid** (mid entre le bid et l'ask avec le plus gros volume), puis on lui applique une **EMA** (alpha = 0.1) pour lisser.

### Pourquoi le Wall Mid plutôt que le BBO mid ?

Le BBO mid (meilleur bid + meilleur ask / 2) est bruité. Des bots placent des ordres petits et éphémères au meilleur prix — ils apparaissent dans le book pendant un timestamp, puis disparaissent. Si on prend le BBO mid comme fair value, on réagit à ces artefacts.

Le Wall Mid prend à la place le prix avec le **plus gros volume** de chaque côté. Ces ordres représentent de la vraie liquidité, pas du bruit. En pratique ça divise la volatilité de l'estimation par ~2 (σ passe de 1.34 à 0.67 sur les données du tutorial).

### Pourquoi l'EMA en v1 ?

L'idée initiale : puisque TOMATOES dérive, lisser le Wall Mid avec une EMA devrait donner une estimation plus stable. Alpha = 0.1 signifie que le prix d'il y a 10 timestamps compte encore pour 35% dans l'estimation.

Le problème — qu'on ne voit pas encore en v1 — c'est que cette mémoire crée du **lag**. Quand le prix monte, l'EMA est en dessous du prix réel. On sous-estime le fair value, donc on prend des positions short à contretemps.

---

## v2 — Supprimer l'EMA

### Ce qu'on voit dans le backtester (Jasper)

En regardant les trades dans Jasper, on voit que sur les tendances fortes, le bot prend des positions dans la mauvaise direction. Le Wall Mid monte, mais l'EMA est encore 5–10 ticks en dessous. Résultat : on take sell sur des bids qui sont en fait en dessous du vrai fair value, et on accumule des positions short en plein uptrend.

On calcule aussi le MAE (mean absolute error) entre l'EMA et le Wall Mid réel : l'EMA **double** le MAE par rapport à utiliser Wall Mid directement.

### Ce qu'on change

On supprime l'EMA. Le fair value de TOMATOES devient simplement le Wall Mid instantané, sans mémoire.

```python
# v1
self.tomato_ema = alpha * wall_mid + (1 - alpha) * self.tomato_ema
fair_value = self.tomato_ema

# v2
fair_value = self.get_wall_mid(state, product)  # direct, pas de lissage
```

C'est contre-intuitif : on ajoute du "bruit" en supprimant le lissage, mais en pratique le Wall Mid instantané est déjà peu bruité, et le lag de l'EMA coûte bien plus cher que ce bruit.

### Ce qu'on améliore aussi

La logique de position-reducing dans `search_buys` et `search_sells` utilisait `abs(ask - fair_value) < 1` pour détecter "je suis au fair value". Ça ne marche pas bien quand le fair value est un float — par exemple 5006.5. Est-ce que 5006 est "au fair value" ? Est-ce que 5007 l'est ?

En v2 on commence à réfléchir à utiliser `math.floor` et `math.ceil` pour gérer ça proprement. La correction complète arrive en v3.

---

## v3 — Corriger la logique floor/ceil

### Le problème qu'on voit

Avec un fair value float (ex. 5006.5), la condition `ask < fair_value` est vraie pour ask = 5006, mais fausse pour ask = 5007 — même si 5007 est encore "au fair value" dans le sens où il n'y a pas d'edge à prendre.

En v2, la condition de position-reducing `abs(ask - fair_value) < 1` couvrait ça approximativement, mais de façon fragile. Si fair_value = 5006.5 et ask = 5006, `abs(5006 - 5006.5) = 0.5 < 1` → on prend. Si ask = 5007, `abs(5007 - 5006.5) = 0.5 < 1` → on prend aussi. Mais la condition globale `ask < fair_value` est déjà vraie pour 5006, donc la branche position-reducing ne sert à rien pour ce cas.

La vraie question est : **à partir de quel prix est-ce qu'il y a un edge clair ?**

- Edge clair côté achat : `ask < floor(fair_value)` — le prix est strictement sous le fair value entier inférieur
- Zone floue (autour du fair value) : `floor(fair_value) <= ask <= ceil(fair_value)` — on prend seulement si ça réduit |position|
- Pas d'edge : `ask > ceil(fair_value)` — on ne prend pas

### Ce qu'on change dans search_buys / search_sells

```python
# v3 — search_buys
if ask < math.floor(fair_value):
    take = True                          # edge clair, toujours prendre
elif ask <= math.ceil(fair_value) and pos < 0:
    take = True                          # zone floue, prendre seulement si on réduit |pos|

# v3 — search_sells
if bid > math.ceil(fair_value):
    take = True                          # edge clair, toujours prendre
elif bid >= math.floor(fair_value) and pos > 0:
    take = True                          # zone floue, prendre seulement si on réduit |pos|
```

La même logique s'applique à la condition de position-reducing dans le market making :

```python
# Avant (v2) : condition fragile
if not (pos > 0 and buy_price == fair_value):

# v3 : condition propre avec floor/ceil
if not (pos > 0 and buy_price >= math.floor(fair_value)):
```

### Ce que ça change en pratique

On évite d'accumuler de l'inventaire dans la zone d'ambiguité autour du fair value. Avant, on pouvait poser des buy orders à `floor(fair_value)` même en étant déjà long — ce qui ne fait que grossir une position sans edge réel.

---

## v4 — Trend following avec MA fast/slow

### La question qu'on se pose

v3 fait du market making neutre : on poste de façon symétrique autour du fair value. Mais TOMATOES a des tendances. Quand le prix monte pendant 200 timestamps d'affilée, faire du MM symétrique signifie qu'on accumule du short à contretemps — on vend à chaque montée parce qu'on pense que le prix va revenir.

La question : est-ce qu'on peut détecter une tendance et **skewer** nos quotes en conséquence ?

### Le mécanisme

On maintient un historique du Wall Mid et on calcule deux moyennes mobiles simples :

- **MA_FAST** (fenêtre courte, défaut 50 timestamps) : capte les mouvements récents
- **MA_SLOW** (fenêtre longue, défaut 200 timestamps) : capte la tendance de fond

Si MA_FAST > MA_SLOW, le prix monte — on est en uptrend. Si MA_FAST < MA_SLOW, downtrend.

On normalise l'écart pour obtenir une `trend_strength` entre -1 et 1 :

```python
trend_strength = (ma_fast - ma_slow) / ma_slow
trend_clamped = max(-1.0, min(1.0, trend_strength * 200))
skew = trend_clamped * SKEW_MAX  # SKEW_MAX = 3 ticks par défaut
```

Le `* 200` amplifie un écart de 0.5% en un signal de force 1.0 — c'est un paramètre à calibrer.

### Ce que le skew fait concrètement

En uptrend (skew > 0), le fair value "perçu" monte de quelques ticks. Résultat :
- On take buy moins agressivement (il faut que l'ask soit encore plus bas que le fair value réel)
- On take sell plus agressivement (on vend dès que le bid est au-dessus du fair value skewé)
- Nos quotes MM sont décalées vers le haut — on se positionne du côté vendeur moins facilement

En downtrend, c'est le symétrique.

### La position limit dynamique

En tendance forte (`|trend_clamped| > 0.3`), on serre la position limit de `MAX_POS_NEUTRAL = 50` à `MAX_POS_TREND = 20`. L'idée : si on détecte un trend mais qu'on se trompe, mieux vaut limiter l'exposition.

```python
if abs(trend_clamped) > 0.3:
    dynamic_limit = MAX_POS_TREND   # 20
else:
    dynamic_limit = MAX_POS_NEUTRAL  # 50
```

### Les deux paramètres à calibrer

| Paramètre | Rôle | Défaut |
|-----------|------|--------|
| `MA_FAST` | Fenêtre courte — réactivité du signal | 50 |
| `MA_SLOW` | Fenêtre longue — tendance de fond | 200 |

Un MA_FAST trop petit → signal bruité, on change de direction à chaque micro-mouvement.
Un MA_SLOW trop grand → signal trop lent, on détecte la tendance après qu'elle soit finie.

Le bon ratio à chercher en backtest : que le signal détecte les tendances d'au moins 100 timestamps sans déclencher trop de faux positifs sur les consolidations latérales.

---

## Résumé des évolutions

| Version | Fair Value TOMATOES | Logique taking | Position reducing |
|---------|--------------------|-----------------|--------------------|
| v1 | Wall Mid + EMA (α=0.1) | `ask < fair_value` simple | `abs(ask - fv) < 1` fragile |
| v2 | Wall Mid direct | idem | idem, début réflexion floor/ceil |
| v3 | Wall Mid direct | `floor`/`ceil` propre | `floor`/`ceil` propre |
| v4 | Wall Mid + skew MA | `floor`/`ceil` sur fv skewé | limit dynamique selon trend |
