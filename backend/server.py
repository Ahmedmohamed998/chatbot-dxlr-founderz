from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Query, WebSocket, WebSocketDisconnect, Header, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os, logging, json, asyncio, uuid, shutil, subprocess
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
        # Migrations: add new columns if they don't exist
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS meta_waba_id VARCHAR(255)")
        await conn.execute("ALTER TABLE contacts ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP")
        await conn.execute("ALTER TABLE contacts ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'")
        await conn.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS unread_count INTEGER DEFAULT 0")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS api_key VARCHAR(64)")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS shopify_store_url VARCHAR(255)")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS shopify_api_token VARCHAR(255)")
        await conn.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS media_url VARCHAR(255)")
        await conn.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS media_type VARCHAR(50)")

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

# Setup local media storage
MEDIA_DIR = Path("data/media")
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/api/media", StaticFiles(directory="data/media"), name="media")

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
    shopify_store_url: Optional[str] = None
    shopify_api_token: Optional[str] = None

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
    media_url: Optional[str] = None
    media_type: Optional[str] = None

class SessionResponse(BaseModel):
    id: str
    contact_id: str
    is_bot_paused: bool
    unread_count: int = 0
    created_at: str
    updated_at: str
    contact: Optional[ContactResponse] = None
    last_message: Optional[MessageResponse] = None

class SendMessageRequest(BaseModel):
    text: str

class ToggleAIRequest(BaseModel):
    is_paused: bool

class UpdateContactNameRequest(BaseModel):
    name: str

class LogMessageRequest(BaseModel):
    text: str
    contact_name: Optional[str] = None
    meta_message_id: Optional[str] = None
    pause_ai: bool = True
    shopify_order_number: Optional[str] = None

class OrderConfirmationItem(BaseModel):
    phone: str
    order_number: str

class BulkOrderConfirmationRequest(BaseModel):
    items: List[OrderConfirmationItem]
    template_name: str = "order_conf"

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

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> Dict:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # 1. Try X-API-Key header first
        if x_api_key:
            user = await conn.fetchrow("SELECT * FROM users WHERE api_key = $1", x_api_key)
            if not user:
                raise HTTPException(status_code=401, detail="Invalid API key")
            return dict(user)
        # 2. Try Bearer token (JWT)
        if not credentials:
            raise HTTPException(status_code=401, detail="Not authenticated")
        # Check if it looks like an api_key (not a JWT)
        token = credentials.credentials
        if not token.startswith('ey'):  # JWTs always start with 'ey'
            user = await conn.fetchrow("SELECT * FROM users WHERE api_key = $1", token)
            if not user:
                raise HTTPException(status_code=401, detail="Invalid API key")
            return dict(user)
        # 3. Standard JWT
        payload = verify_token(token)
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
        return f"wamid.{uuid.uuid4().hex[:15]}"
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

async def send_whatsapp_media_message(phone: str, media_type: str, file_bytes: bytes, mime_type: str, filename: str, access_token: str, phone_number_id: str) -> Optional[str]:
    """Upload media to Meta and send it as a message."""
    if not access_token or not phone_number_id:
        return f"wamid.{uuid.uuid4().hex[:15]}"
    
    upload_url = f"https://graph.facebook.com/v18.0/{phone_number_id}/media"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Upload media
            files = {'file': (filename, file_bytes, mime_type)}
            data = {'messaging_product': 'whatsapp'}
            upload_res = await client.post(upload_url, headers=headers, data=data, files=files)
            if upload_res.status_code != 200:
                logger.error(f"Meta media upload failed: {upload_res.text}")
                return None
            
            meta_media_id = upload_res.json().get("id")
            if not meta_media_id: return None

            # 2. Send media message
            msg_url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
            msg_payload = {
                "messaging_product": "whatsapp",
                "to": phone,
                "type": media_type,
                media_type: {"id": meta_media_id}
            }
            if media_type == 'document':
                msg_payload[media_type]["filename"] = filename

            send_res = await client.post(msg_url, json=msg_payload, headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"})
            if send_res.status_code == 200:
                return send_res.json().get("messages", [{}])[0].get("id")
            else:
                logger.error(f"Meta media send failed: {send_res.text}")
                return None
    except Exception as e:
        logger.error(f"Error sending media message: {e}")
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

async def send_whatsapp_template_with_components(
    phone: str, template_name: str, language: str,
    access_token: str, phone_number_id: str,
    components: List[Dict]
) -> Optional[str]:
    """Send a WhatsApp template message with body parameter components."""
    if not access_token or not phone_number_id:
        return f"wamid.template_{uuid.uuid4().hex[:12]}"
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
            "components": components
        }
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            logger.info(f"Template send to {phone}: {response.status_code} {response.text[:200]}")
            if response.status_code == 200:
                return response.json().get("messages", [{}])[0].get("id")
        return None
    except Exception as e:
        logger.error(f"Template send error: {e}")
        return None

