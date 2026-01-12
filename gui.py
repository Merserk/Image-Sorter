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
        return "<div style='padding: 20px; text-align: center; color: var(--body-text-color-subdued);'>No matches found yet...</div>"
    
    html = "<div style='display: flex; flex-direction: column; gap: 10px;'>"
    for path in reversed(image_paths):
        try:
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
            src = f"data:image/jpeg;base64,{b64}"
            
            html += f"""
            <div style="display: flex; align-items: center; padding: 12px; border: 1px solid var(--border-color-primary); border-radius: 8px; background: var(--background-fill-secondary);">
                <img src="{src}" style="width: 80px; height: 80px; object-fit: cover; border-radius: 6px; margin-right: 15px; flex-shrink: 0;" />
                <span style="font-family: monospace; word-break: break-all; font-size: 0.85rem; color: var(--body-text-color);">{path}</span>
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
    
    cmd = [sys.executable, downloader_script, models_dir, key]
    
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
                    if str(m_data).startswith("SUCCESS|"):
                        downloaded_key = m_data.split("|")[1]
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

# Use Soft theme - clean and modern looking for Gradio 6
theme = gr.themes.Soft(
    primary_hue="indigo",
    secondary_hue="slate",
    neutral_hue="slate",
)

with gr.Blocks(title="Image Sorter") as app:
    
    # Header
    gr.Markdown("# 🖼️ Image Sorter")
    gr.Markdown("*Local Vision Model Sorter & Searcher*")
    
    with gr.Tabs():
        
        # ================= TAB 1: SORTER =================
        with gr.TabItem("🗂️ Sorter"):
            with gr.Row(equal_height=False):
                # LEFT: Config
                with gr.Column(scale=1, min_width=350):
                    with gr.Group():
                        gr.Markdown("### 📁 1. Source Folder")
                        folder_path = gr.Textbox(
                            label="Image Folder", 
                            placeholder="C:\\Images\\Unsorted",
                            show_label=False
                        )
                        with gr.Row():
                            btn_browse = gr.Button("📂 Browse", size="sm", variant="secondary")
                            btn_scan = gr.Button("🔄 Scan", size="sm", variant="secondary")
                        file_count_md = gr.Markdown("No folder selected.")
                    
                    with gr.Group():
                        gr.Markdown("### 📋 2. Sorting Rules")
                        
                        # State to track number of visible categories
                        n_folders = gr.State(value=3)
                        
                        with gr.Row():
                            btn_remove_cat = gr.Button("➖ Remove", size="sm", variant="secondary", scale=1)
                            category_count_display = gr.Markdown("**3** categories", elem_id="cat_count")
                            btn_add_cat = gr.Button("➕ Add", size="sm", variant="secondary", scale=1)
                        
                        rule_names = []
                        rule_prompts = []
                        for i in range(MAX_CATS):
                            with gr.Row(visible=(i < 3)) as r:
                                r_n = gr.Textbox(
                                    value=f"folder_{i+1}", 
                                    show_label=False, 
                                    placeholder="Folder Name", 
                                    scale=1, 
                                    min_width=100
                                )
                                r_p = gr.Textbox(
                                    show_label=False, 
                                    placeholder=f"Prompt (e.g. 'Cat', 'Dog', 'Landscape')", 
                                    scale=2
                                )
                                rule_names.append((r, r_n))
                                rule_prompts.append(r_p)
                        
                        def add_category(n):
                            new_n = min(n + 1, MAX_CATS)
                            visibility = [gr.update(visible=(i < new_n)) for i in range(MAX_CATS)]
                            return new_n, f"**{new_n}** categories", *visibility
                        
                        def remove_category(n):
                            new_n = max(n - 1, 1)
                            visibility = [gr.update(visible=(i < new_n)) for i in range(MAX_CATS)]
                            return new_n, f"**{new_n}** categories", *visibility
                        
                        cat_outputs = [n_folders, category_count_display] + [x[0] for x in rule_names]
                        btn_add_cat.click(add_category, inputs=n_folders, outputs=cat_outputs)
                        btn_remove_cat.click(remove_category, inputs=n_folders, outputs=cat_outputs)

                # RIGHT: Action & Preview
                with gr.Column(scale=2):
                    with gr.Group():
                        gr.Markdown("### 🖼️ 3. Image Preview")
                        gallery = gr.Gallery(
                            height=280, 
                            columns=6, 
                            rows=2,
                            object_fit="cover", 
                            show_label=False,
                            preview=True
                        )
                    
                    with gr.Group():
                        gr.Markdown("### ▶️ 4. Execution")
                        with gr.Row():
                            btn_run = gr.Button("▶ RUN SORTING", variant="primary", interactive=False, scale=2)
                            btn_stop = gr.Button("⏹ STOP", variant="stop", scale=1)
                        
                        log_output = gr.Textbox(
                            label="Process Log", 
                            lines=12, 
                            max_lines=12,
                            value=logic.get_startup_message()
                        )

        # ================= TAB 2: SEARCHER =================
        with gr.TabItem("🔍 Searcher"):
            with gr.Row(equal_height=False):
                with gr.Column(scale=1, min_width=350):
                    with gr.Group():
                        gr.Markdown("### 📁 Search Folder")
                        search_folder = gr.Textbox(
                            label="Image Folder", 
                            placeholder="C:\\Images\\MyCollection",
                            show_label=False
                        )
                        btn_browse_search = gr.Button("📂 Browse", variant="secondary")
                    
                    with gr.Group():
                        gr.Markdown("### 🔎 Search Query")
                        search_query = gr.Textbox(
                            label="Search Prompt", 
                            placeholder="e.g. 'A photo of a red car'", 
                            lines=3,
                            show_label=False
                        )
                        
                        with gr.Row():
                            btn_start_search = gr.Button("🔍 Start Search", variant="primary", scale=2)
                            btn_stop_search = gr.Button("⏹ Stop", variant="stop", scale=1)

                with gr.Column(scale=2):
                    with gr.Group():
                        gr.Markdown("### 📋 Results")
                        search_results_html = gr.HTML(
                            value="<div style='padding: 20px; text-align: center; color: var(--body-text-color-subdued);'>Search results will appear here...</div>"
                        )

        # ================= TAB 3: DOWNLOAD =================
        with gr.TabItem("⬇️ Download"):
            gr.Markdown("### 📦 Download Models")
            gr.Markdown("Select a quality level. Downloads are saved to `bin/models`.")
            
            # --- LOW ---
            with gr.Group():
                with gr.Row(equal_height=True):
                    with gr.Column(scale=3):
                        gr.Markdown(f"**{logic.MODEL_VARIANTS['low']['label']}**")
                        gr.Markdown(f"{logic.MODEL_VARIANTS['low']['desc']}")
                    stat_low = gr.Textbox(
                        value=get_model_status_label("low"), 
                        show_label=False, 
                        interactive=False,
                        scale=1
                    )
                    btn_dl_low = gr.Button("⬇ Download", size="sm", variant="primary", scale=1)
                    btn_del_low = gr.Button("🗑 Delete", size="sm", variant="secondary", scale=1)

            # --- MEDIUM ---
            with gr.Group():
                with gr.Row(equal_height=True):
                    with gr.Column(scale=3):
                        gr.Markdown(f"**{logic.MODEL_VARIANTS['medium']['label']}**")
                        gr.Markdown(f"{logic.MODEL_VARIANTS['medium']['desc']}")
                    stat_med = gr.Textbox(
                        value=get_model_status_label("medium"), 
                        show_label=False, 
                        interactive=False,
                        scale=1
                    )
                    btn_dl_med = gr.Button("⬇ Download", size="sm", variant="primary", scale=1)
                    btn_del_med = gr.Button("🗑 Delete", size="sm", variant="secondary", scale=1)

            # --- HIGH ---
            with gr.Group():
                with gr.Row(equal_height=True):
                    with gr.Column(scale=3):
                        gr.Markdown(f"**{logic.MODEL_VARIANTS['high']['label']}**")
                        gr.Markdown(f"{logic.MODEL_VARIANTS['high']['desc']}")
                    stat_high = gr.Textbox(
                        value=get_model_status_label("high"), 
                        show_label=False, 
                        interactive=False,
                        scale=1
                    )
                    btn_dl_high = gr.Button("⬇ Download", size="sm", variant="primary", scale=1)
                    btn_del_high = gr.Button("🗑 Delete", size="sm", variant="secondary", scale=1)
            
            dl_log_output = gr.Textbox(
                label="Download Log", 
                lines=8,
                max_lines=8,
                autoscroll=True
            )

            # --- MANUAL SECTION ---
            with gr.Accordion("📖 Manual Model Download", open=False):
                gr.Markdown("""
