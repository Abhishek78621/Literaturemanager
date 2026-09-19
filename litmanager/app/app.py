"""
app.py
------
Flask app tying everything together. Runs as a local web server; the
"desktop app" feel comes from run.py, which opens it in a native-looking
browser window (or your default browser) automatically.

Routes map directly onto the workflow in the spec:
  /                -> Library view (browse by domain, list papers)
  /import           -> Drop/select a PDF, extract, (optionally) AI classify
  /paper/<id>        -> Paper detail, mark interesting/read, open PDF
  /search            -> Offline semantic search + optional AI "reasoning" mode
  /today             -> Daily recommendation
  /settings          -> Configure AI provider/key, embedding backend info
"""

import os
import shutil
import random
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, flash

from app import database as db
from app import pdf_processor
from app import embeddings
from app import ai_service

import sys

if getattr(sys, "frozen", False):
    # Running as a PyInstaller-built .exe: templates/static were bundled
    # under _MEIPASS/app/..., and the writable library lives next to the exe.
    _RESOURCE_DIR = os.path.join(sys._MEIPASS, "app")
    BASE_DIR = os.path.dirname(sys.executable)
else:
    _RESOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = os.path.dirname(_RESOURCE_DIR)

LIBRARY_DIR = os.path.join(BASE_DIR, "library")
UNCLASSIFIED_DIR = os.path.join(LIBRARY_DIR, "Unclassified")

app = Flask(
    __name__,
    template_folder=os.path.join(_RESOURCE_DIR, "templates"),
    static_folder=os.path.join(_RESOURCE_DIR, "static"),
)
app.secret_key = "local-personal-library-app"  # local-only app, no real session security needed


def create_app():
    os.makedirs(LIBRARY_DIR, exist_ok=True)
    os.makedirs(UNCLASSIFIED_DIR, exist_ok=True)
    db.init_db()
    return app


# ---------------- Library ----------------

@app.route("/")
def index():
    domain = request.args.get("domain")
    path = request.args.get("path")
    filt = request.args.get("filter")
    
    path_prefix = None
    if path:
        safe_path = os.path.normpath(path)
        path_prefix = os.path.join(LIBRARY_DIR, safe_path)
        # Ensure it has the trailing separator so we don't accidentally match 'AI_Safety' when looking for 'AI'
        path_prefix = path_prefix + os.sep

    papers = db.list_papers(
        domain=domain,
        path_prefix=path_prefix,
        interesting_only=(filt == "interesting"),
        unread_only=(filt == "unread"),
    )
    domains = db.list_domains()
    library_tree = get_library_tree(db.list_papers())
    return render_template("index.html", papers=papers, domains=domains,
                           library_tree=library_tree, active_domain=domain, active_path=path, active_filter=filt, stats=db.stats())


@app.route("/paper/<int:paper_id>")
def paper_detail(paper_id):
    paper = db.get_paper(paper_id)
    if not paper:
        return "Paper not found", 404
    return render_template("paper.html", paper=paper)


@app.route("/paper/<int:paper_id>/pdf")
def paper_pdf(paper_id):
    paper = db.get_paper(paper_id)
    if not paper:
        return "Paper not found", 404
    if not os.path.exists(paper["pdf_path"]):
        return "PDF file not found on disk", 404
    db.increment_open_count(paper_id)
    return send_file(paper["pdf_path"])


@app.route("/paper/<int:paper_id>/interesting", methods=["POST"])
def set_interesting(paper_id):
    value = request.form.get("value") == "1"
    db.set_interesting(paper_id, value)
    return redirect(request.referrer or url_for("paper_detail", paper_id=paper_id))


@app.route("/paper/<int:paper_id>/read", methods=["POST"])
def mark_read(paper_id):
    db.mark_read(paper_id)
    return redirect(request.referrer or url_for("paper_detail", paper_id=paper_id))


@app.route("/paper/<int:paper_id>/delete", methods=["POST"])
def delete_paper(paper_id):
    if db.delete_paper(paper_id):
        flash("Paper successfully deleted.")
        return redirect(url_for("index"))
    return "Paper not found", 404

