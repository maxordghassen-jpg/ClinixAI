# 🏥 ClinixAI

> AI-powered medical assistant platform — multilingual patient triage, doctor search, appointment scheduling, and availability management.

---

## 📋 Table of Contents

- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Environment Variables (Secrets)](#environment-variables-secrets)
- [Running Each Service](#running-each-service)
- [Running the Frontend](#running-the-frontend)
- [Service Ports](#service-ports)
- [Tech Stack](#tech-stack)

---

## Architecture Overview

ClinixAI is a **microservices** application composed of:

| Service | Description | Port |
|---|---|---|
| `agent_service` | AI orchestration layer — intent detection, pre-consultation (OpenAI GPT-4o), doctor search | 8001 |
| `availability_service` | Doctor availability & slot management | 8002 |
| `appointment_service` | Appointment booking & management | 8003 |
| `auth_service` | JWT-based authentication & user management | 8005 |
| `geo_service` | Geolocation & proximity search (Google Maps) | 8001* |
| `evaluation_service` | LLM response quality evaluation (BERTScore, ROUGE, BLEU) | — |
| `frontend` | Next.js patient-facing UI | 3000 |

> *geo_service runs on port 8001 by default — confirm its `.env` if you run agent_service on the same port.

---

## Prerequisites

Install the following on the new device before cloning:

### 1. Python 3.11+
Download from [python.org](https://www.python.org/downloads/) — check **"Add Python to PATH"** during install.

### 2. Node.js 18+
Download from [nodejs.org](https://nodejs.org/)

### 3. Git
Download from [git-scm.com](https://git-scm.com/)

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/maxordghassen-jpg/ClinixAI.git
cd ClinixAI

# 2. Create a shared virtual environment (recommended)
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# 3. Install dependencies for all Python services
pip install -r agent_service/requirements.txt
pip install -r appointment_service/requirements.txt
pip install -r auth_service/requirements.txt
pip install -r availability_service/requirements.txt
pip install -r evaluation_service/requirements.txt
pip install -r geo_service/requirements.txt

# 4. Install frontend dependencies
cd frontend
npm install
cd ..

# 5. Create .env files for each service (see section below)
# 6. Start each service (see section below)
```

---

## Environment Variables (Secrets)

> ⚠️ **`.env` files are NOT committed to Git for security reasons.**  
> Create each file manually on the new device using the values below.

### `agent_service/.env`

```env
OPENAI_API_KEY=<ask team lead>
MODEL_NAME=gpt-4o
GROQ_API_KEY=<ask team lead>
REDIS_HOST=sonic-payment-competition-65048.db.redis.io
REDIS_PORT=17827
REDIS_USERNAME=default
REDIS_PASSWORD=<ask team lead>
MONGODB_URI=mongodb+srv://admin:<password>@medical-cluster.qjwgdmm.mongodb.net/
MONGO_DB_NAME=clinix_agent
JWT_SECRET=clinixai-jwt-secret-change-in-production-2026
JWT_ALGORITHM=HS256
```

### `appointment_service/.env`

```env
PORT=8003
MONGODB_URI=mongodb+srv://admin:<password>@medical-cluster.qjwgdmm.mongodb.net/
DATABASE_NAME=appointment_reservation
```

### `auth_service/.env`

```env
MONGODB_URI=mongodb+srv://admin:<password>@medical-cluster.qjwgdmm.mongodb.net/
MONGO_DB_NAME=clinix_agent
JWT_SECRET=clinixai-jwt-secret-change-in-production-2026
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
```

### `availability_service/.env`

```env
MONGODB_URI=mongodb+srv://admin:<password>@medical-cluster.qjwgdmm.mongodb.net/
DATABASE_NAME=disponibility
APPOINTMENT_SERVICE_URL=http://localhost:8003
```

### `evaluation_service/.env`

```env
MONGODB_URI=mongodb+srv://admin:<password>@medical-cluster.qjwgdmm.mongodb.net/
MONGODB_DB=disponibility
GROQ_API_KEY=<ask team lead>
JUDGE_MODEL=llama-3.3-70b-versatile
AGENT_SERVICE_URL=http://localhost:8004
JWT_SECRET=clinixai-jwt-secret-change-in-production-2026
JWT_ALGORITHM=HS256
ENABLE_BERT_SCORE=true
BERT_SCORE_MODEL=bert-base-multilingual-cased
```

### `geo_service/.env`

```env
GOOGLE_MAPS_API_KEY=<ask team lead>
MONGODB_URI=mongodb+srv://admin:<password>@medical-cluster.qjwgdmm.mongodb.net/
DATABASE_NAME=medical_data_tunisia
PORT=8001
```

### `frontend/.env.local`

```env
AGENT_SERVICE_URL=http://localhost:8001
APPOINTMENT_SERVICE_URL=http://localhost:8003
AVAILABILITY_SERVICE_URL=http://localhost:8002
AUTH_SERVICE_URL=http://localhost:8005
```

---

## Running Each Service

Open a **separate terminal** for each service. Make sure the virtual environment is activated in each terminal.

### Agent Service (port 8001)

```bash
cd agent_service
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### Availability Service (port 8002)

```bash
cd availability_service
uvicorn app.main:app --host 0.0.0.0 --port 8002
```

### Appointment Service (port 8003)

```bash
cd appointment_service
uvicorn main:app --host 0.0.0.0 --port 8003
```

### Auth Service (port 8005)

```bash
cd auth_service
uvicorn app.main:app --host 0.0.0.0 --port 8005
```

### Geo Service (port 8001 / Flask)

```bash
cd geo_service
python api_proximity.py
```

### Evaluation Service

```bash
cd evaluation_service
uvicorn app.main:app --host 0.0.0.0 --port 8004
```

---

## Running the Frontend

```bash
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Service Ports

| Service | Port |
|---|---|
| Agent Service | 8001 |
| Availability Service | 8002 |
| Appointment Service | 8003 |
| Evaluation Service | 8004 |
| Auth Service | 8005 |
| Frontend | 3000 |

---

## Tech Stack

- **AI / LLM:** OpenAI GPT-4o (agent orchestration), Groq LLaMA-3.3-70b (evaluation)
- **Backend:** Python 3.11+, FastAPI, Uvicorn
- **Database:** MongoDB Atlas (shared cloud cluster)
- **Cache / Memory:** Redis (cloud-hosted)
- **Geolocation:** Google Maps API
- **Frontend:** Next.js
- **Auth:** JWT (python-jose)
- **Embeddings:** `sentence-transformers` (multilingual EN/FR/AR)

---

## Notes

- All services share the same **MongoDB Atlas** cluster (`medical-cluster.qjwgdmm.mongodb.net`).
- The **Redis** instance is cloud-hosted on Redis Cloud.
- For production, rotate all secrets (especially `JWT_SECRET`, DB passwords, and API keys).
