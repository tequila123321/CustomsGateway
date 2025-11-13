from fastapi import FastAPI

app = FastAPI(title="Customs AI Gateway")

@app.get("/")
def home():
    return {"message": "Customs AI Gateway is running!"}