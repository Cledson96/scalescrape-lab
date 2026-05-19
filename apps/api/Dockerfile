FROM python:3.12-slim

WORKDIR /app
COPY packages/contracts ./packages/contracts
RUN pip install --no-cache-dir ./packages/contracts
COPY apps/api/pyproject.toml .
RUN pip install --no-cache-dir .
COPY apps/api/app ./app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

