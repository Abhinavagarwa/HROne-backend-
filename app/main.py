from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

app = FastAPI()

# MongoDB setup
MONGO_URL = "mongodb://localhost:27017"
client = AsyncIOMotorClient(MONGO_URL)
db = client["ecommerce"]

# Pydantic models
class ProductCreate(BaseModel):
    name: str
    description: str
    price: int
    size: str

class ProductOut(ProductCreate):
    id: str

class OrderCreate(BaseModel):
    user_id: str
    products: List[str]

class OrderOut(BaseModel):
    id: str
    user_id: str
    products: List[str]

# Helper to convert MongoDB documents to dicts with string IDs
def obj_id(doc):
    doc["id"] = str(doc.pop("_id"))
    return doc

# 1. Create Product
@app.post("/products", status_code=201)
async def create_product(product: ProductCreate):
    result = await db.products.insert_one(product.dict())
    if result.inserted_id:
        return {"message": "Product created successfully"}
    raise HTTPException(status_code=500, detail="Failed to create product")

# 2. List Products
@app.get("/products", response_model=List[ProductOut])
async def list_products(
    name: Optional[str] = Query(None),
    size: Optional[str] = Query(None),
    limit: int = Query(10, ge=1),
    offset: int = Query(0, ge=0)
):
    query = {}
    if name:
        query["name"] = {"$regex": name, "$options": "i"}
    if size:
        query["size"] = size
    cursor = db.products.find(query).skip(offset).limit(limit)
    products = [obj_id(prod) async for prod in cursor]
    return products

# 3. Create Order
@app.post("/orders", status_code=201)
async def create_order(order: OrderCreate):
    # Validate product IDs
    for pid in order.products:
        if not await db.products.find_one({"_id": ObjectId(pid)}):
            raise HTTPException(status_code=404, detail=f"Product {pid} not found")
    order_data = {
        "user_id": order.user_id,
        "products": [ObjectId(pid) for pid in order.products]
    }
    result = await db.orders.insert_one(order_data)
    if result.inserted_id:
        return {"message": "Order created successfully"}
    raise HTTPException(status_code=500, detail="Failed to create order")

# 4. List Orders by User
@app.get("/orders/{user_id}", response_model=List[OrderOut])
async def list_orders_by_user(
    user_id: str,
    limit: int = Query(10, ge=1),
    offset: int = Query(0, ge=0)
):
    cursor = db.orders.find({"user_id": user_id}).skip(offset).limit(limit)
    orders = []
    async for doc in cursor:
        doc = obj_id(doc)
        doc["products"] = [str(pid) for pid in doc.get("products", [])]
        orders.append(doc)
    return orders
