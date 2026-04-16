from dataclasses import dataclass
from typing import List

@dataclass
class Order:
    price: int
    qty: int
    time: int # 0: Existing Book, 1: You

def get_clearing_price(bids: List[Order], asks: List[Order]) -> int:
    all_prices = sorted(list(set([o.price for o in bids] + [o.price for o in asks])))
    best_vol = -1
    clearing_p = -1

    for p in all_prices:
        # Rule: Bids >= p, Asks <= p
        cum_demand = sum(o.qty for o in bids if o.price >= p)
        cum_supply = sum(o.qty for o in asks if o.price <= p)
        vol = min(cum_demand, cum_supply)

        if vol > best_vol:
            best_vol = vol
            clearing_p = p
        elif vol == best_vol and vol > 0:
            if p > clearing_p: # Rule: Higher price tie-break
                clearing_p = p
    return clearing_p

def simulate_my_pnl(my_price, my_qty, book_bids, book_asks, fv, fee):
    bids = [Order(p, q, 0) for p, q in book_bids] + [Order(my_price, my_qty, 1)]
    asks = [Order(p, q, 0) for p, q in book_asks]
    
    cp = get_clearing_price(bids, asks)
    
    if cp == -1 or my_price < cp:
        return 0.0, 0, cp

    # Total liquidity available at the clearing price
    total_supply_at_cp = sum(o.qty for o in asks if o.price <= cp)
    
    # CORRECT PRIORITY:
    # You only lose priority to:
    # 1. Higher prices than yours (Price Priority)
    # 2. Your price at Time 0 (Time Priority)
    # Note: You have priority OVER everyone at prices between CP and your price.
    priority_demand = sum(o.qty for o in bids if o.price > my_price) + \
                      sum(o.qty for o in bids if o.price == my_price and o.time == 0)

    my_fill = max(0, min(my_qty, total_supply_at_cp - priority_demand))
    
    # Standard PnL calculation
    pnl = my_fill * (fv - cp - fee)
    return float(pnl), my_fill, cp

def full_brute_force(book_bids, book_asks, fv, fee):
    best = {"pnl": -1.0}
    
    # Range of prices to test: 1 tick below lowest ask to 1 tick above highest bid
    prices_to_test = sorted(list(set([p for p, q in book_bids] + [p for p, q in book_asks])))
    
    print(f"Searching...")
    for p in prices_to_test:
        # Search every quantity from 1 to 100,000
        for q in range(1, 100001):
            pnl, fill, cp = simulate_my_pnl(p, q, book_bids, book_asks, fv, fee)
            
            if pnl > best["pnl"]:
                best = {
                    "pnl": round(pnl, 2),
                    "bid_p": p,
                    "bid_q": q,
                    "fill": fill,
                    "cp": cp
                }
    return best

# --- Data ---
flax_bids = [(30, 30000), (29, 5000), (28, 12000), (27, 28000)]
flax_asks = [(28, 40000), (31, 20000), (32, 20000), (33, 30000)]

mush_bids = [(20, 43000), (19, 17000), (18, 6000), (17, 5000), (16, 10000), (15, 5000), (14, 10000), (13, 7000)]
mush_asks = [(12, 20000), (13, 25000), (14, 35000), (15, 6000), (16, 5000), (18, 10000), (19, 12000)]

print("Flax Optimal Strategy:", full_brute_force(flax_bids, flax_asks, 30.0, 0.0))
print("Mushroom Optimal Strategy:", full_brute_force(mush_bids, mush_asks, 20.0, 0.1))