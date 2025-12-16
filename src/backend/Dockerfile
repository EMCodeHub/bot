FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY src/backend/requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir -r /workspace/requirements.txt

COPY src /workspace/src/

ENV PYTHONPATH=/workspace/src/backend:${PYTHONPATH}

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
