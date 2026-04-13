from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Query, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Set
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
import httpx
import asyncio
from contextlib import asynccontextmanager
import json
import asyncpg
from asyncpg import Pool

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Environment variables
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://whatsapp_user:whatsapp_pass@postgres:5432/whatsapp_db')
JWT_SECRET = os.environ.get('JWT_SECRET', 'your-super-secret-jwt-key')
META_ACCESS_TOKEN = os.environ.get('META_ACCESS_TOKEN', '')
META_PHONE_NUMBER_ID = os.environ.get('META_PHONE_NUMBER_ID', '')
META_VERIFY_TOKEN = os.environ.get('META_VERIFY_TOKEN', 'whatsapp-verify-token')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

# DB Pool
db_pool: Optional[Pool] = None

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

async def get_db_pool() -> Pool:
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return db_pool

async def init_db():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        admin = await conn.fetchrow('SELECT * FROM users WHERE username = $1', 'admin')
        if not admin:
            password_hash = bcrypt.hashpw('Admin123!'.encode(), bcrypt.gensalt()).decode()
            await conn.execute(
                "INSERT INTO users (username, password_hash) VALUES ($1, $2)",
                "admin", password_hash
            )
            logger.info("Created default admin user")

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

# Pydantic Models
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str
    user: Dict[str, Any]

class UserResponse(BaseModel):
    id: str
    username: str
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

class ChatRequest(BaseModel):
    phone_number: str
    incoming_message_text: str
    message_history: Optional[List[Dict[str, str]]] = []

class ChatResponse(BaseModel):
    generated_text: str

# Helpers
def create_token(user_id: int, username: str) -> str:
    payload = {
        'user_id': user_id,
        'username': username,
        'exp': datetime.now(timezone.utc) + timedelta(hours=24)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def verify_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return verify_token(credentials.credentials)

# AI Embedding logic from ai_service.py
def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i:i + chunk_size]
        chunks.append(' '.join(chunk_words))
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
        logger.error(f"Embedding generation error: {e}")
        return [0.0] * 768

