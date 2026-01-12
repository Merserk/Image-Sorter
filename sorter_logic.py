# --- START OF FILE sorter_logic.py ---
import os
import sys
import shutil
import base64
import json
import subprocess
import time
import atexit
import threading
import configparser
import requests
import uuid
import re
from PIL import Image
from typing import List, Dict, Optional, Iterator

# -------------------- CONFIG & GLOBALS --------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(SCRIPT_DIR, "temp")

KOBOLDCPP_EXE = os.path.join(SCRIPT_DIR, "bin", "koboldcpp", "koboldcpp-launcher.exe")
MODELS_DIR = os.path.join(SCRIPT_DIR, "bin", "models")
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.ini")

# --- MODEL DEFINITIONS ---
MODEL_VARIANTS = {
    "low": {
        "label": "Low (4B)",
        "desc": "5.5GB VRAM | Less precise, Faster (3.34 GB download)",
        "main": {
            "filename": "Qwen3VL-4B-Instruct-Q4_K_M.gguf",
            "url": "https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/resolve/main/Qwen3VL-4B-Instruct-Q4_K_M.gguf",
            "size_mb": 2600
        },
        "mmproj": {
            "filename": "mmproj-Qwen3VL-4B-Instruct-F16.gguf",
            "url": "https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/resolve/main/mmproj-Qwen3VL-4B-Instruct-F16.gguf",
            "size_mb": 600
        }
    },
    "medium": {
        "label": "Medium (8B)",
        "desc": "12GB VRAM | Great quality, Balanced (9.87 GB download)",
        "main": {
            "filename": "Qwen3VL-8B-Instruct-Q8_0.gguf",
            "url": "https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF/resolve/main/Qwen3VL-8B-Instruct-Q8_0.gguf",
            "size_mb": 8500
        },
        "mmproj": {
            "filename": "mmproj-Qwen3VL-8B-Instruct-F16.gguf",
            "url": "https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF/resolve/main/mmproj-Qwen3VL-8B-Instruct-F16.gguf",
            "size_mb": 1500
        }
    },
    "high": {
        "label": "High (30B)",
        "desc": "33GB VRAM | Best quality, Slowest (33.58 GB download)",
        "main": {
            "filename": "Qwen3VL-30B-A3B-Instruct-Q8_0.gguf",
            "url": "https://huggingface.co/Qwen/Qwen3-VL-30B-A3B-Instruct-GGUF/resolve/main/Qwen3VL-30B-A3B-Instruct-Q8_0.gguf",
            "size_mb": 32000
        },
        "mmproj": {
            "filename": "mmproj-Qwen3VL-30B-A3B-Instruct-F16.gguf",
            "url": "https://huggingface.co/Qwen/Qwen3-VL-30B-A3B-Instruct-GGUF/resolve/main/mmproj-Qwen3VL-30B-A3B-Instruct-F16.gguf",
            "size_mb": 2500
        }
    }
}

# Default Defaults
DEFAULT_MODEL_FILE = MODEL_VARIANTS["low"]["main"]["filename"]
DEFAULT_MMPROJ_FILE = MODEL_VARIANTS["low"]["mmproj"]["filename"]

MODEL_PATH = os.path.join(MODELS_DIR, DEFAULT_MODEL_FILE)
MMPROJ_PATH = os.path.join(MODELS_DIR, DEFAULT_MMPROJ_FILE)

# Network
KOBOLD_HOST = "127.0.0.1"
KOBOLD_PORT = 5001
API_BASE_URL = f"http://{KOBOLD_HOST}:{KOBOLD_PORT}"
LOW_VRAM = False

# State
kobold_process: Optional[subprocess.Popen] = None
kobold_job_handle = None
OPENAI_MODEL_NAME: Optional[str] = None
CURRENT_MODEL_PATH: Optional[str] = None
CURRENT_MMPROJ_PATH: Optional[str] = None
stop_event = threading.Event()

ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", 
    ".tif", ".tiff", ".ico", ".avif", ".jxl", ".tga"
}

