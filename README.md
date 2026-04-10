# HiivBuddy

HiivBuddy is a **decision helper** web app. You describe a real choice you’re facing (job offer, product direction, spend, etc.), and a small **panel of AI advisors** discusses it in a **timed session**—each turn is short (up to three sentences), others may **interject** in parallel, and the clock stops new debate turns before the final segment. After that, each advisor **votes** on concrete options. When enough of them agree, that feeds into a **final written report** with options, risks, and next steps. The **last 30 seconds** of the session length you choose are reserved for the **Chief Synthesizer** (closing analysis uses a single batched options/votes/stance pass when possible).

It’s inspired by “swarm” style thinking: not one chatbot answer, but several perspectives that have to engage with each other before a summary.

---

## What you get

- **Decision Room** — Paste your context, **attach** `.txt` / `.md` / `.pdf` (PDF text is extracted via the API), pick a model, and run the flow. **Export Markdown** downloads the current or saved session (context, transcript, votes, report).
- **Timed debate** — You set **session length** (60–600 seconds). The API runs debate until the **debate budget** (`session_duration_sec − 30`) elapses, then runs vote + synthesis. Primary turns are capped at **three sentences**; optional **parallel interjections** after each speaker.
- **Vote** — The system proposes a few clear options from the debate; each advisor picks one. You’ll see counts and whether a **consensus** threshold was met (default: 3 out of 5).
- **Final report** — A structured summary: overview, ranked options, risks, suggested next steps.
- **Saved runs** — Each completed run is stored locally in a small database file on the API side so you can build on this later (e.g. history screens).

---

## How it’s organized (simple picture)

- **`apps/web`** — The website you use in the browser (Next.js).
- **`apps/api`** — The backend that talks to the AI provider and streams results (FastAPI).
- **`docker-compose.yml`** — Optional way to run both in containers.

You normally run **two processes** while developing: the API on port **8000** and the website on port **3000**.

---

## What you need installed

