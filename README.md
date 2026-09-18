# 📚 Personal Literature Manager

A privacy-focused, local-first web application designed to help researchers, students, and professionals organize, search, and understand their literature library. 

Drag and drop your PDFs, and let the system automatically extract metadata, classify domains, generate technical summaries, and organize your files—all while keeping your data entirely local.

---

## ✨ Key Features

- **📂 Automated Hierarchical Organization:** Drop a PDF, and the app automatically determines the document type (e.g., Research Papers, Books, Reports), assigns a primary domain and subdomain (strict 2-level hierarchy), and physically organizes the file on your disk into nested folders.
- **🧠 AI-Powered Insights (Optional):** Plug in your API key (OpenAI, Anthropic, or even a local **Ollama** server) to automatically generate technical summaries, plain-language explanations, and semantic tags for every imported paper.
- **🔍 Fully Offline Semantic Search:** Search your library using natural language. The app uses local embeddings (`sentence-transformers`) to understand the meaning behind your search query, entirely offline.
- **🌳 Beautiful Browser UI:** A clean, intuitive dashboard that mirrors your on-disk folder structure with a collapsible navigation tree. 
- **💬 Reason Across Papers:** Ask deeper questions across your top locally-matched papers for synthesis and comparison.
- **📅 "Today's Paper":** Get a daily recommendation weighted toward unread papers you've marked as interesting to help you stay on top of your reading list.

---

## 🚀 Quick Start (No Installation Needed)

If you're on Windows and want to jump right in, you can build or use the standalone `.exe`:

1. Run `build_exe.bat` to automatically build the application.
2. Double-click the generated `dist\LiteratureManager.exe`.
3. Your browser will automatically open to `http://127.0.0.1:5001`.
4. Go to **Import** and drag-and-drop a PDF.
5. *Optional:* Go to **Settings** and add an API key (or configure a local AI model) to unlock automated summaries and classification.

Everything (PDFs + database) is stored locally in a `library/` folder that appears next to the executable. Your data never leaves your machine unless you explicitly choose to use a cloud AI provider.

---

## 💻 Developer Setup

If you prefer to run the application directly via Python (useful for macOS/Linux or active development):

1. Clone the repository:
   ```bash
   git clone https://github.com/Abhishek78621/Literaturemanager.git
   cd Literaturemanager/litmanager
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *(Optional but recommended: `pip install sentence-transformers` for vastly superior offline semantic search).*

3. Run the application:
   ```bash
   python run.py
   # Or use the provided batch script on Windows: run_dev.bat
   ```

---

## 🏗️ Project Architecture

- **Flask Backend:** Serves the local web interface and handles PDF processing.
- **SQLite Database:** Lightweight, serverless local database for tracking papers, domains, and embeddings.
- **Local Embeddings:** Uses TF-IDF or `sentence-transformers` for offline semantic matching without any cloud dependencies.
- **Pluggable AI Services:** Designed to work flawlessly without AI, but highly extensible to OpenAI, Anthropic, Groq, OpenRouter, or local LLMs.

```text
LiteratureManager/
├── litmanager/
│   ├── run.py                 # Application entry point
│   ├── app/                   
│   │   ├── app.py             # Flask routes and core logic
│   │   ├── database.py        # SQLite schema & operations
│   │   ├── pdf_processor.py   # PDF text & metadata extraction
│   │   ├── embeddings.py      # Semantic search engine
│   │   ├── ai_service.py      # AI integrations & prompts
│   │   ├── templates/         # HTML Jinja templates
│   │   └── static/css/        # UI Styling
│   ├── migrate_folders.py     # Data migration tools
│   └── flatten.py             # Folder structure utilities
└── README.md
```

---

## 🔒 Privacy & Cost Model

This project is deeply committed to the **local-first** philosophy. 
- Browsing, tagging, offline semantic search, and reading PDFs are **100% free and offline**.
- The only time an API call is made is during paper import (1 call) or when specifically using the "Reason across papers" chat feature. 
- You can route these calls through a local **Ollama** server for a completely free and private experience.

---

## 🛣️ Roadmap

- [ ] Automatic merging of near-duplicate domains.
- [ ] Page/section-level full-text search capabilities.
- [ ] Visual citation graphs for tracking paper relationships.
- [ ] BibTeX / Zotero native export integrations.

---

*Built for researchers who want complete control over their library.*
