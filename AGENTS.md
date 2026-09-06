# AGENTS.md - Persistent Project Instructions & Architecture Reference

> **Project:** AI-Powered HOTS Question Generator Using Retrieval-Augmented Generation (RAG)  
> **Scope:** Applies to the entire project repository. This document serves as the persistent single source of truth for architectural decisions, completed milestones, development guidelines, and future phase roadmaps.

---

## 1. Project Goal & Core Concepts

We are building a university-focused AI system that generates **Higher Order Thinking Skills (HOTS)** questions (Bloom's levels: *Apply, Analyze, Evaluate, Create*) from university course materials:
- Course syllabi
- Lecture PPTs / PPTXs
- PDF lecture notes & reference books
- Previous CAT1, CAT2, and FAT examination papers

### Dual Mode User Experience

1. **DEVELOPER MODE (`/dev/…`)**
   - **Access:** Protected by JWT-based developer/admin authentication.
   - **Capabilities:** Course management, document uploading (syllabi, slides, notes, past papers), triggering the ingestion/processing pipeline, and inspecting the course knowledge base.
   - **Constraint:** Students do NOT upload documents or log into Developer Mode.

2. **STUDENT MODE (`/`)**
   - **Access:** Public main interface. **Zero login / no student accounts.**
   - **Capabilities:** Search courses by VIT course code, view course syllabus & descriptions, select specific units/topics, designate exam context (CAT1/CAT2/FAT), configure generation preferences, and generate HOTS questions.

---

## 2. High-Level Architecture & Layering

The system consists of **one unified FastAPI backend** powering both the public student interface and the protected developer interface:

```text
React Frontend (Student: / | Developer: /dev)
      ↓
FastAPI Backend (app/main.py)
      ↓
API Routing Layer (app/api/ — public & auth-guarded endpoints)
      ↓
Service Layer (app/services/ — business logic & orchestration)
      ↓
Repository Layer (app/repositories/ — data access abstraction)
      ↓
MongoDB Atlas & Atlas Vector Search
```

---

## 3. Technology Stack

- **Backend:** Python 3.12, FastAPI, Uvicorn, PyMongo, Pydantic v2, pydantic-settings
- **Database & Search:** MongoDB Atlas (Database) + MongoDB Atlas Vector Search (Vector Indexing & Semantic Search)
- **AI / RAG:** Sentence Transformers (local/lightweight embeddings) + Gemini / Gemma API (LLM reasoning & synthesis)
- **Document Processing:** PyMuPDF (`fitz`), `python-pptx`, `python-docx`, Tesseract OCR
- **Authentication:** JWT (PyJWT) + Bcrypt password hashing (for Developer Mode only)
- **Frontend:** React + Vite
- **Deployment:** Docker

---

## 4. Storage Architecture & Data Principles

- **External File Storage:** Original uploaded raw binaries (PDFs, PPTs, DOCs, scanned images) are **NOT stored in MongoDB**. They are stored in external filesystem / object storage (`EXTERNAL_STORAGE_PATH`).
- **MongoDB Atlas Stores:**
  - `courses`: Structured syllabus hierarchy ($\text{Course} \rightarrow \text{Unit} \rightarrow \text{Topic} \rightarrow \text{Subtopic}$)
  - `materials`: Uploaded file metadata, storage paths, and processing states (`pending`, `processing`, `completed`, `failed`)
  - `teaching_questions`: Structured past exam questions extracted from CAT/FAT papers
  - `chunks`: Granular text chunks alongside their vector embeddings
  - `generated_questions`: AI-synthesized HOTS questions with metadata & validation states
- **Dual Storage in Chunks:** A RAG chunk MUST store both `text` (for prompt context augmentation) and `embedding` (for vector search).

---

## 5. Core RAG Principles

### A. The Teaching File Principle
- **Course Content (PPTs, Notes, Books):** Answers *"What concepts should the question test?"*
- **Previous Exam Papers (CAT/FAT):** Answers *"How does the university ask questions?"* (Tone, mark allocations, problem framing, style).
- Past papers are strictly **teaching examples** and are never simply reproduced verbatim.

### B. Constrained Retrieval Principle
- Retrieval must be logically pre-filtered or filtered jointly by metadata (`course_code`, `unit`, `topic`, `exam_type`) before/alongside semantic vector search.
- **Never perform unconstrained global vector searches** across all courses and topics.

### C. Ingestion Pipeline Principle
```text
Developer Upload → Storage → File Type Detection
  ├── Digital Document → Direct Structured Text Extraction
  └── Scanned Document → Grayscale → Contrast Enhancement → Tesseract OCR
        ↓
Syllabus Understanding & Scope Alignment (Filter Out-of-Syllabus Content)
        ↓
Classification & Structuring
        ├── Course Content → Chunking → Metadata → Embeddings → Chunks Collection
        └── Past Exam Papers → Question Parsing → Teaching Questions Collection
```
- **The syllabus is the ultimate authority:** Out-of-syllabus material must be identified and excluded from the active question generation knowledge base.

---

## 6. Project Status

### Completed Phases:
- **Phase 1: FastAPI Foundation**
  - Modular FastAPI application entrypoint with lifespan event management
  - Environment configuration via `pydantic-settings`
  - Reusable PyMongo `MongoClient` connection lifecycle & error handling
  - Public `GET /` and `GET /health` endpoints
- **Phase 2A: MongoDB Data Foundation**
  - Domain models (`courses`, `materials`, `teaching_questions`, `chunks`, `generated_questions`)
  - Repository layer with ObjectId serialization and CRUD methods
  - Database index provisioning (`init_db_indexes`)
  - Automated database foundation test suite with auto-cleanup
- **Phase 2B: Developer Authentication**
  - JWT token generation & validation (`PyJWT`, `HS256`, expiration handling)
  - Bcrypt password hashing (`ADMIN_PASSWORD_HASH`)
  - Reusable `get_current_developer` FastAPI security dependency
  - `POST /auth/login` endpoint & protected `GET /dev/test` endpoint
  - CLI utility `backend/scripts/create_admin_hash.py`
  - Verified no student login / public routes untouched
- **Phase 3: Course Management**
  - Developer course CRUD endpoints (`POST /dev/courses`, `GET /dev/courses`, `GET /dev/courses/{code}`, `PUT /dev/courses/{code}`, `DELETE /dev/courses/{code}`) guarded by JWT
  - Public student browsing endpoints (`GET /courses`, `GET /courses/{code}`) with zero authentication
  - Separation of Concerns: API Router $\rightarrow$ `CourseService` (normalization, duplicate handling, safe deletion) $\rightarrow$ `CourseRepository`
  - `CoursePublicResponse` model protecting internal IDs/metadata from public exposure

- **Phase 4: Developer Material Management & Drop Box**
  - Protected Developer endpoints (`POST /dev/materials`, `GET /dev/materials`, `GET /dev/materials/{id}`, `DELETE /dev/materials/{id}`)
  - External secure file storage (`storage/documents/<COURSE_CODE>/<uuid>_<file>`) with path traversal prevention & atomic rollback
  - Supported document formats: PDF, PPT, PPTX, DOC, DOCX, PNG, JPG, JPEG
  - Metadata indexing in MongoDB with `processing_status = 'uploaded'`
  - Duplicate upload protection per course & safe disk/DB deletion

- **Phase 5: Document Processing & Text Extraction**
  - Developer processing endpoint (`POST /dev/materials/{material_id}/process`) guarded by JWT
  - Modular document parsers: PyMuPDF (`PDFParser`), `python-pptx` (`PPTParser`), `python-docx` (`DOCParser`), `ImageParser`
  - OCR Pipeline with standardized preprocessing: Grayscale $\rightarrow$ Contrast Enhancement $\rightarrow$ Tesseract OCR with `TESSERACT_CMD_PATH`
  - Automatic OCR fallback for scanned/image-only PDF pages
  - Extracted content persistence in MongoDB (`extracted_content` collection) per page/slide
  - State machine transitions (`uploaded` $\rightarrow$ `processing` $\rightarrow$ `processed` / `failed`) with idempotent reprocessing

- **Phase 6: Syllabus Analysis and Course Structure**
  - Developer syllabus analysis endpoint (`POST /dev/materials/{material_id}/analyze-syllabus`) guarded by JWT
  - Deterministic rule-based parser (`SyllabusParser`) identifying units, topics, and subtopics hierarchy
  - Stable deterministic identifiers (`<COURSE>_U<N>`, `<COURSE>_U<N>_T<M>`, `<COURSE>_U<N>_T<M>_S<K>`)
  - Course model updated with structured `units` in MongoDB
  - Safe re-analysis replacing previous syllabus hierarchy without duplicate creation
  - Public student syllabus retrieval endpoint (`GET /courses/{course_code}/topics`) with zero authentication

### Current Phase:
- **Phase 7: Teaching-File Extraction & Content Classification**

### Next Planned Milestones:
- **Phase 7:** Teaching-File Extraction & Content Classification (Scope Alignment & CAT/FAT Questions)
- **Phase 8:** Chunking, Embedding Generation & MongoDB Atlas Vector Search
- **Phase 9:** RAG Retrieval & Prompt Orchestration
- **Phase 10:** LLM HOTS Question Generation & Validation
- **Phase 11:** React Frontend Integration (Student & Developer UI)

---

## 7. Global Development Rules

1. **Inspect Before Modifying:** Always inspect existing code and file structures before adding or editing functionality.
2. **Preserve Working Code:** Ensure backwards compatibility; never break previously verified endpoints or tests.
3. **Layered Architecture:** Strictly follow `API Router` $\rightarrow$ `Service Layer` $\rightarrow$ `Repository Layer` $\rightarrow$ `Database (PyMongo)`.
4. **No Direct Raw DB in Routers:** API routes must call service or repository methods, never raw PyMongo queries directly.
5. **No Student Auth:** Never create student accounts, login routes, or student JWTs. Student access is completely public.
6. **Protect Developer Routes:** Every `/dev/…` endpoint must be guarded by `Depends(get_current_developer)`.
7. **No Secrets in Code or Logs:** Never hardcode credentials, log passwords, or expose secrets in API responses.
8. **Git Safety:** Ensure `.env` is ignored by Git; `.env.example` must contain variable keys only with blank/safe placeholders.
9. **Timestamps:** Always use UTC timestamps (`datetime.now(timezone.utc)`).
10. **Data Validation:** Always use Pydantic models for API request/response schemas and domain models.
11. **ObjectId Handling:** Convert MongoDB `_id` to string `id` when returning Pydantic models; never leak raw BSON types to APIs.
12. **PyMongo Only:** Do not introduce ODMs like Beanie or MongoEngine.
13. **MongoDB Atlas Vector Search Only:** Do not introduce Chroma, FAISS, Pinecone, Qdrant, or other vector databases.
14. **Incremental Execution:** Implement **ONLY** the specific phase requested in the prompt. Do not jump ahead to future phases.
15. **Status Maintenance:** After completing a milestone, update only the `PROJECT STATUS` section of this file.
