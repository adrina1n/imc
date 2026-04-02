# IMC Prosperity 4 — Round 0 : Post-mortem & Documentation Technique

**Produits :** EMERALDS, TOMATOES  
**Versions du trader :** v1 → v6  
**Objectif de ce document :** retracer les problèmes rencontrés, les hypothèses testées, et les solutions retenues — pour que l'équipe puisse s'en servir comme référence aux rounds suivants.

---

## 1. Architecture de base (traderv1)

### Principes fondateurs

Avant d'écrire une seule ligne de code, on a analysé les CSV de prix (`prices_round_0_day_-1.csv`, `prices_round_0_day_-2.csv`) pour comprendre le comportement des deux produits.

Deux constats immédiats :

- **EMERALDS** est un produit **stationnaire** : le prix gravite autour de 10 000 avec un range très étroit. Fair value constante, MM pur.
- **TOMATOES** est un produit **non-stationnaire** : le prix dérive sur plusieurs centaines de ticks, avec des trends clairs à la hausse ou à la baisse.

### Structure générique du trader

Tous les traders du repo partagent la même architecture :

```
run()
 ├── reset_orders()          — réinitialise les compteurs d'ordres à chaque tick
 ├── trade_emeralds()
 └── trade_tomatoes()
        ├── calcul fair value
        ├── search_buys/sells()   — taking si edge clair
        └── MM avec penny jumping
```

**Helpers clés :**
- `get_wall_mid()` — fair value robuste (voir section 2)
- `get_max_buy/sell()` — respecte les position limits en tenant compte des ordres déjà envoyés ce tick
- `search_buys/sells()` — prend la liquidité disponible si le prix offre un edge par rapport à la fair value
- `get_best_bid/ask()` — trouve le meilleur prix concurrent pour le penny jumping

### Position-reducing à fair value

Inspiré de la stratégie CMU Physics (7e mondial Prosperity 3). La règle :

> Ne pas poster un ordre qui aggraverait la position **sans edge**.

```python
# N'achète pas plus si déjà long ET prix >= fair value
if not (pos > 0 and buy_price >= fair_value):
    send_buy_order(...)

# Ne vend pas plus si déjà short ET prix <= fair value
if not (pos < 0 and sell_price <= fair_value):
    send_sell_order(...)
```

Coût : 0. Bénéfice : évite d'accumuler du risque inutile.

---

## 2. Problème 1 — Fair Value de TOMATOES (v1 → v2)

### Symptôme

En utilisant le **BBO mid** (`(best_bid + best_ask) / 2`) comme fair value pour TOMATOES, l'algo postait des ordres de MM mal positionnés. Les prises de position étaient souvent dans le mauvais sens.

### Diagnostic

En analysant le book de TOMATOES tick par tick, on a observé que le niveau 1 (best bid/ask) est souvent occupé par des **ordres éphémères** de petite taille qui disparaissent dans le tick suivant. Ces ordres créent une forte variance dans le BBO mid, sans représenter la vraie liquidité du marché.

**Mesure empirique :** σ(BBO mid) ≈ 1.34, σ(Wall Mid) ≈ 0.67 — réduction de bruit de ~50%.

### Solution : Wall Mid

Au lieu de prendre le meilleur prix, on prend le **prix avec le plus gros volume** de chaque côté :

```python
# Wall Bid = prix du bid avec le plus gros volume
best_wall_bid = max(order_depth.buy_orders, key=lambda p: order_depth.buy_orders[p])

# Wall Ask = prix du ask avec le plus gros volume
best_wall_ask = max(order_depth.sell_orders, key=lambda p: abs(order_depth.sell_orders[p]))

wall_mid = (best_wall_bid + best_wall_ask) / 2
```

Ce "mur" de liquidité correspond typiquement au niveau 2 du book (bid_price_2 / ask_price_2), plus stable que le niveau 1.

### EMA — testée puis abandonnée

**v1** appliquait une EMA(α=0.1) sur le wall_mid :

```python
self.tomato_ema = alpha * wall_mid + (1 - alpha) * self.tomato_ema
fair_value = self.tomato_ema
```

