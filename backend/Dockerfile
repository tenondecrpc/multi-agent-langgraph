FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
COPY README.md .
COPY alembic.ini .
COPY alembic/ alembic/
COPY src/ src/

RUN uv pip install --system "uvicorn[standard]>=0.34" .

EXPOSE 8000

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
