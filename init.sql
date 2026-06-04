-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- USERS TABLE (multi-tenant: each user is a tenant)
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user' CHECK (role IN ('super_admin', 'user')),
    business_name VARCHAR(255),
    -- Each user stores their own WhatsApp credentials
    meta_access_token TEXT,
    meta_phone_number_id VARCHAR(255),
    meta_verify_token VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- CONTACTS TABLE (scoped per user/tenant)
-- ============================================================
CREATE TABLE IF NOT EXISTS contacts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    phone_number VARCHAR(50) NOT NULL,
    name VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, phone_number)
);

-- ============================================================
-- SESSIONS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    is_bot_paused BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- MESSAGES TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    direction VARCHAR(20) NOT NULL CHECK (direction IN ('INBOUND', 'OUTBOUND')),
    sender_type VARCHAR(20) NOT NULL CHECK (sender_type IN ('CUSTOMER', 'BOT', 'ADMIN')),
    text TEXT NOT NULL,
    meta_message_id VARCHAR(255),
    status VARCHAR(20) DEFAULT 'sent',
    media_url VARCHAR(255),
    media_type VARCHAR(50),
    reply_to_message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TEMPLATES TABLE (scoped per user/tenant)
-- ============================================================
CREATE TABLE IF NOT EXISTS templates (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    language VARCHAR(20),
    status VARCHAR(50),
    components JSONB,
    meta_template_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- KNOWLEDGE CHUNKS TABLE (scoped per user/tenant)
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(768),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_contacts_user ON contacts(user_id);
CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone_number);
CREATE INDEX IF NOT EXISTS idx_contacts_user_phone ON contacts(user_id, phone_number);
CREATE INDEX IF NOT EXISTS idx_sessions_contact ON sessions(contact_id);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_templates_user ON templates(user_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_user ON knowledge_chunks(user_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_embedding ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_users_phone_number_id ON users(meta_phone_number_id);
