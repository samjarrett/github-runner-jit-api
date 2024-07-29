import os
import json
import uuid

import requests
import boto3

import auth

GITHUB_AUTH_MODE = os.environ.get("GITHUB_AUTH_MODE")
GITHUB_PAT = os.environ.get("GITHUB_PAT", "")
GITHUB_APP_ID = os.environ.get("GITHUB_APP_ID", "")
GITHUB_APP_PRIVATE_KEY = os.environ.get("GITHUB_APP_PRIVATE_KEY", "")
GITHUB_APP_INSTALLATION_ID = os.environ.get("GITHUB_APP_INSTALLATION_ID")

GITHUB_ORG = os.environ.get("GITHUB_ORG", "")
GITHUB_RUNNER_GROUP_ID = int(os.environ.get("GITHUB_RUNNER_GROUP_ID", "1"))
GITHUB_RUNNER_LABELS = os.environ.get("GITHUB_RUNNER_LABELS", "self-hosted").split(",")
DEFAULT_RUNNER_NAME = os.environ.get("DEFAULT_RUNNER_NAME", "")


# if we're in app mode, and the private key doesn't appear private key-ey
# assume it's a string to a SSM parameter
if (
    GITHUB_AUTH_MODE == "APP"
    and "-----BEGIN RSA PRIVATE KEY-----" not in GITHUB_APP_PRIVATE_KEY
):
    GITHUB_APP_PRIVATE_KEY = (
        boto3.client("ssm")
        .get_parameter(Name=GITHUB_APP_PRIVATE_KEY, WithDecryption=True)
        .get("Parameter", {})
        .get("Value", "")
    )


class GithubException(RuntimeError):
    """A Github exception"""


def get_github_auth() -> auth.GithubAuth:
    """Get a Github Auth object"""
    if GITHUB_AUTH_MODE == "APP":
        return auth.GithubAppAuth(
            GITHUB_APP_ID,
            GITHUB_APP_PRIVATE_KEY,
            GITHUB_ORG,
            GITHUB_APP_INSTALLATION_ID,
        )

    return auth.GithubPATAuth(GITHUB_PAT)


def get_jit_config(runner_name: str, labels: list[str]) -> str:
    """Retrieve a JIT config"""
    url = f"https://api.github.com/orgs/{GITHUB_ORG}/actions/runners/generate-jitconfig"

    github_auth = get_github_auth()

    response = requests.post(
        url,
        json={
            "name": runner_name,
            "runner_group_id": GITHUB_RUNNER_GROUP_ID,
            "labels": labels,
        },
        headers={
            "Authorization": f"Bearer {github_auth.get_bearer_token()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    response.raise_for_status()

    return response.json()["encoded_jit_config"]


def main(event, _):
    """The main entry point"""
    runner_name = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("iam", {})
        .get("userId", f"uid:{DEFAULT_RUNNER_NAME}")
        .split(":")[-1]
    )

    labels = GITHUB_RUNNER_LABELS
    event_labels = event.get("queryStringParameters", "").get("labels")
    if event_labels:
        labels.extend(event_labels.split(","))

    try:
        jit_config = get_jit_config(runner_name, labels)
    except GithubException as exc:
        if "Already exists" not in str(exc):
            raise
        jit_config = get_jit_config(f"{runner_name}-{uuid.uuid4()}", labels)

    return {
        "statusCode": 200,
        "body": jit_config,
    }


if __name__ == "__main__":
    print(main({}, None))
