# Nexus AI V6 — Multi-AI Super App

4 AI models · 14 tools · MongoDB · FastAPI · Premium Dark UI

---

## Project Structure

```
nexus-ai-v6/
├── backend/
│   ├── main.py        ← FastAPI + 4 model proxy
│   ├── database.py    ← MongoDB connection
│   ├── auth.py        ← JWT + bcrypt
│   ├── admin.py       ← Admin routes
│   └── .env           ← All API keys
├── frontend/
│   ├── index.html     ← Login / Signup
│   ├── app.html       ← Main app (4 models + 14 tools)
│   ├── admin.html     ← Admin panel
│   └── style.css      ← Premium dark theme
├── .vscode/
│   └── settings.json
├── requirements.txt
├── README.md
└── .gitignore
```

---

## AI Models Supported

| Model | Provider | API Key |
|---|---|---|
| Claude Sonnet | Anthropic | ANTHROPIC_API_KEY |
| GPT-4o Mini | OpenAI | OPENAI_API_KEY |
| Gemini 1.5 Flash | Google | GEMINI_API_KEY |
| DeepSeek V3 | DeepSeek | DEEPSEEK_API_KEY |

---

## Setup Steps

### 1. Install MongoDB
```bash
# macOS
brew install mongodb-community && brew services start mongodb-community

# Windows — download from mongodb.com/try/download/community
```

### 2. Create virtual environment
```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

### 3. Configure .env
```bash
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...
DEEPSEEK_API_KEY=sk-...
MONGO_URI=mongodb://localhost:27017/
SECRET_KEY=your-secret-key
```

### 4. Start backend
```bash
cd backend
python main.py
```

You should see:
```
✅  MongoDB connected
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 5. Create demo user + admin (one time)
```powershell
# Register user
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/register" -ContentType "application/json" -Body '{"name":"Demo User","email":"demo@nexusai.app","password":"demo123"}'

# Seed admin
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/admin/seed?secret=nexusai-admin-v6-2025"
```

### 6. Open in browser
```
App   → http://localhost:8000/static/index.html
Admin → http://localhost:8000/static/admin.html
Docs  → http://localhost:8000/docs
```

---

## API Endpoints

| Method | Route | Description |
|---|---|---|
| POST | /api/register | Register new user |
| POST | /api/login | Login, returns JWT |
| GET | /api/me | Current user info |
| POST | /api/claude | AI proxy (all 4 models) |
| GET | /api/history | User chat history |
| DELETE | /api/history | Clear history |
| PATCH | /api/profile | Update profile |
| GET | /api/health | Health check |
| POST | /api/admin/login | Admin login |
| POST | /api/admin/seed | Create admin (one time) |
| GET | /api/admin/stats | Dashboard stats |
| GET | /api/admin/users | All users |
| PATCH | /api/admin/users/:id/ban | Ban/unban user |
| DELETE | /api/admin/users/:id | Delete user |
| GET | /api/admin/history | All history |

---

## Get API Keys

| Provider | URL |
|---|---|
| Anthropic (Claude) | console.anthropic.com |
| OpenAI (ChatGPT) | platform.openai.com/api-keys |
| Google (Gemini) | aistudio.google.com/app/apikey |
| DeepSeek | platform.deepseek.com |

---

## Security Checklist
- [ ] Change SECRET_KEY in .env
- [ ] Change ADMIN_SECRET in admin.py
- [ ] Change admin123 password after first login
- [ ] Never commit .env to git
- [ ] Use HTTPS in production