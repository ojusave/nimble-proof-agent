"""Translate the trusted loopback proxy's browser scope into a repository view."""
import re
from fastapi import HTTPException, Request


def workspace_repository(request: Request):
    workspace=request.headers.get('x-proof-workspace')
    if workspace is None:
        # Direct loopback API/CLI access retains the local workspace.
        return request.app.state.repository
    if not re.fullmatch(r'[a-f0-9]{64}',workspace):
        raise HTTPException(400,'Invalid browser workspace.')
    return request.app.state.repository.scoped(workspace)
