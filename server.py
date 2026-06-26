import http.server
import json
import os
import sys
import subprocess

# Фікс для Windows консолі
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

PORT = 8000

class HybridAdminHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/save':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                file_path = data.get('filePath')
                content = data.get('content')
                
                if not file_path or content is None:
                    self.send_error_response(400, "Missing filePath or content")
                    return
                
                # Security: prevent directory traversal
                normalized_path = os.path.normpath(file_path)
                if normalized_path.startswith("..") or os.path.isabs(normalized_path):
                    self.send_error_response(403, "Access denied")
                    return
                
                # Create folders if they do not exist
                dir_name = os.path.dirname(normalized_path)
                if dir_name:
                    os.makedirs(dir_name, exist_ok=True)
                
                # Write file directly to local disk
                with open(normalized_path, "w", encoding="utf-8") as f:
                    f.write(content)
                
                print(f"[SERVER] Successfully saved local file: {normalized_path}")
                self.send_success_response({"status": "ok", "message": "Saved successfully"})
                
            except json.JSONDecodeError:
                self.send_error_response(400, "Invalid JSON data")
            except Exception as e:
                self.send_error_response(500, f"Server error: {str(e)}")
                
        elif self.path == '/api/git_push':
            try:
                print("[SERVER] Starting Git Publish process...")
                
                # Stage files
                subprocess.run(["git", "add", "data/"], check=True)
                
                # Commit (ignore error if nothing changed)
                commit_res = subprocess.run(
                    ["git", "commit", "-m", "Оновлення даних з адмінки"],
                    capture_output=True,
                    text=True
                )
                print(f"[SERVER] Git commit output: {commit_res.stdout} {commit_res.stderr}")
                
                # Pull with rebase and auto-resolve conflicts in favor of local changes (-Xtheirs)
                print("[SERVER] Pulling latest changes from GitHub...")
                pull_res = subprocess.run(
                    ["git", "pull", "--rebase", "-Xtheirs"],
                    capture_output=True,
                    text=True
                )
                print(f"[SERVER] Git pull output: {pull_res.stdout} {pull_res.stderr}")
                if pull_res.returncode != 0:
                    subprocess.run(["git", "rebase", "--abort"])
                    raise Exception(f"Git pull failed: {pull_res.stderr}")
                
                # Push
                push_res = subprocess.run(
                    ["git", "push"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                print(f"[SERVER] Git push output: {push_res.stdout} {push_res.stderr}")
                
                self.send_success_response({
                    "status": "ok",
                    "message": "Зміни успішно опубліковано на GitHub!",
                    "details": push_res.stdout
                })
                
            except subprocess.CalledProcessError as err:
                error_msg = f"Git command failed: {err.stderr if hasattr(err, 'stderr') else str(err)}"
                print(f"[SERVER] {error_msg}")
                self.send_error_response(500, error_msg)
            except Exception as e:
                print(f"[SERVER] Git Publish error: {str(e)}")
                self.send_error_response(500, f"Git Publish error: {str(e)}")
        else:
            self.send_error_response(404, "Endpoint not found")

    def send_success_response(self, data_dict):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data_dict, ensure_ascii=False).encode('utf-8'))

    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "error", "message": message}, ensure_ascii=False).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

if __name__ == '__main__':
    # Change working dir to script dir to serve static files correctly
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    server_address = ('', PORT)
    httpd = http.server.HTTPServer(server_address, HybridAdminHandler)
    print(f"[SERVER] Hybrid local API server started on http://localhost:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[SERVER] Server stopped.")
        sys.exit(0)
