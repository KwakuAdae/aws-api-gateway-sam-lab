# Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `{"message": "Missing or invalid x-api-key header"}` (403) | No key, wrong key, or key used on the other environment's stack | Each stack has its own key. Re-read it with `aws apigateway get-api-key --api-key <ApiKeyId> --include-value` |
| `{"message": "No such route: …"}` (404) | Wrong path, or the stage is missing from the URL | URLs look like `https://<id>.execute-api.<region>.amazonaws.com/dev/books` |
| `{"message": "Invalid request body", …}` (400) | The body broke the `Book` / `BookUpdate` model | Read `details`. Common: missing `author`, `year` as a string, extra fields |
| `{"message": "Internal server error"}` (502) | Lambda crashed or returned a bad proxy response | `sam logs --stack-name books-api-dev --tail` shows the traceback |
| 500 with `Execution failed due to configuration error: Invalid permissions on Lambda function` | API Gateway can't invoke the alias | The `ApiInvokePermission` resource grants it. Check it exists and targets the `live` alias |
| 429 Too Many Requests | Usage plan throttle or daily quota | Wait, or raise the limits in `UsagePlan` |
| `sam deploy`: `Requires capabilities : [CAPABILITY_IAM]` | IAM roles are created | Already in `samconfig.toml`. When running manually add `--capabilities CAPABILITY_IAM` |
| prod deploy waits for confirmation | `confirm_changeset = true` for prod | Review the changeset and answer `y` (intentional for prod) |
| prod deploy takes 5+ minutes | Canary waits 5 minutes before shifting 100% | Expected. Use `AllAtOnce` while experimenting |
| Stack update failed with `UPDATE_ROLLBACK_COMPLETE` during a prod deploy | `AliasErrorsAlarm` fired and CodeDeploy rolled back | Check `sam logs` for the error in the new version, fix it, deploy again |
| Stage creation fails with `CloudWatch Logs role ARN must be set in account settings` | Access logs enabled before the account role was registered | Make sure `ApiAccessLogGroup` keeps `DependsOn: ApiGatewayAccount`, then redeploy |
| Changes to the OpenAPI body don't show up | Deployment not refreshed | SAM creates a new `AWS::ApiGateway::Deployment` whenever `DefinitionBody` changes, so check `sam deploy` actually ran |
