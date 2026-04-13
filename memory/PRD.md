# WhatsApp AI Chatbot Platform - PRD

## Original Problem Statement
Build a production-ready AI WhatsApp chatbot platform with:
- Frontend: React with Tailwind CSS, dark modern theme
- Backend: FastAPI with MongoDB
- AI: Gemini 3 Flash via Emergent integrations
- WhatsApp: Meta Cloud API integration

## User Personas
1. **Business Admin**: Manages conversations, templates, and campaigns
2. **End Customer**: WhatsApp user who receives AI-powered responses

## Core Requirements (Static)
- Admin authentication with JWT
- Two-panel inbox for chat management
- AI-powered auto-responses using Gemini
- Per-conversation AI toggle
- WhatsApp message templates management
- Bulk campaign messaging
- Webhook handling for incoming messages and status updates
- Knowledge base ingestion for RAG

## What's Been Implemented ✅
**Date: 2026-04-12**

### Backend (FastAPI + MongoDB)
- [x] JWT authentication (login, me endpoints)
- [x] Chat management (list, messages, send, toggle AI)
- [x] Templates CRUD with Meta sync
- [x] Campaigns bulk messaging with rate limiting
- [x] Webhook verification and message processing
- [x] AI integration with Gemini 3 Flash
- [x] Knowledge ingestion for RAG
- [x] Global error handling

### Frontend (React + Tailwind)
- [x] Dark modern theme with Swiss Brutalist design
- [x] Login page with split-screen layout
- [x] Dashboard with fixed 260px sidebar
- [x] Inbox with two-panel chat view
- [x] Message bubbles (green=customer, blue=bot, gray=admin)
- [x] AI toggle switch per conversation
- [x] Templates grid with status badges
- [x] Campaigns form with phone number input
- [x] Loading skeletons
- [x] Toast notifications

### Infrastructure
- [x] Docker Compose config for PostgreSQL + pgvector (optional)
- [x] Environment variable configuration
- [x] Default admin user seeding

## Mocked/Simulated Features
- WhatsApp message sending (returns simulated IDs when no Meta credentials)
- Template sync from Meta (works only with valid credentials)

## Prioritized Backlog

### P0 (Critical - Not Started)
- [ ] Real-time message updates via WebSocket
- [ ] PostgreSQL migration for production scale

### P1 (Important)
- [ ] Knowledge base management UI
- [ ] Template creation form in dashboard
- [ ] Contact profile/details view
- [ ] Message search functionality

### P2 (Nice to Have)
- [ ] Analytics dashboard (messages sent, response times)
- [ ] Multi-agent support
- [ ] Scheduled campaigns
- [ ] Message attachments (images, documents)
- [ ] Contact import/export

## Next Tasks
1. Add Meta WhatsApp credentials and test real message flow
2. Implement WebSocket for real-time inbox updates
3. Build knowledge base management UI
4. Add template creation workflow

## Tech Decisions
- Used MongoDB instead of PostgreSQL for faster MVP (can migrate later)
- AI service integrated into main backend for simplicity
- Emergent LLM key for universal AI access

---
**Update: 2026-04-12 - WebSocket Real-Time Updates**

### Added
- [x] WebSocket endpoint `/api/ws` for real-time updates
- [x] Connection manager for broadcasting to all connected admins
- [x] "Live" indicator in inbox header showing WebSocket status
- [x] Real-time message updates when webhook receives messages
- [x] Real-time updates when admin sends messages
- [x] Auto-reconnect on WebSocket disconnect (3 second retry)
- [x] Heartbeat ping/pong every 30 seconds

### Removed
- Polling (was 3-5 second intervals) - replaced with WebSocket push
