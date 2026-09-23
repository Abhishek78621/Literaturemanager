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
import json
import hashlib
import threading
import time
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, flash, Response

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

def get_library_dir():
    try:
        custom_path = db.get_setting("literature_root_path")
        if custom_path:
            if not os.path.exists(custom_path):
                try:
                    os.makedirs(custom_path, exist_ok=True)
                except Exception:
                    pass
            return custom_path
    except Exception:
        pass
    return os.path.join(BASE_DIR, "library")

def get_unclassified_dir():
    return os.path.join(get_library_dir(), "Unclassified")

app = Flask(
    __name__,
    template_folder=os.path.join(_RESOURCE_DIR, "templates"),
    static_folder=os.path.join(_RESOURCE_DIR, "static"),
)
app.secret_key = "local-personal-library-app"  # local-only app, no real session security needed


def create_app():
    db.init_db()
    os.makedirs(get_library_dir(), exist_ok=True)
    os.makedirs(get_unclassified_dir(), exist_ok=True)
    start_scheduler()
    return app


# ---------------- Library ----------------


SECRET_SALT = "LIT_MANAGER_SECRET_2026_xYz"

def get_hardware_id():
    import subprocess
    try:
        output = subprocess.check_output('wmic csproduct get uuid', shell=True, stderr=subprocess.DEVNULL).decode().split('\n')[1].strip()
        return hashlib.sha256(output.encode("utf-8")).hexdigest()[:16].upper()
    except Exception:
        import uuid
        return hashlib.sha256(str(uuid.getnode()).encode("utf-8")).hexdigest()[:16].upper()

def get_expected_license_key():
    hw_id = get_hardware_id()
    raw_str = hw_id + SECRET_SALT
    full_hash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
    key = full_hash[:16].upper()
    return f"{key[:4]}-{key[4:8]}-{key[8:12]}-{key[12:16]}"


@app.before_request
def check_license_and_setup():
    if request.endpoint and request.endpoint not in ['license_page', 'static']:
        saved_key = db.get_setting("license_key")
        expected_key = get_expected_license_key()
        if not saved_key or saved_key != expected_key:
            return redirect(url_for('license_page'))
            
        if request.endpoint != 'setup' and not db.get_setting("literature_root_path"):
            return redirect(url_for('setup'))

@app.route("/license", methods=["GET", "POST"])
def license_page():
    hw_id = get_hardware_id()
    if request.method == "POST":
        entered_key = request.form.get("license_key", "").strip()
        if entered_key == get_expected_license_key():
            db.set_setting("license_key", entered_key)
            flash("License activated successfully!")
            return redirect(url_for("index"))
        else:
            flash("Invalid License Key. Please try again.")
    return render_template("license.html", hw_id=hw_id)


@app.route("/setup", methods=["GET", "POST"])
def setup():
    if request.method == "POST":
        root_path = request.form.get("literature_root_path", "").strip()
        if root_path and os.path.isdir(root_path):
            db.set_setting("literature_root_path", root_path)
            db.sync_domains_from_folders(root_path)
            flash("Setup complete. Existing folders registered as domains.")
            return redirect(url_for("index"))
        else:
            flash("Invalid directory path. Please ensure the folder exists.")
    return render_template("setup.html")

@app.route("/")
def index():
    domain = request.args.get("domain")
    path = request.args.get("path")
    filt = request.args.get("filter")
    
    path_prefix = None
    if path:
        safe_path = os.path.normpath(path)
        path_prefix = os.path.join(get_library_dir(), safe_path)
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
        db.cleanup_empty_domains()
        flash("Paper successfully deleted.")
        return redirect(url_for("index"))
    return "Paper not found", 404

@app.route("/delete_multiple_papers", methods=["POST"])
def delete_multiple_papers():
    paper_ids = request.form.getlist("paper_ids")
    deleted_count = 0
    for pid in paper_ids:
        try:
            if db.delete_paper(int(pid)):
                deleted_count += 1
        except ValueError:
            pass
    if deleted_count > 0:
        db.cleanup_empty_domains()
        flash(f"Successfully deleted {deleted_count} paper(s).")
    else:
        flash("No papers were deleted.")
    return redirect(url_for("index"))

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
            target_dir = os.path.join(get_library_dir(), doc_type, *safe_domains)
            os.makedirs(target_dir, exist_ok=True)
            
            new_path = os.path.join(target_dir, os.path.basename(old_path))
            new_path = _dedupe_path(new_path)
            
            if os.path.normpath(old_path) != os.path.normpath(new_path) and os.path.exists(old_path):
                shutil.move(old_path, new_path)
                db.update_paper(paper_id, {"pdf_path": new_path})
        else:
            old_path = paper["pdf_path"]
            if os.path.normpath(get_unclassified_dir()) not in os.path.normpath(old_path):
                new_path = os.path.join(get_unclassified_dir(), os.path.basename(old_path))
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

