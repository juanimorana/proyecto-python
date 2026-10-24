from datetime import date, time
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String, Time, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker

# Configuración de la Base de Datos SQLite
SQLALCHEMY_DATABASE_URL = "sqlite:///./ventas.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ==========================================
# MODELOS SQLAlchemy (Base de Datos)
# ==========================================

class ProductoModel(Base):
    __tablename__ = "productos"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nombre = Column(String, nullable=False)
    precio = Column(Float, nullable=False)

    items_carrito = relationship("CarritoProductoModel", back_populates="producto")


class CarritoProductoModel(Base):
    __tablename__ = "carrito_producto"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_carrito = Column(Integer, ForeignKey("carritos.id"), nullable=False)
    id_producto = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Integer, nullable=False)

    carrito = relationship("CarritoModel", back_populates="productos")
    producto = relationship("ProductoModel", back_populates="items_carrito")


class CarritoModel(Base):
    __tablename__ = "carritos"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    fecha_creacion = Column(Date, nullable=False)
    estado = Column(String, nullable=False)  # "abierto" o "cerrado"

    productos = relationship(
        "CarritoProductoModel",
        back_populates="carrito",
        cascade="all, delete-orphan",
    )
    venta = relationship(
        "VentaModel", back_populates="carrito", uselist=False, foreign_keys="VentaModel.id_carrito"
    )


class VentaModel(Base):
    __tablename__ = "ventas"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    fecha = Column(Date, nullable=False)
    hora = Column(Time, nullable=False)
    id_carrito = Column(Integer, ForeignKey("carritos.id"), unique=True, nullable=False)

    carrito = relationship("CarritoModel", back_populates="venta", foreign_keys=[id_carrito])


Base.metadata.create_all(bind=engine)


# Dependencia de BD
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==========================================
# ESQUEMAS Pydantic (Validación y Serialización)
# ==========================================

# --- Productos ---
class ProductoCreate(BaseModel):
    nombre: str
    precio: float

class ProductoUpdate(BaseModel):
    nombre: Optional[str] = None
    precio: Optional[float] = None

class ProductoResponse(BaseModel):
    id: int
    nombre: str
    precio: float

    class Config:
        from_attributes = True


# --- Carritos ---
class CarritoProductoCreate(BaseModel):
    id_producto: int
    cantidad: int

class ProductoEnCarrito(BaseModel):
    id: int
    producto: ProductoResponse
    cantidad: int

    class Config:
        from_attributes = True

class CarritoCreate(BaseModel):
    fecha_creacion: date
    estado: str

class CarritoUpdate(BaseModel):
    fecha_creacion: Optional[date] = None
    estado: Optional[str] = None

class CarritoResponse(BaseModel):
    id: int
    fecha_creacion: date
    estado: str
    productos: List[ProductoEnCarrito] = []

    class Config:
        from_attributes = True


# --- Ventas ---
class VentaCreate(BaseModel):
    fecha: date
    hora: time
    id_carrito: int

class VentaUpdate(BaseModel):
    fecha: Optional[date] = None
    hora: Optional[time] = None
    id_carrito: Optional[int] = None

class AsignarCarritoRequest(BaseModel):
    id_carrito: int

class VentaResponse(BaseModel):
    id: int
    fecha: date
    hora: time
    precio_total: float
    carrito: CarritoResponse

    class Config:
        from_attributes = True


# ==========================================
# APLICACIÓN FASTAPI
# ==========================================

app = FastAPI(title="API Gestión de Ventas - UNLa 2026", version="1.0.0")


def calcular_precio_total_venta(carrito: CarritoModel) -> float:
    total = 0.0
    if carrito and carrito.productos:
        for item in carrito.productos:
            total += item.producto.precio * item.cantidad
    return total


# ==========================================
# ENDPOINTS: PRODUCTOS (ABM A)
# ==========================================

