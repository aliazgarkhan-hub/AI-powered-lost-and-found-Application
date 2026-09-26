# FindBack AI — Backend

AI-powered Lost & Found platform backend. FastAPI + SQLAlchemy + a transparent,
explainable AI matching engine. Built to run standalone (SQLite, zero external
API keys) and to be a real, extendable base for a production deploy.

This is the **backend only** — pair it with a React + Tailwind frontend that
calls the endpoints below (in particular `POST /api/match`, the agreed
matching endpoint).

---

## 1. Quick start

```bash
cd findback-ai-backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env            # edit values if you want, defaults just work

# Create the database tables
python -c "from app.database import init_db; init_db()"

# Optional: load realistic demo data (also available as POST /api/demo/seed)
python seed_demo_data.py

# Optional: create an admin account for the moderation dashboard
python create_admin.py admin@findback.ai "Admin" adminpass123

uvicorn app.main:app --reload --port 8000
```

Then open:
- **http://localhost:8000/docs** — interactive Swagger API docs (auto-generated)
- **http://localhost:8000/health** — health check

No API keys are required to run this. `sentence-transformers` is optional —
if it's not installed (or fails to download a model with no internet
access), the matching engine automatically falls back to TF-IDF cosine
similarity, and then to a plain string-similarity ratio if `scikit-learn`
isn't available either. The app always produces real, calculated similarity
scores — never hard-coded ones.

---

## 2. Project structure

```
findback-ai-backend/
├── app/
│   ├── main.py                # FastAPI app, router wiring, CORS, error handlers
│   ├── config.py              # Settings loaded from environment / .env
│   ├── database.py            # SQLAlchemy engine/session
│   ├── models.py              # ORM models (User, Report, Match, ContactRequest, ModerationTicket)
│   ├── schemas.py             # Pydantic request/response schemas
│   ├── auth.py                # Password hashing + JWT auth
│   ├── storage.py             # Pluggable file storage abstraction (local -> S3-ready)
│   ├── demo_data.py           # "Demo Data" seed logic
│   ├── matching/
│   │   ├── engine.py          # The transparent AI matching / scoring engine
│   │   ├── text_similarity.py # Text similarity abstraction (SBERT -> TF-IDF -> difflib)
│   │   └── image_analysis.py  # Pluggable vision abstraction (local color fallback)
│   └── routers/
│       ├── auth.py            # /api/auth/*
│       ├── lost.py            # /api/lost/*        (Report a Lost Item)
│       ├── found.py           # /api/found/*       (Report a Found Item)
│       ├── matches.py         # POST /api/match, /api/matches/*  (Match Dashboard)
│       ├── search.py          # /api/search        (Browse Reports filters)
│       ├── messages.py        # /api/messages/*    (in-app contact requests)
│       ├── dashboard.py       # /api/dashboard/stats (analytics)
│       ├── admin.py           # /api/admin/*       (moderation, duplicates)
│       ├── recovery.py        # /api/reports/{id}/mark-recovered
│       └── demo.py            # /api/demo/seed
├── seed_demo_data.py          # CLI: load demo data without starting the server
├── create_admin.py            # CLI: create/promote an admin user
├── requirements.txt
├── .env.example
└── README.md
```

---

## 3. The AI matching engine (how scores are calculated)

`app/matching/engine.py` computes a transparent **AI Match Score** (0-100),
explicitly labeled as an AI Match Score, not a scientific probability.

| Factor | Base weight |
|---|---|
| Text/description similarity | 30% |
| Item/category similarity | 15% |
| Brand/model similarity | 15% |
| Color similarity | 10% |
| Distinguishing features similarity | 15% |
| Location proximity | 10% |
| Date/time proximity | 5% |

