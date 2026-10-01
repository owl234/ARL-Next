# backend/app/celeryconfig.py
"""Celery + RabbitMQ 配置"""

import os

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.environ.get("RABBITMQ_PASS", "admin")
RABBITMQ_VHOST = os.environ.get("RABBITMQ_VHOST", "/")

broker_url = "amqp://{}:{}@{}:{}/{}".format(
    RABBITMQ_USER, RABBITMQ_PASS,
    RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_VHOST)

MONGO_URI = os.environ.get(
    "MONGO_URI", "mongodb://admin:admin@mongodb:27017/arl")
result_backend = MONGO_URI

# 队列定义
task_queues = {
    "platform_fetch": {
        "exchange": "platform_fetch",
        "routing_key": "platform_fetch",
    },
    "scan": {
        "exchange": "scan",
        "routing_key": "scan",
    },
    "celery": {
        "exchange": "celery",
        "routing_key": "celery",
    },
}
task_default_queue = "celery"
task_default_exchange = "celery"
task_default_routing_key = "celery"
task_create_missing_queues = True

# 任务路由
task_routes = {
    "app.tasks.vuln_platform.fetch_*": {"queue": "platform_fetch"},
    "app.tasks.vuln_platform.dispatch_*": {"queue": "platform_fetch"},
    "app.tasks.vuln_platform.auto_submit_*": {"queue": "platform_fetch"},
    "app.tasks.vuln_platform.execute_scan": {"queue": "scan"},
}

# 可靠性
broker_transport_options = {"confirm_publish": True}
broker_heartbeat = 60
broker_connection_retry_on_startup = True

task_soft_time_limit = 3600
task_time_limit = 7200
task_acks_late = True
task_reject_on_worker_lost = True
worker_prefetch_multiplier = 1

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "Asia/Shanghai"
enable_utc = False
result_expires = 86400