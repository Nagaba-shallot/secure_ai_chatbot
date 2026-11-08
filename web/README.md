# Companion web app (Next.js)

Chat interface for the Secure AI Companion backend.

## Run it
```bash
# terminal 1: backend (from the repo root)
uvicorn app.main:get_app --factory --reload

# terminal 2: web app
cd web
cp .env.local.example .env.local
npm install
npm run dev          # http://localhost:3000
```

## Security design
- **Token never touches JavaScript.** The browser talks only to this app's `/api/*` routes. They keep the backend token in an `httpOnly`, `SameSite=Lax` cookie and add the `Authorization` header server-side, so an XSS bug cannot steal it.
- **Backend is private to the server.** `BACKEND_URL` is read only on the server, and there is no CORS to configure.
- **CSRF defence:** state-changing routes reject requests whose `Origin` doesn't match the app's host.
- **Input checks at the edge:** message type and length are validated before anything is forwarded, and memory ids must be numeric.
- **Security headers:** CSP (production), `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: no-referrer`.
- **Visible protection:** when the backend masks personal details or blocks a message, the chat shows a short note beside it.

## Known limitations
- Sessions are anonymous: clearing cookies loses access to the conversation. Real sign-in (email or OAuth) is on the roadmap.
- The cookie is `Secure` only in production builds; serve over HTTPS when you deploy.