# Lab: API Gateway with AWS SAM: OpenAPI, Validation and Safe Deployments

A hands-on lab that builds a **Books REST API** on **Amazon API Gateway** with **AWS SAM**.
Unlike a quick "Lambda behind an API" setup, the whole API here is described in an
**OpenAPI 3** document. You learn the API Gateway features that matter in real projects:

- **request validation** with JSON-schema models, so bad requests never reach your code
- a **mock integration** that answers without any backend
- **custom gateway responses** for API Gateway's own errors
- **API keys and usage plans**
- **separate dev and prod environments** from one template
- **gradual (canary) deployments** of new Lambda versions with **automatic rollback**

```
                         ┌──────────────── Amazon API Gateway (REST, from OpenAPI 3) ────────────────┐
 ┌─────────┐   HTTPS     │  GET  /health ─────────────▶ MOCK integration (no backend)                 │
 │ curl /  │ ──────────▶ │  /books, /books/{id}  ──┬──▶ ① API key check  (x-api-key, usage plan)       │
 │ client  │ ◀────────── │                         ├──▶ ② Body validation (Book / BookUpdate models)   │
 └─────────┘             │                         └──▶ ③ Lambda proxy → alias "live"                  │
                         │  Gateway responses: 400 BAD_REQUEST_BODY · 403 INVALID_API_KEY · 404        │
                         └───────────────────────────────────────┬──────────────────────────────────┘
                                                                 ▼
                       ┌──────────── alias "live" ────────────┐       ┌──────────────────────┐
                       │  version N   ◀── 90% ──┐             │ ────▶ │ DynamoDB: books      │
                       │  version N+1 ◀── 10% ──┘ (canary)    │       └──────────────────────┘
                       └──────────────────────────────────────┘
                         CodeDeploy shifts traffic, rolls back if the errors alarm fires

   Stacks:  books-api-dev  (deploys all at once)      books-api-prod  (canary: 10%, then 100% after 5 min)
```

## What you will learn

| Topic | Where |
|-------|-------|
| Defining a REST API in **OpenAPI 3** inside a SAM template (`DefinitionBody`) | `template.yaml` → `BooksApi` |
| API Gateway **OpenAPI extensions** (`x-amazon-apigateway-*`) | integrations, validators, gateway responses, API key source |
| **Request validation** with models: `required`, `minLength`, `additionalProperties`, `minimum` | `components.schemas` |
| **MOCK integration** with mapping templates (VTL) | `GET /health` |
| **Lambda proxy integration** pointing at an **alias** | `/books` routes |
| **API keys, usage plans**, throttling and quotas | `ApiKey`, `UsagePlan`, `MethodSettings` |
| **Multiple environments** with `samconfig.toml` config-envs | `dev` and `prod` stacks |
| **Lambda versions and aliases** (`AutoPublishAlias`) | `BooksFunction` |
| **Gradual deployments** with CodeDeploy (`DeploymentPreference`) and **rollback alarms** | `prod` stack |
| Optional **access logs** in CloudWatch | `EnableAccessLogs=true` |

## API reference

All `/books` routes need the header `x-api-key: <your key>`.

| Method | Path | Body | Success | Errors |
|--------|------|------|---------|--------|
| GET | `/health` | — | `200` status JSON (mock, no key needed) | |
| GET | `/books?author=…` | — | `200` list | `403` |
| POST | `/books` | `{"title", "author", "year"?}` | `201` book | `400` (validated by API Gateway), `403` |
| GET | `/books/{id}` | — | `200` book | `403`, `404` |
| PUT | `/books/{id}` | any of `title`, `author`, `year` | `200` book | `400`, `403`, `404` |
| DELETE | `/books/{id}` | — | `204` | `403`, `404` |

Every Lambda response carries an `X-Served-By` header such as
`{"stage": "prod", "lambdaVersion": "2", "lambdaAlias": "live"}`.

## Project structure

```
aws-api-gateway-sam-lab/
├── template.yaml           # SAM template: OpenAPI definition, Lambda, DynamoDB, keys, CodeDeploy
├── samconfig.toml          # [dev] and [prod] deploy settings
├── src/
│   └── books.py            # Lambda handler
├── tests/
│   └── test_books.py       # 14 unit tests (moto, no AWS needed)
├── scripts/
│   ├── deploy.sh           # sam validate + build + deploy <env>
│   ├── test-api.sh         # call every route of <env>
│   ├── watch-versions.sh   # count which Lambda version answers (during a canary)
│   └── cleanup.sh          # sam delete <env>
└── docs/
    ├── 01-openapi-extensions.md
    ├── 02-gradual-deployments.md
    └── 03-troubleshooting.md
```

