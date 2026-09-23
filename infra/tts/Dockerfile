FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    numpy \
    soundfile \
    torch \
    torchaudio

# Optional section: CosyVoice and Navoiy TTS installation
# Uncomment the following lines to enable full TTS support
# RUN pip install --no-cache-dir \
#     huggingface-hub \
#     FunAudioLLM

# Copy the server code
COPY server.py .

# Create models directory
RUN mkdir -p /models

EXPOSE 8010

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8010"]
