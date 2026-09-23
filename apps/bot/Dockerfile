FROM python:3.12-slim
WORKDIR /app
RUN pip install aiogram httpx pydantic-settings
COPY . .
CMD ["python", "-m", "bot"]
