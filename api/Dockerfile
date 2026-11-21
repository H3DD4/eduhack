FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY api/pyproject.toml ./api/
COPY api/thinkfirst ./api/thinkfirst
RUN pip install --no-cache-dir ./api
COPY api/alembic ./api/alembic
COPY api/alembic.ini ./api/
COPY worker ./worker
WORKDIR /app/api
EXPOSE 8000
CMD ["uvicorn", "thinkfirst.main:app", "--host", "0.0.0.0", "--port", "8000"]