@app.route("/paper/<int:paper_id>/reclassify", methods=["POST"])
def reclassify_paper(paper_id):
    if not ai_service.is_configured():
        flash("AI is not configured. Please configure it in settings first.")
        return redirect(url_for("paper_detail", paper_id=paper_id))

    paper = db.get_paper(paper_id)
    if not paper:
        return "Paper not found", 404
    
    if not os.path.exists(paper["pdf_path"]):
        flash("AI classification failed: PDF file not found on disk.")
        return redirect(url_for("paper_detail", paper_id=paper_id))

    extracted = pdf_processor.extract(paper["pdf_path"])
    text_for_ai = (extracted.get("abstract") or extracted.get("full_text_sample", "")).strip()

    if len(text_for_ai) < 30:
        flash("AI classification failed: could not extract enough text from this PDF.")
        return redirect(url_for("paper_detail", paper_id=paper_id))

    existing_domains = [d["name"] for d in db.list_domains() if d["name"] != "Unclassified"]
    try:
        result = ai_service.classify_and_summarize(text_for_ai, paper["title"], existing_domains)
        meta = {
            "primary_domain": result.get("primary_domain"),
            "domains": [result.get("primary_domain")] + result.get("subdomains", []),
            "keywords": ", ".join(result.get("keywords", [])),
            "technical_summary": result.get("technical_summary"),
            "simple_explanation": result.get("simple_explanation"),
            "tags": result.get("keywords", [])
        }
        meta["domains"] = [d for d in meta["domains"] if d]

        if not meta.get("domains"):
            meta["primary_domain"] = "Unclassified"
            meta["domains"] = ["Unclassified"]

        db.update_paper_classification(paper_id, meta)
        
        if meta["primary_domain"] != "Unclassified":
            old_path = paper["pdf_path"]
            doc_type = meta.get("document_type", "Research_Papers").replace(" ", "_")
            safe_domains = [d.replace(" ", "_") for d in meta.get("domains", []) if d]
            target_dir = os.path.join(LIBRARY_DIR, doc_type, *safe_domains)
            os.makedirs(target_dir, exist_ok=True)
            
            new_path = os.path.join(target_dir, os.path.basename(old_path))
            new_path = _dedupe_path(new_path)
            
            if os.path.normpath(old_path) != os.path.normpath(new_path) and os.path.exists(old_path):
                shutil.move(old_path, new_path)
                db.update_paper(paper_id, {"pdf_path": new_path})
        else:
            old_path = paper["pdf_path"]
            if os.path.normpath(UNCLASSIFIED_DIR) not in os.path.normpath(old_path):
                new_path = os.path.join(UNCLASSIFIED_DIR, os.path.basename(old_path))
                new_path = _dedupe_path(new_path)
                if os.path.exists(old_path):
                    shutil.move(old_path, new_path)
                    db.update_paper(paper_id, {"pdf_path": new_path})
        
        updated_paper = db.get_paper(paper_id)
        
        # Update embedding
        text = embeddings.paper_searchable_text(updated_paper)
        vector = embeddings.embed_text(text)
        db.save_embedding(paper_id, vector)
        
        flash("Paper successfully re-classified.")
    except Exception as e:
        flash(f"AI classification failed: {e}")

    return redirect(url_for("paper_detail", paper_id=paper_id))


# ---------------- Import ----------------

@app.route("/import", methods=["GET", "POST"])
def import_paper():
    if request.method == "GET":
        return render_template("import.html", ai_configured=ai_service.is_configured())

    file = request.files.get("pdf_file")
    if not file or file.filename == "":
        flash("No file selected.")
        return redirect(url_for("import_paper"))

    # 1. Store the PDF once, locally. Initially put it in UNCLASSIFIED_DIR.
    safe_name = _safe_filename(file.filename)
    dest_path = os.path.join(UNCLASSIFIED_DIR, safe_name)
    dest_path = _dedupe_path(dest_path)
    file.save(dest_path)

    # 2. Offline extraction (title/authors/DOI/abstract).
    extracted = pdf_processor.extract(dest_path)

    meta = {
        "title": extracted["title"],
        "authors": extracted["authors"],
        "year": extracted["year"],
        "doi": extracted["doi"],
        "abstract": extracted["abstract"],
        "domains": [],
        "tags": [],
    }

    # 3. Optional AI classification + summaries (only if configured).
    existing_domains = [d["name"] for d in db.list_domains()]
    ai_used = False
    if ai_service.is_configured():
        text_for_ai = (extracted.get("abstract") or extracted.get("full_text_sample", "")).strip()
        if len(text_for_ai) < 30:
            # PDF appears to be a scanned image or has no extractable text —
            # sending an empty/tiny string to the AI produces garbage or empty
            # responses, which then crash the JSON parser.
            flash(
                "AI classification skipped: could not extract enough text from this PDF "
                "(it may be a scanned image). The paper was saved as 'Unclassified'."
            )
        else:
            try:
                result = ai_service.classify_and_summarize(text_for_ai, meta["title"], existing_domains)
                meta["primary_domain"] = result.get("primary_domain")
                meta["domains"] = [result.get("primary_domain")] + result.get("subdomains", [])
                meta["domains"] = [d for d in meta["domains"] if d]
                meta["keywords"] = ", ".join(result.get("keywords", []))
                meta["technical_summary"] = result.get("technical_summary")
                meta["simple_explanation"] = result.get("simple_explanation")
                meta["document_type"] = result.get("document_type", "Research_Papers")
                ai_used = True
            except Exception as e:
                flash(f"AI classification skipped: {e}")

    if not meta.get("domains"):
        meta["primary_domain"] = "Unclassified"
        meta["domains"] = ["Unclassified"]

    # If successfully classified, move it to the right nested folder
    if meta["primary_domain"] != "Unclassified":
        doc_type = meta.get("document_type", "Research_Papers").replace(" ", "_")
        safe_domains = [d.replace(" ", "_") for d in meta.get("domains", []) if d]
        target_dir = os.path.join(LIBRARY_DIR, doc_type, *safe_domains)
        os.makedirs(target_dir, exist_ok=True)
        
        new_dest_path = os.path.join(target_dir, os.path.basename(dest_path))
        new_dest_path = _dedupe_path(new_dest_path)
        if os.path.exists(dest_path):
            shutil.move(dest_path, new_dest_path)
            dest_path = new_dest_path

    paper_id = db.add_paper(meta, dest_path)

    # 4. Local embedding for offline semantic search (always runs, no API needed).
    paper = db.get_paper(paper_id)
    text = embeddings.paper_searchable_text(paper)
    vector = embeddings.embed_text(text)
    db.save_embedding(paper_id, vector)

    return redirect(url_for("paper_detail", paper_id=paper_id))


