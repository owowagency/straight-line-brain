FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

FROM python:3.12-slim AS runtime

WORKDIR /app
COPY --from=builder /install /usr/local
COPY alembic.ini .
COPY alembic/ ./alembic/
COPY src/ ./src/
COPY scripts/ ./scripts/

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
