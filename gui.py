# --- START OF FILE gui.py ---
import sys
import os
import base64
import json
import threading
import subprocess
from functools import partial

# FIX: Add the current script's directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 1. SETUP TEMP DIRECTORY BEFORE IMPORTING GRADIO
temp_path = os.path.join(current_dir, "temp")
if not os.path.exists(temp_path):
    os.makedirs(temp_path)
os.environ["GRADIO_TEMP_DIR"] = temp_path

import gradio as gr
import sorter_logic as logic

# -------------------- STYLES --------------------

css = """
.gradio-container { min-height: 100vh; font-family: 'Segoe UI', sans-serif; }

/* HEADER STYLES */
.header-container {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); 
    padding: 2rem; 
    border-radius: 12px; 
    text-align: center; 
    margin-bottom: 1.5rem; 
    border: 1px solid #334155; 
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
}
.header-title {
    color: white; 
    font-size: 3.5rem; 
    font-weight: 800; 
    margin: 0; 
    line-height: 1.2;
    letter-spacing: -0.025em;
}
.header-subtitle {
    color: #94a3b8; 
    font-size: 1.2rem; 
    margin-top: 0.5rem;
    font-weight: 500;
}

/* BOX STYLES */
.folder-box { padding: 15px; border: 1px solid #e2e8f0; border-radius: 8px; background: #f8fafc; }
.dark .folder-box { border-color: #374151; background: #1f2937; }

.log-box { background: #1e293b; color: #bef264; font-family: monospace; padding: 10px; border-radius: 8px; height: 400px; overflow-y: auto; border: 1px solid #334155; }
.dl-log-box { background: #1e293b; color: #60a5fa; font-family: monospace; padding: 10px; border-radius: 8px; height: 300px; overflow-y: auto; border: 1px solid #334155; }

/* DL CARD STYLE */
.dl-card {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 15px;
    margin-bottom: 10px;
    background: white;
}
.dl-title { font-weight: bold; font-size: 1.1em; margin-bottom: 4px; }
.dl-desc { color: #64748b; font-size: 0.9em; margin-bottom: 8px; }
.dl-status-ok { color: #10b981; font-weight: bold; }
.dl-status-miss { color: #ef4444; font-weight: bold; }

/* Search Result Styles */
.search-result-item {
    display: flex;
    align-items: center;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.search-thumb {
    width: 80px;
    height: 80px;
    object-fit: cover;
    border-radius: 6px;
    margin-right: 15px;
    border: 1px solid #cbd5e1;
    flex-shrink: 0;
}
.search-path { font-family: monospace; color: #334155; word-break: break-all; font-size: 0.9rem; }

/* Buttons */
#run_btn { background: linear-gradient(90deg, #10b981 0%, #059669 100%); color: white; border: none; }
#stop_btn { background: linear-gradient(90deg, #ef4444 0%, #b91c1c 100%); color: white; border: none; }
.dl-btn { background: linear-gradient(90deg, #3b82f6 0%, #2563eb 100%); color: white; border: none; }
.del-btn { background-color: #fecaca; color: #b91c1c; border: 1px solid #fca5a5; }
"""

# -------------------- UI HELPERS --------------------

def open_folder_dialog(current):
    if os.name != "nt": return current
    ps = r"""
    Add-Type -AssemblyName System.Windows.Forms
    $d = New-Object System.Windows.Forms.OpenFileDialog
    $d.ValidateNames = $false
    $d.CheckFileExists = $false
    $d.CheckPathExists = $true
    $d.FileName = "Folder Selection"
    $d.Title = "Select Folder (Navigate inside and click Open)"
    $d.Filter = "Folder|*. "
    if ($d.ShowDialog() -eq 'OK') {
        Write-Host ([System.IO.Path]::GetDirectoryName($d.FileName))
    }
    """
    try:
        res = subprocess.run(["powershell", "-c", ps], capture_output=True, text=True)
        path = res.stdout.strip()
        return path if path else current
    except: return current

def open_file_dialog(current):
    if os.name != "nt": return current
    ps = r'''Add-Type -A System.Windows.Forms;$d=New-Object System.Windows.Forms.OpenFileDialog;$d.Filter="GGUF|*.gguf";if($d.ShowDialog()-eq'OK'){$d.FileName}'''
    try:
        res = subprocess.run(["powershell", "-c", ps], capture_output=True, text=True)
        path = res.stdout.strip()
        return path if path else current
    except: return current

def scan_folder_ui(path):
    path = (path or "").strip('"')
    if not path or not os.path.isdir(path):
        return "Invalid folder.", [], gr.update(interactive=False)
    
    imgs = logic.find_images(path)
    count = len(imgs)
    gallery = imgs[:24] 
    
    stats = f"**{count}** images found."
    return stats, gallery, gr.update(interactive=(count > 0))

