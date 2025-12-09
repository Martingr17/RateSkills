from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.orm import Session
import logging
import os
from pathlib import Path
from datetime import datetime
import traceback

# ИСПОЛЬЗУЙТЕ АБСОЛЮТНЫЕ ИМПОРТЫ
from app.database import SessionLocal, engine, Base
from app.config import settings
from app.models import *
from app.api.api_v1 import api_router
from app.utils import is_development

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('skillmatrix.log')
    ]
)
logger = logging.getLogger(__name__)

# Create database tables
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")
except Exception as e:
    logger.error(f"Error creating database tables: {e}")

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=None,
    redoc_url=None,
    description="""
    SkillMatrix PRO API v3.0

    ## Features

    * **Authentication**: JWT-based auth with roles (employee, manager, admin, hr, director)
    * **Skills Management**: Create, read, update, delete skills and categories
    * **Assessments**: Self-assessments and manager approvals
    * **Reports**: Generate reports and export to CSV/JSON
    * **Dashboard**: Role-based dashboard with statistics
    * **Notifications**: Real-time notifications system

    ## Roles & Permissions

    1. **Employee**: Can self-assess skills, view own profile and progress
    2. **Manager**: Can manage team assessments, approve/reject, view team stats
    3. **HR**: Can manage users, skills, generate company-wide reports
    4. **Admin**: Full system access including configuration
    5. **Director**: Strategic overview and high-level reports

    ## Default Demo Accounts

    * **Employee**: user / 123
    * **Manager**: manager / 123
    * **HR/Admin**: admin / 123
    * **Backend Developer**: dev2 / 123
    * **Designer**: des1 / 123
    * **HR Specialist**: hr1 / 123
    """,
    terms_of_service="https://skillmatrix.example.com/terms/",
    contact={
        "name": "SkillMatrix Support",
        "url": "https://skillmatrix.example.com/support",
        "email": "support@skillmatrix.example.com",
    },
    license_info={
        "name": "Proprietary",
        "url": "https://skillmatrix.example.com/license",
    },
)

# Add middlewares
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# ================== ПУТИ К ФАЙЛАМ ==================
# Путь к вашему index.html в статике
STATIC_DIR = Path(__file__).parent / "static"
INDEX_HTML_PATH = STATIC_DIR / "index.html"

# Монтируем статические файлы (CSS, JS, изображения)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Include API router
app.include_router(api_router)

# ================== Middleware для игнорирования favicon ==================
@app.middleware("http")
async def ignore_favicon(request: Request, call_next):
    if request.url.path == "/favicon.ico":
        return Response(status_code=204)  # No Content
    return await call_next(request)

