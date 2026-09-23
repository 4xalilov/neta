FROM python:3.12-slim
WORKDIR /app
# ffmpeg: Telegram voice (ogg/opus) <-> wav/mp3 (engine/integrations/audio.py, roadmap 5.10)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
RUN pip install uv
COPY pyproject.toml .
RUN uv pip install --system -e ".[dev]"
COPY . .
