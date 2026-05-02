from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timedelta
from bson import ObjectId
from database import db
from auth import hash_password, verify_password, create_token, decode_token

router = APIRouter(prefix="/api/admin", tags=["Admin"])

ADMIN_SECRET = "nexusai-admin-v6-2025"  # ← change before going live

class AdminLoginRequest(BaseModel):
    username: str
    password: str

def require_admin(token: dict = Depends(decode_token)):
    if not token.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return token

# ── Seed first admin ───────────────────────────────────────────────
@router.post("/seed")
def seed_admin(secret: str):
    if secret != ADMIN_SECRET:
        raise HTTPException(403, "Wrong secret key")
    if db.admins.find_one({"username": "admin"}):
        raise HTTPException(400, "Admin already exists")
    db.admins.insert_one({
        "username": "admin", "password": hash_password("admin123"),
        "name": "Super Admin", "created_at": datetime.utcnow(),
    })
    return {"message": "✅ Admin created! username: admin | password: admin123 — CHANGE IMMEDIATELY!"}

# ── Admin login ────────────────────────────────────────────────────
@router.post("/login")
def admin_login(req: AdminLoginRequest):
    admin = db.admins.find_one({"username": req.username})
    if not admin or not verify_password(req.password, admin["password"]):
        raise HTTPException(401, "Invalid admin credentials")
    token = create_token({"id": str(admin["_id"]), "email": admin["username"], "name": admin.get("name","Admin"), "is_admin": True})
    return {"token": token, "admin": {"name": admin.get("name","Admin"), "username": admin["username"]}}

# ── Stats ──────────────────────────────────────────────────────────
@router.get("/stats")
def get_stats(token: dict = Depends(require_admin)):
    total_users  = db.users.count_documents({})
    total_chats  = db.chat_history.count_documents({})
    banned_users = db.users.count_documents({"banned": True})
    week_ago     = datetime.utcnow() - timedelta(days=7)
    new_signups  = db.users.count_documents({"created_at": {"$gte": week_ago}})

    tool_stats = list(db.chat_history.aggregate([
        {"$group": {"_id": "$tool",  "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]))
    model_stats = list(db.chat_history.aggregate([
        {"$group": {"_id": "$model", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]))
    top_users = list(db.chat_history.aggregate([
        {"$group": {"_id": "$user_email", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}, {"$limit": 5}]))

    return {
        "total_users": total_users, "active_users": total_users - banned_users,
        "banned_users": banned_users, "total_chats": total_chats, "recent_signups": new_signups,
        "tool_stats":  [{"tool":  r["_id"], "count": r["count"]} for r in tool_stats],
        "model_stats": [{"model": r["_id"], "count": r["count"]} for r in model_stats],
        "top_users":   [{"email": r["_id"], "chats": r["count"]} for r in top_users],
    }

# ── Users ──────────────────────────────────────────────────────────
@router.get("/users")
def get_users(token: dict = Depends(require_admin)):
    users = list(db.users.find({}, {"password": 0}).sort("created_at", -1))
    return {"users": [{
        "id": str(u["_id"]), "name": u["name"], "email": u["email"],
        "avatar": u.get("avatar", u["name"][0].upper()),
        "banned": u.get("banned", False),
        "chat_count": db.chat_history.count_documents({"user_email": u["email"]}),
        "created_at": u["created_at"].isoformat() if u.get("created_at") else "",
    } for u in users]}

@router.patch("/users/{user_id}/ban")
def toggle_ban(user_id: str, token: dict = Depends(require_admin)):
    u = db.users.find_one({"_id": ObjectId(user_id)})
    if not u: raise HTTPException(404, "User not found")
    new_status = not u.get("banned", False)
    db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"banned": new_status}})
    return {"banned": new_status, "email": u["email"]}

@router.delete("/users/{user_id}")
def delete_user(user_id: str, token: dict = Depends(require_admin)):
    u = db.users.find_one({"_id": ObjectId(user_id)})
    if not u: raise HTTPException(404, "User not found")
    db.users.delete_one({"_id": ObjectId(user_id)})
    deleted = db.chat_history.delete_many({"user_email": u["email"]}).deleted_count
    return {"deleted": True, "email": u["email"], "chats_removed": deleted}

# ── History ────────────────────────────────────────────────────────
@router.get("/history")
def get_all_history(tool: str=None, email: str=None, model: str=None,
                    token: dict=Depends(require_admin)):
    q = {}
    if tool:  q["tool"]       = tool
    if email: q["user_email"] = email
    if model: q["model"]      = model
    items = list(db.chat_history.find(q, {"_id": 0}).sort("created_at", -1).limit(100))
    for i in items: i["created_at"] = i["created_at"].isoformat()
    return {"history": items, "count": len(items)}

@router.delete("/history/{email}")
def delete_user_history(email: str, token: dict=Depends(require_admin)):
    deleted = db.chat_history.delete_many({"user_email": email}).deleted_count
    return {"deleted": deleted, "email": email}

@router.get("/health")
def admin_health(token: dict=Depends(require_admin)):
    return {"status": "ok", "version": "6.0.0", "models": ["claude","openai","gemini","deepseek"],
            "collections": {"users": db.users.count_documents({}), "admins": db.admins.count_documents({}), "chat_history": db.chat_history.count_documents({})}}