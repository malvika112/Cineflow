FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV CINEMAFLO_DB_PATH=/app/db/cinemaflo.db
ENV CINEMAFLO_ADMIN_TOKEN=admin-dev-token

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