- **Node.js** (for the website) — [nodejs.org](https://nodejs.org/)
- **Python 3.11+** (for the API)
- **An API key** for your AI provider (see below)

Optional:

- **Docker** — if you prefer `docker compose` instead of local Node/Python.

---

## Configuration (environment variables)

**Backend (`apps/api`)** reads a file named **`.env`** in the **`apps/api`** folder when you start the API from that folder.

1. Copy the example file:
   - From the **project root**, copy [`.env.example`](.env.example) to **`apps/api/.env`** (you can merge the API-related lines if you already use a root `.env` for Docker).

2. Set at least **one** of:
   - **`NVIDIA_API_KEY`** — for NVIDIA’s OpenAI-compatible API (common setup for this project).
   - **`OPENAI_API_KEY`** — for OpenAI or other providers that use the same style of client.

Other useful variables are documented in [`.env.example`](.env.example) (temperature, max tokens, thinking mode for certain models, etc.).

- **`LLM_DEFAULT_MODEL`** — Default chat model id for `/debate/stream` when the JSON body does not override `model`. Set this in **`apps/api/.env`** to switch models without changing code.
- **`LLM_MERGE_SYSTEM_INTO_USER`** — Optional `true` / `false`. Some OpenAI-compatible models (e.g. **Gemma**) return *System role not supported*; the API normally merges system prompts into the user message automatically for those models. Set explicitly if your provider always requires or forbids merging.

**Frontend (`apps/web`)** needs to know where the API lives. Create **`apps/web/.env.local`**:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
# Optional: default model shown in Decision Room (should match your provider)
# NEXT_PUBLIC_DEFAULT_MODEL=stepfun-ai/step-3.5-flash
```

If the API runs elsewhere, change this URL to match.

**Docker:** put a **`.env`** in the **project root** (same folder as `docker-compose.yml`) with your keys; Compose loads it for the API service.

---

## Run commands (local development)

Open **two terminals** from the **project root** (`HiivBuddy`).

**Terminal 1 — API**

```bash
cd apps/api
pip install -r requirements.txt
# Ensure apps/api/.env exists with your key(s)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Check that it’s up: open `http://127.0.0.1:8000/health` — you should see a small JSON “ok” style response.

**Terminal 2 — Website**

```bash
cd apps/web
npm install
# Ensure apps/web/.env.local exists (see above)
npm run dev
```

Open **`http://localhost:3000`**, go to **Decision Room**, paste enough context (the app asks for a minimum length), set **session length** (60–600 seconds), then **Run debate**.

**`POST /debate/stream` body (JSON):** `context`, `model`, `session_duration_sec` (60–600), `consensus_threshold` (1–5), `enable_interjections`. The server uses a **monotonic clock**: primary debate runs until **`session_duration_sec − 30`** seconds have passed (checked before each new speaker). The **last 30 seconds** of the chosen duration are reserved on that clock for vote extraction, stance signals, and the **Chief Synthesizer**. The synthesizer HTTP call uses a **separate, longer** server timeout (90s in `SYNTH_API_TIMEOUT_SEC`) so slow endpoints can still return a full JSON report.

**`POST /context/extract` (multipart form-data, field `file`):** Extract plain text from **`.txt`**, **`.md` / `.markdown`**, or **`.pdf`** for use as debate context. Limits: **8 MB** raw file size, **65,536** characters of extracted text (truncated with `truncated: true` in JSON if longer). The Decision Room reads **`.txt` / `.md` in the browser** and sends **PDFs** to this endpoint. The combined context field is capped at **65,536 characters** in the UI to match.

---

## Using Make (shortcut)

If you have **`make`** installed (common on Mac/Linux; on Windows, Git Bash often includes it):

```bash
make help          # List targets
make install       # Install API + web dependencies
make dev-api       # Start API (port 8000)
make dev-web       # Start web (port 3000)
make build-web     # Production build of the website
make docker-up     # Build and start API + web via Docker
make docker-down   # Stop Docker stack
```

Run **`make dev-api`** and **`make dev-web`** in **two separate terminals**.

**Windows PowerShell** (no `make`, or scripts in the current folder): from the project root, run **`.\dev-api.cmd`** and **`.\dev-web.cmd`** in two terminals. PowerShell does not run `dev-api.cmd` by name alone—you need the **`.\`** prefix.

---

## Docker (optional)

From the **project root**:

```bash
docker compose up --build
```

- Website: `http://localhost:3000`
- API: `http://localhost:8000`

Ensure **root** `.env` contains the variables the API needs (see [`.env.example`](.env.example)).

---

## Split deploy: Vercel (web) + free API host

The web app is a standard **Next.js** app under **`apps/web`**; the API is **FastAPI** under **`apps/api`**. Deploy them as two services and point the browser at the API with **`NEXT_PUBLIC_API_URL`**.

### Vercel (frontend)

1. Create a project from this repo and set **Root Directory** to **`apps/web`** (Framework Preset: Next.js).
2. In **Project → Settings → Environment Variables**, set **`NEXT_PUBLIC_API_URL`** to your public API base URL (HTTPS, **no trailing slash**), e.g. `https://hiivbuddy-api.onrender.com`.
3. Deploy. Preview deployments get their own `*.vercel.app` URLs; add each origin you use to **`CORS_ORIGINS`** on the API (see below), or use your production Vercel domain only.

### API on Render, Railway, Fly.io, etc.

1. Create a **Web Service** (or equivalent) with **root / working directory** **`apps/api`**.
2. **Build:** `pip install -r requirements.txt`  
   **Start:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`  
   (Or rely on the included **[`apps/api/Procfile`](apps/api/Procfile)** if your host supports it.)
3. Set the same secrets as local development: **`OPENAI_API_KEY`** and/or **`NVIDIA_API_KEY`**, **`LLM_DEFAULT_MODEL`**, and any other variables from [`.env.example`](.env.example).
4. Set **`CORS_ORIGINS`** to a comma-separated list of allowed browser origins, e.g. `https://your-app.vercel.app,https://www.yourdomain.com`. Local **`http://localhost:3000`** is included by default on the API so you can still develop against a remote API if needed.
5. **SQLite:** By default the database lives under **`apps/api/data`**. On many free hosts the filesystem is **ephemeral** (data can be lost on redeploy or sleep). For anything beyond demos, attach a **persistent disk** and set **`HIIVBUDDY_DATA_DIR`** to a path on that volume, or move to a managed database later.

---

## Troubleshooting (plain language)

- **`ENOENT` / `build-manifest.json` under `.next/server/pages/_app`** — Stale or mixed dev/build cache, or Turbopack dev expecting paths that aren’t present. From **`apps/web`**, delete the cache and restart: remove the **`.next`** folder, then run **`npm run dev`** again. Default **`npm run dev`** uses the webpack dev server; use **`npm run dev:turbo`** only if you explicitly want Turbopack.
- **“Error in input stream” / 500 during a run** — Usually the AI returned something the parser didn’t expect. Retry once; if it persists, try a different model or turn off “thinking” extras for that model in `.env` (see `.env.example`).
- **Website can’t reach the API** — Check `NEXT_PUBLIC_API_URL` matches where the API actually runs (`127.0.0.1` vs `localhost` should be consistent with your browser).
- **`OPENAI_API_KEY` / `NVIDIA_API_KEY` errors on startup** — The API didn’t find a key. Confirm **`apps/api/.env`** exists and is loaded (you started `uvicorn` from **`apps/api`**).

---

## Product note

The original product vision (broader roadmap: teams, long-term memory, billing, exports) lives in **`Hivvbuddy_PDD.pdf`** in this repo. This codebase focuses on the **core loop**: timed debate → vote → report, with local persistence.

---

## License

Add a license file if you plan to distribute the project; none is set by default in this README.
