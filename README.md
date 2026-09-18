# PulseHR AI 🚀

**Intelligent Tabular & HR Attendance Analytics Platform**

PulseHR AI is a next-generation HR analytics and tabular intelligence platform that bridges raw organizational spreadsheets, vector-based semantic search, and autonomous AI reasoning.

## Core Highlights
- 📊 **Universal Tabular Pipeline**: Upload any Excel (`.xlsx`, `.xls`) or CSV file; auto-infers schema and ingests into SQLite with vector embeddings.
- ⚡ **Kaggle Dataset Integration**: Pre-seeded with `yasirub/employee-attendance-ratings` for instant employee attendance and rating analysis.
- 🧠 **Vector RAG & AI Copilot**: Semantic similarity search and natural language tabular Q&A powered by local models.
- 🚨 **Proactive HR Alerts**: Detects attendance anomalies, burnout risk, and performance rating disconnects.
- 📑 **1-Click Executive Presentations**: Exports presentation decks in PowerPoint (`.pptx`) and executive printable summaries.
- 🎨 **Executive UI / UX**: Matches high-polish warm-dark design system with accessible contrast and responsive layout.

## Quickstart
```bash
# Backend (Port 8020)
cd backend
source .venv/bin/activate
uvicorn app.main:app --port 8020 --reload

# Frontend (Port 5175)
cd frontend
npm install
npm run dev -- --port 5175
```
