FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY data ./data

RUN pip install --no-cache-dir .

COPY scripts ./scripts

EXPOSE 8000

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