# -------------------- WINDOWS JOB OBJECT HELPERS --------------------
if os.name == 'nt':
    import ctypes
    from ctypes import wintypes

    JobObjectExtendedLimitInformation = 9
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [('ReadOperationCount', ctypes.c_ulonglong), ('WriteOperationCount', ctypes.c_ulonglong), ('OtherOperationCount', ctypes.c_ulonglong), ('ReadTransferCount', ctypes.c_ulonglong), ('WriteTransferCount', ctypes.c_ulonglong), ('OtherTransferCount', ctypes.c_ulonglong)]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [('PerProcessUserTimeLimit', wintypes.LARGE_INTEGER), ('PerJobUserTimeLimit', wintypes.LARGE_INTEGER), ('LimitFlags', wintypes.DWORD), ('MinimumWorkingSetSize', ctypes.c_size_t), ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', wintypes.DWORD), ('Affinity', ctypes.c_size_t), ('PriorityClass', wintypes.DWORD), ('SchedulingClass', wintypes.DWORD)]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [('BasicLimitInformation', JOBOBJECT_BASIC_LIMIT_INFORMATION), ('IoInfo', IO_COUNTERS), ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t), ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]

    def create_kill_on_close_job():
        try:
            hJob = ctypes.windll.kernel32.CreateJobObjectW(None, None)
            if not hJob: return None
            info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            res = ctypes.windll.kernel32.SetInformationJobObject(hJob, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION))
            if not res:
                ctypes.windll.kernel32.CloseHandle(hJob)
                return None
            return hJob
        except: return None

    def assign_process_to_job(hJob, pid):
        if not hJob: return False
        try:
            PROCESS_SET_QUOTA = 0x0100; PROCESS_TERMINATE = 0x0001
            hProcess = ctypes.windll.kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)
            if hProcess:
                res = ctypes.windll.kernel32.AssignProcessToJobObject(hJob, hProcess)
                ctypes.windll.kernel32.CloseHandle(hProcess)
                return bool(res)
        except: pass
        return False

# -------------------- CONFIG & TEMP MANAGEMENT --------------------

def ensure_dirs():
    if not os.path.exists(TEMP_DIR): os.makedirs(TEMP_DIR)
    if not os.path.exists(MODELS_DIR): os.makedirs(MODELS_DIR)

def cleanup_temp_folder():
    if os.path.exists(TEMP_DIR):
        for filename in os.listdir(TEMP_DIR):
            file_path = os.path.join(TEMP_DIR, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path): os.unlink(file_path)
                elif os.path.isdir(file_path): shutil.rmtree(file_path)
            except: pass

def load_config():
    global MODEL_PATH, MMPROJ_PATH
    ensure_dirs()
    if not os.path.exists(CONFIG_PATH): return
    cfg = configparser.ConfigParser()
    try:
        cfg.read(CONFIG_PATH, encoding="utf-8")
        if cfg.has_section("models"):
            mp = cfg.get("models", "model_gguf", fallback=MODEL_PATH)
            mmp = cfg.get("models", "mmproj_gguf", fallback=MMPROJ_PATH)
            if not os.path.isabs(mp): mp = os.path.abspath(os.path.join(SCRIPT_DIR, mp))
            if not os.path.isabs(mmp): mmp = os.path.abspath(os.path.join(SCRIPT_DIR, mmp))
            MODEL_PATH = mp
            MMPROJ_PATH = mmp
    except: pass

def save_config(model_path: str, mmproj_path: str):
    global MODEL_PATH, MMPROJ_PATH
    mp = os.path.abspath(model_path.strip().strip('"'))
    mmp = os.path.abspath(mmproj_path.strip().strip('"'))
    cfg = configparser.ConfigParser()
    cfg.add_section("models")
    cfg.set("models", "model_gguf", mp)
    cfg.set("models", "mmproj_gguf", mmp)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f: cfg.write(f)
    MODEL_PATH = mp
    MMPROJ_PATH = mmp
    stop_koboldcpp()
    return mp, mmp

def check_model_variant_status(key: str) -> bool:
    if key not in MODEL_VARIANTS: return False
    data = MODEL_VARIANTS[key]
    return os.path.exists(os.path.join(MODELS_DIR, data["main"]["filename"])) and \
           os.path.exists(os.path.join(MODELS_DIR, data["mmproj"]["filename"]))

def delete_model_variant(key: str) -> str:
    if key not in MODEL_VARIANTS: return "Invalid Key"
    data = MODEL_VARIANTS[key]
    log = []
    for sub in ["main", "mmproj"]:
        p = os.path.join(MODELS_DIR, data[sub]["filename"])
        if os.path.exists(p):
            try: os.remove(p); log.append(f"Deleted {data[sub]['filename']}")
            except Exception as e: log.append(f"Error {e}")
    return ", ".join(log) if log else "Files not found."

def get_startup_message() -> str:
    if os.path.isfile(MODEL_PATH) and os.path.isfile(MMPROJ_PATH):
        return f"Ready to sort.\nUsing: {os.path.basename(MODEL_PATH)}"
    return "⚠️ NO ACTIVE MODEL FOUND ⚠️\nPlease download a model in the Download tab."

ensure_dirs()
load_config()
atexit.register(cleanup_temp_folder)

# -------------------- PROCESS MANAGEMENT --------------------