def wrapper_run_sort(folder, *args, progress=gr.Progress()):
    n_folders = args[0]
    rule_inputs = args[1:]
    
    rules = []
    for i in range(n_folders):
        name = rule_inputs[i]
        prompt = rule_inputs[i + 100]
        
        if prompt.strip():
            rules.append({
                "id": str(i+1),
                "folder_name": name.strip() or f"Folder_{i+1}",
                "prompt": prompt.strip()
            })
            
    if not rules:
        yield "Error: No rules defined."
        return

    generator = logic.run_sort_process(folder, rules, progress_callback=progress)
    for log_update in generator:
        yield log_update

def format_search_results(image_paths):
    if not image_paths:
        return "<div>No matches found yet...</div>"
    
    html = "<div>"
    for path in reversed(image_paths):
        try:
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
            src = f"data:image/jpeg;base64,{b64}"
            
            html += f"""
            <div class="search-result-item">
                <img src="{src}" class="search-thumb" />
                <span class="search-path">{path}</span>
            </div>
            """
        except Exception:
            continue
    html += "</div>"
    return html

def wrapper_run_search(folder, query, progress=gr.Progress()):
    if not folder or not os.path.isdir(folder):
        yield "Invalid folder"
        return
    if not query.strip():
        yield "Please enter a search prompt."
        return
        
    generator = logic.run_search_process(folder, query, progress_callback=progress)
    for results_list in generator:
        yield format_search_results(results_list)

# --- DOWNLOADER HELPERS ---

def get_model_status_label(key):
    if logic.check_model_variant_status(key):
        return "✅ Downloaded"
    return "❌ Not Downloaded"

def refresh_all_statuses():
    return (
        get_model_status_label("low"),
        get_model_status_label("medium"),
        get_model_status_label("high")
    )

def delete_model_ui(key):
    msg = logic.delete_model_variant(key)
    return f"Deleted: {msg}", *refresh_all_statuses()

def wrapper_run_download(key):
    downloader_script = os.path.join(current_dir, "downloader.py")
    models_dir = logic.MODELS_DIR
    
    if not os.path.exists(downloader_script):
        yield "Error: downloader.py not found."
        return

    data = logic.MODEL_VARIANTS[key]
    yield f"Starting download for: {data['label']}...\n"
    
    # Call with args: output_dir variant_key
    cmd = [sys.executable, downloader_script, models_dir, key]
    
    # FIX: Pass cwd=current_dir to ensure the subprocess finds sorter_logic.py
    process = subprocess.Popen(
        cmd, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT, 
        text=True, 
        bufsize=1,
        cwd=current_dir
    )
    
    full_log = ""
    
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line:
            try:
                msg = json.loads(line)
                m_type = msg.get("type")
                m_data = msg.get("data")
                
                if m_type == "log":
                    full_log += f"> {m_data}\n"
                    yield full_log
                elif m_type == "progress":
                    p_line = f"Downloading {m_data['filename']}: {m_data['percent']:.1f}% ({m_data['speed']})"
                    yield full_log + p_line
                elif m_type == "error":
                    full_log += f"[ERROR] {m_data}\n"
                    yield full_log
                elif m_type == "done":
                    # Check if successful
                    if str(m_data).startswith("SUCCESS|"):
                        downloaded_key = m_data.split("|")[1]
                        # Update Config
                        d_info = logic.MODEL_VARIANTS[downloaded_key]
                        logic.save_config(
                            os.path.join(logic.MODELS_DIR, d_info["main"]["filename"]),
                            os.path.join(logic.MODELS_DIR, d_info["mmproj"]["filename"])
                        )
                        full_log += "\n\n✨ Config updated to use this model automatically."
                    else:
                        full_log += f"\n[DONE] {m_data}\n"
                    yield full_log
            except json.JSONDecodeError:
                full_log += line
                yield full_log
                
    if process.returncode == 0:
        yield full_log + "\nProcess finished."
    else:
        yield full_log + f"\nProcess exited with code {process.returncode}"

# -------------------- BUILD APP --------------------

MAX_CATS = 100

