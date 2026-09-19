"""
database.py
-----------
SQLite data layer for the Personal Research Literature Manager.

Design (per project spec, section 10):
- Papers: one row per PDF, holds metadata + AI-generated text.
- Domains: hierarchical (parent_domain), so subdomains are supported.
- PaperDomains: many-to-many link (a paper can belong to several domains).
- Tags / PaperTags: free-form tagging, independent of domains.
- Embeddings: one semantic-search vector per paper, stored as JSON text.

The PDF file lives once on disk (library/papers/<file>.pdf); the database
never duplicates it even if a paper belongs to multiple domains.
"""

import sqlite3
import json
import os
import sys
from datetime import datetime
from contextlib import contextmanager

if getattr(sys, "frozen", False):
    # Writable location next to the .exe (never inside the read-only PyInstaller bundle).
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(_BASE_DIR, "library", "db", "literature.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_conn():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                authors TEXT,
                year TEXT,
                journal TEXT,
                doi TEXT,
                abstract TEXT,
                technical_summary TEXT,
                simple_explanation TEXT,
                keywords TEXT,
                pdf_path TEXT NOT NULL,
                primary_domain TEXT,
                interesting INTEGER DEFAULT 0,
                read INTEGER DEFAULT 0,
                rating INTEGER,
                date_added TEXT,
                date_read TEXT,
                open_count INTEGER DEFAULT 0,
                document_type TEXT DEFAULT 'Research_Papers'
            );

            CREATE TABLE IF NOT EXISTS domains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                parent_domain INTEGER,
                FOREIGN KEY (parent_domain) REFERENCES domains(id)
            );

            CREATE TABLE IF NOT EXISTS paper_domains (
                paper_id INTEGER NOT NULL,
                domain_id INTEGER NOT NULL,
                PRIMARY KEY (paper_id, domain_id),
                FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE,
                FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS paper_tags (
                paper_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (paper_id, tag_id),
                FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS embeddings (
                paper_id INTEGER PRIMARY KEY,
                vector TEXT NOT NULL,
                FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS search_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )


# ---------- Domains ----------

def _get_or_create_domain(conn, name, parent_id=None):
    """Internal: operates on an already-open connection (avoids nested-lock issues)."""
    name = name.strip()
    row = conn.execute("SELECT id FROM domains WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO domains (name, parent_domain) VALUES (?, ?)", (name, parent_id)
    )
    return cur.lastrowid


def get_or_create_domain(name, parent_id=None):
    with get_conn() as conn:
        return _get_or_create_domain(conn, name, parent_id)


def list_domains():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT d.*, (SELECT COUNT(*) FROM paper_domains pd WHERE pd.domain_id = d.id) as paper_count "
            "FROM domains d ORDER BY d.name"
        ).fetchall()]


# ---------- Tags ----------

def _get_or_create_tag(conn, name):
    name = name.strip()
    row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO tags (name) VALUES (?)", (name,))
    return cur.lastrowid


def get_or_create_tag(name):
    with get_conn() as conn:
        return _get_or_create_tag(conn, name)


# ---------- Papers ----------

def add_paper(meta, pdf_path):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO papers
               (title, authors, year, journal, doi, abstract, technical_summary,
                simple_explanation, keywords, pdf_path, primary_domain,
                interesting, read, date_added, document_type)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                meta.get("title"), meta.get("authors"), meta.get("year"),
                meta.get("journal"), meta.get("doi"), meta.get("abstract"),
                meta.get("technical_summary"), meta.get("simple_explanation"),
                meta.get("keywords"), pdf_path, meta.get("primary_domain"),
                int(meta.get("interesting", False)), 0,
                datetime.utcnow().isoformat(), meta.get("document_type", "Research_Papers"),
            ),
        )
        paper_id = cur.lastrowid
        for domain_name in meta.get("domains", []):
            domain_id = _get_or_create_domain(conn, domain_name)
            conn.execute(
                "INSERT OR IGNORE INTO paper_domains (paper_id, domain_id) VALUES (?, ?)",
                (paper_id, domain_id),
            )
        for tag_name in meta.get("tags", []):
            tag_id = _get_or_create_tag(conn, tag_name)
            conn.execute(
                "INSERT OR IGNORE INTO paper_tags (paper_id, tag_id) VALUES (?, ?)",
                (paper_id, tag_id),
            )
        return paper_id