def start_koboldcpp_if_needed(timeout: int = 90):
    global kobold_process, kobold_job_handle, OPENAI_MODEL_NAME, CURRENT_MODEL_PATH, CURRENT_MMPROJ_PATH
    mp = os.path.abspath(MODEL_PATH)
    mmp = os.path.abspath(MMPROJ_PATH)
    
    if not os.path.isfile(mp) or not os.path.isfile(mmp):
        raise RuntimeError(f"Active model files missing.\nPlease go to the Download tab.")

    if kobold_process is not None and kobold_process.poll() is None:
        if (CURRENT_MODEL_PATH == mp and CURRENT_MMPROJ_PATH == mmp): return
        else: stop_koboldcpp()

    cmd = [KOBOLDCPP_EXE, "--model", mp, "--mmproj", mmp, "--host", KOBOLD_HOST, "--port", str(KOBOLD_PORT), "--quiet", "--contextsize", "4096"]
    if LOW_VRAM: cmd.extend(["--mmprojcpu", "--flashattention"])
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    
    kobold_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    if os.name == 'nt':
        kobold_job_handle = create_kill_on_close_job()
        if kobold_job_handle: assign_process_to_job(kobold_job_handle, kobold_process.pid)
    
    CURRENT_MODEL_PATH = mp; CURRENT_MMPROJ_PATH = mmp
    start_t = time.time()
    while True:
        if kobold_process.poll() is not None: raise RuntimeError("koboldcpp exited immediately.")
        try:
            r = requests.get(f"{API_BASE_URL}/v1/models", timeout=1)
            if r.status_code == 200:
                OPENAI_MODEL_NAME = r.json().get("data", [{}])[0].get("id", "koboldcpp")
                break
        except: pass
        if time.time() - start_t > timeout:
            stop_koboldcpp(); raise RuntimeError("Timeout waiting for koboldcpp.")
        time.sleep(1)

def stop_koboldcpp():
    global kobold_process, kobold_job_handle
    if kobold_process and kobold_process.poll() is None: kobold_process.kill()
    kobold_process = None
    if kobold_job_handle and os.name == 'nt':
        ctypes.windll.kernel32.CloseHandle(kobold_job_handle)
        kobold_job_handle = None

atexit.register(stop_koboldcpp)

# -------------------- UTILS --------------------

def find_images(folder: str) -> List[str]:
    imgs = []
    if not os.path.isdir(folder): return []
    for root, _, files in os.walk(folder):
        for f in files:
            if os.path.splitext(f)[1].lower() in ALLOWED_EXTENSIONS:
                imgs.append(os.path.abspath(os.path.join(root, f)))
    imgs.sort()
    return imgs

def encode_image(path: str) -> str:
    temp_png_path = os.path.join(TEMP_DIR, f"temp_process_{uuid.uuid4().hex}.png")
    try:
        with Image.open(path) as img:
            img = img.convert('RGB')
            # Resize for speed/memory but keep high enough for detail
            # Qwen models handle up to 1000-1500 well.
            if max(img.size) > 1500:
                img.thumbnail((1500, 1500), Image.Resampling.LANCZOS)
            img.save(temp_png_path, format="PNG")
        with open(temp_png_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png;base64,{b64}"
    except Exception as e:
        print(f"[WARN] Image conversion failed: {e}")
        return ""
    finally:
        if os.path.exists(temp_png_path): 
            try: os.remove(temp_png_path)
            except: pass

def move_file_unique(src: str, dst_dir: str) -> str:
    os.makedirs(dst_dir, exist_ok=True)
    base = os.path.basename(src)
    name, ext = os.path.splitext(base)
    dest = os.path.join(dst_dir, base)
    c = 1
    while os.path.exists(dest):
        dest = os.path.join(dst_dir, f"{name}_{c}{ext}")
        c += 1
    shutil.move(src, dest)
    return dest

def clean_json_response(txt: str) -> str:
    """Attempts to extract JSON from markdown code blocks or messy text."""
    try:
        match = re.search(r"```json\s*(.*?)\s*```", txt, re.DOTALL)
        if match:
            return match.group(1)
        start, end = txt.find("{"), txt.rfind("}")
        if start != -1 and end != -1:
            return txt[start:end+1]
    except: pass
    return txt

# -------------------- AI LOGIC (PRECISION CHAIN OF THOUGHT) --------------------

def make_api_call(messages, max_tokens=512):
    payload = {
        "model": OPENAI_MODEL_NAME,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.2, # Slight creativity allowed for description, but low for logic
        "top_p": 0.95
    }
    resp = requests.post(f"{API_BASE_URL}/v1/chat/completions", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

def analyze_image_chain_of_thought(image_path: str, categories: List[Dict]) -> Optional[Dict]:
    """
    High-Precision Mode:
    1. Encodes Image.
    2. Asks model to DESCRIBE the image first (Grounding), THEN matches against categories.
    3. Returns the matched category object or None.
    """
    start_koboldcpp_if_needed()
    img_url = encode_image(image_path)
    if not img_url: return None

    # Construct the Category List for the Prompt
    cat_list_str = "\n".join([f"- ID '{c['id']}': {c['prompt']}" for c in categories])
    
    # --- CHAIN OF THOUGHT PROMPT ---
    # We combine description + classification in one prompt to handle the image once.
    # This is much more accurate than asking "Is this Jinx?" directly.
    
    system_prompt = (
        "You are a precise visual data sorter. Your job is to analyze an image and match it to a specific category."
    )

    user_content = f"""
    <instructions>
    1. First, describe the main subject of the image in detail. 
       - If it is a character, describe their hair color, clothes, and distinctive features (tattoos, weapons, etc).
    2. Then, compare your description to the list of Target Categories below.
    3. If a prompt is a specific name (e.g. "Jinx", "Goku"), use your knowledge to identify if the character matches that name.
    4. Select the best matching ID. If the image does not fit any category confidently, select 'none'.
    </instructions>

    <target_categories>
    {cat_list_str}
    </target_categories>

    Response Format (JSON Only):
    {{
        "description": "Brief description of what you see...",
        "reasoning": "Why it matches or does not match...",
        "selected_id": "ID_OR_NONE"
    }}
    """

    try:
        # Call the model
        response_txt = make_api_call([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {"type": "text", "text": user_content}, 
                {"type": "image_url", "image_url": {"url": img_url}}
            ]}
        ])
        
        # Parse Result
        cleaned_json = clean_json_response(response_txt)
        data = json.loads(cleaned_json)
        
        selected_id = str(data.get("selected_id", "none")).lower()
        
        # Logic Check
        if selected_id == "none":
            return None
            
        candidate = next((c for c in categories if str(c["id"]) == selected_id), None)
        
        # Optional: Log the reasoning (can be printed to console for debug)
        # print(f"DEBUG: {data.get('description')} | {data.get('reasoning')}")
        
        return candidate

    except Exception as e:
        print(f"[AI Error] {e}")
        return None