@app.route("/import", methods=["GET"])
def import_paper():
    return render_template("import.html", ai_configured=ai_service.is_configured())

@app.route("/api/upload_paper", methods=["POST"])
def upload_paper():
    file = request.files.get("pdf_file")
    if not file or file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    relative_path = request.form.get("relative_path") or file.filename
    org_mode = request.form.get("organization_mode", "preserve")

    temp_dir = os.path.join(get_library_dir(), ".temp_uploads")
    os.makedirs(temp_dir, exist_ok=True)

    safe_rel_path = os.path.normpath(relative_path).lstrip("/\\")
    dest_path = os.path.join(temp_dir, safe_rel_path)
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    file.save(dest_path)

    existing_domains = [d["name"] for d in db.list_domains()]

    try:
        res = process_single_file(dest_path, temp_dir, org_mode, existing_domains)
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return jsonify(res)
    except Exception as e:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return jsonify({"error": str(e)}), 500

def get_sha256(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def process_single_file(file_path, folder_path, org_mode, existing_domains):
    filename = os.path.basename(file_path)
    file_hash = get_sha256(file_path)
    if db.get_paper_by_hash(file_hash):
        return {"status": "skipped", "message": f"Skipped duplicate: {filename}"}
    
    extracted = pdf_processor.extract(file_path)
    meta = {
        "title": extracted.get("title") or filename,
        "authors": extracted.get("authors") or "",
        "year": extracted.get("year") or "",
        "doi": extracted.get("doi") or "",
        "abstract": extracted.get("abstract") or "",
        "domains": [],
        "tags": [],
        "sha256": file_hash
    }
    
    if org_mode == "preserve":
        rel_path = os.path.relpath(os.path.dirname(file_path), folder_path)
        
        if rel_path == "." or not rel_path:
            domains = []
        else:
            domains = [d for d in rel_path.split(os.sep) if d]
        
        if domains:
            meta["primary_domain"] = domains[0]
            meta["domains"] = domains
        else:
            meta["primary_domain"] = "Unclassified"
            meta["domains"] = ["Unclassified"]
    else:
        # AI Mode with STRICT existing domain check
        if ai_service.is_configured():
            text_for_ai = (extracted.get("abstract") or extracted.get("full_text_sample", "")).strip()
            if len(text_for_ai) >= 30:
                try:
                    result = ai_service.classify_and_summarize(text_for_ai, meta["title"], existing_domains)
                    
                    primary = result.get("primary_domain")
                    if primary and primary in existing_domains:
                        meta["primary_domain"] = primary
                        meta["domains"] = [primary] + result.get("subdomains", [])
                        meta["domains"] = [d for d in meta["domains"] if d]
                        meta["keywords"] = ", ".join(result.get("keywords", []))
                        meta["technical_summary"] = result.get("technical_summary")
                        meta["simple_explanation"] = result.get("simple_explanation")
                        meta["document_type"] = result.get("document_type", "Research_Papers")
                    else:
                        meta["primary_domain"] = "Unclassified"
                        meta["domains"] = ["Unclassified"]
                except Exception:
                    pass
        
        if not meta.get("domains"):
            meta["primary_domain"] = "Unclassified"
            meta["domains"] = ["Unclassified"]
            
    doc_type = meta.get("document_type", "Research_Papers").replace(" ", "_")
    safe_domains = [d.replace(" ", "_") for d in meta.get("domains", []) if d]
    
    if meta["primary_domain"] != "Unclassified":
        if org_mode == "preserve":
            target_dir = os.path.join(get_library_dir(), *safe_domains)
        else:
            target_dir = os.path.join(get_library_dir(), doc_type, *safe_domains)
    else:
        target_dir = get_unclassified_dir()
        
    os.makedirs(target_dir, exist_ok=True)
    
    safe_name = _safe_filename(filename)
    new_dest_path = os.path.join(target_dir, safe_name)
    new_dest_path = _dedupe_path(new_dest_path)
    
    # If the file is already within the library dir, we move it, else copy
    lib_dir_abs = os.path.abspath(get_library_dir())
    file_path_abs = os.path.abspath(file_path)
    
    if os.path.commonpath([file_path_abs, lib_dir_abs]) == lib_dir_abs:
        if file_path_abs != new_dest_path:
            shutil.move(file_path, new_dest_path)
    else:
        shutil.copy2(file_path, new_dest_path)
    
    paper_id = db.add_paper(meta, new_dest_path)
    
    # Handle multiple domains with hard links (only for AI mode, not preserve mode)
    if org_mode != "preserve" and len(meta.get("domains", [])) > 1:
        primary_domain = meta.get("primary_domain")
        for domain in meta["domains"]:
            if domain != primary_domain and domain != "Unclassified":
                safe_domain = domain.replace(" ", "_")
                link_target_dir = os.path.join(get_library_dir(), doc_type, safe_domain)
                os.makedirs(link_target_dir, exist_ok=True)
                link_dest_path = os.path.join(link_target_dir, safe_name)
                link_dest_path = _dedupe_path(link_dest_path)
                try:
                    os.link(new_dest_path, link_dest_path)
                except Exception as e:
                    print(f"Failed to create hard link for {domain}: {e}")
    
    paper = db.get_paper(paper_id)
    text = embeddings.paper_searchable_text(paper)
    vector = embeddings.embed_text(text)
    db.save_embedding(paper_id, vector)
    
    return {"status": "imported", "message": f"Imported: {filename}"}

def background_scanner_loop():
    while True:
        time.sleep(60)
        try:
            enabled = db.get_setting("auto_scan_enabled")
            interval_hours_str = db.get_setting("auto_scan_interval_hours")
            
            if enabled == "1":
                interval_hours = float(db.get_setting("auto_scan_interval_hours") or 0)
                interval_minutes = float(db.get_setting("auto_scan_interval_minutes") or 0)
                total_seconds = (interval_hours * 3600) + (interval_minutes * 60)
                
                if total_seconds > 0:
                    last_scan_time_str = db.get_setting("last_scan_time")
                    last_scan_time = float(last_scan_time_str) if last_scan_time_str else 0.0
                    
                    current_time = time.time()
                    
                    if current_time - last_scan_time >= total_seconds:
                        db.set_setting("last_scan_time", str(current_time))
                        print("Running scheduled auto-scan...")
                        folder_path = get_library_dir()
                        existing_domains = [d["name"] for d in db.list_domains()]
                        
                        pdf_files = []
                        for root, _, files in os.walk(folder_path):
                            for file in files:
                                if file.lower().endswith(".pdf"):
                                    pdf_files.append(os.path.join(root, file))
                                    
                        for f_path in pdf_files:
                            try:
                                # Use AI mode because the user requested it: 
                                # "Use AI classification only for newly detected files"
                                process_single_file(f_path, folder_path, "ai", existing_domains)
                            except Exception as e:
                                print(f"Error in auto-scan for {f_path}: {e}")
                    
        except Exception as e:
            print(f"Background scanner error: {e}")

def start_scheduler():
    t = threading.Thread(target=background_scanner_loop, daemon=True)
    t.start()



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
        db.set_setting("literature_root_path", request.form.get("literature_root_path", "").strip())
        db.set_setting("auto_scan_enabled", request.form.get("auto_scan_enabled", "0"))
        db.set_setting("auto_scan_interval_hours", request.form.get("auto_scan_interval_hours", "0"))
        db.set_setting("auto_scan_interval_minutes", request.form.get("auto_scan_interval_minutes", "0"))
        flash("Settings saved.")
        return redirect(url_for("settings"))
    cfg = ai_service.get_config()
    literature_root_path = db.get_setting("literature_root_path") or ""
    auto_scan_enabled = db.get_setting("auto_scan_enabled") == "1"
    auto_scan_interval_hours = db.get_setting("auto_scan_interval_hours") or "0"
    auto_scan_interval_minutes = db.get_setting("auto_scan_interval_minutes") or "0"
    return render_template("settings.html", cfg=cfg, backend=embeddings.backend_name_lazy(),
                            stats=db.stats(), literature_root_path=literature_root_path,
                            auto_scan_enabled=auto_scan_enabled, 
                            auto_scan_interval_hours=auto_scan_interval_hours,
                            auto_scan_interval_minutes=auto_scan_interval_minutes)


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
                target_dir = os.path.join(get_library_dir(), doc_type, *safe_domains)
                os.makedirs(target_dir, exist_ok=True)
                
                new_path = os.path.join(target_dir, os.path.basename(old_path))
                new_path = _dedupe_path(new_path)
                
                if os.path.normpath(old_path) != os.path.normpath(new_path) and os.path.exists(old_path):
                    shutil.move(old_path, new_path)
                    db.update_paper(paper["id"], {"pdf_path": new_path})
            else:
                old_path = paper["pdf_path"]
                if os.path.normpath(get_unclassified_dir()) not in os.path.normpath(old_path):
                    new_path = os.path.join(get_unclassified_dir(), os.path.basename(old_path))
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
        doc_type_safe = p.get("document_type", "Research_Papers").replace(" ", "_")
        
        try:
            norm_path = os.path.normpath(pdf_path)
            parts = norm_path.split(os.sep)
            
            if doc_type_safe in parts:
                idx = parts.index(doc_type_safe)
                rel_parts = parts[idx:]
            else:
                rel_path = os.path.relpath(pdf_path, get_library_dir())
                rel_parts = rel_path.split(os.sep)
                if rel_parts and rel_parts[0] == "..":
                    rel_parts = [doc_type_safe, p.get("primary_domain", "Unclassified").replace(" ", "_"), "dummy.pdf"]
            
            if len(rel_parts) >= 2:
                doc_type_raw = rel_parts[0]
                doc_type = doc_type_raw.replace("_", " ")
                domains_raw = rel_parts[1:-1]
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
