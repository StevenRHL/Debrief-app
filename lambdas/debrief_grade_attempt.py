"""debrief-grade-attempt — grades a user's explanation for a scenario.

SCAFFOLD / NOT DEPLOYED. Wraps the shared grading core: length guard (enforced
here, the trust boundary), grade (real or mock), score clamping, then a stubbed
store into `debrief-attempts`.

Mode selection:
  - MOCK_MODE=true (env)  -> shared.synthesize_mock_verdict, no API call, no key.
  - otherwise             -> real Anthropic call; needs ANTHROPIC_API_KEY.
Flip MOCK_MODE to false and provide the key to go live; nothing else changes.
"""

import json
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # make `shared` importable

from shared.grading import grade_attempt  # noqa: E402
from shared.auth import user_from_event  # noqa: E402
from shared.mock_mode import mock_mode  # noqa: E402

PROJECT_ROOT = Path(os.environ.get("DEBRIEF_DATA_ROOT", Path(__file__).resolve().parents[1]))
DEFAULT_SCENARIO_ID = "monza-2024-leclerc-onestop"

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


def _load_scenario(scenario_id: str) -> dict:
    path = PROJECT_ROOT / "data" / "scenarios" / f"{scenario_id}.json"
    if not path.exists():
        raise FileNotFoundError(scenario_id)
    return json.loads(path.read_text())


# One system prompt per domain; the output schema (and everything downstream of
# it) is shared, which is what lets grade_attempt() serve all three modes.
DOMAIN_SYSTEM_PROMPTS = {
    "f1": "grading-system-prompt.txt",
    "valorant": "valorant-grading-system-prompt.txt",
    "cs2": "cs2-grading-system-prompt.txt",
}


def _load_prompt_artifacts(domain: str = "f1"):
    prompt_file = DOMAIN_SYSTEM_PROMPTS.get(domain, DOMAIN_SYSTEM_PROMPTS["f1"])
    system_prompt = (PROJECT_ROOT / "prompts" / prompt_file).read_text()
    output_schema = json.loads((PROJECT_ROOT / "prompts" / "grading-output-schema.json").read_text())
    return system_prompt, output_schema


LOCAL_ATTEMPTS_FILE = PROJECT_ROOT / "results" / "attempts-local.jsonl"


def _attempt_record(user: dict | None, scenario: dict, attempt_text: str,
                    verdict: dict, meta: dict) -> dict:
    """The stored shape, identical across local JSONL and DynamoDB: the full
    clamped verdict (never scratch/thinking tokens) plus attribution, so the
    progress view can query which rubric dimension a user keeps losing on."""
    return {
        "attempt_id": str(uuid.uuid4()),
        "user_id": (user or {}).get("user_id", "anonymous"),
        "username": (user or {}).get("username", "anonymous"),
        "scenario_id": scenario["scenario_id"],
        "domain": scenario.get("domain", "f1"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": meta.get("mode"),
        "attempt_text": attempt_text,
        "verdict": verdict,
    }


def _store_attempt(user: dict | None, scenario: dict, attempt_text: str,
                   verdict: dict, meta: dict) -> None:
    """Persist the graded attempt. Mock/local mode appends to a JSONL file under
    results/ (gitignored); real mode put_items into the debrief-attempts table.
    Storage failures never fail the grading response — the verdict the user is
    waiting on outranks the write."""
    record = _attempt_record(user, scenario, attempt_text, verdict, meta)
    try:
        if mock_mode(scenario.get("domain", "f1")):
            LOCAL_ATTEMPTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with LOCAL_ATTEMPTS_FILE.open("a") as f:
                f.write(json.dumps(record) + "\n")
        else:
            import boto3  # lazy: mock mode stays stdlib-only
            table_name = os.environ.get("DYNAMODB_TABLE_PREFIX", "debrief-") + "attempts"
            table = boto3.resource(
                "dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1")
            ).Table(table_name)
            # DynamoDB rejects float; verdict scores are ints so a JSON round-trip
            # with string fallback is unnecessary — store the record as-is.
            table.put_item(Item=record)
    except Exception as e:  # noqa: BLE001 — deliberate: storage is best-effort
        print(f"[debrief-grade-attempt] attempt store failed (non-fatal): {e}")


def _response(status: int, body: dict) -> dict:
    return {"statusCode": status, "headers": CORS_HEADERS, "body": json.dumps(body)}


def handler(event, context=None):
    """API Gateway proxy handler. POST body: {scenario_id?, attempt_text}."""
    try:
        body = event.get("body") or "{}"
        if isinstance(body, str):
            body = json.loads(body)
    except json.JSONDecodeError:
        return _response(400, {"error": "invalid JSON body"})

    attempt_text = (body.get("attempt_text") or "").strip()
    scenario_id = body.get("scenario_id") or DEFAULT_SCENARIO_ID
    if not attempt_text:
        return _response(400, {"error": "attempt_text is required"})

    try:
        scenario = _load_scenario(scenario_id)
    except FileNotFoundError:
        return _response(404, {"error": f"scenario '{scenario_id}' not found"})

    mock = mock_mode(scenario.get("domain", "f1"))
    if mock:
        result = grade_attempt(scenario=scenario, attempt_text=attempt_text, mock=True)
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return _response(500, {"error": "ANTHROPIC_API_KEY not set and this domain is live (MOCK_MODE off)"})
        system_prompt, output_schema = _load_prompt_artifacts(scenario.get("domain", "f1"))
        result = grade_attempt(
            scenario=scenario,
            attempt_text=attempt_text,
            system_prompt=system_prompt,
            output_schema=output_schema,
            mock=False,
            api_key=api_key,
        )

    # Length guard rejection -> 400, with the same message the client shows.
    if "rejected_by_guard" in result:
        return _response(400, {"error": result["rejected_by_guard"], "guard": True})
    if "error" in result:
        return _response(502, {"error": f"grader {result['error']}"})

    verdict = result["graded"]  # already clamped to schema bounds
    _store_attempt(user_from_event(event), scenario, attempt_text, verdict, result)

    return _response(200, {
        "scenario_id": scenario_id,
        "mode": result["mode"],
        "verdict": verdict,
        "clamp_adjustments": result.get("clamp_adjustments", []),
    })


if __name__ == "__main__":
    os.environ.setdefault("MOCK_MODE", "true")
    sample = "Stay out and commit to the one-stop. A stop costs ~24s and over 20 laps the two-stop car needs ~1.2 s/lap on fresh hards to break even, which the low observed degradation says it won't get. Track position plus clean air wins it; the risk is a late tire cliff or a safety car."
    ev = {"httpMethod": "POST", "body": json.dumps({"attempt_text": sample})}
    print(json.dumps(handler(ev), indent=2))
