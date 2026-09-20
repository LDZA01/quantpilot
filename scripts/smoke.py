"""Read-only health checks, with optional explicitly requested live provider ingestion."""

import argparse
import json

import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--api", default="http://localhost:8000")
parser.add_argument("--live", action="store_true")
args = parser.parse_args()
with httpx.Client(base_url=args.api, timeout=300) as client:
    for path in ("/health", "/ready", "/assets", "/jobs"):
        response = client.get(path)
        response.raise_for_status()
        print(path, response.status_code)
    if args.live:
        for symbol in ("AAPL", "SPY"):
            response = client.post(
                "/ingest", json={"symbol": symbol, "start": "2023-01-01", "end": "2024-01-01"}
            )
            print("ingest", symbol, response.status_code, response.text)
            response.raise_for_status()
        scan = client.post("/scanner", json={"symbols": ["AAPL", "SPY"]})
        scan.raise_for_status()
        print("scanner candidates", len(scan.json()["results"]))
        response = client.post("/backtests", json={"symbol": "AAPL", "strategy": "sma_crossover"})
        response.raise_for_status()
        result = response.json()
        assert result["benchmark"] is not None
        replay = client.post(f"/runs/{result['id']}/reproduce")
        replay.raise_for_status()
        assert replay.json()["matches"]
        print(
            json.dumps(
                {
                    "run_id": result["id"],
                    "replay_matches": True,
                    "benchmark_present": True,
                    "metrics": result["metrics"],
                },
                indent=2,
            )
        )
