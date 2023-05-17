import json

import requests

from lib.logger import logger

# https://docs.github.com/en/rest/metrics/traffic#about-repository-traffic

class GitMetric:
    def __init__(self, owner: str, repo: str, token: str):
        self.repo = repo
        self.owner = owner
        self.token = token

        self.headers = {
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Accept": "application/vnd.github.v3+json"
        }

        self.base_url = "https://api.github.com"
        self.repo_url = f"{self.base_url}/repos/{owner}/{repo}"
        self.referrers_url = f"{self.repo_url}/traffic/popular/referrers"
        self.paths_url = f"{self.repo_url}/traffic/popular/paths"
        self.views_url = f"{self.repo_url}/traffic/views"
        self.clones_url = f"{self.repo_url}/traffic/clones"
        self.forks_url = f"{self.repo_url}/forks"

    def _get_response(self, url: str):
        result = {}
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.HTTPError as err:
            logger.error(f"HTTP error occurred: {err}")
        return result

    def get_referrers(self) -> list:
        logger.info(f"Getting referrers for {self.repo}")
        response = self._get_response(self.referrers_url)
        return response

    def get_paths(self) -> list:
        logger.info(f"Getting paths for {self.repo}")
        response = self._get_response(self.paths_url)
        return response

    def get_views(self) -> dict:
        logger.info(f"Getting views for {self.repo}")
        response = self._get_response(self.views_url)
        return response

    def get_clones(self) -> dict:
        logger.info(f"Getting clones for {self.repo}")
        response = self._get_response(self.clones_url)
        return response

    def get_forks(self) -> list:
        logger.info(f"Getting forks for {self.repo}")
        results = []
        page_counter = 1
        keep_going = True
        while keep_going:
            logger.info(f"Checking page page {page_counter} of forks...")
            response = self._get_response(f"{self.forks_url}?per_page=100&page={page_counter}")
            results = results + response
            page_counter += 1
            if len(response) < 100:
                keep_going = False
        return results
