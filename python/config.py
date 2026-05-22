import os
from dotenv import load_dotenv

load_dotenv()

REDIS_URL    = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:@localhost:5432/office_tools_development")
QUEUE_KEY    = "office_tools:jobs"
PROCESSING_QUEUE_KEY = f"{QUEUE_KEY}:processing"
MAX_WORKBOOK_SIZE_BYTES = int(os.getenv("MAX_WORKBOOK_SIZE_MB", "30")) * 1024 * 1024
# Rails Active Storage writes files here; must match the Docker volume mount path
STORAGE_ROOT = os.getenv("STORAGE_ROOT", "/rails/storage")
