from celery import Celery

from .config import get_settings

settings = get_settings()

celery_app = Celery(
    "haqnow_community",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks"],
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # Dead letter queue and retry configuration
    task_reject_on_worker_lost=True,
    task_acks_late=True,
    worker_disable_rate_limits=True,
    # Routing for different task types
    task_routes={
        "app.tasks.process_document_ocr": {"queue": "ocr"},
        "app.tasks.process_document_tiling": {"queue": "processing"},
        "app.tasks.process_document_thumbnails": {"queue": "processing"},
        "app.tasks.convert_document_to_pdf_task": {"queue": "processing"},
        "monitor_stuck_jobs": {"queue": "celery"},  # Use default queue for monitoring
    },
    # Default retry policy
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    # Periodic tasks
    beat_schedule={
        "monitor-stuck-jobs": {
            "task": "monitor_stuck_jobs",
            "schedule": 300.0,  # Every 5 minutes
        },
    },
)
