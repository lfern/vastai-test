FROM python:3.12-slim

RUN pip install --no-cache-dir fastapi uvicorn[standard] httpx vastai

WORKDIR /app
COPY *.py ./
COPY static/ ./static/

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "11434"]
