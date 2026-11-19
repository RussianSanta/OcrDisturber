"""GitHub release lookup and update package download."""


class GitHubUpdateDownloader:
    """Retrieves release metadata and update files from GitHub."""

    def check_latest_release(self, repository: str) -> None:
        """Look up the latest release for a GitHub repository."""
        pass

    def download_release(self, download_url: str, destination: str) -> None:
        """Download a release asset to the selected destination."""
        pass
