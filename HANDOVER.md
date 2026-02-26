# VECVRAG Project Handover Document

## 1. Project Overview

**VECVRAG** is a robust, scalable RAG (Retrieval-Augmented Generation) application designed for vehicle engineering teams. It enables secure access, search, and interaction with large-scale vehicle validation reports and technical documents (such as ETRs) through natural language queries.

The application uses group-based access control to ensure strict data isolation and security, ensuring that sensitive documents are only available to authorized team members.

---

## 2. Technology Stack

### Backend Stack

- **Framework:** FastAPI (Python 3.x)
- **Database (Relational):** PostgreSQL (managed via SQLAlchemy ORM)
- **Database (Vector):** Qdrant (for document embeddings and semantic search)
- **Database (Analytical/Events):** ClickHouse (for telemetry and events tracking)
- **Object Storage:** MinIO (S3-compatible storage for raw documents)
- **Caching & Message Broker:** Redis (for session management and Celery queue)
- **Async Processing:** Celery (for background document ingestion, chunking, and embedding generation)
- **LLM & Embeddings:** Ollama (self-hosted models) and FastEmbed (for efficient embedding generation)
- **Data Extraction:** PyMuPDF, pdfplumber, python-pptx (for parsing various document formats)

### Frontend Stack

- **Framework:** Next.js (React 19)
- **Styling:** Tailwind CSS (with `@tailwindcss/typography` for rich text and `@tailwindcss/postcss`)
- **Icons:** `lucide-react`
- **Markdown Rendering:** `react-markdown` and `remark-gfm` (for rendering LLM responses with citations)
- **HTTP Client:** Axios

### Infrastructure & Deployment

- **Containerization:** Docker & Docker Compose (`docker-compose.yml`, `docker-compose.app.yml`)
- **Containers include:** `postgres`, `redis`, `qdrant`, `ollama`, `minio`, `clickhouse`

---

## 3. Architecture & Key Workflows

### 3.1 Document Ingestion Pipeline

1. **Upload:** A user (Group Manager) uploads a document via the Next.js frontend to the FastAPI backend.
2. **Storage:** The raw document is uploaded to MinIO.
3. **Queueing:** A background task is pushed to Celery via Redis.
4. **Processing:** The Celery worker (`worker` process):
   - Extracts text and metadata (using PyMuPDF, pdfplumber, etc.).
   - Splits the content using a hybrid chunking strategy (semantic boundaries + fixed token-overlap).
   - Generates embeddings for each chunk via Ollama/FastEmbed.
   - Indexes chunks in Qdrant with appropriate metadata tags (including `group_id` for isolation).

### 3.2 RAG Query Pipeline

1. **Query Input:** A user submits a natural language question.
2. **Embedding:** The backend generates an embedding of the query.
3. **Retrieval:** Qdrant is queried using the `group_id` of the user filters to fetch the top-k most relevant text chunks (Cosine Similarity / HNSW indexing).
4. **Generation:** Re-ranked chunks are formatted as context and passed to the Ollama LLM along with a strict system prompt.
5. **Response:** The LLM generates a strictly data-grounded answer containing citations linking back to original ETR documents, pages, and sections.

### 3.3 Security & Authorization (RBAC)

- **Authentication:** JWT-based user authentication, configured via `auth.py`. Follows a process including Email/Password and OTP verification.
- **Roles:** Admin, Group Manager, Member.
- **Data Isolation:** `group_id` is strictly embedded within Qdrant chunk metadata. A user's query is hard-filtered by the groups they have access to, enforcing zero unauthorized data leakage.

---
