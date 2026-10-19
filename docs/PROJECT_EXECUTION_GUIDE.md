# NovaMart End-to-End Execution Guide

This runbook turns the project rubric into small, verifiable milestones. Run all
commands from the repository root in PowerShell. The deployment region is
`us-east-1`.

> Never paste AWS credentials into a terminal screenshot, GitHub issue, commit,
> or chat. The local `.env` is intentionally ignored by Git.

## Milestone 0 — Local toolchain and source validation

### Goal

Prove that the project can be built locally before creating billable AWS
resources.

### Commands

```powershell
.\.venv\Scripts\python.exe --version
agentcore --version
agentcore validate
.\.venv\Scripts\python.exe -X utf8 -m compileall -q config.py src infrastructure tests
.\.venv\Scripts\python.exe -X utf8 tests\test_agent.py task2
```

### Pass criteria

- Python is 3.12 or newer.
- AgentCore CLI is installed and `agentcore validate` reports `Valid`.
- Compilation exits without errors.
- Task 2 reports `40/40`.

### Evidence

Save a readable terminal screenshot as
`evidence/01-task2-40-of-40.png`.

## Milestone 1 — Authenticate and deploy foundation infrastructure

### Goal

Create the DynamoDB, S3, S3 Vectors, IAM, and CloudWatch resources used by the
agents.

### Commands

First validate the active AWS identity:

```powershell
aws sts get-caller-identity --region us-east-1
```

If the token is invalid, refresh it with the method used by the AWS account:

```powershell
# Long-lived IAM credentials
aws configure

# Or, for an organization using IAM Identity Center
aws sso login --profile <profile-name>
$env:AWS_PROFILE = '<profile-name>'
```

Then deploy the stack:

```powershell
aws cloudformation deploy --template-file infrastructure\starter_stack.yaml --stack-name udacity-agentcore --capabilities CAPABILITY_NAMED_IAM --region us-east-1

aws cloudformation describe-stacks --stack-name udacity-agentcore --query "Stacks[0].StackStatus" --output text --region us-east-1
```

### Pass criteria

- STS returns the intended account and ARN.
- CloudFormation reports `CREATE_COMPLETE` or `UPDATE_COMPLETE`.

### Evidence

Capture the CloudFormation stack Overview and Resources tabs without exposing
credentials. Save the main screenshot as
`evidence/02-cloudformation-complete.png`.

## Milestone 2 — Seed and verify project data

### Goal

Populate both business tables and upload the three policy domains.

### Commands

```powershell
.\.venv\Scripts\python.exe -X utf8 infrastructure\seed_data.py
.\.venv\Scripts\python.exe -X utf8 config.py

$policyBucket = aws cloudformation list-exports --query "Exports[?Name=='udacity-agentcore-PolicyBucket'].Value | [0]" --output text --region us-east-1
aws s3 ls "s3://$policyBucket/policies/" --recursive --region us-east-1

aws dynamodb scan --table-name udacity-agentcore-customers --select COUNT --region us-east-1
aws dynamodb scan --table-name udacity-agentcore-orders --select COUNT --region us-east-1
```

### Pass criteria

- `config.py` resolves all foundation resource names.
- S3 contains documents below `policies/returns/`, `policies/shipping/`, and
  `policies/warranty/`.
- Both DynamoDB scans return non-zero counts.

## Milestone 3 — Create and sync the three Knowledge Bases

### Goal

Build the three self-managed Bedrock Knowledge Bases required by Task 5.

### Console procedure

In **Amazon Bedrock → Knowledge Bases**, create these resources:

| Knowledge Base | S3 prefix | Existing S3 Vectors index |
|---|---|---|
| `novamart-returns-policy-kb` | `policies/returns/` | `returns-policy-index` |
| `novamart-shipping-policy-kb` | `policies/shipping/` | `shipping-policy-index` |
| `novamart-warranty-policy-kb` | `policies/warranty/` | `warranty-policy-index` |

For every Knowledge Base:

1. Choose a self-managed vector store, not Managed KB.
2. Select Amazon Titan Embed Text v2.
3. Select the vector bucket printed by `config.py`.
4. Select the matching pre-created vector index from the table.
5. Set the matching S3 prefix.
6. Create the Knowledge Base and click **Sync** on its data source.
7. Wait for the ingestion job to show **Complete**.

Copy the three IDs into the local `.env`:

