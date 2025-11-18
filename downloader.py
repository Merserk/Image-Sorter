# --- START OF FILE downloader.py ---
import os
import sys

# FIX: Explicitly add the script's directory to sys.path 
# This ensures 'sorter_logic' can be imported when running as a subprocess
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import time
import urllib.request
import json
import sorter_logic  # Import the shared logic file

def send_message(type_, data):
    """Send JSON formatted message to stdout for the GUI to parse."""
    print(json.dumps({"type": type_, "data": data}), flush=True)

def download_file(filename, url, estimated_size_mb, output_dir):
    dest_path = os.path.join(output_dir, filename)
    
    send_message("log", f"Starting download: {filename}...")
    
    try:
        # Check for existing file size for resume support
        downloaded = 0
        if os.path.exists(dest_path):
            downloaded = os.path.getsize(dest_path)
        
        headers = {'User-Agent': 'Python Downloader'}
        if downloaded > 0:
            headers['Range'] = f'bytes={downloaded}-'
            
        req = urllib.request.Request(url, headers=headers)
        
        try:
            response = urllib.request.urlopen(req, timeout=30)
        except urllib.error.HTTPError as e:
            if e.code == 416: 
                # Range Not Satisfiable - likely finished
                send_message("log", f"{filename} appears complete. Skipping.")
                return True
            raise e

        total_size = downloaded
        is_resuming = False
        
        if response.status == 206:
            content_length = int(response.getheader('Content-Length', 0))
            total_size = downloaded + content_length
            is_resuming = True
            send_message("log", f"Resuming {filename} from {downloaded/(1024*1024):.1f}MB...")
        elif response.status == 200:
            total_size = int(response.getheader('Content-Length', 0))
            if downloaded > 0:
                # Server didn't accept range, restart
                downloaded = 0 
                send_message("log", f"Server does not support resume. Restarting {filename}...")
                with open(dest_path, 'wb') as f: pass # clear file
        else:
            # Fallback if no content-length
            total_size = estimated_size_mb * 1024 * 1024

        mode = 'ab' if is_resuming else 'wb'
        
        with open(dest_path, mode) as f:
            start_time = time.time()
            bytes_in_session = 0
            last_report_time = 0
            
            while True:
                chunk = response.read(65536) # 64kb chunks
                if not chunk:
                    break
                f.write(chunk)
                
                chunk_len = len(chunk)
                downloaded += chunk_len
                bytes_in_session += chunk_len
                
                now = time.time()
                if now - last_report_time >= 0.2: # Update every 200ms
                    last_report_time = now
                    
                    elapsed = now - start_time
                    speed = (bytes_in_session / (1024*1024)) / elapsed if elapsed > 0 else 0
                    percent = (downloaded / total_size) * 100 if total_size > 0 else 0
                    
                    send_message("progress", {
                        "filename": filename,
                        "percent": percent,
                        "speed": f"{speed:.1f} MB/s",
                        "downloaded": f"{downloaded/(1024*1024):.1f} MB",
                        "total": f"{total_size/(1024*1024):.1f} MB"
                    })

        send_message("log", f"Successfully downloaded {filename}")
        return True

    except Exception as e:
        send_message("error", f"Failed to download {filename}: {str(e)}")
        return False

def main():
    if len(sys.argv) < 3:
        send_message("error", "Usage: downloader.py <output_dir> <variant_key>")
        return

    output_dir = sys.argv[1]
    variant_key = sys.argv[2]

    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
        except Exception as e:
            send_message("error", f"Could not create folder {output_dir}: {e}")
            return

    if variant_key not in sorter_logic.MODEL_VARIANTS:
        send_message("error", f"Unknown variant: {variant_key}")
        return

    data = sorter_logic.MODEL_VARIANTS[variant_key]
    send_message("log", f"Download started: {data['label']}\nSaving to: {output_dir}")

    # Download Main Model
    ok_main = download_file(
        data["main"]["filename"], 
        data["main"]["url"], 
        data["main"]["size_mb"], 
        output_dir
    )

    if not ok_main:
        send_message("done", "Download Aborted due to error.")
        return

    # Download MMProj
    ok_mm = download_file(
        data["mmproj"]["filename"], 
        data["mmproj"]["url"], 
        data["mmproj"]["size_mb"], 
        output_dir
    )

    if ok_main and ok_mm:
        send_message("done", f"SUCCESS|{variant_key}")
    else:
        send_message("done", "Downloads finished with errors.")

if __name__ == "__main__":
    main()