# ================== Функция для чтения index.html ==================
def get_frontend_html():
    """Читает index.html из статической директории"""
    try:
        if INDEX_HTML_PATH.exists():
            with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
                content = f.read()
                return content
        else:
            logger.error(f"index.html не найден: {INDEX_HTML_PATH}")
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>SkillMatrix Enterprise PRO</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        padding: 50px;
                        text-align: center;
                    }}
                    h1 {{ color: #6366f1; }}
                    code {{
                        background: #f1f5f9;
                        padding: 10px;
                        display: block;
                        margin: 10px 0;
                        border-radius: 5px;
                        font-family: monospace;
                    }}
                </style>
            </head>
            <body>
                <h1>⚠️ Файл index.html не найден</h1>
                <p>Файл должен находиться по пути:</p>
                <code>{INDEX_HTML_PATH}</code>
                <p>Проверьте что файл существует в директории app/static/</p>
                <div style="margin-top: 30px;">
                    <a href="/api/docs" style="color: #6366f1;">📚 API Документация</a> |
                    <a href="/api/health" style="color: #6366f1;">🩺 Проверить здоровье</a>
                </div>
            </body>
            </html>
            """
    except Exception as e:
        logger.error(f"Ошибка чтения index.html: {e}")
        return f"<h1>Ошибка загрузки фронтенда: {e}</h1>"

# ================== Главные эндпоинты для фронтенда ==================
@app.get("/", response_class=HTMLResponse)
async def root():
    """Сервит главную страницу фронтенда"""
    html_content = get_frontend_html()
    return HTMLResponse(content=html_content)

@app.get("/app", response_class=HTMLResponse)
async def app_page():
    """Альтернативный путь к приложению"""
    return await root()

@app.get("/index.html", response_class=HTMLResponse)
async def index_page():
    """Для совместимости с прямыми запросами"""
    return await root()

# ================== Обработчики ошибок ==================
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    logger.warning(f"HTTPException: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "code": exc.status_code,
            "message": exc.detail,
            "path": request.url.path,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "code": 422,
            "message": "Validation error",
            "details": exc.errors(),
            "path": request.url.path,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions"""
    logger.error(f"Unhandled exception: {exc}\n{traceback.format_exc()}")

    if is_development():
        detail = str(exc)
    else:
        detail = "Internal server error"

    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "code": 500,
            "message": detail,
            "path": request.url.path,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# ================== Документация API ==================
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Custom Swagger UI"""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )

@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    """Custom ReDoc"""
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
    )

# ================== Служебные эндпоинты ==================
@app.get("/health")
async def health_check():
    """Health check for load balancers and monitoring"""
    return {
        "status": "healthy",
        "service": "skillmatrix-backend",
        "version": settings.VERSION,
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected"
    }

@app.get("/api")
async def api_docs_redirect():
    """Redirect to API documentation"""
    return RedirectResponse(url="/docs")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

# ================== События запуска/остановки ==================
@app.on_event("startup")
async def startup_event():
    """Actions to perform on application startup"""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")

    # Логируем информацию о БД
    db_url = settings.DATABASE_URL
    if '@' in db_url:
        parts = db_url.split('@')
        if ':' in parts[0]:
            creds_host = parts[0].split(':')
            if len(creds_host) > 2:
                masked_url = f"postgresql://{creds_host[0]}:****@{parts[1]}"
                logger.info(f"Database URL: {masked_url}")
            else:
                logger.info(f"Database URL: {db_url.split('@')[-1]}")
        else:
            logger.info(f"Database URL: {parts[1]}")
    else:
        logger.info(f"Database URL: {db_url}")

    # Проверяем наличие index.html
    if INDEX_HTML_PATH.exists():
        file_size = INDEX_HTML_PATH.stat().st_size
        logger.info(f"✓ Frontend index.html found: {INDEX_HTML_PATH} ({file_size:,} bytes)")
    else:
        logger.warning(f"✗ Frontend index.html NOT found: {INDEX_HTML_PATH}")
        logger.info("Make sure index.html exists in app/static/ directory")

    # Создаем служебные директории
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    logger.info(f"Uploads directory: {uploads_dir}")

    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    logger.info(f"Reports directory: {reports_dir}")

@app.on_event("shutdown")
async def shutdown_event():
    """Actions to perform on application shutdown"""
    logger.info("Shutting down SkillMatrix backend")

# ================== Тестовые эндпоинты ==================
@app.get("/test-db")
async def test_database(db: Session = Depends(SessionLocal)):
    """Test database connection"""
    try:
        result = db.execute("SELECT 1").fetchone()
        return {
            "status": "success",
            "database": "connected",
            "test_query": result[0] if result else None
        }
    except Exception as e:
        logger.error(f"Database test failed: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")

@app.get("/version")
async def get_version():
    """Get application version information"""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "api_version": "v1",
        "build_date": settings.BUILD_DATE,
        "documentation": "/docs"
    }

# ================== SPA catch-all route ==================
@app.get("/{full_path:path}")
async def catch_all(full_path: str, request: Request):
    """Catch-all route for frontend routing (SPA support)"""

    # Если это API маршрут - возвращаем 404
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail=f"API endpoint {full_path} not found")

    # Если запрашивают статический файл - отдаем его
    if full_path.startswith("static/"):
        static_file = STATIC_DIR / full_path[7:]  # Убираем "static/" из пути
        if static_file.is_file():
            return FileResponse(static_file)

    # Если запрашивают favicon - игнорируем
    if full_path == "favicon.ico":
        return Response(status_code=204)

    # Для всех остальных маршрутов отдаем фронтенд (SPA)
    html_content = get_frontend_html()
    return HTMLResponse(content=html_content)

# ================== System info endpoint ==================
@app.get("/system/info")
async def system_info():
    """Get system information"""
    import platform
    import sys

    info = {
        "system": {
            "platform": platform.platform(),
            "python_version": sys.version,
            "hostname": platform.node(),
        },
        "application": {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG,
        },
        "frontend": {
            "index_html_path": str(INDEX_HTML_PATH),
            "exists": INDEX_HTML_PATH.exists(),
        }
    }

    if INDEX_HTML_PATH.exists():
        info["frontend"]["size"] = INDEX_HTML_PATH.stat().st_size
        info["frontend"]["size_human"] = f"{INDEX_HTML_PATH.stat().st_size:,} bytes"

    return info
