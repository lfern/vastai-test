FROM python:3.12-slim

RUN pip install --no-cache-dir fastapi uvicorn[standard] httpx vastai

WORKDIR /app
COPY *.py ./
COPY static/ ./static/
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
