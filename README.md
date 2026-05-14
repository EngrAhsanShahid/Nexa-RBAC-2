# Nexa RBAC Backend

FastAPI backend for the Nexa RBAC system.

## What this service needs

- Python 3.11+
- MongoDB reachable from the backend container or local machine
- Optional but used by the app: Kafka, MinIO, LiveKit, and Gmail SMTP settings

## Quick Start

### Local run

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure your `.env` file.
4. Start the API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

5. Open the API docs:

```text
http://localhost:8000/docs
```

### Optional seed data

If you want the default roles, users, cameras, and alerts in MongoDB:

```bash
python seed_data.py
```

## Dockerized Setup

This repository is containerized with `Dockerfile` and `docker-compose.yml`.

### Build and start

```bash
docker compose up --build -d
```

### Stop

```bash
docker compose down
```

### Logs

```bash
docker compose logs -f backend
```

### Status

```bash
docker compose ps
```

## `.env` Configuration

Copy [`.env.example`](.env.example) to `.env` and update the values for your environment.

### Required or important variables

- `MONGO_URI`: MongoDB connection string
- `MONGO_DB`: Database name
- `SECRET_KEY`: JWT signing secret
- `FRONTEND_ORIGINS`: Allowed frontend URLs
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka broker address
- `KAFKA_ALERTS_TOPIC`: Kafka topic name
- `KAFKA_GROUP_ID`: Kafka consumer group id
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
- `GMAIL_EMAIL`, `GMAIL_APP_PASSWORD`, `GMAIL_SMTP_HOST`, `GMAIL_SMTP_PORT`

### Updating `.env`

If you change any `.env` value:

1. Update the file.
2. Restart the backend container.

```bash
docker compose up --build -d
```

## Docker Notes

- The compose file starts only the backend service.
- MongoDB is expected to be available from the `MONGO_URI` value in `.env`.
- The backend listens on port `8000` inside the container and is published to `localhost:8000`.

## Useful Commands

```bash
docker compose up --build -d
docker compose down
docker compose restart backend
docker compose logs -f backend
```