import os
import sys
import subprocess

def download_model(model_name="all-MiniLM-L6-v2", dest_dir="models"):
    save_path = os.path.join(dest_dir, model_name)
    if os.path.exists(save_path):
        print(f"Model already exists at {save_path}, skipping download.")
        return save_path

    print(f"Downloading {model_name} to {dest_dir} for offline packaging...")
    
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("sentence-transformers is not installed. Skipping model download.")
        print("If you want the offline search model bundled, run: pip install sentence-transformers")
        return None

    # Load the model (this will download it to the default HF cache if not already there)
    print("Loading model via sentence-transformers (this may take a moment)...")
    model = SentenceTransformer(model_name)
    
    # Save the model cleanly to a local directory so PyInstaller can package it
    save_path = os.path.join(dest_dir, model_name)
    print(f"Saving standalone model to {save_path}...")
    model.save(save_path)
    return save_path

def build():
    # Ensure we are in the correct directory so PyInstaller finds the right files
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    # 1. Download/prepare model
    model_path = download_model()
    
    # 2. Run PyInstaller
    print("\nRunning PyInstaller...")
    sep = ";" if os.name == "nt" else ":"
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",  # Creates a single standalone executable
        "--name", "PersonalLiteratureManager",
        f"--add-data=app/templates{sep}app/templates",
        f"--add-data=app/static{sep}app/static"
    ]
    
    if model_path and os.path.exists(model_path):
        cmd.append(f"--add-data={model_path}{sep}models/{os.path.basename(model_path)}")
        
    cmd.append("run.py")
    
    try:
        subprocess.run(cmd, check=True)
        print("\nBuild complete! Check the dist/ folder for PersonalLiteratureManager.exe.")
    except subprocess.CalledProcessError as e:
        print(f"\nPyInstaller build failed: {e}")
        print("Make sure you have PyInstaller installed: pip install pyinstaller")

if __name__ == "__main__":
    build()