```dotenv
RETURNS_KB_ID=<returns-id>
SHIPPING_KB_ID=<shipping-id>
WARRANTY_KB_ID=<warranty-id>
```

Restart each Python process after changing `.env`, because configuration is
loaded when the process starts.

### Verification

```powershell
.\.venv\Scripts\python.exe -X utf8 tests\test_agent.py task5
```

### Pass criteria

- Each KB is `ACTIVE`.
- Each data source has a completed sync.
- Each KB uses Titan Embed Text v2 and its assigned existing S3 Vectors index.
- Task 5 reports `25/25`.

### Evidence

Capture a console view showing all three KBs and their statuses, plus the three
completed ingestion jobs. Save the primary image as
`evidence/03-knowledge-bases-active.png`.

## Milestone 4 — Deploy Guardrail, Runtime, Memory, and Observability

### Goal

Run the full deployment only after all three KB IDs are populated.

### Commands

```powershell
.\.venv\Scripts\python.exe -X utf8 src\agent_orchestrator.py deploy
```

At the end, copy the printed values into `.env`:

```dotenv
AGENTCORE_RUNTIME_ARN=<runtime-arn>
GUARDRAIL_ID=<guardrail-id>
GUARDRAIL_VERSION=<numbered-version>
```

Open a new PowerShell process or rerun Python after editing `.env`, then verify:

```powershell
.\.venv\Scripts\python.exe -X utf8 tests\test_agent.py task3
.\.venv\Scripts\python.exe -X utf8 tests\test_agent.py task4
.\.venv\Scripts\python.exe -X utf8 tests\test_agent.py task6
.\.venv\Scripts\python.exe -X utf8 scripts\verify_guardrail.py
```

### Pass criteria

- Guardrail is published as a numbered version and contains every required
  content, PII, denied-topic, and profanity policy.
- Runtime is `READY`, uses `PUBLIC` networking and `HTTP`, and contains all
  eight rubric environment variables.
- Memory is `ACTIVE`, uses summarization, and expires events after seven days.
- CloudWatch logging is enabled at INFO; X-Ray sampling is 100%.
- The guardrail verifier allows the math input/output and blocks negotiation,
  competitor, and legal-threat examples.

## Milestone 5 — Exercise all routing scenarios and capture X-Ray

### Goal

Prove the functional routing and produce the required service-map evidence.

### Commands

```powershell
.\.venv\Scripts\python.exe -X utf8 src\agent_orchestrator.py test

.\.venv\Scripts\python.exe -X utf8 src\agent_orchestrator.py invoke "I want to return my order ORD-27176"
.\.venv\Scripts\python.exe -X utf8 src\agent_orchestrator.py invoke "What is the return policy for premium customers?"
.\.venv\Scripts\python.exe -X utf8 src\agent_orchestrator.py invoke "How much are 5 items at `$29.99 with 10% off?"
```

Expected routing:

| Scenario | Required route |
|---|---|
| Return | Orchestrator → Inventory → Refund → Communication |
| Policy | Orchestrator → Policy → three parallel KB retrievers → Communication |
| Math | Orchestrator → Communication only |

Wait 30–60 seconds, then open **CloudWatch → X-Ray traces → Service map**,
select **Last 5 minutes**, open the policy request trace if needed, and make
sure the full Orchestrator → Worker → Knowledge Base graph is visible.

Save the required image as `evidence/05-xray-service-map.png`.

## Milestone 6 — Final rubric test and GitHub handoff

### Commands

```powershell
.\.venv\Scripts\python.exe -X utf8 tests\test_agent.py all
git status --short
git diff --check
```

### Pass criteria

- The final suite shows `120/120`.
- The two required screenshots are legible and include relevant console context.
- `src/agent_orchestrator.py` contains no TODO or placeholder implementation.
- The local `.env` contains all six generated IDs/ARN/version values.
- `.env`, `.venv`, build output, and AgentCore state are not committed.

Save the required score screenshot as
`evidence/04-full-tests-120-of-120.png`.

Commit the final implementation, guide, and non-sensitive evidence. Push only
after reviewing `git status` and `git diff --cached`.

## Cleanup — only after submission is accepted

```powershell
.\.venv\Scripts\python.exe -X utf8 infrastructure\cleanup.py
.\.venv\Scripts\python.exe -X utf8 infrastructure\cleanup.py --yes
```

The first command is a dry run. Do not execute the destructive form until the
project has been submitted and all evidence is safely stored.
