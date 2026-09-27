<div align="center">
  <h1>📚 Personal Literature Manager</h1>
  <p><strong>A Smart, Private, and Automated PDF Research Library</strong></p>
  
  <p>
    <a href="#-overview">Overview</a> •
    <a href="#-key-features">Features</a> •
    <a href="#-getting-started">Installation</a> •
    <a href="#-usage-guide">Usage</a> •
    <a href="#%EF%B8%8F-technical-requirements">Requirements</a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Python-3.9%2B-blue.svg" alt="Python Version">
    <img src="https://img.shields.io/badge/Platform-Windows-lightgrey.svg" alt="Platform">
    <img src="https://img.shields.io/badge/AI-Ollama%20%7C%20Claude%20%7C%20GPT-success.svg" alt="AI Support">
    <img src="https://img.shields.io/badge/Search-Semantic%20Embeddings-orange.svg" alt="Search">
  </p>
</div>

---

## 📖 Overview

Personal Literature Manager is a locally-hosted, privacy-first web application designed to help researchers, students, and professionals effortlessly organize, search, and understand PDF collections. It leverages modern AI to automate the categorization of papers while ensuring files never leave the local machine unless a cloud AI provider is explicitly enabled.


## ✨ Key Features

### 🧠 AI-Powered Classification & Summarization
When importing a paper, local AI (e.g., Ollama) or cloud AI (e.g., Claude, ChatGPT) can be utilized for automatic reading and analysis:
* **Auto-Categorization:** The AI determines the best primary and secondary domains for the paper and automatically moves the file into appropriate directories.
* **Smart Summaries:** Generates a technical summary, a simple explanation, and extracts keywords to facilitate rapid comprehension of lengthy papers.
* **Bulk Re-Classification:** For papers imported without an AI key, multiple "Unclassified" documents can be selected from the library view and re-classified through the AI with a single click.

### 🗂️ Smart Automated Organization
* **Custom Library Root:** Specify exactly where on the hard drive PDFs should be stored.
* **First-Time Auto-Sync:** When pointing the application to an existing folder full of categorized PDFs during setup, it automatically adopts the existing subdirectories as library "Domains".
* **Zero-Duplication Hard Links:** If a paper belongs to multiple domains (e.g., both *Computer Vision* and *Robotics*), the application stores only **one** physical copy of the PDF. For the other domains, native Windows **Hard Links** are created, taking up **0 bytes** of extra disk space.

### 🔍 Advanced Semantic Search
* **Find Papers:** Search for concepts, not just keywords. Semantic embeddings are used to understand the *meaning* of a search query to locate the most relevant papers.
* **Reason Across Papers:** Complex queries (e.g., *"What are the limitations of multi-scale attention models mentioned in the library?"*) can be asked. Top relevant papers are located, and AI is used to synthesize a comprehensive answer with citations.

### 🔄 Background Daemon Scanner
Manual importation is no longer necessary. 
* **Interval Scanning:** The application can be configured to scan the Literature folder at specific hour and minute intervals.
* **Headless Mode:** Run on startup with the `--daemon` flag to operate silently in the background, monitoring folders without opening console windows or browsers.
* **Smart Deduplication:** Cryptographic SHA-256 hashing ensures that if a previously imported PDF is dropped into the folder, the scanner instantly skips it.

### 🔐 Secure Offline Licensing
* **Device-Locked:** Uses an offline cryptographic system that binds the software directly to the host's hardware ID. 
* **Offline Transfer:** Licenses can be seamlessly transferred from an old computer to a new computer using a "Deactivate & Transfer" code system without requiring an internet connection.

---

## 🚀 Getting Started

### Installation & Launch
1. **Launch the Application:** Execute the packaged `LiteratureManager.exe` file, or run `python run.py` from the source code.
2. **Activate License:** On first launch, an activation screen will appear. Enter the generated License Key (which is locked to the specific hardware) to unlock the application.
3. **First Setup:** After activation, a prompt will request a **Literature Root Folder Path**. Enter the directory path where PDFs should be stored (or where they are currently located).
4. **Configure AI (Optional but Recommended):** Navigate to **Settings**. A free local AI (like Ollama) or a cloud provider (Anthropic/OpenAI) can be configured for automatic summaries.

---

## 📖 Usage Guide

### Importing Papers
There are three methods for adding papers:
1. **Single File:** Navigate to the Import tab and drag-and-drop a single PDF.
2. **Bulk Folder Import:** Navigate to the Import tab and enter a folder path to scan a large batch of PDFs simultaneously. Existing folder structures can be preserved, or the AI can be allowed to completely re-organize them.
3. **Background Scanner:** Drop a PDF directly into the Literature Root Folder in Windows Explorer. The background daemon will automatically detect it, classify it, and move it to the correct subfolder during its next scheduled scan.

### Background Mode (Start with Windows)
To run the application silently in the background for continuous readiness:
1. Right-click on the Desktop and select **New -> Shortcut**.
2. Point the shortcut to `LiteratureManager.exe`.
3. Right-click the new shortcut, select **Properties**, and append `--daemon` to the end of the **Target** field.
4. Press `Win + R`, type `shell:startup`, and drag this shortcut into the startup folder. The application will now automatically run silently in the background upon system boot.

---

## ⚙️ Technical Requirements

* **Operating System:** Windows 10/11 (Required for native Hard Link implementation)
* **Browser:** Any modern web browser (Chrome, Edge, Firefox, Safari)
* **Optional Dependencies:** `sentence-transformers` Python package for true local semantic search via PyTorch.
