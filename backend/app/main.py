from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import auth, lots, products, analysis

app = FastAPI(
    title="Chip ATE Analysis System",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(lots.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")

@app.get("/")
def root():
    return {"status": "ok", "message": "Chip ATE System Running"}

@app.get("/health")
def health():
    return {"status": "healthy"}