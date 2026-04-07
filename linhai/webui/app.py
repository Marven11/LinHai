"""WebUI FastAPI应用。"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router as agents_router


def create_app() -> FastAPI:
    """创建并配置FastAPI应用。"""
    app = FastAPI(
        title="LinHai WebUI API",
        description="LinHai多Agent管理接口",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(agents_router)

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    return app
