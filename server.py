import http.server
import json
import os
import sys
import subprocess
from datetime import datetime, timedelta, timezone

# Фікс для Windows консолі
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

PORT = 8000

def check_ai_rate_limit(write_new=False):
    """
    Перевіряє, чи минула 1 година з моменту останнього запиту до ШІ.
    Повертає (allowed: bool, seconds_left: int).
    """
    state_path = "data/ai_limit_state.json"
    default_state = {"last_ai_request_time": "1970-01-01T00:00:00Z"}
    
    state = default_state
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            pass
            
    last_time_str = state.get("last_ai_request_time", "1970-01-01T00:00:00Z")
    try:
        last_time = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
    except Exception:
        last_time = datetime.fromtimestamp(0, tz=timezone.utc)
        
    now = datetime.now(timezone.utc)
    diff = now - last_time
    cooldown = 3600  # 1 година в секундах
    
    if diff.total_seconds() >= cooldown:
        if write_new:
            state["last_ai_request_time"] = now.isoformat().replace("+00:00", "Z")
            try:
                os.makedirs(os.path.dirname(state_path), exist_ok=True)
                with open(state_path, "w", encoding="utf-8") as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
        return True, 0
    else:
        seconds_left = int(cooldown - diff.total_seconds())
        return False, seconds_left

class HybridAdminHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api/ai_status'):
            allowed, seconds_left = check_ai_rate_limit(write_new=False)
            self.send_success_response({
                "allowed": allowed,
                "seconds_left": seconds_left
            })
        else:
            super().do_GET()

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
                
        elif self.path == '/api/run_ai_judge_single':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                original_settlement = data.get('settlement')
                street_name = data.get('street')
                houses = data.get('houses', [])
                
                if not original_settlement or not street_name:
                    self.send_error_response(400, "Missing settlement or street")
                    return
                
                # Перевірка ліміту часу
                allowed, seconds_left = check_ai_rate_limit(write_new=True)
                if not allowed:
                    self.send_error_response(429, f"Зачекайте ще {seconds_left} секунд перед наступним запитом до ШІ.")
                    return
                
                # Динамічний імпорт для уникнення проблем
                sys.path.append(os.path.abspath(os.path.dirname(__file__)))
                from ai_judge import AIJudge
                judge = AIJudge()
                
                candidates = judge.get_candidates(original_settlement, street_name)
                decision = judge.ask_gemini_judge(original_settlement, street_name, houses, candidates)
                
                self.send_success_response({
                    "status": "ok",
                    "decision": decision
                })
            except Exception as e:
                print(f"[SERVER] run_ai_judge_single error: {str(e)}")
                self.send_error_response(500, f"Помилка ШІ: {str(e)}")
                
        elif self.path == '/api/clean_houses_ai':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                street_name = data.get('street')
                houses = data.get('houses', [])
                
                if not street_name or not houses:
                    self.send_error_response(400, "Missing street or houses list")
                    return
                
                # Перевірка ліміту часу
                allowed, seconds_left = check_ai_rate_limit(write_new=True)
                if not allowed:
                    self.send_error_response(429, f"Зачекайте ще {seconds_left} секунд перед наступним запитом до ШІ.")
                    return
                
                # Виклик Gemini для очищення номерів
                sys.path.append(os.path.abspath(os.path.dirname(__file__)))
                from formatter import ask_ai
                prompt = f"""Ти — експерт-топоніміст Старокостянтинівської громади.
Тобі надано список номерів будинків та об'єктів для вулиці '{street_name}'.
Деякі з цих записів є технічним сміттям (наприклад: 'опора 12', 'КТП-143', 'будка', 'ділянка', 'садиба', 'ДАЧА', 'ліхтар' тощо) або дублікатами.
Очисти цей список: вилучи всі технічні об'єкти та нежитлові будівлі. Залиши тільки реальні житлові номери будинків (наприклад: '1', '12а', '43/2').

СПИСОК ДЛЯ ОЧИЩЕННЯ:
{", ".join(houses)}

Поверни результат строго у форматі JSON (масив рядків) без жодної markdown розмітки. Формат відповіді:
[
  "номер1",
  "номер2",
  ...
]"""
                response_text = ask_ai(prompt)
                if not response_text:
                    raise Exception("Порожня відповідь від ШІ")
                    
                import re
                cleaned_text = re.sub(r"^```(?:json)?\s*", "", response_text, flags=re.MULTILINE)
                cleaned_text = re.sub(r"\s*```$", "", cleaned_text, flags=re.MULTILINE).strip()
                
                cleaned_houses = json.loads(cleaned_text)
                self.send_success_response({
                    "status": "ok",
                    "cleaned_houses": cleaned_houses
                })
            except Exception as e:
                print(f"[SERVER] clean_houses_ai error: {str(e)}")
                self.send_error_response(500, f"Помилка ШІ: {str(e)}")
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
