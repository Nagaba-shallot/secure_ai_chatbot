# Secure AI Companion

A conversational AI companion ("Nasha") with long-term memory, built with a security-first backend: authentication, per-user data isolation, prompt-injection defences, PII masking, memory-poisoning protection, rate limiting and a repeatable attack corpus.

## Features
- **Free to run:** uses Google Gemini by default (free-tier key, no billing); OpenAI is an optional switch (`LLM_PROVIDER=openai`)
- **Chat API** (FastAPI) with per-user conversation history
- **Long-term memory** extracted from conversations, viewable and deletable by the user
- **Auth:** opaque bearer tokens, hashed at rest
- **Defence in depth:** input validation, injection heuristics, PII/secret masking, canary-token leak detection, output filtering, memory validation
- **Privacy:** only masked text is stored; `DELETE /me` erases an account and its data
- **Tested:** unit tests, API tests with a fake LLM, an attack corpus, CI on every push

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # add your GEMINI_API_KEY (free key from Google AI Studio)
uvicorn app.main:get_app --factory --reload
```
Open http://localhost:8000/docs, then:
```bash
TOKEN=$(curl -s -X POST localhost:8000/auth/register | python -c "import sys,json;print(json.load(sys.stdin)['token'])")
curl -s -X POST localhost:8000/chat -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" -d '{"message":"hey, long day today"}'
```

## Endpoints
| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/register` | Create an account, returns a token (shown once) |
| POST | `/chat` | Send a message, get a reply plus `security_action` |
| GET | `/memories` | List what the companion remembers |
| DELETE | `/memories/{id}` | Forget one memory |
| DELETE | `/me` | Delete the account and all its data |
| GET | `/health` | Liveness check |

## Tests and attacks
```bash
pytest                              # unit + API tests (no real LLM calls)
python attacks/run_attacks.py --report   # runs the attack corpus, writes docs/attack-report.md
```

## Security docs
- [Threat model (STRIDE)](docs/threat-model.md)
- [Attack report](docs/attack-report.md)

## Roadmap
- [ ] Web UI (Next.js) and mobile client
- [ ] Voice (speech-to-text and text-to-speech)
- [ ] Model-based injection classifier to close the known gaps
- [ ] Redis-backed rate limiting, Docker and deployment
- [ ] Simulated IoT "wellness" sensor behind tool-level access control