async def search_similar_chunks(query_embedding: List[float], limit: int = 4) -> List[Dict]:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
        results = await conn.fetch(
            """
            SELECT id, content, metadata, 
                   1 - (embedding <=> $1::vector) as similarity
            FROM knowledge_chunks
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            embedding_str, limit
        )
        return [{"id": r['id'], "content": r['content'], "metadata": r['metadata'], "similarity": float(r['similarity']) if r['similarity'] else 0} for r in results]

async def send_whatsapp_message(phone: str, text: str) -> Optional[str]:
    if not META_ACCESS_TOKEN or not META_PHONE_NUMBER_ID:
        import uuid
        return f"wamid.simulated_{uuid.uuid4().hex[:12]}"
    url = f"https://graph.facebook.com/v18.0/{META_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {META_ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": phone, "type": "text", "text": {"body": text}}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return data.get("messages", [{}])[0].get("id")
            return None
    except Exception:
        return None

async def send_whatsapp_template(phone: str, template_name: str, language: str = "en") -> Optional[str]:
    if not META_ACCESS_TOKEN or not META_PHONE_NUMBER_ID:
        import uuid
        return f"wamid.template_{uuid.uuid4().hex[:12]}"
    url = f"https://graph.facebook.com/v18.0/{META_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {META_ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": phone, "type": "template", "template": {"name": template_name, "language": {"code": language}}}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return data.get("messages", [{}])[0].get("id")
            return None
    except Exception:
        return None

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

@api_router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow('SELECT * FROM users WHERE username = $1', request.username)
        if not user or not bcrypt.checkpw(request.password.encode(), user['password_hash'].encode()):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = create_token(user['id'], user['username'])
        return LoginResponse(
            token=token,
            user={"id": str(user['id']), "username": user['username'], "created_at": str(user['created_at'])}
        )

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: Dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow('SELECT * FROM users WHERE id = $1', current_user['user_id'])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return UserResponse(id=str(user['id']), username=user['username'], created_at=str(user['created_at']))

@api_router.get("/webhook")
async def verify_webhook(hub_mode: str = Query(None, alias="hub.mode"), hub_verify_token: str = Query(None, alias="hub.verify_token"), hub_challenge: str = Query(None, alias="hub.challenge")):
    if hub_mode == "subscribe" and hub_verify_token == META_VERIFY_TOKEN:
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
                
                if "messages" in value:
                    for message in value["messages"]:
                        phone = message.get("from", "")
                        text = message.get("text", {}).get("body", "")
                        meta_message_id = message.get("id", "")
                        
                        if phone and text:
                            async with pool.acquire() as conn:
                                # Upsert contact
                                contact = await conn.fetchrow("""
                                    INSERT INTO contacts (phone_number, name) VALUES ($1, $2)
                                    ON CONFLICT (phone_number) DO UPDATE SET name = EXCLUDED.name
                                    RETURNING id, phone_number
                                """, phone, phone)
                                
                                # Session
                                session = await conn.fetchrow("SELECT * FROM sessions WHERE contact_id = $1", contact['id'])
                                if not session:
                                    session = await conn.fetchrow("""
                                        INSERT INTO sessions (contact_id, is_bot_paused) VALUES ($1, FALSE) RETURNING *
                                    """, contact['id'])
                                else:
                                    session = await conn.fetchrow("""
                                        UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = $1 RETURNING *
                                    """, session['id'])
                                
                                # Message
                                msg_id = await conn.fetchval("""
                                    INSERT INTO messages (session_id, direction, sender_type, text, meta_message_id, status)
                                    VALUES ($1, 'INBOUND', 'CUSTOMER', $2, $3, 'received')
                                    RETURNING id
                                """, session['id'], text, meta_message_id)
                                
                                inbound_msg_time = datetime.now(timezone.utc).isoformat()
                                await ws_manager.broadcast({
                                    "type": "new_message",
                                    "data": {"id": str(msg_id), "session_id": str(session['id']), "phone_number": phone, "direction": "INBOUND", "sender_type": "CUSTOMER", "text": text, "created_at": inbound_msg_time}
                                })
                                
                                if not session.get('is_bot_paused', False):
                                    # Handle AI
                                    history = await conn.fetch("""
                                        SELECT direction, text FROM messages WHERE session_id = $1 ORDER BY created_at DESC LIMIT 10
                                    """, session['id'])
                                    
                                    message_history = [
                                        {"role": "user" if m['direction'] == 'INBOUND' else "assistant", "content": m['text']}
                                        for m in reversed(history)
                                    ]
                                    
                                    ai_response = await generate_ai_response(phone, text, message_history)
                                    if ai_response:
                                        wa_message_id = await send_whatsapp_message(phone, ai_response)
                                        bot_msg_id = await conn.fetchval("""
                                            INSERT INTO messages (session_id, direction, sender_type, text, meta_message_id, status)
                                            VALUES ($1, 'OUTBOUND', 'BOT', $2, $3, 'sent')
                                            RETURNING id
                                        """, session['id'], ai_response, wa_message_id)
                                        bot_msg_time = datetime.now(timezone.utc).isoformat()
                                        await ws_manager.broadcast({
                                            "type": "new_message",
                                            "data": {"id": str(bot_msg_id), "session_id": str(session['id']), "phone_number": phone, "direction": "OUTBOUND", "sender_type": "BOT", "text": ai_response, "created_at": bot_msg_time}
                                        })
                
                if "statuses" in value:
                    for status in value["statuses"]:
                        meta_message_id = status.get("id", "")
                        status_value = status.get("status", "")
                        if meta_message_id and status_value:
                            async with pool.acquire() as conn:
                                await conn.execute("UPDATE messages SET status = $1 WHERE meta_message_id = $2", status_value, meta_message_id)
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/chats", response_model=List[SessionResponse])
async def get_chats(current_user: Dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch("""
            SELECT s.*, c.phone_number, c.name as contact_name, c.created_at as contact_created_at
            FROM sessions s
            JOIN contacts c ON s.contact_id = c.id
            ORDER BY s.updated_at DESC
            LIMIT 100
        """)
        
        result = []
        for r in records:
            last_msg = await conn.fetchrow("""
                SELECT * FROM messages WHERE session_id = $1 ORDER BY created_at DESC LIMIT 1
            """, r['id'])
            
            contact_resp = ContactResponse(id=str(r['contact_id']), phone_number=r['phone_number'], name=r['contact_name'], created_at=str(r['contact_created_at']))
            last_message = None
            if last_msg:
                last_message = MessageResponse(id=str(last_msg['id']), session_id=str(last_msg['session_id']), direction=last_msg['direction'], sender_type=last_msg['sender_type'], text=last_msg['text'], meta_message_id=last_msg['meta_message_id'], status=last_msg['status'], created_at=str(last_msg['created_at']))
            
            result.append(SessionResponse(id=str(r['id']), contact_id=str(r['contact_id']), is_bot_paused=r['is_bot_paused'], created_at=str(r['created_at']), updated_at=str(r['updated_at']), contact=contact_resp, last_message=last_message))
        return result

@api_router.get("/chats/{phone}/messages", response_model=List[MessageResponse])
async def get_chat_messages(phone: str, current_user: Dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow("SELECT id FROM contacts WHERE phone_number = $1", phone)
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        session = await conn.fetchrow("SELECT id FROM sessions WHERE contact_id = $1", contact['id'])
        if not session:
            return []
        messages = await conn.fetch("SELECT * FROM messages WHERE session_id = $1 ORDER BY created_at ASC LIMIT 1000", session['id'])
        return [MessageResponse(id=str(m['id']), session_id=str(m['session_id']), direction=m['direction'], sender_type=m['sender_type'], text=m['text'], meta_message_id=m['meta_message_id'], status=m['status'], created_at=str(m['created_at'])) for m in messages]

@api_router.post("/chats/{phone}/send", response_model=MessageResponse)
async def send_message(phone: str, request: SendMessageRequest, current_user: Dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow("""
            INSERT INTO contacts (phone_number, name) VALUES ($1, $2)
            ON CONFLICT (phone_number) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
        """, phone, phone)
        
        session = await conn.fetchrow("SELECT id FROM sessions WHERE contact_id = $1", contact['id'])
        if not session:
            session = await conn.fetchrow("INSERT INTO sessions (contact_id, is_bot_paused) VALUES ($1, TRUE) RETURNING id", contact['id'])
        else:
            session = await conn.fetchrow("UPDATE sessions SET is_bot_paused = TRUE, updated_at = CURRENT_TIMESTAMP WHERE id = $1 RETURNING id", session['id'])
        
        wa_message_id = await send_whatsapp_message(phone, request.text)
        
        msg_id, msg_created_at = await conn.fetchrow("""
            INSERT INTO messages (session_id, direction, sender_type, text, meta_message_id, status)
            VALUES ($1, 'OUTBOUND', 'ADMIN', $2, $3, 'sent')
            RETURNING id, created_at
        """, session['id'], request.text, wa_message_id)
        
        await ws_manager.broadcast({
            "type": "new_message",
            "data": {"id": str(msg_id), "session_id": str(session['id']), "phone_number": phone, "direction": "OUTBOUND", "sender_type": "ADMIN", "text": request.text, "created_at": str(msg_created_at)}
        })
        
        return MessageResponse(id=str(msg_id), session_id=str(session['id']), direction='OUTBOUND', sender_type='ADMIN', text=request.text, meta_message_id=wa_message_id, status='sent', created_at=str(msg_created_at))

@api_router.put("/chats/{phone}/toggle-ai")
async def toggle_ai(phone: str, request: ToggleAIRequest, current_user: Dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        contact = await conn.fetchrow("SELECT id FROM contacts WHERE phone_number = $1", phone)
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        await conn.execute("UPDATE sessions SET is_bot_paused = $1, updated_at = CURRENT_TIMESTAMP WHERE contact_id = $2", request.is_paused, contact['id'])
    return {"success": True, "is_paused": request.is_paused}

@api_router.get("/templates", response_model=List[TemplateResponse])
async def get_templates(current_user: Dict = Depends(get_current_user)):
    pool = await get_db_pool()
    if META_ACCESS_TOKEN and META_PHONE_NUMBER_ID:
        try:
            url = f"https://graph.facebook.com/v18.0/{META_PHONE_NUMBER_ID}/message_templates"
            headers = {"Authorization": f"Bearer {META_ACCESS_TOKEN}"}
            async with httpx.AsyncClient() as http_client:
                response = await http_client.get(url, headers=headers)
                if response.status_code == 200:
                    templates = response.json().get("data", [])
                    async with pool.acquire() as conn:
                        for t in templates:
                            await conn.execute("""
                                INSERT INTO templates (name, category, language, status, components, meta_template_id)
                                VALUES ($1, $2, $3, $4, $5, $6)
                                ON CONFLICT DO NOTHING
                                -- Simplistic upsert strategy given schema config
                            """, t.get("name"), t.get("category"), t.get("language"), t.get("status"), json.dumps(t.get("components")), t.get("id"))
        except Exception as e:
            logger.error(f"Failed to fetch Meta templates: {e}")
            
    async with pool.acquire() as conn:
        templates = await conn.fetch("SELECT * FROM templates ORDER BY created_at DESC LIMIT 100")
        return [TemplateResponse(id=str(t['id']), name=t['name'], category=t['category'], language=t['language'], status=t['status'], components=json.loads(t['components']) if t['components'] and isinstance(t['components'], str) else t['components'], meta_template_id=t['meta_template_id'], created_at=str(t['created_at'])) for t in templates]

@api_router.post("/templates", response_model=TemplateResponse)
async def create_template(request: CreateTemplateRequest, current_user: Dict = Depends(get_current_user)):
    meta_template_id = None
    status = "PENDING"
    if META_ACCESS_TOKEN and META_PHONE_NUMBER_ID:
        try:
            url = f"https://graph.facebook.com/v18.0/{META_PHONE_NUMBER_ID}/message_templates"
            headers = {"Authorization": f"Bearer {META_ACCESS_TOKEN}", "Content-Type": "application/json"}
            payload = {"name": request.name, "category": request.category, "language": request.language, "components": request.components}
            async with httpx.AsyncClient() as http_client:
                response = await http_client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    meta_template_id = data.get("id")
                    status = data.get("status", "PENDING")
        except Exception:
            pass
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO templates (name, category, language, status, components, meta_template_id)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, created_at
        """, request.name, request.category, request.language, status, json.dumps(request.components), meta_template_id)
        return TemplateResponse(id=str(row['id']), name=request.name, category=request.category, language=request.language, status=status, components=request.components, meta_template_id=meta_template_id, created_at=str(row['created_at']))

