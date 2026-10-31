import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from typing import Optional

import yfinance as yf

# Symbols come from the hco-symbols registry (every non-ETF symbol: ETFs have no analyst
# coverage). Order: SYMBOLS env override -> live registry -> last good copy -> abort.
REGISTRY_URL = os.getenv("SYMBOLS_URL", "https://javed-glitch.github.io/hco-symbols/symbols.json")
CACHE_PATH = os.getenv("SYMBOLS_CACHE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "symbols_last_good.json"))


def registry_symbols(reg):
    out = []
    for e in reg["symbols"]:
        sym = str(e.get("sym", "")).strip().upper()
        if sym and not e.get("etf") and re.fullmatch(r"[A-Z0-9.\-]{1,10}", sym) and sym not in out:
            out.append(sym)
    return out if 0 < len(out) <= 60 else None


def load_symbols():
    explicit = [s.strip().upper() for s in os.getenv("SYMBOLS", "").split(",") if s.strip()]
    if explicit:
        print(f"symbols: SYMBOLS env ({len(explicit)})")
        return explicit
    def live():
        req = urllib.request.Request(REGISTRY_URL, headers={"Cache-Control": "no-cache"})
        return json.load(urllib.request.urlopen(req, timeout=15))
    def cached():
        return json.load(open(CACHE_PATH))
    for name, get in (("registry", live), ("last good copy", cached)):
        try:
            reg = get()
            syms = registry_symbols(reg)
            if not syms:
                raise ValueError("no usable symbols")
            if name == "registry":
                try:
                    new = json.dumps(reg, indent=1, sort_keys=True) + "\n"
                    if not os.path.exists(CACHE_PATH) or open(CACHE_PATH).read() != new:
                        open(CACHE_PATH, "w").write(new)
                except Exception as ex:
                    print(f"symbols: could not save last good copy ({ex!r})")
            print(f"symbols: {name} ({len(syms)}): {','.join(syms)}")
            return syms
        except Exception as ex:
            print(f"symbols: {name} unusable ({ex!r})")
    raise RuntimeError("no symbol source available")


SYMBOLS = load_symbols()

OUT_PATH = "targets.json"


def fetch_one(symbol: str) -> Optional[dict]:
    info = yf.Ticker(symbol).info
    target = info.get("targetMeanPrice")
    if target is None:
        return None
    return {
        "target": round(float(target), 2),
        "high": round(float(info["targetHighPrice"]), 2) if info.get("targetHighPrice") is not None else None,
        "low": round(float(info["targetLowPrice"]), 2) if info.get("targetLowPrice") is not None else None,
        "numAnalysts": info.get("numberOfAnalystOpinions"),
    }


def main():
    results = {}
    failures = []

    for symbol in SYMBOLS:
        try:
            data = fetch_one(symbol)
            if data is None:
                failures.append(f"{symbol}: no targetMeanPrice in response")
                continue
            results[symbol] = data
            print(f"{symbol}: target={data['target']} range=[{data['low']}-{data['high']}] analysts={data['numAnalysts']}")
        except Exception as e:
            failures.append(f"{symbol}: {repr(e)}")

    if not results:
        print("No symbols fetched successfully — not overwriting targets.json", file=sys.stderr)
        for f in failures:
            print(f"  FAILED {f}", file=sys.stderr)
        sys.exit(1)

    payload = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "targets": results,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"\nWrote {len(results)}/{len(SYMBOLS)} symbols to {OUT_PATH}")
    if failures:
        print(f"{len(failures)} failure(s):")
        for f in failures:
            print(f"  {f}")


if __name__ == "__main__":
    main()
