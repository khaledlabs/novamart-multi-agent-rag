# NovaMart Submission Evidence

This directory contains the evidence for the Multi-Agent E-commerce RAG
project. The screenshots are grouped below by rubric requirement.

## Automated tests

| Evidence | What it proves |
|---|---|
| `Task2.png` | Multi-agent orchestration tests pass (40/40) |
| `Task3.png` | Guardrail and AgentCore Runtime tests pass |
| `Task4.png` | AgentCore Memory tests pass |
| `Task5.png`, `Task5-2.png` | Three Knowledge Bases respond through parallel retrieval (25/25) |
| `Task6.png` | Observability tests pass |
| `full-tests-120-of-120.png` | Complete rubric test suite passes (120/120) |

## Required live orchestrator execution

`agent-orchestrator-live-test-01.png` through
`agent-orchestrator-live-test-09.png` show the complete execution of:

```powershell
python src/agent_orchestrator.py test
```

The sequence covers the return/refund, parallel policy RAG, and calculation
scenarios, including the generated responses and published X-Ray trace IDs.

## Knowledge Bases and S3 Vectors

| Evidence | What it proves |
|---|---|
| `knowledge-bases-active.png` | All three Bedrock Knowledge Bases are available |
| `returns-sync-complete.png` | Returns data source is synced |
| `shipping-sync-complete.png` | Shipping data source is synced |
| `warranty-sync-complete.png` | Warranty data source is synced |
| `s3-vector-bucket-indexes.png` | The CloudFormation vector bucket contains the three required indexes |
| `returns-kb-storage-mapping.png` | Returns KB uses Titan Embed Text v2 and the `returns-policy-index` S3 Vectors index |
| `shipping-kb-storage-mapping.png` | Shipping KB uses Titan Embed Text v2 and the `shipping-policy-index` S3 Vectors index |
| `warranty-kb-storage-mapping.png` | Warranty KB uses Titan Embed Text v2 and the `warranty-policy-index` S3 Vectors index |

## Deployed services and observability

| Evidence | What it proves |
|---|---|
| `guardrail-version-2.png` | The numbered Bedrock Guardrail version exists |
| `agentcore-runtime-ready.png` | AgentCore Runtime is deployed and ready |
| `agentcore-memory-active .png` | AgentCore Memory is active |
| `cloudwatch-agent-logs.png` | Agent execution logs reach CloudWatch |
| `xray-service-map.png` | X-Ray shows the connected Orchestrator, workers, and Knowledge Base call chain |

## Environment configuration

The populated project-root `.env` is intentionally tracked for the course
submission. It contains deployed resource identifiers and configuration, not
AWS access keys, secret access keys, session tokens, passwords, or private
keys.

Before publishing future evidence, inspect screenshots for authentication
credentials, session tokens, customer PII, and unrelated private content.
