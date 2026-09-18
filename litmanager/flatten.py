import os
import shutil
from app.app import LIBRARY_DIR
from app import database as db

def flatten_library():
    papers = db.list_papers()
    moved_count = 0
    with db.get_conn() as conn:
        for p in papers:
            if p.get("primary_domain") == "Unclassified":
                continue
            
            old_path = p.get("pdf_path", "")
            if not os.path.exists(old_path):
                continue
                
            rel_path = os.path.relpath(old_path, LIBRARY_DIR)
            parts = rel_path.split(os.sep)
            
            # parts is typically: [doc_type, domain, subdomain, ..., file.pdf]
            # if len(parts) > 4 (e.g. doc_type, domain, sub1, sub2, file.pdf)
            # we want to keep exactly: doc_type, domain, sub1, file.pdf
            if len(parts) > 4:
                doc_type = parts[0]
                domain = parts[1]
                subdomain = parts[2]
                filename = parts[-1]
                
                new_rel_path = os.path.join(doc_type, domain, subdomain, filename)
                new_path = os.path.join(LIBRARY_DIR, new_rel_path)
                
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                print(f"Flattening: {rel_path} -> {new_rel_path}")
                
                shutil.move(old_path, new_path)
                
                # update DB
                conn.execute("UPDATE papers SET pdf_path = ? WHERE id = ?", (new_path, p["id"]))
                moved_count += 1
                
                # Cleanup old directories if empty
                old_dir = os.path.dirname(old_path)
                while old_dir != LIBRARY_DIR:
                    try:
                        os.rmdir(old_dir)
                        print(f"Removed empty directory: {old_dir}")
                    except OSError:
                        break # not empty
                    old_dir = os.path.dirname(old_dir)
                    
    print(f"Flattening complete. Flattened {moved_count} papers.")

if __name__ == "__main__":
    flatten_library()
