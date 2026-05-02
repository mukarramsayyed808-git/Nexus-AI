from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from dotenv import load_dotenv
import httpx, os

from database import db
from auth import hash_password, verify_password, create_token, decode_token
from admin import router as admin_router

load_dotenv()

app = FastAPI(title="Nexus AI V6 — 4 Models", version="6.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(admin_router)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# ── API Keys ───────────────────────────────────────────────────────
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_KEY    = os.getenv("OPENAI_API_KEY",    "")
GEMINI_KEY    = os.getenv("GEMINI_API_KEY",    "")
DEEPSEEK_KEY  = os.getenv("DEEPSEEK_API_KEY",  "")

# ── Pydantic models ────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ChatMessage(BaseModel):
    role: str
    content: str

class ClaudeRequest(BaseModel):
    messages: List[ChatMessage]
    system: Optional[str]           = None
    tool: Optional[str]             = "chat"
    model_preference: Optional[str] = "gemini"

class ProfileUpdate(BaseModel):
    name: Optional[str]     = None
    password: Optional[str] = None

# ── Static routes ──────────────────────────────────────────────────
@app.get("/")
def root():
    idx = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(idx): return FileResponse(idx)
    return {"message": "Nexus AI V6", "models": ["claude","openai","gemini","deepseek"], "docs": "/docs"}

@app.get("/app")
def serve_app():
    p = os.path.join(FRONTEND_DIR, "app.html")
    if os.path.exists(p): return FileResponse(p)
    raise HTTPException(404, "app.html not found")

@app.get("/admin")
def serve_admin():
    p = os.path.join(FRONTEND_DIR, "admin.html")
    if os.path.exists(p): return FileResponse(p)
    raise HTTPException(404, "admin.html not found")

# ── Register ───────────────────────────────────────────────────────
@app.post("/api/register")
def register(req: RegisterRequest):
    if db.users.find_one({"email": req.email}):
        raise HTTPException(400, "Email already registered")
    if len(req.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    user = {
        "name": req.name, "email": req.email,
        "password": hash_password(req.password),
        "avatar": req.name[0].upper(),
        "banned": False, "is_admin": False,
        "created_at": datetime.utcnow(),
    }
    result = db.users.insert_one(user)
    token  = create_token({"id": str(result.inserted_id), "email": req.email,
                           "name": req.name, "is_admin": False})
    return {"token": token, "user": {"name": req.name, "email": req.email,
                                     "avatar": user["avatar"], "is_admin": False}}

# ── Login ──────────────────────────────────────────────────────────
@app.post("/api/login")
def login(req: LoginRequest):
    user = db.users.find_one({"email": req.email})
    if not user or not verify_password(req.password, user["password"]):
        raise HTTPException(401, "Invalid email or password")
    if user.get("banned"):
        raise HTTPException(403, "Account suspended. Contact support.")
    token = create_token({"id": str(user["_id"]), "email": user["email"],
                          "name": user["name"], "is_admin": user.get("is_admin", False)})
    return {"token": token, "user": {"name": user["name"], "email": user["email"],
                                     "avatar": user["name"][0].upper(),
                                     "is_admin": user.get("is_admin", False)}}

# ── Me ─────────────────────────────────────────────────────────────
@app.get("/api/me")
def me(token: dict = Depends(decode_token)):
    if token.get("is_admin"):
        return {"name": token.get("name","Admin"), "email": token.get("email",""),
                "avatar": token.get("name","A")[0].upper(), "is_admin": True}
    user = db.users.find_one({"email": token["email"]}, {"password": 0})
    if not user: raise HTTPException(404, "User not found")
    return {"name": user["name"], "email": user["email"],
            "avatar": user["name"][0].upper(), "is_admin": user.get("is_admin", False)}

@app.get("/api/is-admin")
def is_admin(token: dict = Depends(decode_token)):
    return {"is_admin": token.get("is_admin", False)}

# ── 4 Model AI Proxy ───────────────────────────────────────────────
@app.post("/api/claude")
async def ai_proxy(req: ClaudeRequest, token: dict = Depends(decode_token)):
    # Ban check
    if not token.get("is_admin"):
        u = db.users.find_one({"email": token["email"]})
        if u and u.get("banned"):
            raise HTTPException(403, "Account suspended.")

    model = (req.model_preference or "gemini").lower()
    reply = ""

    # ── CLAUDE ─────────────────────────────────────────────────────
    if model == "claude":
        if not ANTHROPIC_KEY:
            raise HTTPException(500, "ANTHROPIC_API_KEY not set in .env")
        payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 2000,
            "messages": [m.dict() for m in req.messages],
        }
        if req.system: payload["system"] = req.system
        async with httpx.AsyncClient(timeout=90) as c:
            r = await c.post("https://api.anthropic.com/v1/messages",
                headers={"Content-Type": "application/json",
                         "x-api-key": ANTHROPIC_KEY,
                         "anthropic-version": "2023-06-01"},
                json=payload)
        if r.status_code != 200:
            raise HTTPException(r.status_code, f"Claude error: {r.text}")
        reply = r.json()["content"][0]["text"]

    # ── OPENAI (ChatGPT) ────────────────────────────────────────────
    elif model == "openai":
        if not OPENAI_KEY:
            raise HTTPException(500, "OPENAI_API_KEY not set in .env")
        msgs = []
        if req.system: msgs.append({"role": "system", "content": req.system})
        msgs += [m.dict() for m in req.messages]
        async with httpx.AsyncClient(timeout=90) as c:
            r = await c.post("https://api.openai.com/v1/chat/completions",
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {OPENAI_KEY}"},
                json={"model": "gpt-4o-mini", "max_tokens": 2000, "messages": msgs})
        if r.status_code != 200:
            raise HTTPException(r.status_code, f"OpenAI error: {r.text}")
        reply = r.json()["choices"][0]["message"]["content"]

    # ── GEMINI ──────────────────────────────────────────────────────
    elif model == "gemini":
        if not GEMINI_KEY:
            raise HTTPException(500, "GEMINI_API_KEY not set in .env")
        contents = []
        if req.system:
            contents.append({"role": "user",  "parts": [{"text": f"[System]: {req.system}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood."}]})
        for m in req.messages:
            role = "model" if m.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m.content}]})
        async with httpx.AsyncClient(timeout=90) as c:
            r = await c.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}",
                headers={"Content-Type": "application/json"},
                json={"contents": contents,
                      "generationConfig": {"maxOutputTokens": 2000, "temperature": 0.7}})
        if r.status_code != 200:
            raise HTTPException(r.status_code, f"Gemini error: {r.text}")
        try:
            reply = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise HTTPException(500, f"Gemini parse error: {r.text}")

    # ── DEEPSEEK ────────────────────────────────────────────────────
    elif model == "deepseek":
        if not DEEPSEEK_KEY:
            raise HTTPException(500, "DEEPSEEK_API_KEY not set in .env")
        msgs = []
        if req.system: msgs.append({"role": "system", "content": req.system})
        msgs += [m.dict() for m in req.messages]
        async with httpx.AsyncClient(timeout=90) as c:
            r = await c.post("https://api.deepseek.com/v1/chat/completions",
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {DEEPSEEK_KEY}"},
                json={"model": "deepseek-chat", "max_tokens": 2000, "messages": msgs})
        if r.status_code != 200:
            raise HTTPException(r.status_code, f"DeepSeek error: {r.text}")
        reply = r.json()["choices"][0]["message"]["content"]

    else:
        raise HTTPException(400, f"Unknown model: {model}. Use: claude/openai/gemini/deepseek")

    # Save to MongoDB
    db.chat_history.insert_one({
        "user_email": token.get("email", "unknown"),
        "tool":       req.tool or "chat",
        "model":      model,
        "prompt":     req.messages[-1]["content"] if req.messages else "",
        "response":   reply,
        "created_at": datetime.utcnow(),
    })
    return {"reply": reply}

