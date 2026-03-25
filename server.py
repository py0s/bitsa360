#!/usr/bin/env python3
import http.server
import json
import os

PORT = 8080
DIR = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    def do_POST(self):
        if self.path == '/save':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                with open(os.path.join(DIR, 'entry_points.json'), 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())
        elif self.path == '/save_points':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                ptype = data.get('type', 'unknown')
                filename = f"{ptype}.json"
                filepath = os.path.join(DIR, filename)
                # Merge with existing if file exists
                existing = []
                if os.path.exists(filepath):
                    with open(filepath) as f:
                        existing = json.load(f).get('points', [])
                existing.extend(data.get('points', []))
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump({"type": ptype, "label": data.get('label',''), "emoji": data.get('emoji',''), "points": existing}, f, ensure_ascii=False, indent=2)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "total": len(existing)}).encode())
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    print(f'Serving on http://localhost:{PORT}')
    http.server.HTTPServer(('', PORT), Handler).serve_forever()
