import json
import boto3

_secret_cache = None


def get_secret(secret_id="pd/ticobox/config"):
    global _secret_cache

    if _secret_cache:
        return _secret_cache

    client = boto3.client(
        "secretsmanager",
        region_name="us-east-1"
    )

    response = client.get_secret_value(
        SecretId=secret_id
    )

    _secret_cache = json.loads(
        response["SecretString"]
    )

    return _secret_cache