## Prerequisites

| Tool | Check | Install |
|------|-------|---------|
| AWS account | — | Fits in the free tier |
| AWS CLI v2 | `aws --version` | then `aws configure` |
| AWS SAM CLI | `sam --version` | `brew install aws-sam-cli` or the [install guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) |
| Python 3.12 | `python3 --version` | for unit tests |

---

## Quick start

```bash
git clone https://github.com/KwakuAdae/aws-api-gateway-sam-lab.git
cd aws-api-gateway-sam-lab

./scripts/deploy.sh dev        # ~2 min
./scripts/test-api.sh dev
./scripts/cleanup.sh dev
```

---

## Step 1: Run the unit tests

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -v
```

[moto](https://github.com/getmoto/moto) fakes DynamoDB in memory. The 14 tests cover create,
list (with author filter), update, validation, delete, 404s and the `X-Served-By` header.

## Step 2: Read the OpenAPI definition

Open [`template.yaml`](template.yaml) and find `BooksApi → DefinitionBody`. It's a standard
OpenAPI 3 document plus API Gateway extensions:

```yaml
/books:
  post:
    security: [{ api_key: [] }]                       # API key required
    x-amazon-apigateway-request-validator: body-only  # validate the body...
    requestBody:
      content:
        application/json:
          schema: { $ref: "#/components/schemas/Book" } # ...against this model
    x-amazon-apigateway-integration:                  # then call Lambda
      type: aws_proxy
      httpMethod: POST
      uri: !Sub "arn:...:functions/${BooksFunctionAliaslive}/invocations"
```

| Extension | What it does |
|-----------|--------------|
| `x-amazon-apigateway-integration` | Connects a method to a backend: `aws_proxy` (Lambda), `mock`, `http`, `aws` |
| `x-amazon-apigateway-request-validators` | Named validators that methods opt into |
| `x-amazon-apigateway-gateway-responses` | Custom bodies/status codes for API Gateway's own errors |
| `x-amazon-apigateway-api-key-source` | Read API keys from the `x-api-key` header |

More detail: [docs/01-openapi-extensions.md](docs/01-openapi-extensions.md).

The integration points at the alias **`live`**, not the function itself. That's what makes
gradual deployments possible (Step 8).

## Step 3: Validate and build

```bash
sam validate --lint     # template + CloudFormation linting
sam build               # copies src/ into .aws-sam/build
```

## Step 4: Deploy the dev environment

```bash
sam deploy --config-env dev
```

`samconfig.toml` holds the settings for each environment:

```toml
[dev.deploy.parameters]
stack_name = "books-api-dev"
parameter_overrides = "Environment=dev DeploymentType=AllAtOnce EnableAccessLogs=false"
```

Get the URL and API key:

```bash
export API_URL=$(aws cloudformation describe-stacks --stack-name books-api-dev \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)
export API_KEY=$(aws apigateway get-api-key --include-value --query value --output text \
  --api-key $(aws cloudformation describe-stacks --stack-name books-api-dev \
  --query "Stacks[0].Outputs[?OutputKey=='ApiKeyId'].OutputValue" --output text))
```

(`./scripts/deploy.sh dev` does Steps 3–4 and prints both values.)

## Step 5: Mock integration and gateway responses

```bash
curl -s $API_URL/health
# {"status": "ok", "stage": "dev", "requestId": "…", "time": "17/Oct/2026:10:00:00 +0000"}
```

There's no Lambda behind `/health`. API Gateway builds the response from a **mapping template**
using `$context` variables. Mock integrations are handy for health checks, stubbing endpoints
before the backend exists, and CORS preflight.

Custom gateway responses replace API Gateway's default errors:

```bash
curl -s $API_URL/books        # {"message": "Missing or invalid x-api-key header"}   403
curl -s $API_URL/nope         # {"message": "No such route: GET /nope"}              404
```

## Step 6: Request validation

```bash
# Valid → reaches Lambda → 201
curl -s -X POST $API_URL/books -H "x-api-key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"title":"Things Fall Apart","author":"Chinua Achebe","year":1958}'

