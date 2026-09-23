from fastapi import FastAPI

app = FastAPI(title="AI Marketing & Content Engine")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