**Missing data is never treated as a mismatch.** If a factor can't be
computed (e.g. brand wasn't filled in on either report), it's dropped and
its weight is redistributed proportionally across the remaining available
factors, so the final score is always a weighted average over 100% of
*available* signal.

Every match response includes the full factor-by-factor breakdown
(`factors`) and plain-English reasons (`reasons`, e.g. "Same brand: Lenovo",
"Locations are nearby") so the frontend can show *why* two reports matched —
never just a bare number.

Image analysis (`app/matching/image_analysis.py`) is a pluggable
abstraction: out of the box it only extracts a dominant color locally via
Pillow (no external calls, no fabricated brand/category detection). Wire in
a real vision/multimodal API by implementing `VisionProvider.analyze()` and
switching `VISION_API_PROVIDER` in `.env` — nothing else in the app needs to
change.

---

## 4. API reference (also live at `/docs`)

### Auth
- `POST /api/auth/register` — `{name, email, password, contact_method}` → JWT + user
- `POST /api/auth/login` — `{email, password}` → JWT + user
- `GET /api/auth/me` — current user (Bearer token required)

### Report Lost Item
- `POST /api/lost` (multipart form) — item_name, category, description, brand,
  model, color, distinguishing_features, location_text, latitude, longitude,
  event_time, contact_method, photo (optional file)
- `GET /api/lost` — list/filter lost reports
- `GET /api/lost/{id}` — one lost report
- `PATCH /api/lost/{id}/status` — owner/admin only

### Report Found Item
- Same shape as above, under `/api/found`

### AI Matching (the agreed endpoint)
- **`POST /api/match`** — body `{"report_id": "<lost or found report id>"}`.
  Compares against all active opposite-kind reports using the real engine,
  stores/updates `Match` rows, returns them **sorted by AI Match Score
  descending**, each with `score`, `factors`, `reasons`.
- `GET /api/matches` — Match Dashboard feed (filters: `status`, `min_score`)
- `GET /api/matches/{id}` — one match, hydrated with both reports
- `PATCH /api/matches/{id}/status` — `{"status": "confirmed" | "rejected" | "flagged"}`
  backs the **View Details / Not a Match / Report Issue** dashboard buttons
  ("Contact Reporter" uses the Messages endpoints below)

### Search / Browse
- `GET /api/search?q=&kind=&category=&brand=&color=&location=&status=&date_from=&date_to=`

### Messages / Contact requests (privacy-safe)
- `POST /api/messages` — `{report_id, match_id?, message_text}` → sends
  "Someone is interested in your item" — **never exposes contact info directly**
- `GET /api/messages` — inbox + sent
- `PATCH /api/messages/{id}/respond` — `{"accept": true|false}` — recipient
  chooses whether to respond; contact info is revealed only on accept, only
  to the two participants

### Recovery
- `POST /api/reports/{id}/mark-recovered` — `{"confirm": true}` — owner marks
  item Recovered/Returned (requires explicit confirmation)

### Dashboard analytics
- `GET /api/dashboard/stats` — total lost/found, potential matches, returned
  items, match success rate, activity-over-time series (for charts)

### Admin / Moderation
- `POST /api/admin/moderation` — flag fraudulent/inappropriate content (any user)
- `GET /api/admin/moderation` — list open tickets (admin only)
- `PATCH /api/admin/moderation/{id}` — resolve a ticket (admin only)
- `GET /api/admin/duplicates?kind=lost|found` — duplicate-report detection
- `GET /api/admin/users` — list users (admin only)

### Demo mode
- `POST /api/demo/seed` — creates realistic sample lost/found reports
  (including the Block-B Lenovo laptop pair from the spec) and runs the
  real matching engine over them

---

## 5. Status system

Each report moves through: `active` → `possible_match` → `match_confirmed`
→ `returned` / `closed`. Status transitions are triggered automatically by
`POST /api/match` (active → possible_match) and by match status updates
(`confirmed` → match_confirmed on both reports), or explicitly by the owner
via the recovery/status endpoints.

---

## 6. Privacy & trust design choices

- Contact details (email/phone) are **never** returned in report listings —
  only a generic `contact_method` label like "In-app message".
- All contact happens through `ContactRequest` rows; private contact info is
  revealed only after the recipient explicitly accepts, and only to the two
  participants.
- Reports store approximate `location_text` / rounded lat-lon rather than
  requiring an exact home address.
- `POST /api/admin/moderation` lets any user flag a listing as fraudulent or
  inappropriate; an admin resolves it via `PATCH /api/admin/moderation/{id}`.
- `GET /api/admin/duplicates` gives a starting point for duplicate-report
  detection (same-reporter, high name-similarity pairs).
- Marking an item Recovered requires an explicit `confirm: true` flag rather
  than a silent one-click status flip.
- AI match scores are always labeled **"AI Match Score"**, with a visible
  factor breakdown — the API never claims a scientific probability or image
  match certainty.

---

## 7. Notes on the frontend checklist

This backend was built to satisfy, on the backend side:
- ✅ `POST /api/match` exists
- ✅ accepts the agreed request shape (`{"report_id": ...}`)
- ✅ returns the agreed response shape (list of matches with `score`,
  `factors`, `reasons`, hydrated `lost_report` / `found_report`)
- ✅ stores the agreed fields (see `Report` model — matches both the Report
  Lost and Report Found form field lists exactly)
- ✅ exposes a way for the frontend to communicate with the matcher without
  the frontend needing to invent its own scoring logic

## 8. Swapping in production infrastructure later

- **Database**: change `DATABASE_URL` in `.env` to a Postgres URL
  (`postgresql+psycopg2://user:pass@host/db`) — SQLAlchemy models are
  DB-agnostic, no code changes needed.
- **File storage**: implement a new `StorageBackend` subclass in
  `app/storage.py` (e.g. S3) and switch `STORAGE_BACKEND`.
- **Vision API**: implement a new `VisionProvider` subclass in
  `app/matching/image_analysis.py` and switch `VISION_API_PROVIDER`.
- **Text embeddings**: set `TEXT_SIMILARITY_MODEL` to any
  `sentence-transformers`-compatible model name.
