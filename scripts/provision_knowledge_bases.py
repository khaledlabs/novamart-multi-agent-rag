"""Provision and sync the three rubric-required Bedrock Knowledge Bases.

This is an idempotent API equivalent of the AWS Console's "Create self-managed
KB" flow. It intentionally reuses the S3 Vectors bucket and indexes created by
the project's CloudFormation foundation stack.
"""

import json
import sys
import time
import uuid
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402


EMBEDDING_MODEL_ARN = (
    f"arn:aws:bedrock:{config.AWS_REGION}::"
    "foundation-model/amazon.titan-embed-text-v2:0"
)

DOMAINS = {
    "returns": {
        "kb_name": "novamart-returns-policy-kb",
        "source_name": "novamart-returns-policy-source",
        "prefix": "policies/returns/",
        "index": "returns-policy-index",
    },
    "shipping": {
        "kb_name": "novamart-shipping-policy-kb",
        "source_name": "novamart-shipping-policy-source",
        "prefix": "policies/shipping/",
        "index": "shipping-policy-index",
    },
    "warranty": {
        "kb_name": "novamart-warranty-policy-kb",
        "source_name": "novamart-warranty-policy-source",
        "prefix": "policies/warranty/",
        "index": "warranty-policy-index",
    },
}


def _wait(label, getter, success, failures, timeout=600):
    deadline = time.time() + timeout
    while time.time() < deadline:
        resource = getter()
        status = resource.get("status", "UNKNOWN")
        print(f"  {label}: {status}", flush=True)
        if status == success:
            return resource
        if status in failures:
            raise RuntimeError(
                f"{label} failed: {resource.get('failureReasons') or resource}"
            )
        time.sleep(10)
    raise TimeoutError(f"{label} did not reach {success} within {timeout}s")


def _knowledge_bases(client):
    paginator = client.get_paginator("list_knowledge_bases")
    for page in paginator.paginate():
        yield from page.get("knowledgeBaseSummaries", [])


def _data_sources(client, kb_id):
    paginator = client.get_paginator("list_data_sources")
    for page in paginator.paginate(knowledgeBaseId=kb_id):
        yield from page.get("dataSourceSummaries", [])


def ensure_knowledge_base(client, spec, role_arn, vector_bucket_arn):
    existing = next(
        (kb for kb in _knowledge_bases(client) if kb["name"] == spec["kb_name"]),
        None,
    )
    if existing:
        kb_id = existing["knowledgeBaseId"]
        print(f"Reusing {spec['kb_name']}: {kb_id}")
    else:
        index_arn = f"{vector_bucket_arn}/index/{spec['index']}"
        response = client.create_knowledge_base(
            clientToken=str(uuid.uuid4()),
            name=spec["kb_name"],
            description=f"NovaMart {spec['kb_name'].split('-')[1]} policy knowledge base.",
            roleArn=role_arn,
            knowledgeBaseConfiguration={
                "type": "VECTOR",
                "vectorKnowledgeBaseConfiguration": {
                    "embeddingModelArn": EMBEDDING_MODEL_ARN,
                    "embeddingModelConfiguration": {
                        "bedrockEmbeddingModelConfiguration": {
                            "dimensions": 1024,
                            "embeddingDataType": "FLOAT32",
                        }
                    },
                },
            },
            storageConfiguration={
                "type": "S3_VECTORS",
                "s3VectorsConfiguration": {"indexArn": index_arn},
            },
            tags={"Project": config.PROJECT_NAME, "ManagedBy": "project-script"},
        )
        kb_id = response["knowledgeBase"]["knowledgeBaseId"]
        print(f"Created {spec['kb_name']}: {kb_id}")

    _wait(
        spec["kb_name"],
        lambda: client.get_knowledge_base(knowledgeBaseId=kb_id)["knowledgeBase"],
        "ACTIVE",
        {"FAILED", "DELETE_UNSUCCESSFUL"},
    )
    return kb_id


def ensure_data_source(client, spec, kb_id, bucket_arn):
    existing = next(
        (ds for ds in _data_sources(client, kb_id) if ds["name"] == spec["source_name"]),
        None,
    )
    if existing:
        data_source_id = existing["dataSourceId"]
        print(f"Reusing {spec['source_name']}: {data_source_id}")
    else:
        response = client.create_data_source(
            knowledgeBaseId=kb_id,
            clientToken=str(uuid.uuid4()),
            name=spec["source_name"],
            description=f"S3 documents under {spec['prefix']}",
            dataSourceConfiguration={
                "type": "S3",
                "s3Configuration": {
                    "bucketArn": bucket_arn,
                    "inclusionPrefixes": [spec["prefix"]],
                },
            },
            dataDeletionPolicy="RETAIN",
            vectorIngestionConfiguration={
                "chunkingConfiguration": {
                    "chunkingStrategy": "FIXED_SIZE",
                    "fixedSizeChunkingConfiguration": {
                        "maxTokens": 300,
                        "overlapPercentage": 20,
                    },
                }
            },
        )
        data_source_id = response["dataSource"]["dataSourceId"]
        print(f"Created {spec['source_name']}: {data_source_id}")

    _wait(
        spec["source_name"],
        lambda: client.get_data_source(
            knowledgeBaseId=kb_id, dataSourceId=data_source_id
        )["dataSource"],
        "AVAILABLE",
        {"DELETE_UNSUCCESSFUL"},
    )
    return data_source_id


def sync_data_source(client, domain, kb_id, data_source_id):
    response = client.start_ingestion_job(
        knowledgeBaseId=kb_id,
        dataSourceId=data_source_id,
        clientToken=str(uuid.uuid4()),
        description=f"Initial NovaMart {domain} policy sync",
    )
    job_id = response["ingestionJob"]["ingestionJobId"]
    job = _wait(
        f"{domain} ingestion {job_id}",
        lambda: client.get_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=data_source_id,
            ingestionJobId=job_id,
        )["ingestionJob"],
        "COMPLETE",
        {"FAILED", "STOPPED"},
        timeout=900,
    )
    return job


def main():
    client = boto3.client("bedrock-agent", region_name=config.AWS_REGION)
    bucket_arn = f"arn:aws:s3:::{config.POLICY_BUCKET}"
    results = {}

    for domain, spec in DOMAINS.items():
        print(f"\n=== {domain.upper()} ===")
        kb_id = ensure_knowledge_base(
            client, spec, config.AGENTCORE_ROLE_ARN, config.VECTOR_STORE_BUCKET_ARN
        )
        data_source_id = ensure_data_source(client, spec, kb_id, bucket_arn)
        job = sync_data_source(client, domain, kb_id, data_source_id)
        results[domain] = {
            "knowledge_base_id": kb_id,
            "data_source_id": data_source_id,
            "ingestion_job_id": job["ingestionJobId"],
            "ingestion_status": job["status"],
            "statistics": job.get("statistics", {}),
        }

    print("\nKNOWLEDGE_BASE_RESULTS=" + json.dumps(results, default=str))
    print("\nAdd these values to .env:")
    print(f"RETURNS_KB_ID={results['returns']['knowledge_base_id']}")
    print(f"SHIPPING_KB_ID={results['shipping']['knowledge_base_id']}")
    print(f"WARRANTY_KB_ID={results['warranty']['knowledge_base_id']}")


if __name__ == "__main__":
    main()