@api_router.post("/campaigns/send", response_model=CampaignResponse)
async def send_campaign(request: CampaignRequest, current_user: Dict = Depends(get_current_user)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        template = await conn.fetchrow("SELECT * FROM templates WHERE name = $1 LIMIT 1", request.template_name)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    sent_count, failed_count, details = 0, 0, []
    for phone in request.target_phone_numbers:
        phone = phone.strip()
        if not phone: continue
        try:
            message_id = await send_whatsapp_template(phone, request.template_name, template['language'] or 'en')
            if message_id:
                sent_count += 1
                details.append({"phone": phone, "status": "sent", "message_id": message_id})
            else:
                failed_count += 1
                details.append({"phone": phone, "status": "failed", "error": "API returned no message ID"})
            await asyncio.sleep(0.2)
        except Exception as e:
            failed_count += 1
            details.append({"phone": phone, "status": "failed", "error": str(e)})
    return CampaignResponse(success=failed_count==0, sent_count=sent_count, failed_count=failed_count, details=details)

async def generate_ai_response(phone_number: str, incoming_message: str, message_history: List[Dict]) -> str:
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
        query_embedding = await generate_embedding(incoming_message)
        relevant_chunks = await search_similar_chunks(query_embedding, limit=4)
        
        context = ""
        if relevant_chunks:
            context = "\n\nRelevant Knowledge:\n" + "\n".join([f"- {c['content']}" for c in relevant_chunks])
            
        system_message = f"You are a helpful WhatsApp chatbot assistant. Be concise, friendly, and helpful.\n{context}\n\nInstructions:\n- Answer questions based on the knowledge provided above when relevant\n- Keep responses brief and suitable for WhatsApp messaging\n- Be helpful and conversational\n- If you don't know something, be honest about it"
        
        history_text = "\n".join([f"{'Customer' if msg.get('role') == 'user' else 'Assistant'}: {msg.get('content', '')}" for msg in message_history[-5:]]) if message_history else ""
        full_message = f"Previous conversation:\n{history_text}\n\nNew message: {incoming_message}" if history_text else incoming_message
        
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=full_message,
            config=types.GenerateContentConfig(
                system_instruction=system_message
            )
        )
        return response.text
    except Exception as e:
        logger.error(f"AI generation error: {e}")
        return "I apologize, but I'm having trouble processing your message right now. Please try again in a moment."

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
                await conn.execute("INSERT INTO knowledge_chunks (content, embedding, metadata) VALUES ($1, $2::vector, $3)", chunk, embedding_str, json.dumps(request.metadata) if request.metadata else None)
                chunks_created += 1
        return IngestResponse(success=True, chunks_created=chunks_created, message=f"Successfully ingested {chunks_created} chunks")
    except Exception as e:
        logger.error(f"Ingest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/ai/chat", response_model=ChatResponse)
async def ai_chat(request: ChatRequest):
    response = await generate_ai_response(request.phone_number, request.incoming_message_text, request.message_history or [])
    return ChatResponse(generated_text=response)

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

@api_router.get("/")
async def root():
    return {"message": "WhatsApp AI Chatbot API"}

app.include_router(api_router)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','), allow_methods=["*"], allow_headers=["*"])

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=500, content={"error": str(exc)})
