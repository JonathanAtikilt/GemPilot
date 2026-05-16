from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from agent.dependencies import get_github_connection_service
from agent.github_oauth import GitHubConnectionService, GitHubOAuthError

router = APIRouter(prefix="/github", tags=["github"])


@router.get("/connect")
async def connect_github(
    return_to: str | None = Query(default=None),
    service: GitHubConnectionService = Depends(get_github_connection_service),
) -> RedirectResponse:
    try:
        pending = service.create_pending_connection(return_to)
    except GitHubOAuthError as exc:
        raise _http_error(exc) from exc
    return RedirectResponse(pending.authorization_url)


@router.get("/callback")
async def github_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    service: GitHubConnectionService = Depends(get_github_connection_service),
) -> RedirectResponse:
    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid GitHub OAuth state",
        )

    try:
        record = service.complete_callback(code=code, state=state)
    except GitHubOAuthError as exc:
        raise _http_error(exc) from exc
    return RedirectResponse(service.redirect_url_for_completed_callback(record))


def _http_error(exc: GitHubOAuthError) -> HTTPException:
    message = str(exc) or "GitHub OAuth failed."
    status_code = (
        status.HTTP_503_SERVICE_UNAVAILABLE
        if "not configured" in message.lower()
        else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code=status_code, detail=message)
