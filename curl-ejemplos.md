# Ollama con curl (ejemplos directos)

Si prefieres usar solo `curl` sin scripts, aquí tienes ejemplos.

## Una sola pregunta (sin streaming)

```bash
curl -s http://localhost:11434/api/generate -d '{
  "model": "llama3.3",
  "prompt": "¿Qué es Python?",
  "stream": false
}'
```

La respuesta es un JSON; el texto está en el campo `"response"`. Con **jq** puedes quedarte solo con el texto:

```bash
curl -s http://localhost:11434/api/generate -d '{
  "model": "llama3.3",
  "prompt": "¿Qué es Python?",
  "stream": false
}' | jq -r '.response'
```

## Una pregunta con streaming (token a token)

```bash
curl -s -N http://localhost:11434/api/generate -d '{
  "model": "llama3.3",
  "prompt": "¿Qué es Python?",
  "stream": true
}'
```

Cada línea es un objeto JSON con `"response"` (y a veces vacío). Para ver solo el texto con jq:

```bash
curl -s -N http://localhost:11434/api/generate -d '{
  "model": "llama3.3",
  "prompt": "¿Qué es Python?",
  "stream": true
}' | while read -r line; do echo "$line" | jq -r '.response // empty'; done
```

## Chat con historial (varios mensajes)

Endpoint: `POST /api/chat` con un array `messages`.

```bash
curl -s http://localhost:11434/api/chat -d '{
  "model": "llama3.3",
  "messages": [
    {"role": "user", "content": "Mi nombre es Ana."},
    {"role": "assistant", "content": "Hola Ana, encantado."},
    {"role": "user", "content": "¿Cómo me llamo?"}
  ],
  "stream": false
}' | jq -r '.message.content'
```

## Listar modelos

```bash
curl -s http://localhost:11434/api/tags | jq '.models[].name'
```

Sin jq:

```bash
curl -s http://localhost:11434/api/tags
```

## Variables de entorno útiles

- `OLLAMA_HOST`: si Ollama está en otra máquina/puerto (ej. `http://192.168.1.10:11434`).
- En los scripts: `OLLAMA_URL` y `MODEL` (ver `ask.sh` y `chat.sh`).
