from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Query, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os, logging, json, asyncio, uuid
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import jwt, bcrypt, httpx
from contextlib import asynccontextmanager
import asyncpg
from asyncpg import Pool

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://whatsapp_user:whatsapp_pass@postgres:5432/whatsapp_db')
JWT_SECRET = os.environ.get('JWT_SECRET', 'your-super-secret-jwt-key')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

db_pool: Optional[Pool] = None

# ── WebSocket Manager ────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

ws_manager = ConnectionManager()

# ── DB Pool ──────────────────────────────────────────────────
async def get_db_pool() -> Pool:
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return db_pool

async def init_db():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Add meta_waba_id column if it doesn't exist (migration)
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS meta_waba_id VARCHAR(255)
        """)
        admin = await conn.fetchrow("SELECT id FROM users WHERE username = $1", 'admin')
        if not admin:
            password_hash = bcrypt.hashpw('Admin123!'.encode(), bcrypt.gensalt()).decode()
            await conn.execute(
                "INSERT INTO users (username, password_hash, role, business_name) VALUES ($1, $2, $3, $4)",
                'admin', password_hash, 'super_admin', 'Super Admin'
            )
            logger.info("Created default super_admin user")

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    yield
    global db_pool
    if db_pool:
        await db_pool.close()

app = FastAPI(lifespan=lifespan)
api_router = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

# ── Pydantic Models ──────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str
    user: Dict[str, Any]

class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    business_name: Optional[str]
    created_at: str

class CreateUserRequest(BaseModel):
    username: str
    password: str
    business_name: str
    meta_access_token: Optional[str] = None
    meta_phone_number_id: Optional[str] = None
    meta_verify_token: Optional[str] = None

class UpdateUserRequest(BaseModel):
    business_name: Optional[str] = None
    meta_access_token: Optional[str] = None
    meta_phone_number_id: Optional[str] = None
    meta_waba_id: Optional[str] = None
    meta_verify_token: Optional[str] = None
    password: Optional[str] = None

class UserAdminResponse(BaseModel):
    id: str
    username: str
    role: str
    business_name: Optional[str]
    meta_phone_number_id: Optional[str]
    has_token: bool
    created_at: str

class ContactResponse(BaseModel):
    id: str
    phone_number: str
    name: Optional[str]
    created_at: str

class MessageResponse(BaseModel):
    id: str
    session_id: str
    direction: str
    sender_type: str
    text: str
    meta_message_id: Optional[str]
    status: Optional[str]
    created_at: str

class SessionResponse(BaseModel):
    id: str
    contact_id: str
    is_bot_paused: bool
    created_at: str
    updated_at: str
    contact: Optional[ContactResponse] = None
    last_message: Optional[MessageResponse] = None

class SendMessageRequest(BaseModel):
    text: str

class ToggleAIRequest(BaseModel):
    is_paused: bool

class TemplateResponse(BaseModel):
    id: str
    name: str
    category: Optional[str]
    language: Optional[str]
    status: Optional[str]
    components: Optional[Any]
    meta_template_id: Optional[str]
    created_at: str

class CreateTemplateRequest(BaseModel):
    name: str
    category: str
    language: str
    components: List[Dict[str, Any]]

class CampaignRequest(BaseModel):
    template_name: str
    target_phone_numbers: List[str]

class CampaignResponse(BaseModel):
    success: bool
    sent_count: int
    failed_count: int
    details: List[Dict[str, Any]]

class IngestRequest(BaseModel):
    text_content: str
    metadata: Optional[Dict[str, Any]] = None

class IngestResponse(BaseModel):
    success: bool
    chunks_created: int
    message: str

# ── Auth Helpers ─────────────────────────────────────────────
def create_token(user_id: int, username: str, role: str, business_name: str) -> str:
    payload = {
        'user_id': user_id,
        'username': username,
        'role': role,
        'business_name': business_name or '',
        'exp': datetime.now(timezone.utc) + timedelta(hours=24)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def verify_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(credentials.credentials)
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE id = $1", payload['user_id'])
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
    return dict(user)

async def require_super_admin(current_user: Dict = Depends(get_current_user)) -> Dict:
    if current_user['role'] != 'super_admin':
        raise HTTPException(status_code=403, detail="Super admin access required")
    return current_user

# ── AI Helpers ───────────────────────────────────────────────
def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunks.append(' '.join(words[i:i + chunk_size]))
        i += chunk_size - overlap
    return chunks if chunks else [text]

async def generate_embedding(text: str) -> List[float]:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=GEMINI_API_KEY)
    try:
        result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
        )
        embedding = list(result.embeddings[0].values)
        while len(embedding) < 768:
            embedding.append(0.0)
        return embedding[:768]
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return [0.0] * 768

async def search_similar_chunks(query_embedding: List[float], user_id: int, limit: int = 4) -> List[Dict]:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
        results = await conn.fetch(
            """
            SELECT id, content, metadata,
                   1 - (embedding <=> $1::vector) as similarity
            FROM knowledge_chunks
            WHERE embedding IS NOT NULL AND user_id = $2
            ORDER BY embedding <=> $1::vector
            LIMIT $3
            """,
            embedding_str, user_id, limit
        )
        return [{"id": r['id'], "content": r['content'], "similarity": float(r['similarity'] or 0)} for r in results]

async def send_whatsapp_message(phone: str, text: str, access_token: str, phone_number_id: str) -> Optional[str]:
    if not access_token or not phone_number_id:
        return f"wamid.simulated_{uuid.uuid4().hex[:12]}"
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": phone, "type": "text", "text": {"body": text}}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                return response.json().get("messages", [{}])[0].get("id")
        return None
    except Exception:
        return None

async def send_whatsapp_template(phone: str, template_name: str, language: str, access_token: str, phone_number_id: str) -> Optional[str]:
    if not access_token or not phone_number_id:
        return f"wamid.template_{uuid.uuid4().hex[:12]}"
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": phone, "type": "template", "template": {"name": template_name, "language": {"code": language}}}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                return response.json().get("messages", [{}])[0].get("id")
        return None
    except Exception:
        return None

async def generate_ai_response(phone_number: str, incoming_message: str, message_history: List[Dict], user_id: int) -> str:
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
        query_embedding = await generate_embedding(incoming_message)
        relevant_chunks = await search_similar_chunks(query_embedding, user_id=user_id, limit=4)
        context = ""
        if relevant_chunks:
            context = "\n\nRelevant Knowledge:\n" + "\n".join([f"- {c['content']}" for c in relevant_chunks])
        system_message = (
            f"You are a helpful WhatsApp chatbot assistant. Be concise, friendly, and helpful.{context}\n\n"
            "Instructions:\n- Answer based on the knowledge above when relevant\n"
            "- Keep responses brief and suitable for WhatsApp\n"
            "- If you don't know something, be honest\n"
            "- answer with the same customer question language"
        )
        history_text = "\n".join([
            f"{'Customer' if msg.get('role') == 'user' else 'Assistant'}: {msg.get('content', '')}"
            for msg in message_history[-5:]
        ]) if message_history else ""
        full_message = f"Previous conversation:\n{history_text}\n\nNew message: {incoming_message}" if history_text else incoming_message
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=full_message,
            config=types.GenerateContentConfig(system_instruction=system_message)
        )
        return response.text
    except Exception as e:
        logger.error(f"AI generation error: {e}")
        return "I apologize, but I'm having trouble processing your message right now. Please try again in a moment."

# ── WebSocket ────────────────────────────────────────────────
@api_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

# ── Auth Endpoints ───────────────────────────────────────────
@api_router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE username = $1", request.username)
        if not user or not bcrypt.checkpw(request.password.encode(), user['password_hash'].encode()):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = create_token(user['id'], user['username'], user['role'], user['business_name'] or '')
        return LoginResponse(
            token=token,
            user={
                "id": str(user['id']),
                "username": user['username'],
                "role": user['role'],
                "business_name": user['business_name'] or '',
                "created_at": str(user['created_at'])
            }
        )

@api_router.get("/auth/me")
async def get_me(current_user: Dict = Depends(get_current_user)):
    return {
        "id": str(current_user['id']),
        "username": current_user['username'],
        "role": current_user['role'],
        "business_name": current_user['business_name'] or '',
        "meta_phone_number_id": current_user['meta_phone_number_id'] or '',
        "has_token": bool(current_user['meta_access_token']),
        "created_at": str(current_user['created_at'])
    }

# ── Settings (user updates their own WhatsApp credentials) ───
@api_router.put("/settings")
async def update_settings(request: UpdateUserRequest, current_user: Dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        updates, vals, idx = [], [], 1
        if request.business_name is not None:
            updates.append(f"business_name = ${idx}"); vals.append(request.business_name); idx += 1
        if request.meta_access_token is not None:
            updates.append(f"meta_access_token = ${idx}"); vals.append(request.meta_access_token); idx += 1
        if request.meta_phone_number_id is not None:
            updates.append(f"meta_phone_number_id = ${idx}"); vals.append(request.meta_phone_number_id); idx += 1
        if request.meta_verify_token is not None:
            updates.append(f"meta_verify_token = ${idx}"); vals.append(request.meta_verify_token); idx += 1
        if request.meta_waba_id is not None:
            updates.append(f"meta_waba_id = ${idx}"); vals.append(request.meta_waba_id); idx += 1
        if request.password is not None:
            pw_hash = bcrypt.hashpw(request.password.encode(), bcrypt.gensalt()).decode()
            updates.append(f"password_hash = ${idx}"); vals.append(pw_hash); idx += 1
        if not updates:
            raise HTTPException(status_code=400, detail="Nothing to update")
        vals.append(current_user['id'])
        await conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ${idx}", *vals)
    return {"success": True}

@api_router.get("/settings")
async def get_settings(current_user: Dict = Depends(get_current_user)):
    return {
        "business_name": current_user['business_name'] or '',
        "meta_phone_number_id": current_user['meta_phone_number_id'] or '',
        "meta_waba_id": current_user.get('meta_waba_id') or '',
        "meta_verify_token": current_user['meta_verify_token'] or '',
        "has_token": bool(current_user['meta_access_token']),
    }

# ── Super Admin — User Management ───────────────────────────
@api_router.get("/admin/users", response_model=List[UserAdminResponse])
async def list_users(current_user: Dict = Depends(require_super_admin)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        users = await conn.fetch("SELECT * FROM users ORDER BY created_at DESC")
        return [
            UserAdminResponse(
                id=str(u['id']), username=u['username'], role=u['role'],
                business_name=u['business_name'], meta_phone_number_id=u['meta_phone_number_id'],
                has_token=bool(u['meta_access_token']), created_at=str(u['created_at'])
            ) for u in users
        ]

@api_router.post("/admin/users", response_model=UserAdminResponse)
async def create_user(request: CreateUserRequest, current_user: Dict = Depends(require_super_admin)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM users WHERE username = $1", request.username)
        if existing:
            raise HTTPException(status_code=400, detail="Username already exists")
        pw_hash = bcrypt.hashpw(request.password.encode(), bcrypt.gensalt()).decode()
        user = await conn.fetchrow(
            """INSERT INTO users (username, password_hash, role, business_name, meta_access_token, meta_phone_number_id, meta_verify_token)
               VALUES ($1,$2,'user',$3,$4,$5,$6) RETURNING *""",
            request.username, pw_hash, request.business_name,
            request.meta_access_token, request.meta_phone_number_id, request.meta_verify_token
        )
        return UserAdminResponse(
            id=str(user['id']), username=user['username'], role=user['role'],
            business_name=user['business_name'], meta_phone_number_id=user['meta_phone_number_id'],
            has_token=bool(user['meta_access_token']), created_at=str(user['created_at'])
        )

@api_router.put("/admin/users/{user_id}")
async def update_user(user_id: int, request: UpdateUserRequest, current_user: Dict = Depends(require_super_admin)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        updates, vals, idx = [], [], 1
        if request.business_name is not None:
            updates.append(f"business_name = ${idx}"); vals.append(request.business_name); idx += 1
        if request.meta_access_token is not None:
            updates.append(f"meta_access_token = ${idx}"); vals.append(request.meta_access_token); idx += 1
        if request.meta_phone_number_id is not None:
            updates.append(f"meta_phone_number_id = ${idx}"); vals.append(request.meta_phone_number_id); idx += 1
        if request.meta_verify_token is not None:
            updates.append(f"meta_verify_token = ${idx}"); vals.append(request.meta_verify_token); idx += 1
        if request.password is not None:
            pw_hash = bcrypt.hashpw(request.password.encode(), bcrypt.gensalt()).decode()
            updates.append(f"password_hash = ${idx}"); vals.append(pw_hash); idx += 1
        if not updates:
            raise HTTPException(status_code=400, detail="Nothing to update")
        vals.append(user_id)
        await conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ${idx}", *vals)
    return {"success": True}

@api_router.delete("/admin/users/{user_id}")
async def delete_user(user_id: int, current_user: Dict = Depends(require_super_admin)):
    if user_id == current_user['id']:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM users WHERE id = $1", user_id)
    return {"success": True}

# ── Webhook ──────────────────────────────────────────────────
@api_router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT id FROM users WHERE meta_verify_token = $1", hub_verify_token)
    if hub_mode == "subscribe" and user:
        return int(hub_challenge) if hub_challenge else ""
    raise HTTPException(status_code=403, detail="Verification failed")

@api_router.post("/webhook")
async def handle_webhook(request: Request):
    try:
        body = await request.json()
        pool = await get_db_pool()
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                phone_number_id = value.get("metadata", {}).get("phone_number_id", "")
                async with pool.acquire() as conn:
                    tenant = await conn.fetchrow("SELECT * FROM users WHERE meta_phone_number_id = $1", phone_number_id)
                if not tenant:
                    logger.warning(f"No tenant for phone_number_id: {phone_number_id}")
                    continue
                tenant_id = tenant['id']
                if "messages" in value:
                    for message in value["messages"]:
                        phone = message.get("from", "")
                        text = message.get("text", {}).get("body", "")
                        meta_message_id = message.get("id", "")
                        if not phone or not text:
                            continue
                        async with pool.acquire() as conn:
                            contact = await conn.fetchrow(
                                """INSERT INTO contacts (user_id,phone_number,name) VALUES ($1,$2,$2)
                                   ON CONFLICT (user_id,phone_number) DO UPDATE SET name=EXCLUDED.name RETURNING id,phone_number""",
                                tenant_id, phone)
                            session = await conn.fetchrow("SELECT * FROM sessions WHERE contact_id=$1", contact['id'])
                            if not session:
                                session = await conn.fetchrow(
                                    "INSERT INTO sessions (contact_id,is_bot_paused) VALUES ($1,FALSE) RETURNING *", contact['id'])
                            else:
                                session = await conn.fetchrow(
                                    "UPDATE sessions SET updated_at=CURRENT_TIMESTAMP WHERE id=$1 RETURNING *", session['id'])
                            msg_id = await conn.fetchval(
                                """INSERT INTO messages (session_id,direction,sender_type,text,meta_message_id,status)
                                   VALUES ($1,'INBOUND','CUSTOMER',$2,$3,'received') RETURNING id""",
                                session['id'], text, meta_message_id)
                        await ws_manager.broadcast({"type":"new_message","user_id":tenant_id,
                            "data":{"id":str(msg_id),"session_id":str(session['id']),"phone_number":phone,
                                    "direction":"INBOUND","sender_type":"CUSTOMER","text":text,
                                    "created_at":datetime.now(timezone.utc).isoformat()}})
                        if not session.get('is_bot_paused', False):
                            async with pool.acquire() as conn:
                                history = await conn.fetch(
                                    "SELECT direction,text FROM messages WHERE session_id=$1 ORDER BY created_at DESC LIMIT 10", session['id'])
                            msg_history = [{"role":"user" if m['direction']=='INBOUND' else "assistant","content":m['text']}
                                           for m in reversed(history)]
                            ai_response = await generate_ai_response(phone, text, msg_history, tenant_id)
                            if ai_response:
                                wa_id = await send_whatsapp_message(phone, ai_response, tenant['meta_access_token'], tenant['meta_phone_number_id'])
                                async with pool.acquire() as conn:
                                    bot_id = await conn.fetchval(
                                        """INSERT INTO messages (session_id,direction,sender_type,text,meta_message_id,status)
                                           VALUES ($1,'OUTBOUND','BOT',$2,$3,'sent') RETURNING id""",
                                        session['id'], ai_response, wa_id)
                                await ws_manager.broadcast({"type":"new_message","user_id":tenant_id,
                                    "data":{"id":str(bot_id),"session_id":str(session['id']),"phone_number":phone,
                                            "direction":"OUTBOUND","sender_type":"BOT","text":ai_response,
                                            "created_at":datetime.now(timezone.utc).isoformat()}})
                if "statuses" in value:
                    for status in value["statuses"]:
                        mid, sv = status.get("id",""), status.get("status","")
                        if mid and sv:
                            async with pool.acquire() as conn:
                                await conn.execute("UPDATE messages SET status=$1 WHERE meta_message_id=$2", sv, mid)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── Chat Endpoints ───────────────────────────────────────────
@api_router.get("/chats", response_model=List[SessionResponse])
async def get_chats(current_user: Dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch(
            """SELECT s.*,c.phone_number,c.name as contact_name,c.created_at as contact_created_at
               FROM sessions s JOIN contacts c ON s.contact_id=c.id
               WHERE c.user_id=$1 ORDER BY s.updated_at DESC LIMIT 100""", current_user['id'])
        result = []
        for r in records:
            last_msg = await conn.fetchrow("SELECT * FROM messages WHERE session_id=$1 ORDER BY created_at DESC LIMIT 1", r['id'])
            cr = ContactResponse(id=str(r['contact_id']),phone_number=r['phone_number'],name=r['contact_name'],created_at=str(r['contact_created_at']))
            lm = None
            if last_msg:
                lm = MessageResponse(id=str(last_msg['id']),session_id=str(last_msg['session_id']),direction=last_msg['direction'],
                                     sender_type=last_msg['sender_type'],text=last_msg['text'],meta_message_id=last_msg['meta_message_id'],
                                     status=last_msg['status'],created_at=str(last_msg['created_at']))
            result.append(SessionResponse(id=str(r['id']),contact_id=str(r['contact_id']),is_bot_paused=r['is_bot_paused'],
                                          created_at=str(r['created_at']),updated_at=str(r['updated_at']),contact=cr,last_message=lm))
        return result

@api_router.get("/chats/{phone}/messages", response_model=List[MessageResponse])
async def get_chat_messages(phone: str, current_user: Dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow("SELECT id FROM contacts WHERE user_id=$1 AND phone_number=$2", current_user['id'], phone)
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        session = await conn.fetchrow("SELECT id FROM sessions WHERE contact_id=$1", contact['id'])
        if not session:
            return []
        msgs = await conn.fetch("SELECT * FROM messages WHERE session_id=$1 ORDER BY created_at ASC LIMIT 1000", session['id'])
        return [MessageResponse(id=str(m['id']),session_id=str(m['session_id']),direction=m['direction'],
                                sender_type=m['sender_type'],text=m['text'],meta_message_id=m['meta_message_id'],
                                status=m['status'],created_at=str(m['created_at'])) for m in msgs]

@api_router.post("/chats/{phone}/send", response_model=MessageResponse)
async def send_message(phone: str, request: SendMessageRequest, current_user: Dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow(
            "INSERT INTO contacts (user_id,phone_number,name) VALUES ($1,$2,$2) ON CONFLICT (user_id,phone_number) DO UPDATE SET name=EXCLUDED.name RETURNING id",
            current_user['id'], phone)
        session = await conn.fetchrow("SELECT id FROM sessions WHERE contact_id=$1", contact['id'])
        if not session:
            session = await conn.fetchrow("INSERT INTO sessions (contact_id,is_bot_paused) VALUES ($1,TRUE) RETURNING id", contact['id'])
        else:
            session = await conn.fetchrow("UPDATE sessions SET is_bot_paused=TRUE,updated_at=CURRENT_TIMESTAMP WHERE id=$1 RETURNING id", session['id'])
        wa_id = await send_whatsapp_message(phone, request.text, current_user['meta_access_token'], current_user['meta_phone_number_id'])
        msg_id, msg_created_at = await conn.fetchrow(
            "INSERT INTO messages (session_id,direction,sender_type,text,meta_message_id,status) VALUES ($1,'OUTBOUND','ADMIN',$2,$3,'sent') RETURNING id,created_at",
            session['id'], request.text, wa_id)
    await ws_manager.broadcast({"type":"new_message","user_id":current_user['id'],
        "data":{"id":str(msg_id),"session_id":str(session['id']),"phone_number":phone,
                "direction":"OUTBOUND","sender_type":"ADMIN","text":request.text,"created_at":str(msg_created_at)}})
    return MessageResponse(id=str(msg_id),session_id=str(session['id']),direction='OUTBOUND',
                           sender_type='ADMIN',text=request.text,meta_message_id=wa_id,status='sent',created_at=str(msg_created_at))

@api_router.put("/chats/{phone}/toggle-ai")
async def toggle_ai(phone: str, request: ToggleAIRequest, current_user: Dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow("SELECT id FROM contacts WHERE user_id=$1 AND phone_number=$2", current_user['id'], phone)
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        await conn.execute("UPDATE sessions SET is_bot_paused=$1,updated_at=CURRENT_TIMESTAMP WHERE contact_id=$2", request.is_paused, contact['id'])
    return {"success": True, "is_paused": request.is_paused}

@api_router.put("/chats/ai/global-toggle")
async def global_toggle_ai(request: ToggleAIRequest, current_user: Dict = Depends(get_current_user)):
    """Pause or resume AI for ALL sessions belonging to this user."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE sessions SET is_bot_paused=$1, updated_at=CURRENT_TIMESTAMP
               WHERE contact_id IN (SELECT id FROM contacts WHERE user_id=$2)""",
            request.is_paused, current_user['id']
        )
    await ws_manager.broadcast({
        "type": "global_ai_toggle",
        "user_id": current_user['id'],
        "is_paused": request.is_paused
    })
    return {"success": True, "is_paused": request.is_paused}

@api_router.get("/chats/ai/global-status")
async def global_ai_status(current_user: Dict = Depends(get_current_user)):
    """Returns True if ANY session has AI active (not paused)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        active = await conn.fetchval(
            """SELECT COUNT(*) FROM sessions WHERE is_bot_paused=FALSE
               AND contact_id IN (SELECT id FROM contacts WHERE user_id=$1)""",
            current_user['id']
        )
    return {"ai_active": (active or 0) > 0, "active_sessions": active or 0}

