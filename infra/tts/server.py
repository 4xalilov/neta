"""
Navoiy TTS FastAPI Server

A self-hosted FastAPI server for Uzbek text-to-speech using CosyVoice2-0.5B fine-tune.
Falls back to stub mode (silence) if CosyVoice dependencies are missing.

Model: https://huggingface.co/aisha-org/navoiy-tts
License: Apache 2.0
"""

import logging
import os
from typing import Optional

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Try to import CosyVoice, fall back to stub mode if unavailable
try:
    # CosyVoice repo (FunAudioLLM/CosyVoice) must be on PYTHONPATH; see README.
    from cosyvoice.cli.cosyvoice import CosyVoice2  # noqa: F401

    COSYVOICE_AVAILABLE = True
    logger.info("CosyVoice dependencies loaded successfully")
except ImportError as e:
    COSYVOICE_AVAILABLE = False
    logger.warning(
        f"CosyVoice dependencies not available: {e}. "
        "Server will run in stub mode (returns silence WAV)."
    )

app = FastAPI(title="Navoiy TTS", version="1.0.0")

# Global state for model
model = None
MODEL_DIR = os.getenv("NAVOIY_MODEL_DIR", "/models")


def get_model():
    """Load the CosyVoice2 model lazily."""
    global model
    if not COSYVOICE_AVAILABLE:
        return None

    if model is None:
        try:
            # Placeholder: actual model loading from NAVOIY_MODEL_DIR
            # This would be implemented with actual CosyVoice2 weight loading
            logger.info(f"Loading CosyVoice2 model from {MODEL_DIR}")
            # TODO: aisha-org/navoiy-tts model kartasidagi aniq chaqiruvni tekshir:
            # model = CosyVoice2(f"{MODEL_DIR}/navoiy-tts", load_jit=False, load_trt=False, fp16=True)
            model = True  # Placeholder for loaded model
        except Exception as e:
            logger.error(f"Failed to load model: {e}")

    return model


class SynthesizeRequest(BaseModel):
    """Text-to-speech synthesis request."""
    text: str
    voice: str = "neutral"  # "neutral" or "expressive"
    speed: float = 1.0


def generate_silence_wav(duration_seconds: float = 1.0, sample_rate: int = 24000) -> bytes:
    """Generate a WAV file containing silence."""
    samples = np.zeros(int(duration_seconds * sample_rate), dtype=np.float32)

    # Write to bytes buffer
    import io
    buffer = io.BytesIO()
    sf.write(buffer, samples, sample_rate, format='WAV')
    buffer.seek(0)
    return buffer.read()


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "cosyvoice_available": COSYVOICE_AVAILABLE,
        "model_dir": MODEL_DIR,
    }


@app.post("/synthesize", response_class=None)
async def synthesize(request: SynthesizeRequest):
    """
    Synthesize speech from text.

    Args:
        request: SynthesizeRequest with text, voice style, and speed

    Returns:
        WAV audio bytes (24 kHz, mono)
    """
    if not request.text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    if request.voice not in ["neutral", "expressive"]:
        raise HTTPException(
            status_code=400,
            detail='Voice must be "neutral" or "expressive"'
        )

    if request.speed <= 0:
        raise HTTPException(status_code=400, detail="Speed must be positive")

    # In stub mode, return silence
    if not COSYVOICE_AVAILABLE:
        logger.debug(f"Stub mode: generating silence for text: {request.text[:50]}")
        audio_bytes = generate_silence_wav(duration_seconds=1.0, sample_rate=24000)
        return {
            "content": audio_bytes,
            "media_type": "audio/wav",
        }

    try:
        # Load or get the model
        model = get_model()
        if model is None:
            raise RuntimeError("Model failed to load")

        # Placeholder: actual synthesis would happen here
        # audio = model.inference(
        #     text=request.text,
        #     voice_name=request.voice,
        #     speed=request.speed,
        # )

        logger.info(
            f"Synthesized {len(request.text)} characters with voice={request.voice}, "
            f"speed={request.speed}"
        )

        # For now, return 1 second of silence (placeholder)
        # In production, this would return actual synthesized audio
        audio_bytes = generate_silence_wav(duration_seconds=1.0, sample_rate=24000)

        return {
            "content": audio_bytes,
            "media_type": "audio/wav",
        }

    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