**Instructions:**
1. Open the link below and find the `.gguf` model you need.
2. Download both the **main gguf model** and the **mmproj gguf model**.
3. Place them in `\\bin\\models` inside the main folder.
4. Open **Settings** tab, select the model paths, and click **Save & Reload Config**.

[🔗 Browse compatible models on HuggingFace](https://huggingface.co/models?pipeline_tag=image-text-to-text&library=gguf&apps=llama.cpp&sort=trending)
""")

        # ================= TAB 4: SETTINGS =================
        with gr.TabItem("⚙️ Settings"):
            gr.Markdown("### ⚙️ Model Configuration")
            gr.Markdown("Point to your local `.gguf` files. Changes require a restart.")
            
            with gr.Group():
                with gr.Row():
                    with gr.Column():
                        m_path = gr.Textbox(label="Vision Model (.gguf)", value=logic.MODEL_PATH)
                        btn_sel_m = gr.Button("📂 Browse Model", variant="secondary")
                    with gr.Column():
                        mm_path = gr.Textbox(label="MMProj Adapter (.gguf)", value=logic.MMPROJ_PATH)
                        btn_sel_mm = gr.Button("📂 Browse MMProj", variant="secondary")
                
                btn_save = gr.Button("💾 Save & Restart", variant="primary")
                cfg_status = gr.Markdown("")

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
    
    def refresh_startup_message():
        # Reload config to pick up new model paths
        logic.load_config()
        return logic.get_startup_message()
    
    btn_dl_low.click(partial(wrapper_run_download, "low"), None, dl_log_output).then(refresh_all_statuses, None, status_outputs).then(refresh_startup_message, None, log_output)
    btn_del_low.click(partial(delete_model_ui, "low"), None, [dl_log_output] + status_outputs).then(refresh_startup_message, None, log_output)
    
    btn_dl_med.click(partial(wrapper_run_download, "medium"), None, dl_log_output).then(refresh_all_statuses, None, status_outputs).then(refresh_startup_message, None, log_output)
    btn_del_med.click(partial(delete_model_ui, "medium"), None, [dl_log_output] + status_outputs).then(refresh_startup_message, None, log_output)

    btn_dl_high.click(partial(wrapper_run_download, "high"), None, dl_log_output).then(refresh_all_statuses, None, status_outputs).then(refresh_startup_message, None, log_output)
    btn_del_high.click(partial(delete_model_ui, "high"), None, [dl_log_output] + status_outputs).then(refresh_startup_message, None, log_output)

    # Settings Wiring
    btn_sel_m.click(open_file_dialog, m_path, m_path)
    btn_sel_mm.click(open_file_dialog, mm_path, mm_path)
    def save_and_restart(m, mm):
        # Save config
        logic.save_config(m, mm)
        # Restart using subprocess (handles paths with spaces properly on Windows)
        script_path = os.path.abspath(__file__)
        subprocess.Popen([sys.executable, script_path], cwd=current_dir)
        # Exit current process
        os._exit(0)
    btn_save.click(save_and_restart, [m_path, mm_path], None)

if __name__ == "__main__":
    roots = [f"{d}:\\" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:")]
    app.launch(inbrowser=True, allowed_paths=roots, theme=theme)