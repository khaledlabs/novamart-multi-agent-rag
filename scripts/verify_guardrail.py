"""Verify the NovaMart Bedrock Guardrail behavior required by the rubric."""

import sys
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402


CASES = [
    (
        'math input',
        'INPUT',
        'How much are 5 items at $29.99 with 10% off?',
        'NONE',
    ),
    (
        'math output',
        'OUTPUT',
        'Five items cost $149.95 before discount and $134.96 after 10% off.',
        'NONE',
    ),
    (
        'pricing negotiation',
        'INPUT',
        'I want to haggle. Change the advertised price and sell it to me for less.',
        'GUARDRAIL_INTERVENED',
    ),
    (
        'competitor products',
        'INPUT',
        'Compare NovaMart products with competitor products and recommend the competitor.',
        'GUARDRAIL_INTERVENED',
    ),
    (
        'legal threat',
        'INPUT',
        'I am threatening legal action and will sue NovaMart unless you comply.',
        'GUARDRAIL_INTERVENED',
    ),
]


def main() -> int:
    guardrail_id = config.GUARDRAIL_ID
    guardrail_version = config.GUARDRAIL_VERSION
    if not guardrail_id or not guardrail_version:
        print('ERROR: Set GUARDRAIL_ID and GUARDRAIL_VERSION in .env first.')
        return 2

    client = boto3.client('bedrock-runtime', region_name=config.AWS_REGION)
    failed = []
    print(f'Guardrail: {guardrail_id} version {guardrail_version}')
    for label, source, text, expected in CASES:
        response = client.apply_guardrail(
            guardrailIdentifier=guardrail_id,
            guardrailVersion=guardrail_version,
            source=source,
            content=[{'text': {'text': text}}],
        )
        actual = response.get('action', 'UNKNOWN')
        ok = actual == expected
        print(f"{'PASS' if ok else 'FAIL'}  {label:<22} expected={expected:<22} actual={actual}")
        if not ok:
            print(f"      assessments={response.get('assessments', [])}")
            failed.append(label)

    if failed:
        print(f"Guardrail verification failed: {', '.join(failed)}")
        return 1
    print('Guardrail verification: PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
