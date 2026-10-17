"""Books API: Lambda function behind an API Gateway REST API defined with OpenAPI in AWS SAM.

Routes (Lambda proxy integration)
  GET    /books              list books (optional ?author=... filter)
  POST   /books              add a book       body validated by API Gateway: {"title", "author", "year"?}
  GET    /books/{id}         get one book
  PUT    /books/{id}         update a book    body: any of {"title", "author", "year"}
  DELETE /books/{id}         delete a book

Every response has an X-Served-By header with the API stage, Lambda version and alias, so you
can watch a gradual (canary) deployment shift traffic from the old version to the new one.
"""
import json
import os
import uuid
from decimal import Decimal

import boto3

TABLE_NAME = os.environ.get("TABLE_NAME", "books")
FIELDS = {"title": str, "author": str, "year": int}

_table = None


def table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(TABLE_NAME)
    return _table


def to_json(value):
    """DynamoDB returns numbers as Decimal; convert them for JSON."""
    if isinstance(value, list):
        return [to_json(v) for v in value]
    if isinstance(value, dict):
        return {k: to_json(v) for k, v in value.items()}
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


def respond(status, body, event, context):
    arn_parts = (getattr(context, "invoked_function_arn", "") or "").split(":")
    served_by = {
        "stage": (event.get("requestContext") or {}).get("stage"),
        "lambdaVersion": getattr(context, "function_version", None),
        "lambdaAlias": arn_parts[7] if len(arn_parts) > 7 else None,
    }
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "X-Served-By": json.dumps(served_by)},
        "body": "" if body is None else json.dumps(to_json(body)),
    }


def validate_update(data):
    """API Gateway validates POST bodies with a model; PUT is checked here."""
    if not isinstance(data, dict) or not data:
        return "Body must be a JSON object with title, author and/or year"
    unknown = set(data) - set(FIELDS)
    if unknown:
        return f"Unknown field(s): {', '.join(sorted(unknown))}"
    for name, kind in FIELDS.items():
        if name in data and (not isinstance(data[name], kind) or isinstance(data[name], bool)):
            return f"'{name}' must be a {kind.__name__}"
    if "title" in data and not data["title"].strip():
        return "'title' cannot be empty"
    return None


def lambda_handler(event, context):
    method = event.get("httpMethod")
    book_id = (event.get("pathParameters") or {}).get("id")
    reply = lambda status, body=None: respond(status, body, event, context)
    try:
        body = json.loads(event["body"]) if event.get("body") else None
    except json.JSONDecodeError:
        return reply(400, {"message": "Body must be valid JSON"})

    if book_id is None and method == "GET":
        books = table().scan().get("Items", [])
        author = (event.get("queryStringParameters") or {}).get("author")
        if author:
            books = [b for b in books if b["author"].lower() == author.lower()]
        return reply(200, sorted(books, key=lambda b: b["title"]))

    if book_id is None and method == "POST":
        if not isinstance(body, dict) or "title" not in body or "author" not in body:
            return reply(400, {"message": "'title' and 'author' are required"})
        book = {"id": str(uuid.uuid4())[:8], **{k: body[k] for k in FIELDS if k in body}}
        table().put_item(Item=book)
        return reply(201, book)

    if book_id is not None and method == "GET":
        book = table().get_item(Key={"id": book_id}).get("Item")
        return reply(200, book) if book else reply(404, {"message": f"Book {book_id} not found"})

    if book_id is not None and method == "PUT":
        error = validate_update(body)
        if error:
            return reply(400, {"message": error})
        try:
            result = table().update_item(
                Key={"id": book_id},
                UpdateExpression="SET " + ", ".join(f"#{k} = :{k}" for k in body),
                ConditionExpression="attribute_exists(id)",
                ExpressionAttributeNames={f"#{k}": k for k in body},
                ExpressionAttributeValues={f":{k}": v for k, v in body.items()},
                ReturnValues="ALL_NEW",
            )
        except table().meta.client.exceptions.ConditionalCheckFailedException:
            return reply(404, {"message": f"Book {book_id} not found"})
        return reply(200, result["Attributes"])

    if book_id is not None and method == "DELETE":
        try:
            table().delete_item(Key={"id": book_id}, ConditionExpression="attribute_exists(id)")
        except table().meta.client.exceptions.ConditionalCheckFailedException:
            return reply(404, {"message": f"Book {book_id} not found"})
        return reply(204)

    return reply(405, {"message": f"{method} is not supported here"})
