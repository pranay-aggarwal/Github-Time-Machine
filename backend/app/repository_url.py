from dataclasses import dataclass
import re


@dataclass(frozen=True)
class RepoSlug:
    owner: str
    name: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


def parse_github_url(repo_url: str) -> RepoSlug:
    patterns = [
        r"github\.com[:/](?P<owner>[^/\s]+)/(?P<name>[^/\s]+?)(?:\.git)?/?$",
        r"^https?://github\.com/(?P<owner>[^/\s]+)/(?P<name>[^/\s]+?)(?:\.git)?/?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, repo_url)
        if match:
            return RepoSlug(match.group("owner"), match.group("name"))
    raise ValueError("Only GitHub repository URLs are supported.")
