FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir uv && uv pip install --system -e .
CMD ["python", "-m", "bot"]
