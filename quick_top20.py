"""Quick Top20: Use Data API to rank wallets by copy-trading potential.
No need for full on-chain backfill. Runs in ~30 seconds."""
import urllib.request, json, os, time
from collections import defaultdict

DATA_API = "https://data-api.polymarket.com"

# Known high-performing wallets from our research + candidate pool
KNOWN_WALLETS = [
    "0xe1D6b51521Bd4365769199f392F9818661BD907c",  # Bonereaper
    "0x06dc51826bc524d9a83770e7de9dd7e005b0452",  # XRPDips / xuanxuan008
    "0x15ceffed7bf820cd2d90f90ea24ae9909f5cd5fa",  # HondaCivic
    "0x57ee70867b4e387de9de34fd62bc685aa02a8112",  # ikik111
    "0x1838cca016850ac7185a9b149fe7d0bd2d6629b4",  # JoeMeteorolog
    "0x331bf91c132af9d921e1908ca0979363fc47193f",  # BeefSlayer
    "0xd75d96a23515172778d3281f53c9180b985100c8",  # Varyage
    "0x1f66796b45581868376365aef54b51eb84184c8d",  # Maskache2
    "0x63d43bbb87f85af03b8f2f9e2fad7b54334fa2f",  # wokerjoesleeper
    "0x38e59b36aae31b164200d0cad7c3fe5e0ee795e7",  # cowcat
    "0x07921379f7b31ef93da634b688b2fe36897db778",  # ewelmealt
    "0x8c0b024c17831a0dde038547b7e791ae6a0d7aa5",  # EFFICIENCYEXPERT
    "0x40471b34671887546013ceb58740625c2efe7293",  # Frank0951
    "0xbacd00c9080a82ded56f504ee8810af732b0ab35",  # ScottyNooo
    "0x2110ba2a1e18840109482ff4ddc547baeff45850",  # GeorgeSmiley
    "0xd5b97d08ec6098407bfbf66c2786ccc9967fe44e",  # Optimus
    "0x41816fc1ebdfeb33f6356f2655ab499253b3de86",  # BobInvestments
    "0x5ecde7348ea5100af4360dd7a6e0a3fb1d420787",  # Mujurry
    "0x92672c80d36dcd08172aa1e51dface0f20b70f9a",  # CKW
    "0x8e0b7ae246205b1ddf79172148a58a3204139e5c",  # synnet
    "0x6c743aafd813475986dcd930f380a1f50901bd4e",  # middleoftheocean
    "0x06dcaa14f57d8a0573f5dc5940565e6de667af59",  # BigChungus
    "0xdf6da574f8b0c0ce5e01ddb1c5a49b87993e9c5c",  # TheRedChip
    "0x668d85d791049bf0100e557a72c7ed4dc97297d2",  # BeN
    "0x36e7e560c4d4cf32926906d939a18cf91f8a0b6b",  # pol76
]

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def main():
    print("Quick Top20 Generator (Data API)")
    print(f"Analyzing {len(KNOWN_WALLETS)} wallets...")
    scores = []

    for i, addr in enumerate(KNOWN_WALLETS):
        try:
            trades = fetch(f"{DATA_API}/trades?user={addr}&limit=50")
            if not trades:
                scores.append({"addr": addr, "trades": 0, "score": 0})
                continue

            # Compute wallet metrics
            n = len(trades)
            buy_count = sum(1 for t in trades if t.get('side') == 'BUY')
            unique_markets = len(set(t.get('conditionId', '') for t in trades))
            total_vol = sum(float(t.get('size', 0)) * float(t.get('price', 0.5)) for t in trades)

            # Copy score: favors moderate frequency, diverse markets, decent volume
            freq_score = min(n, 50) / 50 * 30       # up to 30 points for trade count
            div_score = min(unique_markets, 20) / 20 * 25  # up to 25 for diversity
            vol_score = min(total_vol / 5000, 1) * 25       # up to 25 for volume
            buy_pct = buy_count / n if n > 0 else 0
            # Penalize extreme buying (market makers/scalpers)
            balance_penalty = 1.0 - abs(buy_pct - 0.5) * 0.5
            score = round((freq_score + div_score + vol_score) * balance_penalty, 1)

            scores.append({
                "addr": addr,
                "trades": n,
                "volume": round(total_vol, 1),
                "markets": unique_markets,
                "buy_pct": round(buy_pct, 2),
                "score": score,
            })
            print(f"  [{i+1:02d}/{len(KNOWN_WALLETS)}] {addr[:10]}... {n} trades, {unique_markets} markets, score={score}")

        except Exception as e:
            scores.append({"addr": addr, "trades": 0, "score": 0})
            print(f"  [{i+1:02d}/{len(KNOWN_WALLETS)}] {addr[:10]}... ERROR: {e}")
        time.sleep(0.3)  # rate limit

    # Sort by score desc, take top 20
    scores.sort(key=lambda x: x['score'], reverse=True)
    top20 = scores[:20]

    # Assign names
    WALLET_NAMES = {
        "0xe1D6b51521Bd4365769199f392F9818661BD907c": "Bonereaper",
        "0x06dc51826bc524d9a83770e7de9dd7e005b0452": "XRPDips",
        "0x15ceffed7bf820cd2d90f90ea24ae9909f5cd5fa": "HondaCivic",
        "0x57ee70867b4e387de9de34fd62bc685aa02a8112": "ikik111",
        "0x1838cca016850ac7185a9b149fe7d0bd2d6629b4": "JoeMeteorolog",
        "0x331bf91c132af9d921e1908ca0979363fc47193f": "BeefSlayer",
        "0xd75d96a23515172778d3281f53c9180b985100c8": "Varyage",
        "0x1f66796b45581868376365aef54b51eb84184c8d": "Maskache2",
        "0x63d43bbb87f85af03b8f2f9e2fad7b54334fa2f": "wokerjoesleeper",
        "0x38e59b36aae31b164200d0cad7c3fe5e0ee795e7": "cowcat",
        "0x07921379f7b31ef93da634b688b2fe36897db778": "ewelmealt",
        "0x8c0b024c17831a0dde038547b7e791ae6a0d7aa5": "EFFICIENCYEXPERT",
        "0x40471b34671887546013ceb58740625c2efe7293": "Frank0951",
        "0xbacd00c9080a82ded56f504ee8810af732b0ab35": "ScottyNooo",
        "0x2110ba2a1e18840109482ff4ddc547baeff45850": "GeorgeSmiley",
        "0xd5b97d08ec6098407bfbf66c2786ccc9967fe44e": "Optimus",
        "0x41816fc1ebdfeb33f6356f2655ab499253b3de86": "BobInvestments",
        "0x5ecde7348ea5100af4360dd7a6e0a3fb1d420787": "Mujurry",
        "0x92672c80d36dcd08172aa1e51dface0f20b70f9a": "CKW",
        "0x8e0b7ae246205b1ddf79172148a58a3204139e5c": "synnet",
        "0x6c743aafd813475986dcd930f380a1f50901bd4e": "middleoftheocean",
        "0x06dcaa14f57d8a0573f5dc5940565e6de667af59": "BigChungus",
        "0xdf6da574f8b0c0ce5e01ddb1c5a49b87993e9c5c": "TheRedChip",
        "0x668d85d791049bf0100e557a72c7ed4dc97297d2": "BeN",
        "0x36e7e560c4d4cf32926906d939a18cf91f8a0b6b": "pol76",
    }

    # Output
    top_list = []
    print(f"\n{'='*70}")
    print(f"  Top 20 Wallets by Copy-Trading Score")
    print(f"{'='*70}")
    print(f"  {'Rank':<5} {'Name':<20} {'Trades':<8} {'Markets':<8} {'Volume':<12} {'Score':<8}")
    print(f"  {'-'*5} {'-'*20} {'-'*8} {'-'*8} {'-'*12} {'-'*8}")

    for i, w in enumerate(top20):
        name = WALLET_NAMES.get(w['addr'], f"Unknown_{w['addr'][:6]}")
        vol_str = f"${w['volume']:,.0f}" if w['volume'] > 0 else "$0"
        print(f"  {i+1:<5} {name:<20} {w['trades']:<8} {w['markets']:<8} {vol_str:<12} {w['score']:<8.1f}")

        top_list.append({
            "addr": w['addr'],
            "name": name,
            "cat": "DataAPI",
            "total_trades": w['trades'],
            "total_volume": w['volume'],
            "markets_traded": w['markets'],
            "copy_score": w['score'],
        })

    # Save for dashboard
    out_dir = "G:/trade/poly_data/processed"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "wallets_top20.json")
    with open(out_path, 'w') as f:
        json.dump(top_list, f, indent=2)
    print(f"\n  Saved: {out_path}")
    print(f"  Dashboard tab: http://localhost:8766/copy_dashboard.html → 📦 PolyData Top20")
    return top_list

if __name__ == '__main__':
    main()
