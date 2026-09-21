import json
import boto3
from decouple import config

_secret_cache = {}


def get_secret(secret_id="pd/ticobox/config", region_name=None):
    """Reads a Secrets Manager secret (JSON string) as a dict, cached per secret."""
    if secret_id in _secret_cache:
        return _secret_cache[secret_id]

    region = region_name or config("AWS_REGION", default="us-east-1")

    client = boto3.client(
        "secretsmanager",
        region_name=region,
    )

    response = client.get_secret_value(
        SecretId=secret_id
    )

    secret = json.loads(
        response["SecretString"]
    )

    _secret_cache[secret_id] = secret
    return secret