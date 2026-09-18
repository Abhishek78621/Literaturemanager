# Personal Literature Manager

A local-first app for the workflow described in the requirements document:
drop a PDF → extract metadata → classify + summarize (optional AI step) →
store locally → search semantically **offline** → open the original PDF →
ask deeper questions via AI only when you actually need reasoning → get one
daily "interesting paper" recommendation.

It runs as a small local web server (Flask) that opens in your browser, and
is packaged into a single Windows `.exe` so you don't need to touch Python
day-to-day.

## What's implemented (Phases 1–5 from the spec, in MVP form)

- Drag-and-drop PDF import, offline metadata extraction (title, authors,
  year, DOI, abstract) — `app/pdf_processor.py`
- SQLite database with papers / domains (with subdomains) / tags /
  embeddings, matching section 10 of the spec — `app/database.py`
- Optional AI step on import: automatically determines document type (Research Papers, Books, Reports) and classifies by a primary domain and subdomain (strict 2-level hierarchy). Also generates a technical summary and a plain-language explanation — one
  API call per paper, only if you've configured a key — `app/ai_service.py`
- Fully offline local semantic search (no API call, no internet required)
  — `app/embeddings.py`. Uses a real sentence-embedding model if you install
  `sentence-transformers`, otherwise falls back automatically to a
  zero-setup offline TF-IDF-style backend — the app never fails to search
  just because that optional package isn't installed.
- "Reason across papers" mode: sends only the top locally-matched papers
  (not your whole library) to the AI for comparison/synthesis — this is the
  only other place that costs API tokens.
- "Interesting" flag, read/unread tracking, open-count tracking.
- "Today's Paper" daily recommendation, weighted toward unread papers you've
  marked interesting.
- Configurable AI provider: Anthropic (paid), OpenAI (paid), or **OpenAI-compatible** —
  which covers genuinely free options with zero code changes:
  - **Ollama**, running locally on your own machine — 100% free, no API key,
    fully offline once the model's downloaded. Fits this project's whole
    "local-first" idea especially well.
  - **Groq** — free tier, cloud-hosted, fast.
  - **OpenRouter** — some models are free.
  Point Settings → Base URL at whichever server you want; the app doesn't
  care which one it's talking to as long as it speaks the same request format.
  The app is also 100% usable with **no AI configured at all**.

Not yet built (see section 28/29 of the spec for the roadmap — these are
natural follow-ups, not needed for daily use): automatic *merging* of
near-duplicate domains, page/section-level full-text search, citation
graphs, BibTeX/Zotero export.

## Quick start (no installation needed once you have the .exe)

1. Double-click `LiteratureManager.exe`.
2. Your browser opens to `http://127.0.0.1:5001`.
3. Go to **Import**, drop a PDF.
4. Optionally go to **Settings** and paste an Anthropic or OpenAI API key to
   turn on automatic classification/summaries — entirely optional.
5. Use **Search** to find papers offline, or **Today's Paper** for a daily
   pick.

Everything (PDFs + database) is stored in a `library/` folder that appears
next to the `.exe`. As papers are imported, they are automatically organized into neat, hierarchical folders on your disk (e.g., `library/Research_Papers/Remote_Sensing/Change_Detection/paper.pdf`). The browser UI mirrors this structure with a clean, collapsible navigation tree. 

Back that folder up like any other personal data — it's
plain SQLite + nested PDF files, nothing proprietary.

## Building the .exe yourself (Windows)

You need Python 3.10+ installed once (from python.org — check "Add
python.exe to PATH" during setup). Then, from this project folder:

```
build_exe.bat
```

That installs dependencies and runs PyInstaller for you. The result is
`dist\LiteratureManager.exe` — copy that single file wherever you like.

If you'd rather do it by hand:

```
python -m pip install -r requirements.txt
python -m pip install pyinstaller
pyinstaller litmanager.spec --noconfirm
```

> Why you have to build it yourself: PyInstaller doesn't cross-compile — a
> Windows `.exe` has to be built *on* Windows. I've already test-built this
> exact spec file (on Linux, producing a Linux binary) to confirm the
> packaging config, template/static bundling, and database path handling
> all work correctly when frozen — running `build_exe.bat` on your machine
> just repeats that same verified process for a native Windows binary.

## Running without building an .exe at all

```
run_dev.bat
```

(or `python run.py` on macOS/Linux). Same app, just launched via Python
directly — handy while you're still tweaking things.

## Upgrading search quality (optional)

By default, offline search uses a zero-setup TF-IDF-style backend so the
app works immediately with no download. For noticeably better "understands
what I mean, not just matching words" search:

```
python -m pip install sentence-transformers
```

Re-run the app; it auto-detects the package and switches to real semantic
embeddings (needs internet the first time only, to download the ~80MB
model). No code changes or re-import needed for *new* papers; if you want
existing papers re-embedded with the better model, re-import them or ask
me for a small migration script.

## Project layout

```
litmanager/
├── run.py                 # entry point (dev + packaged .exe)
├── litmanager.spec        # PyInstaller build config
├── build_exe.bat          # one-click Windows build
├── run_dev.bat            # one-click run without building
├── requirements.txt
├── app/
│   ├── app.py              # Flask routes
│   ├── database.py         # SQLite schema + queries
│   ├── pdf_processor.py    # offline PDF metadata/text extraction
│   ├── embeddings.py       # offline semantic search
│   ├── ai_service.py       # optional, pluggable AI provider
│   ├── templates/          # HTML pages
│   └── static/css/         # styling
└── library/                # created on first run: your PDFs + literature.db
```

## Cost model (matches section 22 of the spec)

- Browsing, tagging, offline search, opening PDFs, daily recommendation:
  **$0**, no internet needed.
- Import with AI classification/summary on: **1 API call per paper**.
- "Reason across papers": **1 API call per question**, scoped to only the
  papers your offline search already found relevant — not your whole
  library.

## Known limitations of this MVP (things to sand down as you use it)

- Metadata extraction (title/year/DOI/abstract) is heuristic/regex-based
  for offline speed; odd PDF layouts occasionally need a manual fix — there's
  no edit-metadata UI yet, so for now that means re-importing after a
  page-layout tweak, or asking me to add an edit form.
- New-domain proposals are auto-accepted rather than asking for confirmation
  first (section 3 of the spec recommends a confirm step) — worth adding
  once you see how often the AI actually proposes near-duplicate domains.
- No backup/export tooling yet (section 27 mentions this as a requirement)
  — the `library/` folder is plain SQLite + PDFs, so a normal file copy
  works today, but there's no in-app "export/backup" button.
