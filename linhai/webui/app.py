"""WebUI FastAPI应用。"""

import os
import sys

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routes import router as agents_router, config_router
from .schemas import AuthRequest

_AUTH_WHITELIST_PATHS = frozenset({"/health", "/api/auth"})


def create_app() -> FastAPI:
    """创建并配置FastAPI应用。

    初始化时生成随机API token并打印到stderr。
    注意：通过stdio泄漏密钥的问题是已知限制，后续会解决。
    """
    token = os.urandom(16).hex()
    print(token, file=sys.stderr)

    app = FastAPI(
        title="LinHai WebUI API",
        description="LinHai多Agent管理接口",
        version="0.1.0",
    )

    app.state.api_token = token

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        if request.url.path in _AUTH_WHITELIST_PATHS:
            return await call_next(request)
        if request.cookies.get("api_token") == token:
            return await call_next(request)
        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized"},
        )

    @app.post("/api/auth")
    async def authenticate(request: AuthRequest):
        if request.api_key == token:
            response = JSONResponse({"status": "ok"})
            response.set_cookie("api_token", token)
            return response
        raise HTTPException(status_code=403, detail="Invalid API key")

    app.include_router(agents_router)
    app.include_router(config_router)

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    return app
