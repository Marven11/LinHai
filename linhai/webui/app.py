"""WebUI FastAPI应用。"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routes import router as agents_router, config_router, problem_router
from .schemas import AuthRequest

_AUTH_WHITELIST_PATHS = frozenset({"/health", "/api/auth"})


def create_app(api_token: str) -> FastAPI:
    """创建并配置FastAPI应用。

    Args:
        api_token: API认证token，用于验证请求。
    """
    token = api_token

    app = FastAPI(
        title="LinHai WebUI API",
        description="LinHai多Agent管理接口",
        version="0.3.0",
    )

    app.state.api_token = token

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r".*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
        if request.url.path in _AUTH_WHITELIST_PATHS:
            return await call_next(request)
        auth_header = request.headers.get("authorization", "")
        if (
            auth_header.startswith("Bearer ") and auth_header[7:] == token
        ) or request.query_params.get("token") == token:
            return await call_next(request)
        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized"},
        )

    @app.post("/api/auth")
    async def authenticate(request: AuthRequest):
        if request.api_key == token:
            return JSONResponse({"status": "ok", "token": token})
        raise HTTPException(status_code=403, detail="Invalid API key")

    app.include_router(agents_router)
    app.include_router(config_router)
    app.include_router(problem_router)

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    return app
