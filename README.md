# AI-Powered HOTS Question Generator Using Retrieval-Augmented Generation (RAG)

A university-focused AI system that generates Higher Order Thinking Skills (HOTS) questions from academic course materials using RAG.

## Project Overview

- **Target Bloom's Levels:** Apply, Analyze, Evaluate, Create
- **Input Sources:** Syllabi, Lecture PPTs/PPTXs, PDF notes, Reference Books, Previous CAT/FAT Papers (as teaching examples)
- **Database & Retrieval:** MongoDB + MongoDB Atlas Vector Search
- **Backend:** FastAPI (Python 3.12)
- **Frontend:** React

## Project Architecture & Directory Layout

```text
project-root/
│
├── frontend/                  # React frontend application
│   ├── student/               # Public student UI (course search, topic selection, question generation)
│   ├── developer/             # Protected developer UI (/dev - upload, syllabus alignment, knowledge base)
│   └── package.json           # Frontend dependencies configuration
│
├── backend/                   # FastAPI modular backend service
│   ├── .venv/                 # Local Python virtual environment (ignored by Git)
│   ├── api/                   # API routes and router declarations
│   ├── auth/                  # JWT authentication for Developer Mode
│   ├── core/                  # Configuration, logging, environment settings
│   ├── database/              # MongoDB client and Atlas Vector Search interfaces
│   ├── ingestion/             # Document extraction, OCR, syllabus alignment, chunking
│   ├── retrieval/             # Metadata filtering and semantic search pipelines
│   ├── generation/            # Prompt engineering and Gemini/Gemma LLM integration
│   ├── validation/            # HOTS question quality and schema validation
│   ├── models/                # Pydantic schemas and database models
│   ├── services/              # Business logic coordinating pipelines and database
│   └── requirements.txt       # Backend dependencies specification
│
├── tests/                     # Automated test suites
├── docker/                    # Docker configuration
│   └── Dockerfile             # Container definition for backend and OCR services
├── .env.example               # Environment variables template
├── .gitignore                 # Git ignore rules
└── README.md                  # Project documentation
```

## Setup Instructions (Development Environment)

### 1. Environment Configuration
Copy `.env.example` to `.env` and fill in the required credentials:
```bash
cp .env.example .env
```

### 2. Backend Environment
A Python virtual environment is located at `backend/.venv/`.
Activate it:
- **Windows (PowerShell):** `backend\.venv\Scripts\Activate.ps1`
- **Linux/macOS:** `source backend/.venv/bin/activate`

### 3. Execution Principle
Development proceeds incrementally. Core modules and features will be implemented and validated phase-by-phase.
