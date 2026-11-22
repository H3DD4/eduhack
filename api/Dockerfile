FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# Dependencies first, in their own layer: code changes do not re-download every package.
COPY api/pyproject.toml ./api/
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('api/pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt \
    && pip install --no-cache-dir --retries 10 --timeout 60 -r /tmp/requirements.txt
COPY api/thinkfirst ./api/thinkfirst
COPY api/tutor ./api/tutor
RUN pip install --no-cache-dir --no-deps ./api
COPY api/alembic ./api/alembic
COPY api/alembic.ini ./api/
COPY worker ./worker
WORKDIR /app/api
EXPOSE 8000
CMD ["uvicorn", "thinkfirst.main:app", "--host", "0.0.0.0", "--port", "8000"]
