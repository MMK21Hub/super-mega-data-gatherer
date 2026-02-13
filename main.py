from fastapi import FastAPI

app = FastAPI()


@app.get("/api/v1/super-mega-stats")
async def super_mega_stats():
    return {"message": "Hello World"}
