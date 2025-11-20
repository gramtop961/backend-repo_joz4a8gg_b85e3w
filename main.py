import os
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bson import ObjectId

from database import db, create_document, get_documents

app = FastAPI(title="EcoTrail Gear API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProductModel(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    sale_price: Optional[float] = None
    category: str
    brand: str
    images: List[str] = []
    sustainability: List[str] = []
    rating: float = 0
    review_count: int = 0
    in_stock: bool = True
    features: List[str] = []


class SearchSuggestion(BaseModel):
    type: str
    label: str
    value: str


# Helpers
class ObjectIdEncoder:
    @staticmethod
    def transform(doc: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(doc, dict):
            return doc
        out = {}
        for k, v in doc.items():
            if isinstance(v, ObjectId):
                out[k] = str(v)
            elif isinstance(v, list):
                out[k] = [ObjectIdEncoder.transform(i) for i in v]
            elif isinstance(v, dict):
                out[k] = ObjectIdEncoder.transform(v)
            else:
                out[k] = v
        return out


@app.get("/")
def read_root():
    return {"message": "EcoTrail Gear backend running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": [],
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, "name") else "Unknown"
            _ = db.list_collection_names()
            response["collections"] = _
            response["database"] = "✅ Connected & Working"
            response["connection_status"] = "Connected"
    except Exception as e:
        response["database"] = f"⚠️ Issue: {str(e)[:80]}"
    return response


@app.on_event("startup")
def seed_products_if_empty():
    if db is None:
        return
    if db["product"].count_documents({}) == 0:
        sample: List[dict] = [
            {
                "name": "Evergreen Ultralight Tent 2P",
                "description": "Carbon-neutral, recycled fly fabric, storm-ready.",
                "price": 429.0,
                "sale_price": 389.0,
                "category": "Carbon-Neutral Camping Equipment",
                "brand": "EcoTrail",
                "images": [
                    "https://images.unsplash.com/photo-1504280390368-3971fc7cbe22",
                    "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee",
                ],
                "sustainability": ["carbon-neutral", "recycled"],
                "rating": 4.7,
                "review_count": 214,
                "in_stock": True,
                "features": ["waterproof", "ultralight", "packable"],
            },
            {
                "name": "Summit Flow Recycled Fleece",
                "description": "Cozy warmth from 100% recycled fibers.",
                "price": 129.0,
                "sale_price": None,
                "category": "Recycled Material Hiking Gear",
                "brand": "EcoTrail",
                "images": [
                    "https://images.unsplash.com/photo-1519710164239-da123dc03ef4",
                    "https://images.unsplash.com/photo-1520975922291-6ce663cc0ae8",
                ],
                "sustainability": ["recycled", "fair-trade"],
                "rating": 4.5,
                "review_count": 98,
                "in_stock": True,
                "features": ["insulated", "packable"],
            },
            {
                "name": "TrailSpark Solar Charger",
                "description": "Renewable energy for off-grid adventures.",
                "price": 89.0,
                "sale_price": 79.0,
                "category": "Renewable Energy Outdoor Accessories",
                "brand": "EcoTrail",
                "images": [
                    "https://images.unsplash.com/photo-1509395176047-4a66953fd231",
                    "https://images.unsplash.com/photo-1530693090124-102a1c1c58c6",
                ],
                "sustainability": ["renewable", "carbon-neutral"],
                "rating": 4.3,
                "review_count": 61,
                "in_stock": True,
                "features": ["waterproof"],
            },
        ]
        for p in sample:
            create_document("product", p)


@app.get("/api/impact")
def get_impact_metrics():
    return {
        "trees_planted": 182345,
        "bottles_recycled": 12983457,
        "carbon_offset_kg": 9238456,
    }


@app.get("/api/search", response_model=List[SearchSuggestion])
def search(q: str = Query("")):
    suggestions: List[SearchSuggestion] = []
    if db is not None and q.strip():
        regex = {"$regex": q, "$options": "i"}
        for doc in db["product"].find({"$or": [{"name": regex}, {"category": regex}, {"brand": regex}]}, {"name": 1, "category": 1}).limit(8):
            suggestions.append(SearchSuggestion(type="product", label=doc.get("name", ""), value=str(doc.get("_id"))))
        # Category suggestions
        cats = db["product"].distinct("category", {"category": regex})
        for c in cats[:3]:
            suggestions.append(SearchSuggestion(type="category", label=c, value=c))
    else:
        # Fallback featured suggestions
        suggestions = [
            SearchSuggestion(type="category", label="Carbon-Neutral Camping Equipment", value="Carbon-Neutral Camping Equipment"),
            SearchSuggestion(type="category", label="Recycled Material Hiking Gear", value="Recycled Material Hiking Gear"),
            SearchSuggestion(type="category", label="Renewable Energy Outdoor Accessories", value="Renewable Energy Outdoor Accessories"),
        ]
    return suggestions


@app.get("/api/products")
def list_products(
    page: int = 1,
    limit: int = 12,
    sort: str = "relevance",
    category: Optional[str] = None,
    sustainability: Optional[str] = None,  # comma-separated
    features: Optional[str] = None,  # comma-separated
    q: Optional[str] = None,
):
    if db is None:
        # Simple fallback data if DB not configured
        items = [
            {"name": "Sample Product", "price": 10.0, "category": "Sample", "images": ["https://images.unsplash.com/photo-1500530855697-b586d89ba3ee"], "rating": 4.2, "review_count": 10, "sustainability": ["recycled"], "in_stock": True},
        ]
        return {"items": items, "total": len(items)}

    filter_q: Dict[str, Any] = {}

    if category:
        filter_q["category"] = category

    if q:
        filter_q["$or"] = [{"name": {"$regex": q, "$options": "i"}}, {"brand": {"$regex": q, "$options": "i"}}, {"category": {"$regex": q, "$options": "i"}}]

    if sustainability:
        filter_q["sustainability"] = {"$all": [s.strip() for s in sustainability.split(",") if s.strip()]}

    if features:
        filter_q["features"] = {"$all": [f.strip() for f in features.split(",") if f.strip()]}

    sort_map = {
        "price_asc": ("price", 1),
        "price_desc": ("price", -1),
        "newest": ("created_at", -1),
        "highest_rated": ("rating", -1),
        "best_sellers": ("review_count", -1),
        "most_sustainable": ("sustainability_len", -1),
    }

    pipeline = [{"$match": filter_q}]

    if sort == "most_sustainable":
        pipeline.append({"$addFields": {"sustainability_len": {"$size": {"$ifNull": ["$sustainability", []]}}}})
    sort_field, direction = sort_map.get(sort, ("created_at", -1))
    pipeline.append({"$sort": {sort_field: direction}})

    total = list(db["product"].aggregate(pipeline + [{"$count": "count"}]))
    total_count = total[0]["count"] if total else 0

    pipeline += [
        {"$skip": max(0, (page - 1) * limit)},
        {"$limit": limit},
    ]

    items = list(db["product"].aggregate(pipeline))
    items = [ObjectIdEncoder.transform(i) for i in items]

    return {"items": items, "total": total_count}


@app.post("/api/saved-searches")
def save_search(payload: Dict[str, Any]):
    """Save user-defined filters (anonymous demo)."""
    if db is None:
        return {"status": "ok"}
    _id = create_document("savedsearch", payload)
    return {"id": _id}


@app.get("/api/categories")
def get_categories():
    cats = [
        {"key": "camping", "label": "Carbon-Neutral Camping Equipment", "icon": "Tent"},
        {"key": "hiking", "label": "Recycled Material Hiking Gear", "icon": "Mountain"},
        {"key": "energy", "label": "Renewable Energy Outdoor Accessories", "icon": "Sun"},
    ]
    return cats


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