def update_paper(paper_id, fields):
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [paper_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE papers SET {cols} WHERE id = ?", values)


def update_paper_classification(paper_id, meta):
    fields = {
        "technical_summary": meta.get("technical_summary"),
        "simple_explanation": meta.get("simple_explanation"),
        "keywords": meta.get("keywords"),
        "primary_domain": meta.get("primary_domain"),
    }
    if "document_type" in meta:
        fields["document_type"] = meta["document_type"]
    update_paper(paper_id, fields)

    with get_conn() as conn:
        conn.execute("DELETE FROM paper_domains WHERE paper_id = ?", (paper_id,))
        conn.execute("DELETE FROM paper_tags WHERE paper_id = ?", (paper_id,))

        for domain_name in meta.get("domains", []):
            domain_id = _get_or_create_domain(conn, domain_name)
            conn.execute(
                "INSERT OR IGNORE INTO paper_domains (paper_id, domain_id) VALUES (?, ?)",
                (paper_id, domain_id),
            )
        for tag_name in meta.get("tags", []):
            tag_id = _get_or_create_tag(conn, tag_name)
            conn.execute(
                "INSERT OR IGNORE INTO paper_tags (paper_id, tag_id) VALUES (?, ?)",
                (paper_id, tag_id),
            )


def set_interesting(paper_id, value: bool):
    update_paper(paper_id, {"interesting": int(value)})


def mark_read(paper_id):
    update_paper(paper_id, {"read": 1, "date_read": datetime.utcnow().isoformat()})


def increment_open_count(paper_id):
    with get_conn() as conn:
        conn.execute("UPDATE papers SET open_count = open_count + 1 WHERE id = ?", (paper_id,))


def get_paper(paper_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        if not row:
            return None
        paper = dict(row)
        paper["domains"] = [
            d["name"] for d in conn.execute(
                "SELECT dm.name FROM domains dm "
                "JOIN paper_domains pd ON pd.domain_id = dm.id WHERE pd.paper_id = ?",
                (paper_id,),
            ).fetchall()
        ]
        paper["tags"] = [
            t["name"] for t in conn.execute(
                "SELECT tg.name FROM tags tg "
                "JOIN paper_tags pt ON pt.tag_id = tg.id WHERE pt.paper_id = ?",
                (paper_id,),
            ).fetchall()
        ]
        return paper

def delete_paper(paper_id):
    """Deletes a paper from the database and removes its PDF file from disk."""
    paper = get_paper(paper_id)
    if not paper:
        return False
        
    with get_conn() as conn:
        # SQLite foreign keys with ON DELETE CASCADE will clean up 
        # paper_domains, paper_tags, and embeddings automatically
        conn.execute("DELETE FROM papers WHERE id = ?", (paper_id,))
        
    # Delete the physical file
    pdf_path = paper.get("pdf_path")
    if pdf_path and os.path.exists(pdf_path):
        try:
            os.remove(pdf_path)
            # Try to cleanup empty parent directories
            dir_path = os.path.dirname(pdf_path)
            # Prevent deleting the root LIBRARY_DIR or going beyond it
            library_dir = os.path.join(_BASE_DIR, "library")
            while dir_path and dir_path != library_dir and len(dir_path) > len(library_dir):
                try:
                    os.rmdir(dir_path)
                    dir_path = os.path.dirname(dir_path)
                except OSError:
                    break # Directory not empty, stop deleting upwards
        except Exception as e:
            print(f"Error deleting file {pdf_path}: {e}")
            
    return True


def list_papers(domain=None, path_prefix=None, interesting_only=False, unread_only=False):
    query = "SELECT DISTINCT p.* FROM papers p"
    conditions = []
    params = []
    if domain:
        query += " JOIN paper_domains pd ON pd.paper_id = p.id JOIN domains d ON d.id = pd.domain_id"
        conditions.append("d.name = ?")
        params.append(domain)
    if path_prefix:
        conditions.append("p.pdf_path LIKE ?")
        # In SQLite, LIKE is case-insensitive by default, which is usually fine
        # We append % to match any file inside the directory
        params.append(path_prefix + "%")
    if interesting_only:
        conditions.append("p.interesting = 1")
    if unread_only:
        conditions.append("p.read = 0")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY p.date_added DESC"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def all_papers_with_embeddings():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT p.id, p.title, e.vector FROM papers p "
            "JOIN embeddings e ON e.paper_id = p.id"
        ).fetchall()
        return [(r["id"], r["title"], json.loads(r["vector"])) for r in rows]


def save_embedding(paper_id, vector):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO embeddings (paper_id, vector) VALUES (?, ?) "
            "ON CONFLICT(paper_id) DO UPDATE SET vector = excluded.vector",
            (paper_id, json.dumps(vector)),
        )


def log_search(query_text):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO search_log (query, created_at) VALUES (?, ?)",
            (query_text, datetime.utcnow().isoformat()),
        )


def recent_searches(limit=10):
    with get_conn() as conn:
        return [r["query"] for r in conn.execute(
            "SELECT query FROM search_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()]


def get_setting(key, default=None):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def stats():
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM papers").fetchone()["c"]
        interesting = conn.execute("SELECT COUNT(*) c FROM papers WHERE interesting=1").fetchone()["c"]
        unread = conn.execute("SELECT COUNT(*) c FROM papers WHERE read=0").fetchone()["c"]
        domains = conn.execute("SELECT COUNT(*) c FROM domains").fetchone()["c"]
        return {"total": total, "interesting": interesting, "unread": unread, "domains": domains}
