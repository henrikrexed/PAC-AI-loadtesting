FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY otel_setup.py tools.py agent.py main.py ./

EXPOSE 8080
# Single worker: each turn is CPU-light but LLM-latency-bound; scale via replicas, not workers,
# so the OTel BatchSpanProcessor flush stays simple per-pod.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
