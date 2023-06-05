import os
import json
import urllib3
import uuid


GITHUB_AUTH_MODE = os.environ.get("GITHUB_AUTH_MODE")
GITHUB_PAT = os.environ.get("GITHUB_PAT", "")
GITHUB_ORG = os.environ.get("GITHUB_ORG", "")
GITHUB_RUNNER_GROUP_ID = int(os.environ.get("GITHUB_RUNNER_GROUP_ID", "1"))
GITHUB_RUNNER_LABELS = os.environ.get("GITHUB_RUNNER_LABELS", "self-hosted").split(",")
DEFAULT_RUNNER_NAME = os.environ.get("DEFAULT_RUNNER_NAME", "")


class GithubException(RuntimeError):
    """A Github exception"""


def get_bearer_token() -> str:
    """Retrieve a bearer token"""
    if GITHUB_AUTH_MODE == "PAT":
        return GITHUB_PAT

    return ""


def get_jit_config(runner_name: str) -> str:
    """Retrieve a JIT config"""
    url = f"https://api.github.com/orgs/{GITHUB_ORG}/actions/runners/generate-jitconfig"

    http = urllib3.PoolManager()
    response = http.request(
        "POST",
        url,
        json={
            "name": runner_name,
            "runner_group_id": GITHUB_RUNNER_GROUP_ID,
            "labels": GITHUB_RUNNER_LABELS,
        },
        headers={
            "Authorization": f"Bearer {get_bearer_token()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    json_response = json.loads(response.data)
    if response.status != 201:
        raise GithubException(json_response.get("message", response.data))

    return json_response["encoded_jit_config"]


def main(event, _):
    """The main entry point"""
    print(json.dumps(event))
    runner_name = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("iam", {})
        .get("userId", f"uid:{DEFAULT_RUNNER_NAME}")
        .split(":")[-1]
    )

    try:
        jit_config = get_jit_config(runner_name)
    except GithubException as exc:
        if "Already exists" not in str(exc):
            raise
        jit_config = get_jit_config(f"{runner_name}-{uuid.uuid4()}")

    return {
        "statusCode": 200,
        "body": jit_config,
    }


if __name__ == "__main__":
    print(main({}, None))