# ── History ────────────────────────────────────────────────────────
@app.get("/api/history")
def get_history(tool: Optional[str]=None, token: dict=Depends(decode_token)):
    q = {"user_email": token["email"]}
    if tool: q["tool"] = tool
    items = list(db.chat_history.find(q, {"_id": 0}).sort("created_at", -1).limit(100))
    for i in items: i["created_at"] = i["created_at"].isoformat()
    return {"history": items}

@app.delete("/api/history")
def clear_history(token: dict=Depends(decode_token)):
    return {"deleted": db.chat_history.delete_many({"user_email": token["email"]}).deleted_count}

# ── Profile ────────────────────────────────────────────────────────
@app.patch("/api/profile")
def update_profile(req: ProfileUpdate, token: dict=Depends(decode_token)):
    update = {}
    if req.name:
        update["name"]   = req.name
        update["avatar"] = req.name[0].upper()
    if req.password and len(req.password) >= 6:
        update["password"] = hash_password(req.password)
    if not update: raise HTTPException(400, "Nothing to update")
    db.users.update_one({"email": token["email"]}, {"$set": update})
    return {"message": "Profile updated successfully"}

# ── Health ─────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "version": "6.0.0",
            "models": ["claude", "openai", "gemini", "deepseek"],
            "tools": 14, "db": "connected"}

# ── Entry point ────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)