@app.post("/productos", response_model=ProductoResponse, status_code=status.HTTP_201_CREATED)
def crear_producto(prod: ProductoCreate, db: Session = Depends(get_db)):
    db_prod = ProductoModel(nombre=prod.nombre, precio=prod.precio)
    db.add(db_prod)
    db.commit()
    db.refresh(db_prod)
    return db_prod


@app.get("/productos", response_model=List[ProductoResponse])
def listar_productos(db: Session = Depends(get_db)):
    return db.query(ProductoModel).all()


@app.get("/productos/{id}", response_model=ProductoResponse)
def obtener_producto(id: int, db: Session = Depends(get_db)):
    prod = db.query(ProductoModel).filter(ProductoModel.id == id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return prod


@app.put("/productos/{id}", response_model=ProductoResponse)
def actualizar_producto(id: int, prod_data: ProductoUpdate, db: Session = Depends(get_db)):
    prod = db.query(ProductoModel).filter(ProductoModel.id == id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    if prod_data.nombre is not None:
        prod.nombre = prod_data.nombre
    if prod_data.precio is not None:
        prod.precio = prod_data.precio
        
    db.commit()
    db.refresh(prod)
    return prod


@app.delete("/productos/{id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_producto(id: int, db: Session = Depends(get_db)):
    prod = db.query(ProductoModel).filter(ProductoModel.id == id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Regla de negocio: No se debe permitir eliminar un producto registrado en algún carrito
    en_carrito = db.query(CarritoProductoModel).filter(CarritoProductoModel.id_producto == id).first()
    if en_carrito:
        raise HTTPException(status_code=400, detail="No se puede eliminar un producto que está registrado en algún carrito.")
    
    db.delete(prod)
    db.commit()
    return None


# ==========================================
# ENDPOINTS: CARRITO (ABM C)
# ==========================================

@app.post("/carritos", response_model=CarritoResponse, status_code=status.HTTP_201_CREATED)
def crear_carrito(carrito: CarritoCreate, db: Session = Depends(get_db)):
    db_carrito = CarritoModel(fecha_creacion=carrito.fecha_creacion, estado=carrito.estado)
    db.add(db_carrito)
    db.commit()
    db.refresh(db_carrito)
    return db_carrito


@app.get("/carritos", response_model=List[CarritoResponse])
def listar_carritos(db: Session = Depends(get_db)):
    return db.query(CarritoModel).all()


@app.get("/carritos/{id}", response_model=CarritoResponse)
def obtener_carrito(id: int, db: Session = Depends(get_db)):
    carrito = db.query(CarritoModel).filter(CarritoModel.id == id).first()
    if not carrito:
        raise HTTPException(status_code=404, detail="Carrito no encontrado")
    return carrito


@app.put("/carritos/{id}", response_model=CarritoResponse)
def actualizar_carrito(id: int, carrito_data: CarritoUpdate, db: Session = Depends(get_db)):
    carrito = db.query(CarritoModel).filter(CarritoModel.id == id).first()
    if not carrito:
        raise HTTPException(status_code=404, detail="Carrito no encontrado")
    
    # Regla: Un carrito asociado a una venta no puede ser modificado
    if carrito.venta:
        raise HTTPException(status_code=400, detail="El carrito está asociado a una venta y no puede ser modificado.")
    
    if carrito_data.fecha_creacion is not None:
        carrito.fecha_creacion = carrito_data.fecha_creacion
    if carrito_data.estado is not None:
        carrito.estado = carrito_data.estado
        
    db.commit()
    db.refresh(carrito)
    return carrito


@app.delete("/carritos/{id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_carrito(id: int, db: Session = Depends(get_db)):
    carrito = db.query(CarritoModel).filter(CarritoModel.id == id).first()
    if not carrito:
        raise HTTPException(status_code=404, detail="Carrito no encontrado")
    
    # Regla: Si el carrito se encuentra asociado a una venta, no se puede eliminar
    if carrito.venta:
        raise HTTPException(status_code=400, detail="El carrito está asociado a una venta y no puede ser eliminado.")
    
    db.delete(carrito)
    db.commit()
    return None


@app.post("/carritos/{id}/productos", response_model=CarritoResponse)
def agregar_producto_carrito(id: int, item: CarritoProductoCreate, db: Session = Depends(get_db)):
    carrito = db.query(CarritoModel).filter(CarritoModel.id == id).first()
    if not carrito:
        raise HTTPException(status_code=404, detail="Carrito no encontrado")
    
    # Regla: Carrito asociado a venta no puede modificarse
    if carrito.venta:
        raise HTTPException(status_code=400, detail="El carrito está asociado a una venta y no se puede modificar.")
    
    # Regla: Solo en estado 'abierto'
    if carrito.estado != "abierto":
        raise HTTPException(status_code=400, detail="Solo se pueden agregar productos a carritos con estado 'abierto'.")
    
    # Regla: Cantidad mayor a 0
    if item.cantidad <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a 0.")
    
    # Regla: Producto debe existir
    producto = db.query(ProductoModel).filter(ProductoModel.id == item.id_producto).first()
    if not producto:
        raise HTTPException(status_code=404, detail="El producto indicado no existe.")
    
    # Verificar si ya está en el carrito
    item_existente = db.query(CarritoProductoModel).filter(
        CarritoProductoModel.id_carrito == id,
        CarritoProductoModel.id_producto == item.id_producto
    ).first()
    
    if item_existente:
        item_existente.cantidad += item.cantidad
    else:
        nuevo_item = CarritoProductoModel(
            id_carrito=id,
            id_producto=item.id_producto,
            cantidad=item.cantidad
        )
        db.add(nuevo_item)
        
    db.commit()
    db.refresh(carrito)
    return carrito


@app.delete("/carritos/{id}/productos/{id_producto}", response_model=CarritoResponse)
def quitar_producto_carrito(id: int, id_producto: int, db: Session = Depends(get_db)):
    carrito = db.query(CarritoModel).filter(CarritoModel.id == id).first()
    if not carrito:
        raise HTTPException(status_code=404, detail="Carrito no encontrado")
    
    # Regla: Carrito asociado a venta no puede modificarse
    if carrito.venta:
        raise HTTPException(status_code=400, detail="El carrito está asociado a una venta y no se puede modificar.")
    
    # Regla: Solo estado 'abierto'
    if carrito.estado != "abierto":
        raise HTTPException(status_code=400, detail="Solo se pueden quitar productos de carritos con estado 'abierto'.")
    
    item_existente = db.query(CarritoProductoModel).filter(
        CarritoProductoModel.id_carrito == id,
        CarritoProductoModel.id_producto == id_producto
    ).first()
    
    if not item_existente:
        raise HTTPException(status_code=404, detail="El producto no se encuentra en el carrito.")
    
    db.delete(item_existente)
    db.commit()
    db.refresh(carrito)
    return carrito


# ==========================================
# ENDPOINTS: VENTAS (ABM B)
# ==========================================

@app.post("/ventas", response_model=VentaResponse, status_code=status.HTTP_201_CREATED)
def crear_venta(venta: VentaCreate, db: Session = Depends(get_db)):
    carrito = db.query(CarritoModel).filter(CarritoModel.id == venta.id_carrito).first()
    if not carrito:
        raise HTTPException(status_code=404, detail="El carrito indicado no existe.")
    
    # Regla: Carrito no debe estar asociado a otra venta
    if carrito.venta:
        raise HTTPException(status_code=400, detail="El carrito ya se encuentra asociado a otra venta.")
    
    # Regla: Carrito debe tener estado 'cerrado'
    if carrito.estado != "cerrado":
        raise HTTPException(status_code=400, detail="Solo se puede asociar un carrito con estado 'cerrado' a una venta.")
    
    db_venta = VentaModel(
        fecha=venta.fecha,
        hora=venta.hora,
        id_carrito=venta.id_carrito
    )
    db.add(db_venta)
    db.commit()
    db.refresh(db_venta)
    
    response_data = VentaResponse(
        id=db_venta.id,
        fecha=db_venta.fecha,
        hora=db_venta.hora,
        precio_total=calcular_precio_total_venta(db_venta.carrito),
        carrito=db_venta.carrito
    )
    return response_data


@app.get("/ventas", response_model=List[VentaResponse])
def listar_ventas(db: Session = Depends(get_db)):
    ventas = db.query(VentaModel).all()
    resultado = []
    for v in ventas:
        resultado.append(
            VentaResponse(
                id=v.id,
                fecha=v.fecha,
                hora=v.hora,
                precio_total=calcular_precio_total_venta(v.carrito),
                carrito=v.carrito
            )
        )
    return resultado


@app.get("/ventas/{id}", response_model=VentaResponse)
def obtener_venta(id: int, db: Session = Depends(get_db)):
    v = db.query(VentaModel).filter(VentaModel.id == id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    
    return VentaResponse(
        id=v.id,
        fecha=v.fecha,
        hora=v.hora,
        precio_total=calcular_precio_total_venta(v.carrito),
        carrito=v.carrito
    )


@app.put("/ventas/{id}", response_model=VentaResponse)
def actualizar_venta(id: int, venta_data: VentaUpdate, db: Session = Depends(get_db)):
    v = db.query(VentaModel).filter(VentaModel.id == id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    
    if venta_data.fecha is not None:
        v.fecha = venta_data.fecha
    if venta_data.hora is not None:
        v.hora = venta_data.hora
    if venta_data.id_carrito is not None and venta_data.id_carrito != v.id_carrito:
        nuevo_carrito = db.query(CarritoModel).filter(CarritoModel.id == venta_data.id_carrito).first()
        if not nuevo_carrito:
            raise HTTPException(status_code=404, detail="El nuevo carrito no existe.")
        if nuevo_carrito.venta and nuevo_carrito.venta.id != id:
            raise HTTPException(status_code=400, detail="El nuevo carrito ya está asociado a otra venta.")
        if nuevo_carrito.estado != "cerrado":
            raise HTTPException(status_code=400, detail="El nuevo carrito debe tener estado 'cerrado'.")
        v.id_carrito = venta_data.id_carrito
        
    db.commit()
    db.refresh(v)
    
    return VentaResponse(
        id=v.id,
        fecha=v.fecha,
        hora=v.hora,
        precio_total=calcular_precio_total_venta(v.carrito),
        carrito=v.carrito
    )


@app.delete("/ventas/{id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_venta(id: int, db: Session = Depends(get_db)):
    v = db.query(VentaModel).filter(VentaModel.id == id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    
    db.delete(v)
    db.commit()
    return None


@app.post("/ventas/{id}/carrito", response_model=VentaResponse)
def asignar_carrito_a_venta(id: int, body: AsignarCarritoRequest, db: Session = Depends(get_db)):
    v = db.query(VentaModel).filter(VentaModel.id == id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    
    nuevo_carrito = db.query(CarritoModel).filter(CarritoModel.id == body.id_carrito).first()
    if not nuevo_carrito:
        raise HTTPException(status_code=404, detail="El carrito indicado no existe.")
    
    # Regla: Si el carrito se encuentra asociado a otra venta, devolver error
    if nuevo_carrito.venta and nuevo_carrito.venta.id != id:
        raise HTTPException(status_code=400, detail="El carrito ya está asociado a otra venta.")
    
    # Regla: El carrito debe estar en estado 'cerrado'
    if nuevo_carrito.estado != "cerrado":
        raise HTTPException(status_code=400, detail="El carrito debe tener estado 'cerrado' para asignarse a una venta.")
    
    v.id_carrito = body.id_carrito
    db.commit()
    db.refresh(v)
    
    return VentaResponse(
        id=v.id,
        fecha=v.fecha,
        hora=v.hora,
        precio_total=calcular_precio_total_venta(v.carrito),
        carrito=v.carrito
    )