import pytest

from app.repository_url import parse_github_url


def test_parse_https_url():
    slug = parse_github_url("https://github.com/openai/openai-python")
    assert slug.owner == "openai"
    assert slug.name == "openai-python"
    assert slug.full_name == "openai/openai-python"


def test_parse_git_url():
    slug = parse_github_url("git@github.com:owner/repo.git")
    assert slug.full_name == "owner/repo"


def test_rejects_non_github_url():
    with pytest.raises(ValueError):
        parse_github_url("https://example.com/owner/repo")
