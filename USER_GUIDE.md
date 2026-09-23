# 📚 Personal Literature Manager — Complete User Guide

> **Version**: 1.0 | **Platform**: Windows | **Runs at**: `http://127.0.0.1:5001`

---

## Table of Contents

1. [What Is This App?](#1-what-is-this-app)
2. [How It Works Internally](#2-how-it-works-internally)
3. [Getting Started (First-Time Setup)](#3-getting-started-first-time-setup)
4. [Feature 1 — Library Browser](#4-feature-1--library-browser)
5. [Feature 2 — Importing Papers](#5-feature-2--importing-papers)
6. [Feature 3 — Paper Detail Page](#6-feature-3--paper-detail-page)
7. [Feature 4 — Semantic Search](#7-feature-4--semantic-search)
8. [Feature 5 — Today's Recommendation](#8-feature-5--todays-recommendation)
9. [Feature 6 — Background Auto-Scanner](#9-feature-6--background-auto-scanner)
10. [Feature 7 — Settings Page](#10-feature-7--settings-page)
11. [Feature 8 — AI Integration](#11-feature-8--ai-integration)
12. [Feature 9 — Hard Links & Zero-Duplication Storage](#12-feature-9--hard-links--zero-duplication-storage)
13. [Feature 10 — Daemon / Background Mode](#13-feature-10--daemon--background-mode)
14. [Data Storage & File Layout](#14-data-storage--file-layout)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. What Is This App?

**Personal Literature Manager** is a locally-hosted, privacy-first web application that runs entirely on your own computer. It helps you:

- **Organize** PDF research papers into a smart folder structure automatically.
- **Summarize** papers using AI so you can understand a 30-page paper in 30 seconds.
- **Search** your library using natural-language queries (semantic search), not just keywords.
- **Track** what you have read, starred as interesting, and your daily reading recommendations.
- **Auto-scan** a folder in the background and classify new PDFs without you lifting a finger.

Everything stays **100% on your machine**. No account. No cloud sync. No telemetry. The only time it contacts the internet is when you explicitly configure an AI provider (and even that is optional — a free local option is available via Ollama).

---

## 2. How It Works Internally

Understanding the internals helps you use the app confidently.

### Core Stack
| Layer | Technology |
|-------|-----------|
| Web server | Python + Flask (runs locally on port 5001) |
| Database | SQLite (`library/db/literature.db`) |
| PDF text extraction | PyMuPDF (offline, no API needed) |
| Semantic search | `sentence-transformers` (all-MiniLM-L6-v2 model) OR TF-IDF fallback |
| AI classification | Anthropic Claude / OpenAI / Ollama / Groq / OpenRouter (all optional) |
| File deduplication | SHA-256 cryptographic hash per PDF |

### Data Flow When You Import a Paper
```
You drop a PDF
      |
      v
[1] PyMuPDF extracts: title, authors, year, DOI, abstract (offline)
      |
      v
[2] AI reads abstract -> returns: domain, subdomain, keywords, summaries (optional)
      |
      v
[3] PDF is moved to: Library Root / DocumentType / PrimaryDomain / SubDomain /
      |
      v
[4] Embedding vector computed -> saved to SQLite for search
      |
      v
[5] Paper metadata saved in database -> appears in Library view
```

---

## 3. Getting Started (First-Time Setup)

### Step 1 — Launch the App

Run one of:
```
LiteratureManager.exe          <- double-click if you have the packaged version
python run.py                  <- if running from source
```

Your browser opens automatically to `http://127.0.0.1:5001`.

> **Note:** The console window that appears is the app's server. **Do not close it** while you are using the app. Press `Ctrl+C` in it to stop the app.

### Step 2 — First-Time Setup Screen

On the very first launch you will see the **Setup** screen. You must enter your **Literature Root Folder Path** — this is the folder where all your PDFs will be stored and organized.

**Examples:**
```
C:\Users\YourName\Documents\Literature
D:\Research\Papers
```

**Rules:**
- The folder **must already exist** on disk.
- If you already have sub-folders (e.g., `AI`, `Robotics`, `Biology`) inside it, the app will **automatically detect and register them as domains**.
- Changing this path later (in Settings) does **not** move your existing files — you must do that manually.

Click **"Save"** and the app will redirect you to the Library.

---

## 4. Feature 1 — Library Browser

**URL:** `http://127.0.0.1:5001/`

This is your home screen. It shows all papers in your library with a sidebar for navigation.

### Sidebar Navigation

The left sidebar shows a **tree of your library folder structure**, grouped by:
1. **Document Type** (e.g., `Research Papers`, `Books`, `Reports`)
2. **Primary Domain** (e.g., `Machine Learning`)
3. **Sub-Domain** (e.g., `Transformers`)

Click any domain/sub-domain to filter the paper list to only those papers.

### Filter Bar

At the top of the paper list you can filter:
- **All papers** — show everything
- **Interesting** — show only papers you have starred
- **Unread** — show only papers you have not marked as read

### Stats Bar

The header shows live counts:
- **Total papers** in your library
- **Domains** (categories) you have
- **Interesting** papers starred

### Paper Cards

Each card shows:
- Title, authors, year
- Primary domain badge
- "Interesting" star indicator

Click a card to open the **Paper Detail** page.

---

## 5. Feature 2 — Importing Papers

**URL:** `http://127.0.0.1:5001/import`

You have **two import methods**: single file and bulk folder.

---

### Method A — Single File Import

1. Go to the **Import** tab in the navigation.
2. **Drag and drop** a PDF onto the upload area, or click to browse and select a file.
3. Click **"Import"**.

**What happens automatically:**

| Step | What happens |
|------|-------------|
| Text extraction | Title, authors, year, DOI, and abstract are pulled from the PDF using PyMuPDF. If the embedded metadata is missing, heuristics are used (first non-title lines of page 1). |
| AI classification | If you have configured an AI provider, it reads the abstract and returns: primary domain, one sub-domain, up to 6 keywords, a technical summary, and a plain-English explanation. |
| File organization | The PDF is moved from the temporary `Unclassified` folder into `LibraryRoot/DocumentType/PrimaryDomain/SubDomain/`. |
| Embedding | A semantic search vector is computed and saved so the paper is findable via Search immediately. |

**If AI is not configured:** The paper is saved as "Unclassified" with only the basic metadata extracted from the PDF. You can re-classify it later once you add an AI key.

**If the PDF is a scanned image:** PyMuPDF cannot extract text from scanned images. The paper will be saved as Unclassified and you will see a flash message explaining this.

---

### Method B — Bulk Folder Import

1. Go to the **Import** tab.
2. Enter a **folder path** (e.g., `C:\Downloads\Papers`) in the folder import box.
3. Choose an **organization mode**:

| Mode | What it does |
|------|-------------|
| **Preserve Structure** | Uses the existing sub-folder names as domains. A file at `Papers/AI/deep_learning.pdf` gets domain = `AI`. |
| **AI Re-organize** | Ignores existing folders; AI reads each paper and assigns it to the best matching existing domain in your library. Papers that do not fit any existing domain go to `Unclassified`. |

4. Click **"Start Import"**.

A **live progress bar** appears, updating in real-time via server-sent events. You see each file as it is processed, skipped (duplicate), or failed.

**Deduplication:** Every file is SHA-256 hashed before processing. If the same PDF already exists in your library (even under a different filename), it is silently skipped. You will never have duplicates.

---

## 6. Feature 3 — Paper Detail Page

**URL:** `http://127.0.0.1:5001/paper/<id>`

Click any paper in the library to open this page. It shows everything about a paper.

### What You See

| Section | Content |
|---------|---------|
| **Title / Authors / Year** | Extracted from PDF or AI-enriched |
| **DOI** | Auto-extracted via regex from PDF text |
| **Primary Domain** | Where the paper is filed |
| **Keywords** | Up to 6 keywords extracted by AI |
| **Technical Summary** | 2-4 sentence expert-level summary (AI-generated) |
| **Simple Explanation** | 2-3 sentence plain-language summary (AI-generated) |
| **Abstract** | Raw abstract text from the PDF |
| **Tags / Domains** | All domains this paper belongs to |

### Actions You Can Take

#### Mark as Interesting
Click **"Mark Interesting"** / **"Remove from Interesting"** to toggle the star. Interesting papers:
- Appear in the **"Interesting" filter** in the library.
- Are **prioritized** by the **Today's Recommendation** feature.

#### Mark as Read
Click **"Mark as Read"**. This records:
- `read = 1` in the database
- The current timestamp as `date_read`

Unread interesting papers get highest priority in daily recommendations.

#### Open PDF
Click **"Open PDF"** to view the original PDF file directly in your browser. Every time you open a PDF, the app increments an `open_count` counter for that paper.

#### Re-classify with AI
Click **"Re-classify with AI"** to re-run AI analysis on a paper that was previously saved without AI (e.g., you added an API key after importing). This will:
1. Re-extract text from the PDF.
2. Send it to the AI for fresh classification.
3. Update domain, keywords, and summaries in the database.
4. **Move the PDF file** to the correct folder for the new domain.
5. Re-compute the search embedding.

#### Delete Paper
Click **"Delete"** to permanently remove the paper. This deletes:
- The paper row from the database (all linked domain/tag/embedding rows are auto-deleted via SQLite `ON DELETE CASCADE`).
- The **physical PDF file** from disk.
- Any empty parent directories left behind.

> **WARNING: This action is irreversible. There is no recycle bin.**

---

## 7. Feature 4 — Semantic Search

**URL:** `http://127.0.0.1:5001/search`

The search page has **two modes**, toggled via radio buttons.

---

### Mode A — "Find Papers" (Offline Semantic Search)

**What it does:** Finds the most relevant papers in your library for your query using **semantic similarity** — it understands meaning, not just keywords.

**How to use:**
1. Type a concept or question (e.g., `"attention mechanism in NLP"`)
2. Select **"Find Papers"** mode.
3. Click **Search**.

**Results** are ranked by **relevance %** (cosine similarity between your query's embedding and each paper's embedding). Top 10 results are shown.

**How it works under the hood:**
1. Your query is converted to a vector using the same embedding model used during import.
2. That vector is compared against every paper's stored vector using cosine similarity.
3. Papers are ranked by similarity score.

**The embedding backend used:**

| Backend | When active | Quality |
|---------|-------------|---------|
| `sentence_transformers` | When `sentence-transformers` Python package is installed | True semantic understanding; understands synonyms and paraphrasing |
| `hashing` (TF-IDF fallback) | When `sentence-transformers` is not installed | Keyword overlap; faster but weaker |

You can see which backend is active on the Settings page. The app never requires the internet for this — once the `all-MiniLM-L6-v2` model is downloaded (first use), it runs fully offline.

---

### Mode B — "Reason Across Papers" (AI-Powered Synthesis)

**What it does:** Finds relevant papers AND asks the AI to synthesize a written answer to your question by reading the summaries of those papers.

**How to use:**
1. Type a complex analytical question (e.g., `"What are the limitations of multi-scale attention models mentioned in my library?"`)
2. Select **"Reason Across Papers"** mode.
3. Click **Search**.

**How it works under the hood:**
1. First, the top **6 semantically relevant papers** are found (same as Find mode, no AI used yet).
2. Their titles and summaries are sent to the AI with your question.
3. The AI returns a synthesized, citation-aware written answer.

> Requires AI to be configured in Settings. If AI is not set up, you get a flash message and only the paper list is shown (no synthesized answer).

**Important:** The AI only reads the summaries already stored in your database — it does NOT re-read the full PDFs. This keeps API costs minimal.

---

### Search History
Every search query you run is logged to the database. The recent searches are accessible for quick re-use.

---

## 8. Feature 5 — Today's Recommendation

**URL:** `http://127.0.0.1:5001/today`

Click **"Today"** in the navigation to get a single paper recommendation for your reading session.

### Selection Priority

The app uses this priority order to pick your paper:

```
1st priority: Interesting papers you have NOT yet read
2nd priority: Interesting papers (read or unread)
3rd priority: Any paper in your library (if no interesting papers exist)
```

The selection within each priority tier is **random**, so you get a different pick each time.

A **reason message** is also displayed so you know why that paper was chosen (e.g., *"Picked from your 'Interesting' list — you haven't read it yet."*)

---

## 9. Feature 6 — Background Auto-Scanner

This feature monitors your Library Root Folder automatically and classifies new PDFs without you having to open the Import page.

### How to Enable

1. Go to **Settings**.
2. Check **"Enable background auto-scan of Literature Root Folder"**.
3. Set a **Scan Interval** (e.g., `1` hour `30` minutes).
4. Click **"Save settings"**.

### How It Works

A background thread starts when the app launches and runs forever (it is a daemon thread — it dies when the app closes). Every **60 seconds** this thread wakes up and checks:

```
Is auto-scan enabled?          -> NO -> sleep 60s
      |
      v YES
Is the interval > 0?           -> NO -> sleep 60s
      |
      v YES
Has enough time passed since   -> NO -> sleep 60s
the last scan?
      |
      v YES
Walk ALL files in Library Root
  For each .pdf file found:
    Compute SHA-256 hash
    Already in database?       -> YES -> skip (no duplicate)
          |
          v NO
    Extract text -> AI classify -> Move to correct folder -> Save to DB
Update "last scan time" in database
```

### Key Behaviors

- **Accuracy**: The timer is accurate to within +-1 minute (the heartbeat interval).
- **Persistence**: `last_scan_time` is stored in the database. If you restart the app, the scheduler picks up where it left off — it will not re-scan early.
- **Safe deduplication**: SHA-256 hashing means a PDF already in your library is always skipped, even if you rename it or move it.
- **AI mode only**: The auto-scanner always uses AI classification. If AI is not configured, new papers will be placed in `Unclassified`.
- **Domain safety**: During auto-scan, the AI is only allowed to assign papers to **existing domains**. A paper that does not fit any known domain goes to `Unclassified` instead of creating random new folders.

### Setting the Interval

| Hours | Minutes | Effective interval |
|-------|---------|-------------------|
| `1` | `0` | Every 1 hour |
| `0` | `30` | Every 30 minutes |
| `2` | `30` | Every 2 hours 30 minutes |
| `0` | `0` | **Disabled** (even if checkbox is checked) |

> **Tip:** Set at least 5-10 minutes minimum for practical use. Sub-minute intervals are not supported.

---

## 10. Feature 7 — Settings Page

**URL:** `http://127.0.0.1:5001/settings`

### Library Stats Panel
Shows live totals: total papers, number of domains, interesting-starred count, and the active semantic search backend name.

### Storage Section
Change the **Literature Root Folder Path**.

> **WARNING:** Changing this path will **not** move existing PDFs. Update the path only if you have already moved your files, or if starting fresh.

### Scheduled Auto-Scan Section
Configure the background scanner (see Feature 6 above).

### AI Provider Section
Choose and configure your AI backend (see Feature 8 below).

### Rebuild Search Index
Click **"Rebuild search index"** if:
- You installed `sentence-transformers` after importing papers (papers were embedded with the weaker hashing backend; now you want to re-embed them with the better model).
- You removed `sentence-transformers` and search starts returning errors.
- Search returns unexpectedly empty or wrong results.

This re-computes the embedding vector for **every paper** using the currently active backend. It can take a minute if you have many papers.

### Re-classify All 'Unclassified' Papers
If you imported papers before configuring AI, they were stored as "Unclassified". Once you add an API key:
1. Click **"Re-classify all Unclassified papers"**.
2. The app sends each unclassified paper through AI classification one by one.
3. Successfully classified papers are **moved to the correct folder** on disk.
4. Their database records (domain, keywords, summaries) are updated.
5. A summary flash message tells you how many succeeded and how many failed.

---

## 11. Feature 8 — AI Integration

AI is **entirely optional**. The app works without it — you just will not get summaries, auto-categorization, or the "Reason" search mode.

### Supported Providers

| Provider | Cost | Requires Internet | API Key Needed |
|----------|------|------------------|----------------|
| **Anthropic (Claude)** | Paid | Yes | Yes |
| **OpenAI (GPT)** | Paid | Yes | Yes |
| **Ollama (local)** | Free | No (after model download) | No |
| **Groq** | Free tier | Yes | Yes (free) |
| **OpenRouter** | Some free models | Yes | Yes (free) |

### Setting Up Anthropic (Claude)
1. In Settings -> AI Provider, select **"Anthropic (Claude) — paid"**.
2. Enter your **API key** (starts with `sk-ant-...`).
3. Model defaults to `claude-sonnet-4-6`. Change if needed.
4. Click **Save**.

### Setting Up OpenAI
1. Select **"OpenAI — paid"**.
2. Enter your **API key** (starts with `sk-...`).
3. Model defaults to `gpt-4o-mini`.
4. Click **Save**.

### Setting Up Ollama (Free, Local)
1. Install Ollama from ollama.com and download a model (e.g., `ollama pull llama3`).
2. In Settings -> AI Provider, select **"OpenAI-compatible (local/free)"**.
3. Base URL: `http://localhost:11434/v1/chat/completions`
4. Model: `llama3` (or whatever model you pulled).
5. Leave API key blank.
6. Click **Save**.

### Setting Up Groq (Free Cloud)
1. Get a free API key at console.groq.com.
2. Select **"OpenAI-compatible (local/free)"**.
3. Base URL: `https://api.groq.com/openai/v1/chat/completions`
4. Model: e.g., `llama3-8b-8192`
5. API key: your Groq key.
6. Click **Save**.

### What the AI Does (One API Call Per Paper)
The app makes a **single, cost-efficient API call** per paper containing:
- The paper's abstract (up to 2,000 characters)
- A list of your existing domain names

The AI returns JSON with:
- `document_type` — broad type (Research Paper, Book, Report, etc.)
- `primary_domain` — best matching existing domain, or a new one if none fit
- `subdomains` — exactly 1 more specific sub-category
- `is_new_domain` — true if AI is suggesting a brand-new domain
- `keywords` — up to 6 short terms
- `technical_summary` — 2-4 sentences for a researcher
- `simple_explanation` — 2-3 plain-language sentences

### New Domain Safety
If the AI suggests a **brand-new domain** that does not exist in your library yet:
- During **single file import**: the new domain is accepted and created.
- During **bulk import** or **auto-scan**: the paper goes to `Unclassified` instead. This prevents unexpected new folders from being created automatically in bulk operations.

---

## 12. Feature 9 — Hard Links & Zero-Duplication Storage

When a paper belongs to **multiple domains** (primary domain + sub-domains), the app stores only **one physical copy** of the PDF on disk and creates **Windows Hard Links** for the other domains.

### What is a Hard Link?
A hard link is a directory entry that points to the same file data on disk as the original. It:
- **Looks and behaves** like a normal file in Windows Explorer.
- Takes up **0 extra bytes** of disk space.
- Can be opened, read, and copied normally.
- Is deleted when ALL hard links to it are removed.

### Example
You import `transformer_paper.pdf`. The AI says:
- Primary domain: `Machine_Learning`
- Sub-domain: `NLP`

The app creates:
```
Library/Research_Papers/Machine_Learning/NLP/transformer_paper.pdf   <- real file (1 copy)
Library/Research_Papers/NLP/transformer_paper.pdf                    <- hard link (0 bytes extra)
```

Both "files" are the same data. Opening, editing, or copying either one is identical.

---

## 13. Feature 10 — Daemon / Background Mode

Run the app silently in the background with no browser window or console:

```
LiteratureManager.exe --daemon
python run.py --daemon
```

In daemon mode:
- No browser opens automatically.
- The server still runs at `http://127.0.0.1:5001` — you can open it manually anytime.
- The background auto-scanner thread still runs.

### Auto-Start with Windows

1. Right-click Desktop -> **New -> Shortcut**.
2. Target: `"C:\path\to\LiteratureManager.exe" --daemon`
3. Right-click the shortcut -> **Properties** -> add `--daemon` to the **Target** field.
4. Press `Win + R` -> type `shell:startup` -> press Enter.
5. Drag the shortcut into the Startup folder.

Now the app runs silently every time your PC starts, monitoring your library in the background.

---

## 14. Data Storage & File Layout

```
LiteratureManager/
  litmanager/
    library/
      db/
        literature.db          <- SQLite database (all metadata, settings, embeddings)
      Unclassified/            <- Papers that could not be classified
      Research_Papers/
        Machine_Learning/
          NLP/
            paper.pdf
          Computer_Vision/
            paper2.pdf
        Robotics/
          paper3.pdf
      Books/
      Reports/
```

### Database Tables
| Table | Contents |
|-------|---------|
| `papers` | One row per PDF: title, authors, year, DOI, abstract, summaries, keywords, path, interesting flag, read flag, open count, SHA-256 hash |
| `domains` | All domains/sub-domains with optional parent relationship |
| `paper_domains` | Many-to-many: which papers belong to which domains |
| `tags` | Free-form tags |
| `paper_tags` | Many-to-many: which papers have which tags |
| `embeddings` | One search vector (JSON array of floats) per paper |
| `search_log` | History of every search query |
| `settings` | Key-value store for all app settings |

---

## 15. Troubleshooting

### App does not open in browser
The server runs on port `5001`. Open `http://127.0.0.1:5001` manually. Ensure nothing else is using port 5001.

### Search returns no results
- You may have no papers imported yet.
- If you recently switched embedding backends (installed or removed `sentence-transformers`), go to **Settings -> Rebuild search index**.

### AI classification skipped
- Check that your API key is correct in Settings.
- For Ollama: ensure the Ollama app is running on your PC (`ollama serve`).
- For scanned PDFs: no text can be extracted. These will always be Unclassified.

### Paper was saved as Unclassified
This happens when:
1. AI is not configured.
2. AI failed to return a valid response.
3. PDF is a scanned image (no extractable text).
4. During bulk import / auto-scan: AI suggested a new domain not in your library.

**Fix:** Configure AI in Settings, then use **"Re-classify all Unclassified papers"** in Settings, or **"Re-classify with AI"** on the individual paper's detail page.

### Duplicate papers appearing
This should not happen — SHA-256 hashing prevents duplicates. If you see it, the papers may have different binary content (e.g., different downloads of the same paper with different metadata embedded). They are genuinely different files at the binary level.

### Auto-scan is not running
- Check that **"Enable background auto-scan"** is checked in Settings AND that the interval is not `0 hours 0 minutes`.
- The scan loop checks every 60 seconds. Wait at least 1-2 minutes after saving settings.
- Ensure the app is running (the exe is not closed).

### Search index error / size mismatch
This happens when you switch embedding backends after papers are already indexed. Go to **Settings -> Rebuild search index** to fix it.

---

*This guide was written from a full analysis of the application source code and covers every implemented feature.*
