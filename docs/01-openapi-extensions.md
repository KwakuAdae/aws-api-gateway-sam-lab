# API Gateway OpenAPI Extensions Used in This Lab

API Gateway imports standard OpenAPI 3 (or Swagger 2) and reads extra settings from
`x-amazon-apigateway-*` keys. This page explains each one used in `template.yaml`.

## `x-amazon-apigateway-integration`

Attached to each method. It says what API Gateway calls.

```yaml
x-amazon-apigateway-integration:
  type: aws_proxy           # Lambda proxy: send the whole request, return Lambda's response as-is
  httpMethod: POST          # always POST when calling Lambda (not the client's method)
  uri: arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/<function-or-alias-arn>/invocations
```

| `type` | Backend | Mapping templates? |
|--------|---------|--------------------|
| `aws_proxy` | Lambda (proxy) | No. Lambda receives the full request |
| `aws` | Any AWS service action (e.g. DynamoDB `PutItem`, SQS `SendMessage`) | Yes |
| `http_proxy` | Any HTTP endpoint (pass-through) | No |
| `http` | Any HTTP endpoint | Yes |
| `mock` | Nothing: API Gateway builds the response | Yes |

The `mock` integration on `/health`:

```yaml
x-amazon-apigateway-integration:
  type: mock
  requestTemplates:
    application/json: '{"statusCode": 200}'    # picks which response below to use
  responses:
    default:
      statusCode: "200"
      responseTemplates:
        application/json: '{"status": "ok", "stage": "$context.stage"}'
```

## `x-amazon-apigateway-request-validators` and `x-amazon-apigateway-request-validator`

Defined once at the top level, then referenced per method:

```yaml
x-amazon-apigateway-request-validators:
  body-only:   { validateRequestBody: true,  validateRequestParameters: false }
  params-only: { validateRequestBody: false, validateRequestParameters: true }
...
post:
  x-amazon-apigateway-request-validator: body-only
```

The body is checked against the method's `requestBody` schema. API Gateway supports
**JSON Schema draft 4** keywords: `type`, `required`, `properties`, `additionalProperties`,
`minLength`/`maxLength`, `minimum`/`maximum`, `enum`, `pattern`, `minProperties`, `items`, `$ref`.

## `x-amazon-apigateway-gateway-responses`

Overrides the responses API Gateway itself sends (before or instead of your backend):

| Response type | Default status | When |
|---------------|----------------|------|
| `BAD_REQUEST_BODY` | 400 | Body failed validation |
| `INVALID_API_KEY` | 403 | Missing or unknown API key |
| `MISSING_AUTHENTICATION_TOKEN` | 403 | Route doesn't exist (we change it to 404) |
| `THROTTLED` | 429 | Rate or burst limit exceeded |
| `QUOTA_EXCEEDED` | 429 | Usage plan quota used up |
| `DEFAULT_4XX` / `DEFAULT_5XX` | — | Fallback for all 4XX / 5XX |

`$context.error.validationErrorString` and `$context.error.message` are available in templates.

## `x-amazon-apigateway-api-key-source`

`HEADER` (default) reads the key from `x-api-key`. `AUTHORIZER` lets a Lambda authorizer return
the key, which is useful when clients authenticate with tokens rather than raw API keys.

## Security scheme for API keys

```yaml
components:
  securitySchemes:
    api_key: { type: apiKey, name: x-api-key, in: header }
...
security: [{ api_key: [] }]     # on a method → apiKeyRequired = true
```

## Useful `$context` variables

`$context.requestId`, `$context.stage`, `$context.httpMethod`, `$context.resourcePath`,
`$context.path`, `$context.identity.sourceIp`, `$context.identity.apiKeyId`,
`$context.requestTime`, `$context.status`, `$context.responseLatency`,
`$context.integrationLatency`, `$context.error.message`.
