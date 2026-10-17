# Gradual Deployments: How the Canary Release Works

## The pieces SAM creates

`AutoPublishAlias: live` plus `DeploymentPreference` on `BooksFunction` make SAM generate:

| Resource | Purpose |
|----------|---------|
| `AWS::Lambda::Version` | A new immutable version every time the code or config changes |
| `AWS::Lambda::Alias` (`live`) | A stable pointer that API Gateway invokes |
| `AWS::CodeDeploy::Application` + `DeploymentGroup` | Shift the alias from the old version to the new one |
| `CodeDeployServiceRole` | Lets CodeDeploy update the alias |

API Gateway always calls `…:function:books-api-prod-handler:live`. During a deployment the
alias has **weighted routing**: e.g. 90% to version 1 and 10% to version 2.

```bash
aws lambda get-alias --function-name books-api-prod-handler --name live \
  --query '{main: FunctionVersion, weights: RoutingConfig.AdditionalVersionWeights}'
# { "main": "1", "weights": { "2": 0.1 } }
```

## Deployment types

| `DeploymentType` | Behaviour |
|------------------|-----------|
| `AllAtOnce` | 100% immediately (used for dev) |
| `Canary10Percent5Minutes` | 10% for 5 minutes, then 100% (used for prod) |
| `Canary10Percent30Minutes` | 10% for 30 minutes, then 100% |
| `Linear10PercentEvery1Minute` | +10% every minute (10 minutes total) |
| `Linear10PercentEvery10Minutes` | +10% every 10 minutes |

## Automatic rollback

`AliasErrorsAlarm` watches the `Errors` metric of the **new** version through the `live` alias.
If it goes into ALARM while traffic is shifting, CodeDeploy stops and points `live` back at the
old version. The CloudFormation stack update then fails and rolls back too.

### Try it: deploy a broken version

1. In `src/books.py`, add a bug to the list route, e.g. right after `if book_id is None and method == "GET":` add
   `raise RuntimeError("bad release")`.
2. Deploy prod: `./scripts/deploy.sh prod`.
3. Send traffic so the canary receives some requests: `./scripts/watch-versions.sh prod 60`.
4. Within a minute or two the alarm fires. Watch **CodeDeploy → Deployments**: the status becomes
   *Stopped / Rolled back*, and CloudFormation shows `UPDATE_ROLLBACK_COMPLETE`.
5. Remove the bug and deploy again.

## Hooks (going further)

`DeploymentPreference.Hooks.PreTraffic` and `PostTraffic` run Lambda functions that test the
new version **before** it gets any traffic, and again after the shift. If a hook reports
failure, CodeDeploy rolls back. See the
[SAM docs on safe deployments](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/automating-updates-to-serverless-apps.html).