async def fetch_shopify_order(order_number: str, store_url: str, api_token: str) -> Optional[Dict]:
    """Fetch a Shopify order by order number (e.g. 7940 or #7940)."""
    clean = order_number.strip().lstrip('#')
    base = store_url.rstrip('/')
    headers = {"X-Shopify-Access-Token": api_token, "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Try by name (most reliable)
            resp = await client.get(
                f"{base}/admin/api/2024-01/orders.json",
                params={"name": f"#{clean}", "status": "any"},
                headers=headers
            )
            if resp.status_code == 200:
                orders = resp.json().get("orders", [])
                if orders:
                    return orders[0]
            logger.warning(f"Shopify order #{clean} not found: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        logger.error(f"Shopify fetch error: {e}")
    return None

async def update_shopify_order_tags(order_id: int, tags_to_add: List[str], tags_to_remove: List[str], store_url: str, api_token: str) -> bool:
    """Update a Shopify order's tags by adding and removing specific tags."""
    base = store_url.rstrip('/')
    headers = {"X-Shopify-Access-Token": api_token, "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # First, fetch existing tags
            resp = await client.get(
                f"{base}/admin/api/2024-01/orders/{order_id}.json",
                headers=headers
            )
            if resp.status_code != 200:
                logger.error(f"Failed to fetch order {order_id} for tagging: {resp.text}")
                return False
                
            order = resp.json().get("order", {})
            current_tags = order.get("tags", "")
            
            # Parse existing tags
            tags_list = [t.strip() for t in current_tags.split(",")] if current_tags else []
            
            # Remove requested tags
            tags_list = [t for t in tags_list if t not in tags_to_remove]
            
            # Add requested tags if not already present
            for t in tags_to_add:
                if t not in tags_list:
                    tags_list.append(t)
            
            updated_tags = ", ".join(tags_list)
            
            # Avoid unnecessary API calls if tags didn't change
            if updated_tags == current_tags:
                return True
            
            # Update the order
            update_resp = await client.put(
                f"{base}/admin/api/2024-01/orders/{order_id}.json",
                json={"order": {"id": order_id, "tags": updated_tags}},
                headers=headers
            )
            if update_resp.status_code == 200:
                logger.info(f"Successfully tagged Shopify order {order_id} with {tags_to_add} (removed {tags_to_remove})")
                return True
            else:
                logger.error(f"Failed to update tags for order {order_id}: {update_resp.text}")
                return False
    except Exception as e:
        logger.error(f"Shopify tagging error: {e}")
        return False

async def download_meta_media(media_id: str, access_token: str, media_type: str) -> Optional[str]:
    """Download media from Meta and return the local URL path."""
    if not media_id or not access_token: return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {access_token}"}
            # 1. Get media URL
            res = await client.get(f"https://graph.facebook.com/v18.0/{media_id}", headers=headers)
            if res.status_code != 200:
                logger.error(f"Failed to get media url: {res.text}")
                return None
            media_info = res.json()
            download_url = media_info.get("url")
            mime_type = media_info.get("mime_type", "")
            
            if not download_url: return None

            # 2. Download binary data
            res_bin = await client.get(download_url, headers=headers)
            if res_bin.status_code != 200:
                logger.error("Failed to download media binary")
                return None
            
            # Determine extension
            ext = ""
            if "jpeg" in mime_type or "jpg" in mime_type: ext = ".jpg"
            elif "png" in mime_type: ext = ".png"
            elif "mp4" in mime_type: ext = ".mp4"
            elif "ogg" in mime_type: ext = ".ogg"
            elif "pdf" in mime_type: ext = ".pdf"
            elif "webp" in mime_type: ext = ".webp"
            
            filename = f"{media_type}_{media_id}{ext}"
            filepath = MEDIA_DIR / filename
            filepath.write_bytes(res_bin.content)
            return f"/api/media/{filename}"
    except Exception as e:
        logger.error(f"Error downloading media: {e}")
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
        if request.shopify_store_url is not None:
            updates.append(f"shopify_store_url = ${idx}"); vals.append(request.shopify_store_url); idx += 1
        if request.shopify_api_token is not None:
            updates.append(f"shopify_api_token = ${idx}"); vals.append(request.shopify_api_token); idx += 1
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
        "api_key": current_user.get('api_key') or '',
        "shopify_store_url": current_user.get('shopify_store_url') or '',
        "has_shopify_token": bool(current_user.get('shopify_api_token')),
    }

@api_router.post("/settings/generate-api-key")
async def generate_api_key(current_user: Dict = Depends(get_current_user)):
    """Generate (or regenerate) a permanent API key for machine-to-machine integrations."""
    import secrets
    new_key = 'wba_' + secrets.token_hex(28)  # 60-char key with prefix
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET api_key=$1 WHERE id=$2", new_key, current_user['id'])
    return {"api_key": new_key}

@api_router.post("/chats/{phone}/mark-read")
async def mark_chat_read(phone: str, current_user: Dict = Depends(get_current_user)):
    """Reset the unread count for a specific chat session."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow("SELECT id FROM contacts WHERE user_id=$1 AND phone_number=$2", current_user['id'], phone)
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        await conn.execute(
            "UPDATE sessions SET unread_count=0 WHERE contact_id=$1", 
            contact['id']
        )
    return {"success": True}

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
                        meta_message_id = message.get("id", "")
                        msg_type = message.get("type", "")

                        media_url = None
                        media_type = None

                        # Extract text based on message type
                        if msg_type == "text":
                            text = message.get("text", {}).get("body", "")
                        elif msg_type == "interactive":
                            # Customer clicked a template button or selected from list
                            interactive = message.get("interactive", {})
                            i_type = interactive.get("type", "")
                            if i_type == "button_reply":
                                text = f"[زر: {interactive.get('button_reply', {}).get('title', '')}]"
                            elif i_type == "list_reply":
                                text = f"[قائمة: {interactive.get('list_reply', {}).get('title', '')}]"
                            else:
                                text = "[interactive message]"
                        elif msg_type == "button":
                            # Quick reply button
                            text = f"[رد: {message.get('button', {}).get('text', '')}]"
                        elif msg_type in ["image", "audio", "video", "document", "sticker"]:
                            media_id = message.get(msg_type, {}).get("id")
                            # for stickers, the media id might be in the object differently depending on payload, but standard is message.sticker.id
                            if media_id:
                                media_type = msg_type
                                media_url = await download_meta_media(media_id, tenant['meta_access_token'], msg_type)
                            if msg_type == "image": text = "[صورة 📷]"
                            elif msg_type == "audio": text = "[صوت 🎵]"
                            elif msg_type == "video": text = "[فيديو 🎬]"
                            elif msg_type == "document": text = "[ملف 📄]"
                            elif msg_type == "sticker": text = "[ستيكر 🎭]"
                        elif msg_type == "location":
                            loc = message.get("location", {})
                            text = f"[موقع 📍 {loc.get('name', '')}]"
                        else:
                            text = f"[{msg_type}]" if msg_type else ""

                        if not phone or (not text and not media_url):
                            continue
                        async with pool.acquire() as conn:
                            contact = await conn.fetchrow(
                                """INSERT INTO contacts (user_id,phone_number,name) VALUES ($1,$2,$2)
                                   ON CONFLICT (user_id,phone_number) DO UPDATE SET updated_at=CURRENT_TIMESTAMP
                                   RETURNING id,phone_number,name,metadata""",
                                tenant_id, phone)
                            session = await conn.fetchrow("SELECT * FROM sessions WHERE contact_id=$1", contact['id'])
                            if not session:
                                session = await conn.fetchrow(
                                    "INSERT INTO sessions (contact_id,is_bot_paused) VALUES ($1,TRUE) RETURNING *", contact['id'])
                            else:
                                session = await conn.fetchrow(
                                    "UPDATE sessions SET updated_at=CURRENT_TIMESTAMP, unread_count=unread_count+1 WHERE id=$1 RETURNING *", session['id'])
                            msg_id = await conn.fetchval(
                                """INSERT INTO messages (session_id,direction,sender_type,text,meta_message_id,status,media_url,media_type)
                                   VALUES ($1,'INBOUND','CUSTOMER',$2,$3,'received',$4,$5) RETURNING id""",
                                session['id'], text or '', meta_message_id, media_url, media_type)
                        await ws_manager.broadcast({"type":"new_message","user_id":tenant_id,
                            "data":{"id":str(msg_id),"session_id":str(session['id']),"phone_number":phone,
                                    "direction":"INBOUND","sender_type":"CUSTOMER","text":text or '',
                                    "media_url": media_url, "media_type": media_type,
                                    "created_at":datetime.now(timezone.utc).isoformat()}})

                        # Handle Shopify Order Tagging
                        if tenant.get('shopify_store_url') and tenant.get('shopify_api_token') and contact.get('metadata'):
                            try:
                                metadata = contact['metadata']
                                if isinstance(metadata, str):
                                    metadata = json.loads(metadata)
                                
                                order_id = metadata.get("shopify_order_id")
                                if order_id and text:
                                    text_clean = text.replace("[رد: ", "").replace("[زر: ", "").replace("[قائمة: ", "").replace("]", "").strip()
                                    
                                    tags_to_add = []
                                    tags_to_remove = []
                                    if "تاكيد" in text_clean or "تأكيد" in text_clean:
                                        tags_to_add = ["Confirmed ✅"]
                                        tags_to_remove = ["Cancelled ❌", "Pending ⚠️", "No Whats 🚨"]
                                    elif "الغاء" in text_clean or "إلغاء" in text_clean:
                                        tags_to_add = ["Cancelled ❌"]
                                        tags_to_remove = ["Confirmed ✅", "Pending ⚠️", "No Whats 🚨"]
                                        
                                    if tags_to_add:
                                        # Run tagging in background task so we don't block the webhook
                                        asyncio.create_task(update_shopify_order_tags(
                                            order_id=order_id, 
                                            tags_to_add=tags_to_add, 
                                            tags_to_remove=tags_to_remove,
                                            store_url=tenant['shopify_store_url'], 
                                            api_token=tenant['shopify_api_token']
                                        ))
                            except Exception as e:
                                logger.error(f"Failed to process Shopify tagging in webhook: {e}")

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
                                
                                # If message failed, check if we need to update the Shopify order to "No Whats"
                                if sv == "failed" and tenant.get('shopify_store_url') and tenant.get('shopify_api_token'):
                                    try:
                                        row = await conn.fetchrow(
                                            """SELECT c.metadata 
                                               FROM messages m 
                                               JOIN sessions s ON m.session_id = s.id 
                                               JOIN contacts c ON s.contact_id = c.id 
                                               WHERE m.meta_message_id = $1""", 
                                            mid
                                        )
                                        if row and row['metadata']:
                                            metadata = row['metadata']
                                            if isinstance(metadata, str):
                                                metadata = json.loads(metadata)
                                            order_id = metadata.get("shopify_order_id")
                                            if order_id:
                                                asyncio.create_task(update_shopify_order_tags(
                                                    order_id=order_id,
                                                    tags_to_add=["No Whats 🚨"],
                                                    tags_to_remove=["Pending ⚠️", "Confirmed ✅", "Cancelled ❌"],
                                                    store_url=tenant['shopify_store_url'],
                                                    api_token=tenant['shopify_api_token']
                                                ))
                                    except Exception as e:
                                        logger.error(f"Failed to process No Whats tag on webhook: {e}")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── Contact Management ───────────────────────────────────────
@api_router.put("/contacts/{phone}/name")
async def update_contact_name(phone: str, request: UpdateContactNameRequest, current_user: Dict = Depends(get_current_user)):
    """Save or update a contact's display name."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow(
            "UPDATE contacts SET name=$1 WHERE phone_number=$2 AND user_id=$3 RETURNING id, name, phone_number",
            request.name.strip(), phone, current_user['id']
        )
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
    return {"success": True, "name": contact['name'], "phone_number": contact['phone_number']}

@api_router.post("/chats/{phone}/log-outbound")
async def log_outbound_message(
    phone: str,
    request: LogMessageRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    Log an externally-sent WhatsApp message (e.g. from n8n/Shopify automation)
    so it appears in the Inbox alongside the customer conversation.
    Call this endpoint AFTER your automation has already sent the message via Meta API.
    """
    pool = await get_db_pool()
    user_id = current_user['id']
    
    # Optional: fetch shopify internal ID if an order number was provided
    shopify_order_id = None
    if request.shopify_order_number and current_user.get('shopify_store_url') and current_user.get('shopify_api_token'):
        try:
            order = await fetch_shopify_order(
                request.shopify_order_number, 
                current_user['shopify_store_url'], 
                current_user['shopify_api_token']
            )
            if order:
                shopify_order_id = order['id']
                # Tag as pending initially
                asyncio.create_task(update_shopify_order_tags(
                    order_id=shopify_order_id,
                    tags_to_add=["Pending ⚠️"],
                    tags_to_remove=["Confirmed ✅", "Cancelled ❌", "No Whats 🚨"],
                    store_url=current_user['shopify_store_url'],
                    api_token=current_user['shopify_api_token']
                ))
        except Exception as e:
            logger.error(f"Failed to fetch shopify order id during log-outbound: {e}")

    async with pool.acquire() as conn:
        # Create contact if it doesn't exist yet
        display_name = request.contact_name.strip() if request.contact_name else phone
        metadata_json = json.dumps({"shopify_order_id": shopify_order_id}) if shopify_order_id else "{}"
        order_name_for_contact = request.shopify_order_number.strip().lstrip('#') if request.shopify_order_number else None
        
        initial_name = order_name_for_contact if order_name_for_contact else display_name
        
        contact = await conn.fetchrow(
            """INSERT INTO contacts (user_id, phone_number, name, metadata)
               VALUES ($1, $2, $3, $4::jsonb)
               ON CONFLICT (user_id, phone_number) DO UPDATE
                 SET updated_at = CURRENT_TIMESTAMP,
                     metadata = COALESCE(contacts.metadata, '{}'::jsonb) || $4::jsonb
               RETURNING id, phone_number, name""",
            user_id, phone, initial_name, metadata_json
        )
        
        # Smart update contact name to order numbers only
        old_name = contact['name']
        new_name = old_name
        
        import re
        if order_name_for_contact:
            # If the old name contains letters (it's a customer name), or is the phone number, overwrite it completely.
            # We only append if the old name is strictly order numbers (digits, spaces, hyphens).
            if not old_name or old_name == phone or not bool(re.match(r'^[\d\s\-]+$', old_name)):
                new_name = order_name_for_contact
            elif order_name_for_contact not in old_name.split(" - "):
                new_name = old_name + " - " + order_name_for_contact
        elif request.contact_name and old_name == phone:
            new_name = display_name
            
        if new_name != old_name:
            await conn.execute("UPDATE contacts SET name=$1 WHERE id=$2", new_name, contact['id'])
        # Get or create session; new sessions from automations start with AI paused
        session = await conn.fetchrow("SELECT * FROM sessions WHERE contact_id=$1", contact['id'])
        if not session:
            session = await conn.fetchrow(
                "INSERT INTO sessions (contact_id, is_bot_paused) VALUES ($1, $2) RETURNING *",
                contact['id'], request.pause_ai
            )
        else:
            session = await conn.fetchrow(
                "UPDATE sessions SET updated_at=CURRENT_TIMESTAMP WHERE id=$1 RETURNING *",
                session['id']
            )
        # Log the outbound message as ADMIN (externally sent)
        msg_id = await conn.fetchval(
            """INSERT INTO messages (session_id, direction, sender_type, text, meta_message_id, status)
               VALUES ($1, 'OUTBOUND', 'ADMIN', $2, $3, 'sent') RETURNING id""",
            session['id'], request.text, request.meta_message_id
        )
    # Push to dashboard via WebSocket in real-time
    await ws_manager.broadcast({
        "type": "new_message",
        "user_id": user_id,
        "data": {
            "id": str(msg_id),
            "session_id": str(session['id']),
            "phone_number": phone,
            "direction": "OUTBOUND",
            "sender_type": "ADMIN",
            "text": request.text,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    })
    logger.info(f"Logged outbound message to {phone} for user {user_id}: {request.text[:50]}")
    return {"success": True, "message_id": str(msg_id), "phone": phone}


# ── Chat Endpoints ───────────────────────────────────────────
@api_router.get("/chats")
async def get_chats(
    current_user: Dict = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    search: str = Query(None),
    unread_only: bool = Query(False)
):
    pool = await get_db_pool()
    offset = (page - 1) * limit
    async with pool.acquire() as conn:
        if search:
            search_val = f"%{search}%"
            where_clause_total = "c.user_id=$1 AND (c.phone_number ILIKE $2 OR c.name ILIKE $2)"
            where_clause_records = "c.user_id=$1 AND (c.phone_number ILIKE $4 OR c.name ILIKE $4)"
            params_total = [current_user['id'], search_val]
            params_records = [current_user['id'], limit, offset, search_val]
        else:
            where_clause_total = "c.user_id=$1"
            where_clause_records = "c.user_id=$1"
            params_total = [current_user['id']]
            params_records = [current_user['id'], limit, offset]

        if unread_only:
            where_clause_total += " AND s.unread_count > 0"
            where_clause_records += " AND s.unread_count > 0"

        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM sessions s JOIN contacts c ON s.contact_id=c.id WHERE {where_clause_total}",
            *params_total
        )
        total_unread = await conn.fetchval(
            "SELECT COUNT(*) FROM sessions s JOIN contacts c ON s.contact_id=c.id WHERE c.user_id=$1 AND s.unread_count > 0",
            current_user['id']
        )
        records = await conn.fetch(
            f"""SELECT s.*,c.phone_number,c.name as contact_name,c.created_at as contact_created_at
               FROM sessions s JOIN contacts c ON s.contact_id=c.id
               WHERE {where_clause_records} ORDER BY s.updated_at DESC LIMIT $2 OFFSET $3""",
            *params_records
        )
        result = []
        for r in records:
            last_msg = await conn.fetchrow(
                "SELECT * FROM messages WHERE session_id=$1 ORDER BY created_at DESC LIMIT 1", r['id']
            )
            cr = ContactResponse(id=str(r['contact_id']),phone_number=r['phone_number'],name=r['contact_name'],created_at=str(r['contact_created_at']))
            lm = None
            if last_msg:
                lm = MessageResponse(id=str(last_msg['id']),session_id=str(last_msg['session_id']),direction=last_msg['direction'],
                                     sender_type=last_msg['sender_type'],text=last_msg['text'],meta_message_id=last_msg['meta_message_id'],
                                     status=last_msg['status'],created_at=str(last_msg['created_at']))
            result.append(SessionResponse(id=str(r['id']),contact_id=str(r['contact_id']),is_bot_paused=r['is_bot_paused'],
                                          unread_count=r['unread_count'] or 0,
                                          created_at=str(r['created_at']),updated_at=str(r['updated_at']),contact=cr,last_message=lm))
    return {
        "chats": result,
        "total": total,
        "total_unread": total_unread,
        "page": page,
        "limit": limit,
        "has_more": (offset + len(result)) < total
    }


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
                                sender_type=m.get('sender_type') or 'CUSTOMER',
                                text=m.get('text') or '',
                                meta_message_id=m.get('meta_message_id') or '',
                                status=m['status'],created_at=str(m['created_at']),
                                media_url=m.get('media_url'), media_type=m.get('media_type')) for m in msgs]

@api_router.post("/chats/{phone}/mark-read")
async def mark_chat_read(phone: str, current_user: Dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE sessions SET unread_count=0 
               FROM contacts 
               WHERE sessions.contact_id=contacts.id 
                 AND contacts.phone_number=$1 
                 AND contacts.user_id=$2""",
            phone, current_user['id']
        )
    return {"status": "ok"}

@api_router.post("/chats/{phone}/mark-unread")
async def mark_chat_unread(phone: str, current_user: Dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE sessions SET unread_count=1 
               FROM contacts 
               WHERE sessions.contact_id=contacts.id 
                 AND contacts.phone_number=$1 
                 AND contacts.user_id=$2""",
            phone, current_user['id']
        )
    return {"status": "ok"}

@api_router.post("/chats/{phone}/send-media", response_model=MessageResponse)
async def send_media(phone: str, file: UploadFile = File(...), current_user: Dict = Depends(get_current_user)):
    file_bytes = await file.read()
    mime_type = file.content_type
    
    media_type = "document"
    ext = ".bin"
    if mime_type.startswith("image/"):
        media_type = "image"
        ext = ".jpg" if "jpeg" in mime_type else ".png"
    elif mime_type.startswith("audio/"):
        media_type = "audio"
        ext = ".ogg"
    elif mime_type.startswith("video/"):
        media_type = "video"
        ext = ".mp4"
    elif "pdf" in mime_type:
        ext = ".pdf"
    
    filename = f"out_{uuid.uuid4().hex[:8]}{ext}"
    filepath = MEDIA_DIR / filename
    filepath.write_bytes(file_bytes)
    local_url = f"/api/media/{filename}"

    # WhatsApp requires audio to be OGG Opus or MP4 AAC. Browsers often record WebM.
    # Convert audio to OGG Opus using FFMPEG if available.
    if media_type == "audio" and shutil.which("ffmpeg"):
        opus_filename = f"opus_{uuid.uuid4().hex[:8]}.ogg"
        opus_filepath = MEDIA_DIR / opus_filename
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(filepath), "-c:a", "libopus", "-b:a", "32k", str(opus_filepath)],
                check=True, capture_output=True
            )
            # FFMPEG succeeded, use the transcoded file
            file_bytes = opus_filepath.read_bytes()
            mime_type = "audio/ogg"
            filename = opus_filename
            local_url = f"/api/media/{filename}"
            logger.info(f"Successfully transcoded audio to {filename}")
        except Exception as e:
            logger.error(f"FFMPEG conversion failed: {e}")
            # Fall back to original file if conversion fails

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow(
            "INSERT INTO contacts (user_id,phone_number,name) VALUES ($1,$2,$2) ON CONFLICT (user_id,phone_number) DO UPDATE SET updated_at=CURRENT_TIMESTAMP RETURNING id",
            current_user['id'], phone)

        session = await conn.fetchrow("SELECT id FROM sessions WHERE contact_id=$1", contact['id'])
        if not session:
            session = await conn.fetchrow("INSERT INTO sessions (contact_id,is_bot_paused) VALUES ($1,TRUE) RETURNING id", contact['id'])
        else:
            session = await conn.fetchrow("UPDATE sessions SET is_bot_paused=TRUE,updated_at=CURRENT_TIMESTAMP WHERE id=$1 RETURNING id", session['id'])
        
        wa_id = await send_whatsapp_media_message(phone, media_type, file_bytes, mime_type, file.filename or filename, current_user['meta_access_token'], current_user['meta_phone_number_id'])
        msg_id, msg_created_at = await conn.fetchrow(
            """INSERT INTO messages (session_id,direction,sender_type,text,meta_message_id,status,media_url,media_type) 
               VALUES ($1,'OUTBOUND','ADMIN','',$2,'sent',$3,$4) RETURNING id,created_at""",
            session['id'], wa_id, local_url, media_type)
        
    await ws_manager.broadcast({"type":"new_message","user_id":current_user['id'],
        "data":{"id":str(msg_id),"session_id":str(session['id']),"phone_number":phone,
                "direction":"OUTBOUND","sender_type":"ADMIN","text":"",
                "media_url": local_url, "media_type": media_type,
                "created_at":str(msg_created_at)}})
    
    return MessageResponse(id=str(msg_id),session_id=str(session['id']),direction='OUTBOUND',
                           sender_type='ADMIN',text="",meta_message_id=wa_id,status='sent',created_at=str(msg_created_at),
                           media_url=local_url, media_type=media_type)

@api_router.post("/chats/{phone}/send", response_model=MessageResponse)
async def send_message(phone: str, request: SendMessageRequest, current_user: Dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow(
            "INSERT INTO contacts (user_id,phone_number,name) VALUES ($1,$2,$2) ON CONFLICT (user_id,phone_number) DO UPDATE SET updated_at=CURRENT_TIMESTAMP RETURNING id",
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
    waba_id = current_user.get('meta_waba_id')
    meta_template_id, status = None, "PENDING"
    if token and waba_id:
        try:
            # Templates are created at WABA level, NOT phone number level
            url = f"https://graph.facebook.com/v18.0/{waba_id}/message_templates"
            payload = {
                "name": request.name,
                "category": request.category,
                "language": request.language,
                "components": request.components
            }
            async with httpx.AsyncClient() as http_client:
                resp = await http_client.post(
                    url, json=payload,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                )
                logger.info(f"Create template Meta response: {resp.status_code} - {resp.text}")
                if resp.status_code == 200:
                    data = resp.json()
                    meta_template_id = data.get("id")
                    status = data.get("status", "PENDING")
                else:
                    logger.error(f"Meta create template error: {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.error(f"Create template exception: {e}")
    elif not waba_id:
        logger.warning("No WABA ID set — template saved locally only. Set WABA ID in Settings.")
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
    user_id = current_user['id']
    async with pool.acquire() as conn:
        template = await conn.fetchrow(
            "SELECT * FROM templates WHERE user_id=$1 AND name=$2 LIMIT 1",
            user_id, request.template_name
        )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Extract template body text for inbox logging
    template_text = request.template_name  # fallback
    try:
        components = json.loads(template['components']) if isinstance(template['components'], str) else template['components']
        if components:
            body = next((c for c in components if c.get('type') in ('BODY', 'body')), None)
            if body and body.get('text'):
                template_text = body['text']
    except Exception:
        pass

    sent_count, failed_count, details = 0, 0, []
    for phone in request.target_phone_numbers:
        phone = phone.strip()
        if not phone:
            continue
        try:
            message_id = await send_whatsapp_template(
                phone, request.template_name, template['language'] or 'en',
                current_user['meta_access_token'], current_user['meta_phone_number_id']
            )
            if message_id:
                sent_count += 1
                details.append({"phone": phone, "status": "sent", "message_id": message_id})

                # ── Log to inbox ─────────────────────────────────
                async with pool.acquire() as conn:
                    # Ensure contact exists
                    contact = await conn.fetchrow(
                        """INSERT INTO contacts (user_id, phone_number, name)
                           VALUES ($1, $2, $2)
                           ON CONFLICT (user_id, phone_number) DO UPDATE
                             SET updated_at = CURRENT_TIMESTAMP
                           RETURNING id, phone_number, name""",
                        user_id, phone
                    )
                    # Ensure session exists (AI paused — campaign contacts shouldn't get AI auto-replies)
                    session = await conn.fetchrow(
                        "SELECT * FROM sessions WHERE contact_id=$1", contact['id']
                    )
                    if not session:
                        session = await conn.fetchrow(
                            "INSERT INTO sessions (contact_id, is_bot_paused) VALUES ($1, TRUE) RETURNING *",
                            contact['id']
                        )
                    # Log the campaign message
                    msg_id = await conn.fetchval(
                        """INSERT INTO messages (session_id, direction, sender_type, text, meta_message_id, status)
                           VALUES ($1, 'OUTBOUND', 'ADMIN', $2, $3, 'sent') RETURNING id""",
                        session['id'], f"[Campaign: {request.template_name}] {template_text}", message_id
                    )
                # Broadcast to inbox in real-time
                await ws_manager.broadcast({
                    "type": "new_message",
                    "user_id": user_id,
                    "data": {
                        "id": str(msg_id),
                        "session_id": str(session['id']),
                        "phone_number": phone,
                        "direction": "OUTBOUND",
                        "sender_type": "ADMIN",
                        "text": f"[Campaign: {request.template_name}] {template_text}",
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
                })
            else:
                failed_count += 1
                details.append({"phone": phone, "status": "failed", "error": "No message ID returned"})
            await asyncio.sleep(0.2)
        except Exception as e:
            failed_count += 1
            details.append({"phone": phone, "status": "failed", "error": str(e)})
    return CampaignResponse(success=failed_count == 0, sent_count=sent_count, failed_count=failed_count, details=details)


# ── Bulk Order Confirmations ──────────────────────────────────
@api_router.post("/campaigns/order-confirmations")
async def bulk_order_confirmations(
    request: BulkOrderConfirmationRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    For each (phone, order_number) pair:
    1. Fetch order from Shopify
    2. Send WhatsApp template with order details
    3. Log message to inbox (so it appears in dashboard)
    """
    store_url = current_user.get('shopify_store_url')
    api_token = current_user.get('shopify_api_token')
    if not store_url or not api_token:
        raise HTTPException(
            status_code=400,
            detail="Shopify credentials not configured. Go to Settings → Shopify Integration."
        )

    pool = await get_db_pool()
    user_id = current_user['id']
    results = []

    for item in request.items:
        phone = item.phone.strip()
        order_num = item.order_number.strip().lstrip('#')
        if not phone or not order_num:
            continue
        try:
            # 1. Fetch order from Shopify
            order = await fetch_shopify_order(order_num, store_url, api_token)
            if not order:
                results.append({"phone": phone, "order": order_num, "status": "failed", "error": "Order not found in Shopify"})
                continue
            shipping  = order.get("shipping_address") or {}
            line_items = order.get("line_items", [])
            total_price = order.get("total_price", "0.00")
            order_name  = str(order.get("name", f"#{order_num}")).lstrip('#')
            contact_name = shipping.get("name") or phone

            # Build products string matching the template format
            products_text = " | ".join([
                f"{li.get('title', '')} - مقاس {li.get('variant_title') or 'N/A'} - العدد {li.get('quantity', 1)}"
                for li in line_items
            ])

            # 2. Send WhatsApp template with components
            message_id = await send_whatsapp_template_with_components(
                phone=phone,
                template_name=request.template_name,
                language="ar_EG",
                access_token=current_user['meta_access_token'],
                phone_number_id=current_user['meta_phone_number_id'],
                components=[{
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": order_name},
                        {"type": "text", "text": products_text},
                        {"type": "text", "text": f"{total_price} EGP"},
                    ]
                }]
            )
            
            # Tag in Shopify depending on whether the message sent successfully
            if message_id:
                asyncio.create_task(update_shopify_order_tags(
                    order_id=order["id"],
                    tags_to_add=["Pending ⚠️"],
                    tags_to_remove=["Confirmed ✅", "Cancelled ❌", "No Whats 🚨"],
                    store_url=store_url,
                    api_token=api_token
                ))
            else:
                asyncio.create_task(update_shopify_order_tags(
                    order_id=order["id"],
                    tags_to_add=["No Whats 🚨"],
                    tags_to_remove=["Confirmed ✅", "Cancelled ❌", "Pending ⚠️"],
                    store_url=store_url,
                    api_token=api_token
                ))

            # 3. Build readable inbox log text
            log_text = (
                f"📦 تأكيد طلب #{order_name}\n"
                f"المنتجات: {products_text}\n"
                f"الإجمالي: {total_price} EGP"
            )

            # 4. Log to inbox (same as campaigns flow)
            async with pool.acquire() as conn:
                metadata_json = json.dumps({"shopify_order_id": order["id"]})
                
                contact = await conn.fetchrow(
                    """INSERT INTO contacts (user_id, phone_number, name, metadata)
                       VALUES ($1, $2, $3, $4::jsonb)
                       ON CONFLICT (user_id, phone_number) DO UPDATE SET 
                           updated_at=CURRENT_TIMESTAMP, 
                           metadata = COALESCE(contacts.metadata, '{}'::jsonb) || $4::jsonb
                       RETURNING id, phone_number, name""",
                    user_id, phone, order_name, metadata_json
                )
                
                # Smart update contact name to order numbers only (not customer name)
                old_name = contact['name']
                new_name = old_name
                
                import re
                if not old_name or old_name == phone or not bool(re.match(r'^[\d\s\-]+$', old_name)):
                    new_name = order_name
                elif order_name not in old_name.split(" - "):
                    new_name = old_name + " - " + order_name
                    
                if new_name != old_name:
                    await conn.execute("UPDATE contacts SET name=$1 WHERE id=$2", new_name, contact['id'])

                session = await conn.fetchrow("SELECT * FROM sessions WHERE contact_id=$1", contact['id'])
                if not session:
                    session = await conn.fetchrow(
                        "INSERT INTO sessions (contact_id, is_bot_paused) VALUES ($1, TRUE) RETURNING *",
                        contact['id']
                    )
                else:
                    session = await conn.fetchrow(
                        "UPDATE sessions SET updated_at=CURRENT_TIMESTAMP WHERE id=$1 RETURNING *",
                        session['id']
                    )
                msg_id = await conn.fetchval(
                    """INSERT INTO messages (session_id, direction, sender_type, text, meta_message_id, status)
                       VALUES ($1, 'OUTBOUND', 'ADMIN', $2, $3, 'sent') RETURNING id""",
                    session['id'], log_text, message_id
                )

            # 5. Broadcast to inbox in real-time
            await ws_manager.broadcast({
                "type": "new_message",
                "user_id": user_id,
                "data": {
                    "id": str(msg_id),
                    "session_id": str(session['id']),
                    "phone_number": phone,
                    "direction": "OUTBOUND",
                    "sender_type": "ADMIN",
                    "text": log_text,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            })

            results.append({"phone": phone, "order": order_num, "status": "sent", "message_id": message_id, "contact_name": contact_name})
            logger.info(f"Order confirmation sent to {phone} for order #{order_num}")
            await asyncio.sleep(0.3)  # Rate limit: ~3/sec

        except Exception as e:
            logger.error(f"Order confirmation error for {phone} #{order_num}: {e}")
            results.append({"phone": phone, "order": order_num, "status": "failed", "error": str(e)})

    sent   = sum(1 for r in results if r['status'] == 'sent')
    failed = len(results) - sent
    return {"success": failed == 0, "sent": sent, "failed": failed, "results": results}


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
