Here is the updated `README.md` reflecting the **portable, no-install** nature of your release.

***

# 📂 Smart AI Image Sorter

> **Organize your photo collections using the power of Local AI.**  
> Sort images by content, character, or style using natural language prompts. Runs 100% offline on your PC.

**Smart AI Image Sorter** takes the manual labor out of organizing folders. Instead of dragging and dropping thousands of files, simply tell the AI: *"Put photos of mountains here"* and *"Put memes here"*. It analyzes every image using a state-of-the-art Vision Language Model and sorts them accordingly.

![Platform](https://img.shields.io/badge/Platform-Windows-blue) ![Portable](https://img.shields.io/badge/Type-Portable-green) ![License](https://img.shields.io/badge/License-MIT-orange)

---

## ✨ Key Features

*   **🚀 Fully Portable:** No installation required. No Python, Git, or dependencies needed. Just unzip and run.
*   **🧠 Natural Language Sorting:** Define categories using plain English (e.g., "A screenshot of a tweet," "A photo of a cat").
*   **🔍 Semantic Search:** Find specific images instantly by describing them (e.g., "Red sports car in the rain") without moving files.
*   **🔒 100% Private & Offline:** No images are uploaded to the cloud. Everything runs locally on your machine.
*   **⚡ Hardware Flexible:** Includes a built-in Downloader to fetch models (Low, Medium, High) matching your PC's specs.

---

## 📥 Getting Started

This application is **portable**. You do not need to install Python or mess with command lines.

1.  **Download** the latest release: `Image.Sorter.zip`.
2.  **Extract** the zip file to a folder of your choice.
3.  **Run** the executable (e.g., `Image Sorter.exe` or `run.bat`).
4.   The interface will open automatically in your web browser.

---

## 🚀 How to Use

### 1. First Run: Download a Model
The app needs an AI brain to work.
1.  Go to the **Download** tab in the app.
2.  Select a model size based on your hardware:
    *   **Low (4B):** Fast, works on most modern PCs (~5.5GB VRAM).
    *   **Medium (8B):** Recommended. Good balance of speed and intelligence.
    *   **High (30B):** Maximum intelligence, requires a powerful GPU.
3.  Click **Download**. The app will fetch the necessary files automatically.

### 2. Sorting Images
1.  Go to the **Sorter** tab.
2.  **Source:** Click "Browse" to select the folder containing your unsorted images.
3.  **Rules:**
    *   Set the **Number of Categories** (how many output folders you want).
    *   **Folder Name:** Name the folder (e.g., `Landscapes`).
    *   **Prompt:** Describe what belongs there (e.g., `A photo of nature, mountains, or forests`).
4.  Click **RUN SORTING**.
5.  Watch the log as the AI moves your images to the right folders.

### 3. Searching
1.  Go to the **Searcher** tab.
2.  Select an image folder.
3.  Enter a text query (e.g., *"Girl holding a coffee cup"*).
4.  The AI will show you all matches found in that folder.

---

## ⚙️ Advanced Settings

*   **Manual Models:** If you already have `.gguf` Vision models (like Qwen-VL or LLaVA), you can drop them into the `bin/models` folder and link them in the **Settings** tab.
*   **System Requirements:**
    *   Windows 10/11 (64-bit).
    *   A dedicated GPU (NVIDIA/AMD) is recommended for faster processing, but it will run on CPU (slower).

---

## 📄 License
[MIT](https://choosealicense.com/licenses/mit/)
