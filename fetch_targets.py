import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional

import yfinance as yf

# Full watchlist — kept in sync manually with Netlify's STOCKS list (excluding
# VUSA, which has no analyst coverage as an index tracker and is handled via
# manual entry only on the Netlify side). Override via SYMBOLS env var.
DEFAULT_SYMBOLS = (
    "TSLA,PLTR,NVDA,CEG,CRWV,NBIS,ZETA,BE,TER,CRWD,DDOG,MRVL,ANET,CDNS,TSM,ASML,AMAT,ZS"
)
SYMBOLS = [s.strip().upper() for s in os.getenv("SYMBOLS", DEFAULT_SYMBOLS).split(",") if s.strip()]

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