# -------------------- WORKFLOWS --------------------

def run_sort_process(folder: str, rules: List[Dict], progress_callback=None) -> Iterator[str]:
    stop_event.clear()
    folder = os.path.abspath(folder.strip('"'))
    images = find_images(folder)
    
    if not images:
        yield "No images found."
        return

    log = [f"Starting High-Precision Sort in: {folder}", f"Found {len(images)} images.", "Initializing AI Engine..."]
    yield "\n".join(log)
    
    stats = {r["folder_name"]: 0 for r in rules}
    skipped = 0
    processed = 0
    
    try:
        start_koboldcpp_if_needed()
        total = len(images)
        
        for i, img_path in enumerate(images):
            if stop_event.is_set():
                log.append("\n[STOPPED BY USER]")
                yield "\n".join(log); break
                
            if not os.path.exists(img_path): continue
            
            fname = os.path.basename(img_path)
            if progress_callback: progress_callback((i, total), desc=f"Analyzing: {fname}")
            
            processed += 1
            
            # CALL NEW PRECISION LOGIC
            match = analyze_image_chain_of_thought(img_path, rules)
            
            if match:
                target = os.path.join(folder, match["folder_name"])
                try:
                    move_file_unique(img_path, target)
                    stats[match["folder_name"]] += 1
                    log.append(f"✓ {fname} -> {match['folder_name']}")
                except Exception as e:
                    log.append(f"✗ Error moving {fname}: {e}"); skipped += 1
            else:
                skipped += 1
                log.append(f"- {fname} (No confident match)")
                
            yield "\n".join(log)
            
    except Exception as e:
        log.append(f"\nCRITICAL ERROR: {e}")
        yield "\n".join(log)
    finally:
        stop_koboldcpp()
        cleanup_temp_folder()
        summary = ["\n--- COMPLETE ---", f"Processed: {processed}/{len(images)}", f"Skipped (No Match): {skipped}"]
        for k, v in stats.items(): summary.append(f"  {k}: {v}")
        log.extend(summary)
        yield "\n".join(log)

def run_search_process(folder: str, query: str, progress_callback=None) -> Iterator[List[str]]:
    stop_event.clear()
    folder = os.path.abspath(folder.strip('"'))
    images = find_images(folder)
    found_images = []
    if not images: return

    try:
        start_koboldcpp_if_needed()
        total = len(images)
        
        # For search, we define a single category.
        search_rule = [{"id": "match", "prompt": query, "folder_name": "search_result"}]
        
        for i, img_path in enumerate(images):
            if stop_event.is_set(): break
            if progress_callback: progress_callback((i, total), desc=f"Searching: {os.path.basename(img_path)}")
            
            match = analyze_image_chain_of_thought(img_path, search_rule)
            
            if match: found_images.append(img_path)
            yield found_images

    except Exception as e: print(f"Search Error: {e}")
    finally:
        stop_koboldcpp()
        cleanup_temp_folder()
        yield found_images

def request_stop():
    stop_event.set()