from fastapi import FastAPI # type: ignore
from pydantic import BaseModel, Field # type: ignore

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/personas/{persona_id}")
@app.post("/personas", status_code=status.HTTP_201_CREATED) # type: ignore
@app.put("/personas/{persona_id}")
@app.delete("/personas/{persona_id}", status_code=status.HTTP_204_NO_CONTENT) # type: ignore
    
class ProductoCrear(BaseModel):
    nombre: str = Field(..., min_length=1)
    precio: int = Field(..., gt=0)

class ProductoDB(ProductoCrear):
    id: int

base_de_datos: list[ProductoDB] = []
id_contador: int = 1

@app.post("/productos/", status_code=201, response_model=ProductoDB)