with gr.Blocks(css=css, title="Image Sorter") as app:
    
    # Custom Header Banner
    gr.HTML("""
        <div class="header-container">
            <h1 class="header-title">Image Sorter</h1>
            <div class="header-subtitle">Local Vision Model Sorter & Searcher</div>
        </div>
    """)
    
    with gr.Tabs():
        
        # ================= TAB 1: SORTER =================
        with gr.TabItem("Sorter", id="tab_sort"):
            with gr.Row():
                # LEFT: Config
                with gr.Column(scale=1, min_width=300):
                    with gr.Group(elem_classes="folder-box"):
                        gr.Markdown("### 1. Source")
                        folder_path = gr.Textbox(label="Image Folder", placeholder="C:\\Images\\Unsorted")
                        with gr.Row():
                            btn_browse = gr.Button("📂 Browse", size="sm")
                            btn_scan = gr.Button("🔄 Scan", size="sm", variant="secondary")
                        file_count_md = gr.Markdown("No folder selected.")
                    
                    gr.Markdown("### 2. Rules")
                    n_folders = gr.Slider(1, 100, value=3, step=1, label="Number of Categories")
                    
                    rule_names = []
                    rule_prompts = []
                    rules_container = gr.Group()
                    with rules_container:
                        for i in range(MAX_CATS):
                            with gr.Row(visible=(i < 3)) as r:
                                r_n = gr.Textbox(value=f"folder_{i+1}", show_label=False, placeholder="Folder Name", scale=1, min_width=80)
                                r_p = gr.Textbox(show_label=False, placeholder=f"Prompt (e.g. 'Cat')", scale=2)
                                rule_names.append((r, r_n))
                                rule_prompts.append(r_p)
                    
                    def update_rules(n):
                        return [gr.update(visible=(i < n)) for i in range(MAX_CATS)]
                    n_folders.change(update_rules, inputs=n_folders, outputs=[x[0] for x in rule_names])

                # RIGHT: Action
                with gr.Column(scale=2):
                    with gr.Group():
                        gr.Markdown("### 3. Preview")
                        gallery = gr.Gallery(height="auto", columns=6, object_fit="cover", show_label=False)
                    
                    gr.Markdown("### 4. Execution")
                    with gr.Row():
                        btn_run = gr.Button("▶ RUN SORTING", elem_id="run_btn", interactive=False)
                        btn_stop = gr.Button("⏹ STOP", elem_id="stop_btn")
                    
                    log_output = gr.Textbox(
                        label="Process Log", 
                        elem_classes="log-box", 
                        lines=15, 
                        max_lines=15,
                        value=logic.get_startup_message() 
                    )

        # ================= TAB 2: SEARCHER =================
        with gr.TabItem("Searcher", id="tab_search"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### Search Config")
                    with gr.Group(elem_classes="folder-box"):
                        search_folder = gr.Textbox(label="Image Folder", placeholder="C:\\Images\\MyCollection")
                        btn_browse_search = gr.Button("📂 Browse")
                    
                    search_query = gr.Textbox(label="Search Prompt", placeholder="e.g. 'A photo of a red car'", lines=2)
                    
                    with gr.Row():
                        btn_start_search = gr.Button("🔍 Start Search", variant="primary")
                        btn_stop_search = gr.Button("⏹ Stop", variant="stop")

                with gr.Column(scale=2):
                    gr.Markdown("### Results")
                    search_results_html = gr.HTML(label="Found Images")

        # ================= TAB 3: DOWNLOAD =================
        with gr.TabItem("Download", id="tab_download"):
            gr.Markdown("### Download Models")
            gr.Markdown("Select a quality level. Downloads are saved to `bin/models`.")
            
            # --- LOW ---
            with gr.Group(elem_classes="dl-card"):
                with gr.Row(elem_classes="dl-row"):
                    with gr.Column(scale=4):
                        gr.Markdown(f"<div class='dl-title'>{logic.MODEL_VARIANTS['low']['label']}</div><div class='dl-desc'>{logic.MODEL_VARIANTS['low']['desc']}</div>")
                    with gr.Column(scale=2):
                        stat_low = gr.Label(value=get_model_status_label("low"), show_label=False)
                    with gr.Column(scale=1):
                        btn_dl_low = gr.Button("⬇ Download", elem_classes="dl-btn", size="sm")
                    with gr.Column(scale=1):
                        btn_del_low = gr.Button("🗑 Delete", elem_classes="del-btn", size="sm")

            # --- MEDIUM ---
            with gr.Group(elem_classes="dl-card"):
                with gr.Row(elem_classes="dl-row"):
                    with gr.Column(scale=4):
                        gr.Markdown(f"<div class='dl-title'>{logic.MODEL_VARIANTS['medium']['label']}</div><div class='dl-desc'>{logic.MODEL_VARIANTS['medium']['desc']}</div>")
                    with gr.Column(scale=2):
                        stat_med = gr.Label(value=get_model_status_label("medium"), show_label=False)
                    with gr.Column(scale=1):
                        btn_dl_med = gr.Button("⬇ Download", elem_classes="dl-btn", size="sm")
                    with gr.Column(scale=1):
                        btn_del_med = gr.Button("🗑 Delete", elem_classes="del-btn", size="sm")

            # --- HIGH ---
            with gr.Group(elem_classes="dl-card"):
                with gr.Row(elem_classes="dl-row"):
                    with gr.Column(scale=4):
                        gr.Markdown(f"<div class='dl-title'>{logic.MODEL_VARIANTS['high']['label']}</div><div class='dl-desc'>{logic.MODEL_VARIANTS['high']['desc']}</div>")
                    with gr.Column(scale=2):
                        stat_high = gr.Label(value=get_model_status_label("high"), show_label=False)
                    with gr.Column(scale=1):
                        btn_dl_high = gr.Button("⬇ Download", elem_classes="dl-btn", size="sm")
                    with gr.Column(scale=1):
                        btn_del_high = gr.Button("🗑 Delete", elem_classes="del-btn", size="sm")
            
            dl_log_output = gr.Textbox(label="Download Log", elem_classes="dl_log-box", lines=10)

            # --- NEW MANUAL SECTION ---
            with gr.Group(elem_classes="folder-box"):
                gr.Markdown("### Manual search/download models")
                gr.Markdown("""
                **Instructions:**
                1. Open the link below and find the `.gguf` model which you need and download it.
                2. To get it works download the **main gguf model** and the **mmproj gguf model**.
                3. Put them to `\\bin\\models` inside main folder.
                4. After launch program - open **Settings** and select new models path and click - **Save & Reload Config**.

                <br>
                <a href="https://huggingface.co/models?pipeline_tag=image-text-to-text&library=gguf&apps=llama.cpp&sort=trending" target="_blank" style="color: #3b82f6; font-weight: bold; font-size: 1.1em; text-decoration: underline;">
                    🔗 Click to browse compatible models on HuggingFace
                </a>
                """)

        # ================= TAB 4: SETTINGS =================
        with gr.TabItem("Settings", id="tab_settings"):
            gr.Markdown("### Model Configuration")
            gr.Markdown("Point to your local `.gguf` files. Changes require a restart.")
            with gr.Row():
                with gr.Column():
                    m_path = gr.Textbox(label="Vision Model (.gguf)", value=logic.MODEL_PATH)
                    btn_sel_m = gr.Button("Browse Model")
                with gr.Column():
                    mm_path = gr.Textbox(label="MMProj Adapter (.gguf)", value=logic.MMPROJ_PATH)
                    btn_sel_mm = gr.Button("Browse MMProj")
            btn_save = gr.Button("Save & Reload Config", variant="primary")
            cfg_status = gr.HTML("")

    # -------------------- WIRING --------------------
    
    # Sorter Wiring
    btn_browse.click(open_folder_dialog, folder_path, folder_path)
    scan_inputs = [folder_path]
    scan_outputs = [file_count_md, gallery, btn_run]
    folder_path.submit(scan_folder_ui, scan_inputs, scan_outputs)
    btn_scan.click(scan_folder_ui, scan_inputs, scan_outputs)
    folder_path.change(scan_folder_ui, scan_inputs, scan_outputs)

    name_boxes = [x[1] for x in rule_names]
    sort_inputs = [folder_path, n_folders] + name_boxes + rule_prompts
    btn_run.click(wrapper_run_sort, inputs=sort_inputs, outputs=log_output)
    btn_stop.click(fn=logic.request_stop, inputs=None, outputs=None)

    # Search Wiring
    btn_browse_search.click(open_folder_dialog, search_folder, search_folder)
    btn_start_search.click(
        wrapper_run_search, 
        inputs=[search_folder, search_query], 
        outputs=[search_results_html]
    )
    btn_stop_search.click(fn=logic.request_stop, inputs=None, outputs=None)

    # Download Wiring
    status_outputs = [stat_low, stat_med, stat_high]
    
    # Low
    btn_dl_low.click(partial(wrapper_run_download, "low"), None, dl_log_output).then(refresh_all_statuses, None, status_outputs)
    btn_del_low.click(partial(delete_model_ui, "low"), None, [dl_log_output] + status_outputs)
    
    # Medium
    btn_dl_med.click(partial(wrapper_run_download, "medium"), None, dl_log_output).then(refresh_all_statuses, None, status_outputs)
    btn_del_med.click(partial(delete_model_ui, "medium"), None, [dl_log_output] + status_outputs)

    # High
    btn_dl_high.click(partial(wrapper_run_download, "high"), None, dl_log_output).then(refresh_all_statuses, None, status_outputs)
    btn_del_high.click(partial(delete_model_ui, "high"), None, [dl_log_output] + status_outputs)

    # Settings Wiring
    btn_sel_m.click(open_file_dialog, m_path, m_path)
    btn_sel_mm.click(open_file_dialog, mm_path, mm_path)
    def save_cfg_ui(m, mm):
        m, mm = logic.save_config(m, mm)
        return m, mm, "<span style='color:green'>✅ Saved.</span>"
    btn_save.click(save_cfg_ui, [m_path, mm_path], [m_path, mm_path, cfg_status])

if __name__ == "__main__":
    roots = [f"{d}:\\" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:")]
    app.launch(inbrowser=True, allowed_paths=roots)