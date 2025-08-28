from celery import Celery

from .config import get_settings

settings = get_settings()

celery_app = Celery(
    "haqnow_community",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks"],
)

# Configure Celery - Optimized for sequential processing
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Optimized batch processing configuration
    worker_prefetch_multiplier=2,  # Allow 2 tasks per worker for better throughput
    worker_disable_rate_limits=True,
    worker_max_tasks_per_child=100,  # Restart workers after 100 tasks to prevent memory leaks
    # Task timeouts to prevent stuck jobs - increased for batch processing
    task_time_limit=25 * 60,  # 25 minutes max per task
    task_soft_time_limit=20 * 60,  # 20 minutes soft limit
    # Routing for different task types
    task_routes={
        "app.tasks.process_document_ocr": {"queue": "ocr"},
        "app.tasks.process_document_tiling": {"queue": "processing"},
        "app.tasks.process_document_thumbnails": {"queue": "processing"},
        "app.tasks.convert_document_to_pdf_task": {"queue": "processing"},
        "monitor_stuck_jobs": {"queue": "celery"},  # Use default queue for monitoring
    },
    # Periodic tasks
    beat_schedule={
        "monitor-stuck-jobs": {
            "task": "monitor_stuck_jobs",
            "schedule": 300.0,  # Every 5 minutes
        },
    },
)
