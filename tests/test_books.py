"""Unit tests for the Books Lambda, using moto to fake DynamoDB (no AWS account needed).

Run:  pip install -r requirements-dev.txt && pytest -v
"""
import json
import os
import sys
from types import SimpleNamespace

import boto3
import pytest
from moto import mock_aws

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ["TABLE_NAME"] = "books-test"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import books  # noqa: E402

CONTEXT = SimpleNamespace(function_version="3",
                          invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:books:live")


@pytest.fixture(autouse=True)
def dynamodb():
    with mock_aws():
        boto3.client("dynamodb").create_table(
            TableName="books-test",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        books._table = None
        yield
        books._table = None


def call(method, book_id=None, body=None, query=None, stage="dev"):
    event = {
        "httpMethod": method,
        "pathParameters": {"id": book_id} if book_id else None,
        "queryStringParameters": query,
        "body": body if isinstance(body, str) or body is None else json.dumps(body),
        "requestContext": {"stage": stage},
    }
    res = books.lambda_handler(event, CONTEXT)
    return res["statusCode"], (json.loads(res["body"]) if res["body"] else None), res["headers"]


def test_create_and_get():
    status, book, _ = call("POST", body={"title": "Learning SQL", "author": "Alan Beaulieu", "year": 2020})
    assert status == 201
    assert book["year"] == 2020 and len(book["id"]) == 8
    status, fetched, _ = call("GET", book["id"])
    assert status == 200 and fetched == book


def test_list_sorted_and_filtered_by_author():
    call("POST", body={"title": "Zeta", "author": "Ama"})
    call("POST", body={"title": "Alpha", "author": "Kofi"})
    call("POST", body={"title": "Beta", "author": "ama"})
    _, all_books, _ = call("GET")
    assert [b["title"] for b in all_books] == ["Alpha", "Beta", "Zeta"]
    _, by_ama, _ = call("GET", query={"author": "AMA"})
    assert [b["title"] for b in by_ama] == ["Beta", "Zeta"]


def test_update():
    _, book, _ = call("POST", body={"title": "Draft", "author": "Me"})
    status, updated, _ = call("PUT", book["id"], {"title": "Final", "year": 2026})
    assert status == 200
    assert updated == {**book, "title": "Final", "year": 2026}


@pytest.mark.parametrize("body", [{}, {"isbn": "123"}, {"year": "2020"}, {"year": True}, {"title": "  "}, [1]])
def test_update_validation(body):
    _, book, _ = call("POST", body={"title": "X", "author": "Y"})
    assert call("PUT", book["id"], body)[0] == 400


def test_delete():
    _, book, _ = call("POST", body={"title": "Temp", "author": "Y"})
    assert call("DELETE", book["id"])[0] == 204
    assert call("GET", book["id"])[0] == 404
    assert call("DELETE", book["id"])[0] == 404


def test_missing_book_returns_404():
    assert call("GET", "nope")[0] == 404
    assert call("PUT", "nope", {"title": "X"})[0] == 404


def test_invalid_json_and_missing_fields():
    assert call("POST", body="{not json")[0] == 400
    assert call("POST", body={"title": "No author"})[0] == 400


def test_served_by_header_shows_stage_and_version():
    _, _, headers = call("GET", stage="prod")
    assert json.loads(headers["X-Served-By"]) == {"stage": "prod", "lambdaVersion": "3", "lambdaAlias": "live"}


def test_unsupported_method():
    assert call("PATCH")[0] == 405