# ---------------- Search / Chat ----------------

@app.route("/search", methods=["GET", "POST"])
def search():
    results = []
    answer = None
    query = ""
    mode = "find"
    if request.method == "POST":
        query = request.form.get("query", "").strip()
        mode = request.form.get("mode", "find")
        if query:
            db.log_search(query)

        if query and mode == "find":
            candidates = db.all_papers_with_embeddings()
            scored = embeddings.semantic_search(query, candidates, top_k=10)
            results = []
            for pid, title, score in scored:
                p = db.get_paper(pid)
                p["relevance"] = round(score * 100, 1)
                results.append(p)

        elif query and mode == "reason":
            # Reasoning mode: first find relevant papers locally, then send
            # ONLY those (not the whole library) to the AI for synthesis.
            candidates = db.all_papers_with_embeddings()
            scored = embeddings.semantic_search(query, candidates, top_k=6)
            top_papers = [db.get_paper(pid) for pid, _, _ in scored]
            if not ai_service.is_configured():
                flash("Configure an AI API key in Settings to use reasoning mode.")
            else:
                try:
                    answer = ai_service.answer_complex_query(query, top_papers)
                except Exception as e:
                    flash(f"AI request failed: {e}")
            results = top_papers

    return render_template("search.html", results=results, answer=answer, query=query,
                            mode=mode, ai_configured=ai_service.is_configured(),
                            backend=embeddings.backend_name_lazy())


# ---------------- Daily recommendation ----------------

@app.route("/today")
def today():
    interesting = db.list_papers(interesting_only=True)
    unread_interesting = [p for p in interesting if not p["read"]]
    pool = unread_interesting or interesting or db.list_papers()
    pick = random.choice(pool) if pool else None
    reason = None
    if pick:
        if pick in unread_interesting:
            reason = "Picked from your 'Interesting' list -- you haven't read it yet."
        elif pick in interesting:
            reason = "Picked from your 'Interesting' list."
        else:
            reason = "Your 'Interesting' list is empty, so this is a recent addition to your library."
    return render_template("today.html", paper=pick, reason=reason)


# ---------------- Settings ----------------

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        db.set_setting("ai_provider", request.form.get("ai_provider", "anthropic"))
        db.set_setting("ai_api_key", request.form.get("ai_api_key", ""))
        db.set_setting("ai_model", request.form.get("ai_model", ""))
        db.set_setting("ai_base_url", request.form.get("ai_base_url", ""))
        flash("Settings saved.")
        return redirect(url_for("settings"))
    cfg = ai_service.get_config()
    return render_template("settings.html", cfg=cfg, backend=embeddings.backend_name_lazy(),
                            stats=db.stats())


@app.route("/settings/reembed", methods=["POST"])
def reembed():
    """
    Recomputes every paper's search vector using whichever embedding backend
    is currently active. Needed after installing/removing sentence-transformers,
    since vectors from different backends have different sizes and can't be
    compared against each other (that's what caused the /search crash).
    """
    papers = db.list_papers()
    count = 0
    for p in papers:
        full = db.get_paper(p["id"])
        text = embeddings.paper_searchable_text(full)
        vector = embeddings.embed_text(text)
        db.save_embedding(p["id"], vector)
        count += 1
    flash(f"Rebuilt search index for {count} paper(s) using the '{embeddings.backend_name()}' backend.")
    return redirect(url_for("settings"))


