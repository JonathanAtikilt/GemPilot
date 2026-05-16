from pathlib import Path


FRONTEND_PAGE = Path(__file__).resolve().parents[1] / "frontend" / "app" / "page.tsx"


def test_frontend_uses_backend_owned_github_oauth_flow():
    source = FRONTEND_PAGE.read_text(encoding="utf-8")

    assert "/github/connect" in source
    assert "github_connection_id" in source
    assert "github_auth_code" not in source
    assert "NEXT_PUBLIC_GITHUB_CLIENT_ID" not in source
    assert "https://github.com/login/oauth/authorize" not in source
