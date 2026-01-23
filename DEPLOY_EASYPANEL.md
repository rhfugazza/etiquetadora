EasyPanel deployment (API only)
===============================

This repo is deployed as one EasyPanel app that serves:
- FastAPI API

n8n should run as a separate EasyPanel app.

Single app (API)
----------------
1) Create a new app in EasyPanel from GitHub.
2) Build type: Dockerfile
3) Dockerfile path: `Dockerfile`
4) Expose port: `8000`
5) Add a persistent volume mounted at `/data`
6) Environment variables:
   - `API_KEY` = `ROTATIVA-PRINT-2025` (or your own)
   - Optional (already defaulted in Dockerfile):
     - `QUEUE_FILE=/data/queue`
     - `PRINT_QUEUE_FILE=/data/print_queue`
     - `INFLIGHT_FILE=/data/inflight`
     - `LOG_FILE=/data/print_log`

n8n (separate app)
------------------
Use the official image `n8nio/n8n` in EasyPanel. Minimum env examples:
- `N8N_HOST=your-n8n-domain`
- `N8N_PROTOCOL=https`
- `WEBHOOK_URL=https://your-n8n-domain/`
- `N8N_PORT=5678`
- `NODE_ENV=production`
- `TZ=America/Sao_Paulo`

Also add a persistent volume at `/home/node/.n8n`.

Update n8n flows
----------------
Replace all `http://127.0.0.1:8000` URLs with your API domain, for example:
`https://your-api-domain/jobs`

Local print agent config
------------------------
On the PC connected to the printer:
1) Copy `agent_config.example.json` to `agent_config.json`
2) Set:
   - `api_base_url=https://your-api-domain`
   - `api_key` to match the API key
3) Run `start_agent.bat`

Note
----
The Lovable front-end will be deployed later as a separate app.