**Problème identifié :** l'EMA introduit un **lag** — le fair value reste au-dessus du prix réel en downtrend, ce qui pousse les ordres buy trop haut et les ordres sell trop tard. Résultat : accumulation de positions longues perdantes.

**Décision (v2) :** suppression de l'EMA. `fair_value = wall_mid` directement.

---

## 3. Problème 2 — Accumulation en downtrend (v3 → v6)

### Symptôme

Même avec le Wall Mid comme fair value, le PnL de TOMATOES se dégrade significativement pendant les phases de downtrend prolongé (visible sur les backtests Jasper). L'algo accumule du long pendant que le prix continue de baisser.

### Analyse du problème

Le MM symétrique (`fair ± spread`) est structurellement défavorable en tendance :
- On capture le spread (~4-6 ticks) sur chaque trade
- Mais on perd bien plus à chaque tick de mouvement adverse (~10-20 ticks par tick de trend)

La cause : le MM achète autant qu'il vend, mais en downtrend les bids se remplissent plus souvent que les asks → accumulation nette de long.

### Visualisation du trend

On a construit `dataviz_with_MA.ipynb` pour superposer MA_fast et MA_slow sur le mid_price et wall_mid des deux jours concaténés :

```python
FAST = 50    # à ajuster
SLOW = 200   # à ajuster
tom['MA_fast'] = tom['wall_mid'].rolling(window=FAST).mean()
tom['MA_slow'] = tom['wall_mid'].rolling(window=SLOW).mean()
```

Ce graph permet de calibrer visuellement les fenêtres et de voir à quel moment le signal trend bascule.

### Solution v4 — Skew + Position limit dynamique

**Calcul du trend :**

```python
trend_strength = (ma_fast - ma_slow) / ma_slow  # relatif, scale-invariant
trend_clamped  = max(-1.0, min(1.0, trend_strength * 200))  # normalisé dans [-1, 1]
```

**Deux effets selon `|trend_clamped|` :**

| `\|trend_clamped\|` | Effet |
|---|---|
| < 0.3 | MM normal, position limit = 50 |
| ≥ 0.3 | position limit réduite à 20 + fair_value décalée |

**Décalage de fair value :**
```python
skew = trend_clamped * SKEW_MAX   # ex: SKEW_MAX=3 → max ±3 ticks
fair_value_skewed = fair_value + skew
```

En downtrend, `fair_value_skewed` est plus basse → les bids sont postés plus bas, les asks plus bas → on capture moins mais on accumule moins.

### Solution v6 — 3 régimes avec momentum pur

v4 restait du MM des deux côtés même en trend fort. v6 introduit un 3e régime :

| Régime | `\|trend_clamped\|` | Comportement | Position limit |
|---|---|---|---|
| FLAT | < 0.3 | MM normal | 50 |
| MODERATE | 0.3 – 0.7 | MM + fair_value décalée | 25 |
| STRONG | > 0.7 | Momentum pur, buy side coupé | 10 |

**En régime STRONG downtrend :**
1. On liquide d'abord toute position longue existante à market
2. On ne pose qu'un sell side (pas de bid)
3. La position limit tombe à 10 pour limiter l'exposition

```python
if regime == "STRONG" and trend_clamped < 0:
    # liquider le long existant
    if pos > 0:
        sell_at_market(state)
    # MM asymétrique : sell only
    send_sell_order(sell_price, max_sell)
    # pas de buy order
    return
```

**Paramètre clé : `TREND_SCALE`**

Remplace le multiplicateur hardcodé `200` de v4. Se calibre ainsi :
1. Loguer `trend_strength_raw` en Jasper pendant le backtest
2. Lire la valeur au pic du downtrend
3. `TREND_SCALE = 0.7 / valeur_observée` pour que le seuil STRONG soit atteint au bon moment

---

## 4. Analyse insider trading

### Objectif

Vérifier si certains bots du marché ont de l'information avancée sur les mouvements de TOMATOES, et si on peut en tirer un signal.

### Méthode

**`trader_spy.py`** — trader léger qui loggue tous les `market_trades` TOMATOES sans trader :

