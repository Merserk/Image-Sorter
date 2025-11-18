Here is the updated `README.md` with the corrected license and specific VRAM requirements.

***

# 📂 Smart AI Image Sorter

> **Organize your photo collections using the power of Local AI.**  
> Sort images by content, character, or style using natural language prompts. Runs 100% offline on your PC.

**Smart AI Image Sorter** takes the manual labor out of organizing folders. Instead of dragging and dropping thousands of files, simply tell the AI: *"Put photos of mountains here"* and *"Put memes here"*. It analyzes every image using a state-of-the-art Vision Language Model and sorts them accordingly.

![Platform](https://img.shields.io/badge/Platform-Windows-blue) ![Portable](https://img.shields.io/badge/Type-Portable-green) ![License](https://img.shields.io/badge/License-AGPL--3.0-red)

---

## ✨ Key Features

*   **🚀 Fully Portable:** No installation required. No Python, Git, or dependencies needed. Just unzip and run.
*   **🧠 Natural Language Sorting:** Define categories using plain English (e.g., "A screenshot of a tweet," "A photo of a cat").
*   **🔍 Semantic Search:** Find specific images instantly by describing them (e.g., "Red sports car in the rain") without moving files.
*   **🔒 100% Private & Offline:** No images are uploaded to the cloud. Everything runs locally on your machine.
*   **⚡ Hardware Flexible:** Choose from multiple intelligence levels to match your GPU capabilities.

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
The app needs an AI brain to work. Go to the **Download** tab and select a model based on your available Video Memory (VRAM):

| Model | VRAM Required | Description |
| :--- | :--- | :--- |
| **Low (4B)** | **~5.5 GB** | Fast, lightweight. Works on most modern entry-level GPUs. |
| **Medium (8B)** | **~12 GB** | **Recommended.** Great balance of speed and high sorting accuracy. |
| **High (30B)** | **~33 GB** | Maximum intelligence. Requires a high-end GPU (e.g., RTX 3090/4090). |

*Click "Download" inside the app to fetch the required files automatically.*

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
    *   **RAM:** 16GB+ Recommended.
    *   **GPU:** NVIDIA or AMD GPU recommended for reasonable speeds. Runs on CPU if no GPU is found (significantly slower).

---

## 📄 License
This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.  
[View License](https://www.gnu.org/licenses/agpl-3.0.html)