# Invalid → rejected by API Gateway → 400, Lambda never runs (and isn't billed)
curl -s -X POST $API_URL/books -H "x-api-key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"title":"","year":"soon","isbn":"x"}'
# {"message": "Invalid request body", "details": "[instance has properties which are not allowed by the
#  schema: [\"isbn\"], object has missing required properties ([\"author\"]), ...]"}
```

The rules come from the `Book` model: `required`, `minLength`, `type: integer`, `minimum`/`maximum`
and `additionalProperties: false`.

## Step 7: Exercise every route

```bash
./scripts/test-api.sh dev
```

✅ **Checkpoint:** in the console, open **API Gateway → books-api-dev-api → Resources**. You'll
see every resource and method from the OpenAPI document. **Models** shows `Book` and
`BookUpdate`, and **Gateway responses** shows your three customised responses.

## Step 8: Deploy prod with a canary release

The prod environment uses the same template with different parameters:

```toml
[prod.deploy.parameters]
stack_name = "books-api-prod"
parameter_overrides = "Environment=prod DeploymentType=Canary10Percent5Minutes ..."
confirm_changeset = true      # review changes before they reach prod
```

1. First deploy (creates the stack, version 1):

   ```bash
   ./scripts/deploy.sh prod
   ```

2. Make a visible change. In `src/books.py`, change the 404 message to
   `f"No book with id {book_id}"`.

3. Deploy again and, in a second terminal, watch the traffic split:

   ```bash
   ./scripts/deploy.sh prod                 # terminal 1
   ./scripts/watch-versions.sh prod 40      # terminal 2, run a few times
   #   36 version 1
   #    4 version 2      ← 10% canary
   ```

   Open **CodeDeploy → Deployments** to see the traffic shift. After 5 minutes CodeDeploy moves
   the remaining 90%, and `watch-versions.sh` shows only `version 2`.

4. **Rollback:** if `AliasErrorsAlarm` fires during those 5 minutes (any error on the new
   version), CodeDeploy automatically moves all traffic back to the previous version.
   [docs/02-gradual-deployments.md](docs/02-gradual-deployments.md) shows how to trigger a
   rollback on purpose.

Other strategies to try in `samconfig.toml`: `Linear10PercentEvery1Minute`, `AllAtOnce`.

## Step 9: API keys and usage plans

```bash
aws apigateway get-usage-plans --query 'items[].[name,throttle.rateLimit,quota.limit]' --output table

# Today's usage for the key
aws apigateway get-usage --usage-plan-id <plan-id> \
  --start-date $(date -u +%F) --end-date $(date -u +%F)
```

The plan allows 10 requests/second (burst 20) and 1,000 requests per day. Beyond that,
API Gateway returns **429 Too Many Requests**.

## Step 10 (optional): Access logs

```bash
sam deploy --config-env dev --parameter-overrides \
  "Environment=dev DeploymentType=AllAtOnce EnableAccessLogs=true"

aws logs tail /aws/apigateway/books-api-dev-access --follow
```

Each request produces one JSON line with method, path, status, latency, integration latency and
API key ID.

> This sets API Gateway's **account-level** CloudWatch role for the region
> (`AWS::ApiGateway::Account`). Skip it if your account already has one configured.

## Step 11: Clean up

```bash
./scripts/cleanup.sh dev
./scripts/cleanup.sh prod
```

---

## Cost

Within the free tier for normal lab use: API Gateway (1M REST calls/month for 12 months),
Lambda (1M requests/month), DynamoDB on-demand (pennies) and CodeDeploy for Lambda (free).

## Going further

- Add a **Cognito user pool authorizer** to the OpenAPI document (`x-amazon-apigateway-authorizer`)
- Add **CORS** with a mock `OPTIONS` method per resource
- Export the API for clients: `aws apigateway get-export --parameters extensions='apigateway' --export-type oas30 ...`
- Generate an SDK: `aws apigateway get-sdk --sdk-type javascript ...`
- Run `PreTraffic` / `PostTraffic` **hook functions** that test the new version before traffic shifts
- Sister labs: [API Gateway (SAM quick build)](https://github.com/KwakuAdae/aws-serverless-tasks-api-lab) ·
  [ECS Fargate](https://github.com/KwakuAdae/aws-ecs-fargate-website-lab) ·
  [EKS](https://github.com/KwakuAdae/aws-eks-website-lab) ·
  [SQL with CloudFormation](https://github.com/KwakuAdae/aws-cloudformation-sql-lab) ·
  [CloudWatch Logs with Terraform](https://github.com/KwakuAdae/aws-cloudwatch-logs-terraform-lab)

## Troubleshooting

See [docs/03-troubleshooting.md](docs/03-troubleshooting.md).

## Author

**Kwaku Adae**: [github.com/KwakuAdae](https://github.com/KwakuAdae)

Feedback and reviews are welcome. Open an issue or a pull request!
