# Meeting Intelligence frontend

React/Vite frontend connected to the FastAPI backend. The Stitch exports in
`~/Downloads/stitch_meeting_intelligence_frontend/organized/` were used as
visual references; this app uses real API responses rather than their mock data.

## Local development

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open `http://localhost:5173`. The API URL defaults to
`http://localhost:8000`. Set `VITE_API_BASE_URL` in `frontend/.env` to change it.
Start the backend separately (`docker compose up --build` from the repository
root, or the local FastAPI/PostgreSQL/Redis setup). The backend must include
`http://localhost:5173` in `CORS_ORIGINS`.

## Netlify deployment

1. Push this repository to GitHub.
2. In Netlify, choose **Add new site → Import an existing project**.
3. Set **Base directory** to `frontend`, **Build command** to `npm run build`,
   and **Publish directory** to `dist`. `frontend/netlify.toml` provides these
   defaults and the single-page redirect.
4. Add the environment variable `VITE_API_BASE_URL` with your public HTTPS API
   origin, for example `https://api.example.com` (no `/docs` suffix).
5. Redeploy after setting the variable.
6. On the FastAPI host, set `CORS_ORIGINS` to the exact Netlify URL and your
   custom frontend domain, comma-separated, for example
   `https://meeting-intelligence.netlify.app,https://app.example.com`.

Netlify serves only the frontend. It does **not** run FastAPI, PostgreSQL,
Redis, or Celery. A public Netlify page cannot access the user's
`http://localhost:8000` API; deploy the backend to a reachable HTTPS host
before expecting production login and uploads to work. Keep OpenRouter,
OpenAI, database, and encryption secrets on the backend only. The only
frontend environment variable is the public API URL.

Agent thread IDs are kept in session storage because the backend does not yet
provide a list-threads endpoint. Existing threads can still be opened using
`#agent/<thread-id>`. Authentication tokens are stored in session storage and
are cleared when that browser session ends.