# ── Templates ────────────────────────────────────────────────
@api_router.get("/templates", response_model=List[TemplateResponse])
async def get_templates(current_user: Dict = Depends(get_current_user)):
    pool = await get_db_pool()
    token = current_user['meta_access_token']
    waba_id = current_user.get('meta_waba_id')
    if token and waba_id:
        try:
            async with httpx.AsyncClient() as http_client:
                resp = await http_client.get(
                    f"https://graph.facebook.com/v18.0/{waba_id}/message_templates",
                    params={"limit": 100},
                    headers={"Authorization": f"Bearer {token}"}
                )
                logger.info(f"Templates API status: {resp.status_code} for WABA: {waba_id}")
                if resp.status_code == 200:
                    templates = resp.json().get("data", [])
                    logger.info(f"Fetched {len(templates)} templates from Meta")
                    async with pool.acquire() as conn:
                        await conn.execute(
                            "DELETE FROM templates WHERE user_id=$1 AND meta_template_id IS NOT NULL",
                            current_user['id']
                        )
                        for t in templates:
                            await conn.execute(
                                """INSERT INTO templates (user_id,name,category,language,status,components,meta_template_id)
                                   VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                                current_user['id'], t.get("name"), t.get("category"), t.get("language"),
                                t.get("status"), json.dumps(t.get("components")), t.get("id"))
                else:
                    logger.error(f"Meta templates error: {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.error(f"Meta templates fetch error: {e}")
    elif token and not waba_id:
        logger.warning("No WABA ID set — skipping template sync. Set it in Settings.")
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM templates WHERE user_id=$1 ORDER BY created_at DESC LIMIT 100", current_user['id'])
        return [TemplateResponse(id=str(t['id']),name=t['name'],category=t['category'],language=t['language'],
                                 status=t['status'],components=json.loads(t['components']) if t['components'] and isinstance(t['components'],str) else t['components'],
                                 meta_template_id=t['meta_template_id'],created_at=str(t['created_at'])) for t in rows]

@api_router.post("/templates", response_model=TemplateResponse)
async def create_template(request: CreateTemplateRequest, current_user: Dict = Depends(get_current_user)):
    token = current_user['meta_access_token']
    pid = current_user['meta_phone_number_id']
    meta_template_id, status = None, "PENDING"
    if token and pid:
        try:
            url = f"https://graph.facebook.com/v18.0/{pid}/message_templates"
            payload = {"name":request.name,"category":request.category,"language":request.language,"components":request.components}
            async with httpx.AsyncClient() as http_client:
                resp = await http_client.post(url, json=payload, headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"})
                if resp.status_code == 200:
                    data = resp.json()
                    meta_template_id = data.get("id")
                    status = data.get("status", "PENDING")
        except Exception:
            pass
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO templates (user_id,name,category,language,status,components,meta_template_id) VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id,created_at",
            current_user['id'], request.name, request.category, request.language, status, json.dumps(request.components), meta_template_id)
        return TemplateResponse(id=str(row['id']),name=request.name,category=request.category,language=request.language,
                                status=status,components=request.components,meta_template_id=meta_template_id,created_at=str(row['created_at']))

# ── Campaigns ────────────────────────────────────────────────
@api_router.post("/campaigns/send", response_model=CampaignResponse)
async def send_campaign(request: CampaignRequest, current_user: Dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        template = await conn.fetchrow("SELECT * FROM templates WHERE user_id=$1 AND name=$2 LIMIT 1", current_user['id'], request.template_name)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    sent_count, failed_count, details = 0, 0, []
    for phone in request.target_phone_numbers:
        phone = phone.strip()
        if not phone:
            continue
        try:
            message_id = await send_whatsapp_template(phone, request.template_name, template['language'] or 'en',
                                                      current_user['meta_access_token'], current_user['meta_phone_number_id'])
            if message_id:
                sent_count += 1
                details.append({"phone": phone, "status": "sent", "message_id": message_id})
            else:
                failed_count += 1
                details.append({"phone": phone, "status": "failed", "error": "No message ID returned"})
            await asyncio.sleep(0.2)
        except Exception as e:
            failed_count += 1
            details.append({"phone": phone, "status": "failed", "error": str(e)})
    return CampaignResponse(success=failed_count==0, sent_count=sent_count, failed_count=failed_count, details=details)

# ── Knowledge Base ───────────────────────────────────────────
@api_router.post("/ai/ingest", response_model=IngestResponse)
async def ingest_knowledge(request: IngestRequest, current_user: Dict = Depends(get_current_user)):
    try:
        chunks = chunk_text(request.text_content)
        pool = await get_db_pool()
        chunks_created = 0
        async with pool.acquire() as conn:
            for chunk in chunks:
                embedding = await generate_embedding(chunk)
                embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                await conn.execute(
                    "INSERT INTO knowledge_chunks (user_id,content,embedding,metadata) VALUES ($1,$2,$3::vector,$4)",
                    current_user['id'], chunk, embedding_str,
                    json.dumps(request.metadata) if request.metadata else None)
                chunks_created += 1
        return IngestResponse(success=True, chunks_created=chunks_created, message=f"Ingested {chunks_created} chunks")
    except Exception as e:
        logger.error(f"Ingest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/ai/knowledge")
async def clear_knowledge(current_user: Dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM knowledge_chunks WHERE user_id=$1", current_user['id'])
        await conn.execute("DELETE FROM knowledge_chunks WHERE user_id=$1", current_user['id'])
    return {"success": True, "deleted": count}

@api_router.get("/ai/knowledge/stats")
async def knowledge_stats(current_user: Dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM knowledge_chunks WHERE user_id=$1", current_user['id'])
    return {"total_chunks": count}

# ── Health ───────────────────────────────────────────────────
@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

@api_router.get("/")
async def root():
    return {"message": "WhatsApp AI Chatbot API - Multi-Tenant"}

# ── App Bootstrap ────────────────────────────────────────────
app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=500, content={"error": str(exc)})
