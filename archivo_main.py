from fastapi import FastAPI # type: ignore

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/personas/{persona_id}")
@app.post("/personas", status_code=status.HTTP_201_CREATED) # type: ignore
@app.put("/personas/{persona_id}")
@app.delete("/personas/{persona_id}", status_code=status.HTTP_204_NO_CONTENT) # type: ignore