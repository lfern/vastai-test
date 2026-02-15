# Imagen mínima con Python para el CLI de Vast.ai
FROM python:3.12-slim

RUN pip install --no-cache-dir vastai

# El CLI guarda la API key en ~/.config/vastai/vast_api_key (o ~/.vast_api_key).
# Monta un volumen en runtime a /root/.config/vastai para persistir la key.
ENV HOME=/root
WORKDIR /workspace

ENTRYPOINT ["vastai"]
CMD ["--help"]
