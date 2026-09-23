# Personal Literature Manager
**Your Smart, Private, and Automated PDF Research Library**

Personal Literature Manager is a locally-hosted, privacy-first web application designed to help researchers, students, and professionals effortlessly organize, search, and understand their PDF collections. It leverages modern AI to do the heavy lifting of categorizing your papers while ensuring your files never leave your computer unless you explicitly enable a cloud AI provider.

---

## 🌟 Key Features

### 1. Smart Automated Organization
- **Custom Library Root**: Choose exactly where on your hard drive your PDFs are stored.
- **First-Time Auto-Sync**: Got an existing folder full of categorized PDFs? Point the app to it during setup, and it will automatically adopt your existing subfolders as your "Domains".
- **Zero-Duplication Hard Links**: If a paper belongs to multiple domains (e.g., both "Computer Vision" and "Robotics"), the app stores only **one** physical copy of the PDF. For the other domains, it creates native Windows **Hard Links**, which act like normal files but take up **0 bytes** of extra disk space.

### 2. AI-Powered Classification & Summarization
When you import a paper, you can use local AI (like Ollama) or cloud AI (like Claude or ChatGPT) to automatically read it for you:
- **Auto-Categorization**: The AI determines the best primary and secondary domains for the paper and automatically moves the file into those folders.
- **Smart Summaries**: Generates a technical summary, a simple explanation, and extracts keywords so you can understand a 30-page paper in 30 seconds.
- **Fallback to Unclassified**: If the AI suggests a brand new domain that you haven't approved, the app safely places the paper in an "Unclassified" folder for manual review.

### 3. Background Daemon Scanner
Never manually import a paper again. 
- **Interval Scanning**: Configure the app to scan your Literature folder every X hours and Y minutes.
- **Headless Mode**: Run the app on startup with the `--daemon` flag. It will run silently in the background, monitoring your folders without opening any annoying console windows or browsers.
- **Smart Deduplication**: The scanner uses cryptographic SHA-256 hashing. If you drop a PDF into the folder that you already imported months ago, the scanner instantly skips it. It only processes genuinely new files.

### 4. Advanced Semantic Search
- **Find Papers**: Search for concepts, not just keywords. The app uses semantic embeddings to understand the *meaning* of your search query and finds the most relevant papers.
- **Reason Across Papers**: Ask a complex question (e.g., "What are the limitations of multi-scale attention models mentioned in my library?"). The app will find the top relevant papers and use AI to synthesize a comprehensive answer with citations.

---

## 🚀 How to Use It

### Getting Started
1. **Launch the App**: Double click the `LiteratureManager.exe` file, or run `python run.py`.
2. **First Setup**: Your browser will open. You will be prompted to enter your **Literature Root Folder Path**. Enter the path where you want to keep your PDFs (or where they already are).
3. **Configure AI (Optional but Recommended)**: Go to **Settings**. You can configure a free local AI (like Ollama) or a cloud provider (Anthropic/OpenAI) for automatic summaries.

### Importing Papers
You have three ways to add papers:
1. **Single File**: Go to the Import tab and drag-and-drop a single PDF.
2. **Bulk Folder Import**: Go to the Import tab and enter a folder path to scan a massive batch of PDFs at once. You can choose to preserve their existing folder structure or let the AI completely re-organize them.
3. **Background Scanner**: Drop a PDF directly into your Literature Root Folder in Windows Explorer. The background daemon will automatically find it, classify it, and move it to the right subfolder on its next scheduled scan!

### Background Mode (Start with Windows)
To run the app silently in the background so it's always ready:
1. Right-click on your Desktop and choose **New -> Shortcut**.
2. Point it to `LiteratureManager.exe`.
3. Right-click the new shortcut, go to **Properties**, and add `--daemon` to the end of the **Target** field.
4. Press `Win + R`, type `shell:startup`, and drag this shortcut into the folder. The app will now automatically run silently in the background every time you turn on your PC!

---

## ⚙️ Technical Requirements
- **OS**: Windows (due to native Hard Link implementation)
- **Browser**: Any modern web browser (Chrome, Edge, Firefox, Safari)
- **Optional**: `sentence-transformers` Python package for true local semantic search.
