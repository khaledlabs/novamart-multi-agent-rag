"""Refine the live pricing-negotiation topic and publish a new Guardrail version."""

import sys
import time
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402


PRICING_DEFINITION = (
    "A customer asks NovaMart to agree to a new price that differs from the "
    "listed or advertised price. This includes haggling, bargaining, and asking "
    "a seller to lower, override, or change a price. Exclude all arithmetic and "
    "calculation questions: totals, multiplication, percentages, sale discounts, "
    "tax, and calculations using a specified price are allowed and are not "
    "pricing negotiations."
)

PRICING_EXAMPLES = [
    'Will you lower the listed price from $100 to $80 for me?',
    'I want to haggle; give me a price below the advertised price.',
    'Override the store price and sell this item to me for less.',
]


def main() -> int:
    if not config.GUARDRAIL_ID:
        print('ERROR: Set GUARDRAIL_ID in .env first.')
        return 2

    client = boto3.client('bedrock', region_name=config.AWS_REGION)
    draft = client.get_guardrail(
        guardrailIdentifier=config.GUARDRAIL_ID,
        guardrailVersion='DRAFT',
    )

    topics = draft['topicPolicy']['topics']
    for topic in topics:
        if topic['name'] == 'Pricing Negotiations':
            topic['definition'] = PRICING_DEFINITION
            topic['examples'] = PRICING_EXAMPLES
            break
    else:
        raise RuntimeError('Pricing Negotiations topic not found in the Guardrail draft')

    payload = {
        'guardrailIdentifier': config.GUARDRAIL_ID,
        'name': draft['name'],
        'description': draft.get('description', ''),
        'topicPolicyConfig': {
            'topicsConfig': topics,
            'tierConfig': {'tierName': 'STANDARD'},
        },
        'contentPolicyConfig': {
            'filtersConfig': draft['contentPolicy']['filters'],
        },
        'wordPolicyConfig': {
            'managedWordListsConfig': draft['wordPolicy']['managedWordLists'],
        },
        'sensitiveInformationPolicyConfig': {
            'piiEntitiesConfig': draft['sensitiveInformationPolicy']['piiEntities'],
        },
        'crossRegionConfig': {
            'guardrailProfileIdentifier': 'us.guardrail.v1:0',
        },
        'blockedInputMessaging': draft['blockedInputMessaging'],
        'blockedOutputsMessaging': draft['blockedOutputsMessaging'],
    }
    if draft['wordPolicy'].get('customWords'):
        payload['wordPolicyConfig']['wordsConfig'] = draft['wordPolicy']['customWords']
    if draft['sensitiveInformationPolicy'].get('regexes'):
        payload['sensitiveInformationPolicyConfig']['regexesConfig'] = (
            draft['sensitiveInformationPolicy']['regexes']
        )
    client.update_guardrail(**payload)

    deadline = time.time() + 180
    while time.time() < deadline:
        current = client.get_guardrail(
            guardrailIdentifier=config.GUARDRAIL_ID,
            guardrailVersion='DRAFT',
        )
        if current['status'] == 'READY':
            break
        if current['status'] == 'FAILED':
            raise RuntimeError(f"Guardrail update failed: {current.get('statusReasons', [])}")
        time.sleep(5)
    else:
        raise TimeoutError('Guardrail draft did not become READY after refinement')

    published = client.create_guardrail_version(
        guardrailIdentifier=config.GUARDRAIL_ID,
        description='Refined pricing-negotiation detection; arithmetic remains allowed.',
    )
    print(f"GUARDRAIL_ID={config.GUARDRAIL_ID}")
    print(f"GUARDRAIL_VERSION={published['version']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
