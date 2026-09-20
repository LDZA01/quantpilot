import argparse
import json

import httpx


def main():
    parser = argparse.ArgumentParser(description="QuantPilot local research CLI")
    parser.add_argument("command", choices=["ingest", "scan", "backtest"])
    parser.add_argument("symbols", nargs="+")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--strategy", default="sma_crossover")
    args = parser.parse_args()
    with httpx.Client(base_url=args.api, timeout=300) as client:
        if args.command == "ingest":
            responses = [
                client.post("/ingest", json={"symbol": s.upper(), "start": args.start})
                for s in args.symbols
            ]
        elif args.command == "scan":
            responses = [
                client.post("/scanner", json={"symbols": [s.upper() for s in args.symbols]})
            ]
        else:
            responses = [
                client.post(
                    "/backtests",
                    json={
                        "symbol": args.symbols[0].upper(),
                        "strategy": args.strategy,
                        "start": args.start,
                    },
                )
            ]
        for response in responses:
            print(json.dumps(response.json(), indent=2))
            response.raise_for_status()


if __name__ == "__main__":
    main()