@app.route("/settings/reclassify_all", methods=["POST"])
def reclassify_all():
    if not ai_service.is_configured():
        flash("AI is not configured. Please configure it first.")
        return redirect(url_for("settings"))
        
    papers = db.list_papers()
    # Filter only unclassified ones
    unclassified = [p for p in papers if p.get("primary_domain") == "Unclassified"]
    
    count = 0
    errors = 0
    existing_domains = [d["name"] for d in db.list_domains() if d["name"] != "Unclassified"]
    
    for paper in unclassified:
        if not os.path.exists(paper["pdf_path"]):
            errors += 1
            continue
            
        extracted = pdf_processor.extract(paper["pdf_path"])
        text_for_ai = (extracted.get("abstract") or extracted.get("full_text_sample", "")).strip()
        if len(text_for_ai) < 30:
            errors += 1
            continue
            
        try:
            result = ai_service.classify_and_summarize(text_for_ai, paper["title"], existing_domains)
            meta = {
                "primary_domain": result.get("primary_domain"),
                "domains": [result.get("primary_domain")] + result.get("subdomains", []),
                "keywords": ", ".join(result.get("keywords", [])),
                "technical_summary": result.get("technical_summary"),
                "simple_explanation": result.get("simple_explanation"),
                "tags": result.get("keywords", [])
            }
            meta["domains"] = [d for d in meta["domains"] if d]
            if not meta.get("domains"):
                meta["primary_domain"] = "Unclassified"
                meta["domains"] = ["Unclassified"]
                
            db.update_paper_classification(paper["id"], meta)
            
            if meta["primary_domain"] != "Unclassified":
                old_path = paper["pdf_path"]
                doc_type = meta.get("document_type", "Research_Papers").replace(" ", "_")
                safe_domains = [d.replace(" ", "_") for d in meta.get("domains", []) if d]
                target_dir = os.path.join(LIBRARY_DIR, doc_type, *safe_domains)
                os.makedirs(target_dir, exist_ok=True)
                
                new_path = os.path.join(target_dir, os.path.basename(old_path))
                new_path = _dedupe_path(new_path)
                
                if os.path.normpath(old_path) != os.path.normpath(new_path) and os.path.exists(old_path):
                    shutil.move(old_path, new_path)
                    db.update_paper(paper["id"], {"pdf_path": new_path})
            else:
                old_path = paper["pdf_path"]
                if os.path.normpath(UNCLASSIFIED_DIR) not in os.path.normpath(old_path):
                    new_path = os.path.join(UNCLASSIFIED_DIR, os.path.basename(old_path))
                    new_path = _dedupe_path(new_path)
                    if os.path.exists(old_path):
                        shutil.move(old_path, new_path)
                        db.update_paper(paper["id"], {"pdf_path": new_path})
            
            # Re-embed
            updated_paper = db.get_paper(paper["id"])
            text = embeddings.paper_searchable_text(updated_paper)
            vector = embeddings.embed_text(text)
            db.save_embedding(paper["id"], vector)
            
            count += 1
        except Exception:
            errors += 1
            
    msg = f"Successfully re-classified {count} papers."
    if errors > 0:
        msg += f" ({errors} papers failed or skipped due to errors)."
    flash(msg)
    return redirect(url_for("settings"))


# ---------------- helpers ----------------

def _safe_filename(name):
    keep = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    cleaned = "".join(c for c in name if c in keep).strip()
    return cleaned or "paper.pdf"

def get_library_tree(all_papers):
    tree = {}
    for p in all_papers:
        if p.get("primary_domain") == "Unclassified":
            continue
        pdf_path = p.get("pdf_path", "")
        try:
            rel_path = os.path.relpath(pdf_path, LIBRARY_DIR)
            parts = rel_path.split(os.sep)
            if len(parts) >= 2:
                doc_type_raw = parts[0]
                doc_type = doc_type_raw.replace("_", " ")
                # everything after doc_type until the filename are domains
                domains_raw = parts[1:-1]
                domains = [part.replace("_", " ") for part in domains_raw]
                
                if doc_type not in tree:
                    tree[doc_type] = {}
                
                curr = tree[doc_type]
                current_prefix = doc_type_raw
                for i, d in enumerate(domains):
                    current_prefix = current_prefix + "/" + domains_raw[i]
                    if d not in curr:
                        curr[d] = {"count": 0, "subdomains": {}, "path": current_prefix}
                    curr[d]["count"] += 1
                    curr = curr[d]["subdomains"]
        except ValueError:
            pass
    return tree


def _dedupe_path(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while os.path.exists(f"{base}_{i}{ext}"):
        i += 1
    return f"{base}_{i}{ext}"


if __name__ == "__main__":
    create_app()
    app.run(debug=True, port=5001)
