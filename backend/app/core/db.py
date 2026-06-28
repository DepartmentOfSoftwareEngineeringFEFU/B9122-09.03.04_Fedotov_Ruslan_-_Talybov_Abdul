import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

SQLALCHEMY_DATABASE_URL = (
    f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}@"
    f"{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DB}"
)

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def check_db() -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def init_db() -> None:
    """Deprecated: schema changes are managed through Alembic migrations.

    Kept only for old imports/tests. Do not call this from application startup.
    """
    logger.warning("init_db() is deprecated; run `alembic upgrade head` instead")
    check_db()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
