"""Test Environment Firewall Middleware.

Enforces absolute separation between test runs and live application state:
1. Rejects any mutating test request (POST, PUT, DELETE, PATCH with X-HighView-Test-Run header)
   if received by a live or normal development instance.
2. Guarantees that mutating test operations are only processed when the backend is
   explicitly running in an isolated test environment (APP_ENV=test) backed by an ephemeral database.
"""
from __future__ import annotations

import os
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import config
from .db_isolation import LIVE_DB_PATH


class TestEnvironmentFirewallMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        test_run_id = (
            request.headers.get("x-highview-test-run")
            or request.headers.get("x-test-execution")
        )
        is_mutating = request.method in ("POST", "PUT", "DELETE", "PATCH")

        if test_run_id and is_mutating:
            is_isolated_backend = (
                (config.ENVIRONMENT == "test" or os.getenv("APP_ENV") == "test" or os.getenv("TESTING") == "true")
                and config.DB_PATH.resolve() != LIVE_DB_PATH
            )

            if not is_isolated_backend:
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "FORBIDDEN_TEST_MUTATION_ON_LIVE_INSTANCE",
                        "detail": (
                            f"CRITICAL TEST FIREWALL BREACH: Test execution '{test_run_id}' attempted "
                            f"{request.method} {request.url.path} against normal/live HighView instance. "
                            "Automated test mutations must execute exclusively against an isolated ephemeral backend."
                        ),
                    },
                )

        return await call_next(request)
