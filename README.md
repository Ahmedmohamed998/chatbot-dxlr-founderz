# WhatsApp AI Chatbot Platform

A production-ready AI-powered WhatsApp automation platform for modern businesses.

## Features

- **AI-Powered Conversations**: Gemini 3 Flash handles customer conversations automatically
- **Admin Dashboard**: Modern dark-themed dashboard with inbox, templates, and campaigns management
- **Two-Panel Inbox**: View all conversations with real-time message history
- **AI Toggle**: Pause/resume AI for individual conversations to take over manually
- **Message Templates**: Sync and manage WhatsApp approved message templates from Meta
- **Bulk Campaigns**: Send template messages to multiple contacts with rate limiting
- **Webhook Integration**: Process incoming WhatsApp messages and delivery status updates
- **Knowledge Base**: Ingest custom knowledge for RAG-powered responses

## Tech Stack

- **Frontend**: React 19, Tailwind CSS, Lucide React icons
- **Backend**: FastAPI, Python 3.11
- **Database**: PostgreSQL (with pgvector for embeddings)
- **AI**: Gemini 1.5 Flash API
- **WhatsApp**: Meta Cloud API (Graph API v18+)

## Production VPS Deployment (chatbot.matbkh-elcontent.com)

This app is fully containerized with Docker and ready to deploy on any VPS inside an Nginx reverse-proxied environment.

### 1. Connecting to GitHub Desktop
1. Open GitHub Desktop and click "Add > Add Local Repository..." and point it to this project folder.
2. Publish to your GitHub account (private or public).
3. On your VPS (`187.124.168.34`), clone the repository:
```bash
git clone <your-repo-url>
cd chatbot-dxlr-founderz-main
```

### 2. Configure Production Secrets
Create your `.env` file from the example:
```bash
cp .env.example .env
```
Ensure you have updated the variables inside, most importantly your backend URL for the React production dashboard:
```env
REACT_APP_BACKEND_URL=https://chatbot.matbkh-elcontent.com
```

### 3. Setup Nginx Reverse Proxy
Copy the provided `vps_nginx.conf` file to your server's Nginx configuration to point traffic:
```bash
sudo cp vps_nginx.conf /etc/nginx/sites-available/whatsapp
sudo ln -s /etc/nginx/sites-available/whatsapp /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```
*(Optionally run `sudo certbot --nginx` to auto-install SSL certificates on your domain!)*

### 4. Build and Run!
Execute Docker Compose to bring the entire stack online:
```bash
sudo docker-compose up --build -d
```
Your vector database, backend API, and React frontend are now online.

### 1. Clone the repository

```bash
git clone <repo-url>
cd whatsapp-ai-bot
```

### 2. Configure environment variables

Copy the example file and configure your credentials. Docker Compose will automatically read this file:

```bash
cp .env.example .env
# Edit .env with your credentials
```

### Required Environment Variables (.env):

```env
# Database Configuration
POSTGRES_USER=whatsapp_user
POSTGRES_PASSWORD=whatsapp_pass
POSTGRES_DB=whatsapp_db

# Security
JWT_SECRET=your-super-secret-jwt-key

# Meta / WhatsApp API
META_ACCESS_TOKEN=your-meta-access-token
META_PHONE_NUMBER_ID=your-phone-number-id
META_VERIFY_TOKEN=your-webhook-verify-token

# AI / Gemini
GEMINI_API_KEY=your-gemini-api-key
```

### Configure WhatsApp Webhook

In your Meta Developer Console:
1. Go to WhatsApp > Configuration
2. Set Webhook URL: `https://your-domain.com/api/webhook`
3. Set Verify Token: Same as `META_VERIFY_TOKEN` in .env
4. Subscribe to: `messages`, `message_status`

## Default Credentials

- **Admin Username**: admin
- **Admin Password**: Admin123!

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login with username/password
- `GET /api/auth/me` - Get current user info

### Chats
- `GET /api/chats` - List all conversations
- `GET /api/chats/{phone}/messages` - Get message history
- `POST /api/chats/{phone}/send` - Send manual message
- `PUT /api/chats/{phone}/toggle-ai` - Toggle AI bot

### Templates
- `GET /api/templates` - List templates (syncs from Meta)
- `POST /api/templates` - Create new template

### Campaigns
- `POST /api/campaigns/send` - Send bulk template messages

### Webhook
- `GET /api/webhook` - Verify webhook (Meta challenge)
- `POST /api/webhook` - Receive incoming messages/status

### AI
- `POST /api/ai/ingest` - Ingest knowledge base content
- `POST /api/ai/chat` - Generate AI response

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  React Frontend │────▶│  FastAPI        │────▶│  PostgreSQL     │
│  (Port 3000)    │     │  (Port 8001)    │     │  (pgvector)     │
│                 │     │                 │     │                 │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    ▼                         ▼
          ┌─────────────────┐     ┌─────────────────┐
          │                 │     │                 │
          │  Meta WhatsApp  │     │  Gemini AI      │
          │  Cloud API      │     │  Vector & Gen   │
          │                 │     │                 │
          └─────────────────┘     └─────────────────┘
```

## License

MIT
