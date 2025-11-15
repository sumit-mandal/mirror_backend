from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware 
from apis.users import router as users_router

app = FastAPI(title= "Backend for MirrorMinds")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(users_router)

@app.get("/ping")
def read_root():
    return {"message": "Healthy server "}