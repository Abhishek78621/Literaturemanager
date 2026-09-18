import os
import shutil
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from app import database as db
from app.app import LIBRARY_DIR, UNCLASSIFIED_DIR, _dedupe_path

def migrate():
    db.init_db()
    
    # Run the database schema update (it might be needed if they have an old database)
    try:
        with db.get_conn() as conn:
            conn.execute("ALTER TABLE papers ADD COLUMN document_type TEXT DEFAULT 'Research_Papers'")
            print("Added document_type column to papers table.")
    except Exception as e:
        if "duplicate column name" in str(e):
            print("Column document_type already exists.")
        else:
            print("Error adding column:", e)

    os.makedirs(UNCLASSIFIED_DIR, exist_ok=True)
    papers = db.list_papers()
    moved_count = 0

    for p in papers:
        old_path = p.get("pdf_path")
        if not old_path or not os.path.exists(old_path):
            continue

        primary_domain = p.get("primary_domain")
        doc_type = p.get("document_type", "Research_Papers").replace(" ", "_")
        
        if primary_domain and primary_domain != "Unclassified":
            # get domains logic
            paper_full = db.get_paper(p["id"])
            domains = paper_full.get("domains", [])
            safe_domains = [d.replace(" ", "_") for d in domains if d]
            
            target_dir = os.path.join(LIBRARY_DIR, doc_type, *safe_domains)
            os.makedirs(target_dir, exist_ok=True)
            new_path = os.path.join(target_dir, os.path.basename(old_path))
        else:
            new_path = os.path.join(UNCLASSIFIED_DIR, os.path.basename(old_path))
            
        new_path = _dedupe_path(new_path)
            
        if os.path.normpath(old_path) != os.path.normpath(new_path):
            print(f"Moving: {old_path} -> {new_path}")
            shutil.move(old_path, new_path)
            db.update_paper(p["id"], {"pdf_path": new_path})
            moved_count += 1
            
    # Optionally, remove old empty directories if they are empty
    old_papers_dir = os.path.join(LIBRARY_DIR, "papers")
    old_unclassified_dir = os.path.join(LIBRARY_DIR, "unclassified_papers")
    
    for old_dir in [old_papers_dir, old_unclassified_dir]:
        if os.path.exists(old_dir):
            try:
                os.rmdir(old_dir)
                print(f"Removed empty directory {old_dir}")
            except OSError:
                print(f"Directory {old_dir} is not empty, skipping removal.")

    print(f"Migration complete. Moved {moved_count} papers.")

if __name__ == "__main__":
    migrate()
