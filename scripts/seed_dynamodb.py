"""Seed the debrief-scenarios DynamoDB table from data/scenarios/.

SCAFFOLD — safe by default. Without --execute this is a dry run: it validates
every scenario file and prints what WOULD be written, touching nothing and
needing no AWS credentials or boto3. Deployment (and therefore executing this
for real) is gated on the user's explicit greenlight.

    python3 scripts/seed_dynamodb.py                # dry run (default)
    python3 scripts/seed_dynamodb.py --execute      # real writes; needs AWS creds

DynamoDB rejects Python floats, so scenario JSON is parsed with Decimal floats
before writing — the read path (json.dumps with a Decimal-aware default) is the
responsibility of the Lambda-side loaders when they swap to DynamoDB.
"""

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_DIR = ROOT / "data" / "scenarios"

REQUIRED_KEYS = ("scenario_id", "domain", "title", "presented_to_user",
                 "ground_truth", "verified_data_points")


def load_scenarios():
    """Yield (path, scenario) for every valid scenario file; report the rest."""
    valid, invalid = [], []
    for path in sorted(SCENARIOS_DIR.glob("*.json")):
        try:
            scenario = json.loads(path.read_text(), parse_float=Decimal)
        except json.JSONDecodeError as e:
            invalid.append((path.name, f"invalid JSON: {e}"))
            continue
        missing = [k for k in REQUIRED_KEYS if k not in scenario]
        if missing:
            invalid.append((path.name, f"missing keys: {', '.join(missing)}"))
            continue
        valid.append((path, scenario))
    return valid, invalid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true",
                        help="actually write to DynamoDB (default: dry run)")
    parser.add_argument("--table", default="debrief-scenarios",
                        help="target table name (default: debrief-scenarios)")
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()

    valid, invalid = load_scenarios()
    for name, reason in invalid:
        print(f"SKIP  {name}: {reason}")
    for path, scenario in valid:
        mock_flag = " [MOCK fixture]" if "MOCK" in (scenario.get("source", {}).get("note") or "") else ""
        print(f"{'PUT ' if args.execute else 'DRY '} {scenario['scenario_id']:<40} "
              f"domain={scenario['domain']:<9}{mock_flag}")

    if not args.execute:
        print(f"\nDry run: {len(valid)} scenario(s) would be written to '{args.table}'. "
              "Re-run with --execute to write (needs AWS credentials; deployment is "
              "gated on the project owner's explicit greenlight).")
        return 0

    import boto3  # lazy: dry run needs no AWS SDK
    table = boto3.resource("dynamodb", region_name=args.region).Table(args.table)
    for _, scenario in valid:
        table.put_item(Item=scenario)
    print(f"\nWrote {len(valid)} scenario(s) to '{args.table}' in {args.region}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