```python
for trade in state.market_trades.get("TOMATOES", []):
    logger.print(f"SPY;{state.timestamp};{trade.buyer};{trade.seller};{trade.price};{trade.quantity};{trade.timestamp}")
```

**`insider_analysis.ipynb`** — parse le `.log` Jasper et calcule pour chaque trade :
- `price_move` : mouvement du mid_price dans les `FORWARD_WINDOW` ticks suivants
- `signed_move` : positif si le bot avait raison (acheteur avant hausse, vendeur avant baisse)
- Corrélation entre agressivité du trade (prix > mid) et direction future

### Résultats sur Round 0

- **Pente de régression = 0.012** → quasi nulle, pas de corrélation
- **Distribution de price_move** centrée sur ~0 (mean = -0.20)
- **Conclusion : pas d'insider info détectable** sur TOMATOES au round 0

Les buyer/seller sont vides dans les logs du round tutorial. Aux rounds suivants (Olivia, Pablo, Caesar, etc.), relancer l'analyse avec identification par bot.

---

## 5. Fichiers du repo

| Fichier | Description |
|---|---|
| `traderv1.py` | Base : Wall Mid + EMA, MM symétrique |
| `traderv2.py` | Suppression EMA, Wall Mid pur |
| `traderv3.py` | Taking amélioré (floor/ceil autour de fair value) |
| `traderv4.py` | + Trend detection, skew de fair value, position limit dynamique |
| `traderv5.py` | Renommage propre des hyperparams (TREND_SCALE, FV_SHIFT_MAX) |
| `traderv6.py` | + Régime STRONG : momentum pur, buy side coupé |
| `trader_spy.py` | Logger market trades pour analyse insider |
| `dataviz_with_MA.ipynb` | Visualisation MA_fast/slow superposées sur TOMATOES |
| `insider_analysis.ipynb` | Analyse corrélation trades → prix futur |

---

## 6. Hyperparams et comment les tuner

### TOMATOES

```python
MA_FAST = 50        # fenêtre MA rapide — réduire si le trend change vite
MA_SLOW = 200       # fenêtre MA lente — doit couvrir la durée typique d'un trend

TREND_SCALE = 500   # amplifie trend_strength_raw dans [-1, 1]
                    # calibrage : logguer trend_raw au pic du downtrend
                    # puis TREND_SCALE = 0.7 / valeur_observée

FV_SHIFT_MAX = 5    # décalage max de fair_value en ticks (régimes FLAT/MODERATE)

THRESHOLD_MODERATE = 0.3   # seuil d'entrée en régime modéré
THRESHOLD_STRONG   = 0.7   # seuil d'entrée en momentum pur

MAX_POS_NEUTRAL  = 50
MAX_POS_MODERATE = 25
MAX_POS_STRONG   = 10
```

### Procédure de calibrage recommandée

1. Lancer `traderv6.py` avec les logs activés (`--vis`)
2. Repérer dans Jasper le timestamp du downtrend le plus prononcé
3. Lire `trend_raw` à ce moment → ajuster `TREND_SCALE`
4. Vérifier que `regime=STRONG` est atteint pendant le downtrend
5. Jouer sur `FV_SHIFT_MAX` et `MAX_POS_*` en dernier

---

## 7. Leçons clés pour les rounds suivants

- **Wall Mid > BBO Mid** pour tout produit non-stationnaire — à brancher par défaut sur KELP, SQUID_INK, etc.
- **Logger discipline** : `self.logs = ""` doit être réinitialisé après chaque flush (risque connu, a coûté 150+ places à CMU au round 3 de Prosperity 3)
- **`datamodel.py`** : toujours prendre depuis `prosperity4btx`, pas le repo CMU Prosperity 3 (incompatible)
- **L'analyse insider** est à relancer dès le round 1 — les noms des bots seront visibles et le signal sera bien plus exploitable
- **La logique 3 régimes** de v6 est générique — réutilisable sur n'importe quel produit non-stationnaire
- **Tester les hyperparams sur les données du round précédent** avant de soumettre — le backtester `prosperity4btx trader.py N` est fiable
