from typing import Optional
from abc import ABC, abstractmethod
from time import time
import json

import jwt
import requests


class GithubAuth(ABC):
    """Base class for all Github Auth providers"""

    @abstractmethod
    def get_bearer_token(self) -> str:
        """Produce a bearer token"""


class GithubPATAuth(GithubAuth):
    pat: str

    def __init__(self, pat: str):
        self.pat = pat

    def get_bearer_token(self) -> str:
        """Produce a bearer token using a PAT"""
        return self.pat


class GithubAppAuth(GithubAuth):
    integration_id: str
    private_key: str
    github_org: str
    installation_id: Optional[str]

    def __init__(
        self,
        integration_id: str,
        private_key: str,
        github_org: str,
        installation_id: Optional[str] = None,
    ) -> None:
        self.integration_id = integration_id
        self.private_key = private_key
        self.github_org = github_org
        self.installation_id = installation_id

    def create_jwt(self, expiration: int = 60) -> str:
        """
        Creates a signed JWT, valid for 60 seconds by default.
        The expiration can be extended beyond this, to a maximum of 600 seconds.

        :param expiration: int
        :return string:
        """
        now = int(time())
        payload = {"iat": now, "exp": now + expiration, "iss": self.integration_id}
        encrypted = jwt.encode(payload, key=self.private_key, algorithm="RS256")

        if isinstance(encrypted, bytes):
            encrypted = encrypted.decode("utf-8")

        return encrypted

    def get_installation_access_token_url(self) -> str:
        """Get the installation ID"""
        if self.installation_id:
            return f"https://api.github.com/app/installations/{self.installation_id}/access_tokens"

        url = f"https://api.github.com/orgs/{self.github_org}/installation"

        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {self.create_jwt()}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

        response.raise_for_status()

        return response.json()["access_tokens_url"]

    def get_installation_access_token(self, url: str) -> str:
        """Get the installation ID"""
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.create_jwt()}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

        response.raise_for_status()

        return response.json()["token"]

    def get_bearer_token(self) -> str:
        """Produce a bearer token using a Github Application"""
        access_token_url = self.get_installation_access_token_url()

        return self.get_installation_access_token(access_token_url)
