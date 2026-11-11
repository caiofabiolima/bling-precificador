"""Bling API v3 - autorizacao e chamadas.
Uso:
  python bling.py auth            -> abre o navegador, autoriza e salva tokens.json
  python bling.py get /produtos   -> GET em qualquer rota (renova o token sozinho)
"""
import base64, json, os, sys, time, threading, webbrowser
import urllib.request, urllib.parse, urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

DIR = os.path.dirname(os.path.abspath(__file__))
TOKENS = os.path.join(DIR, "tokens.json")
API = "https://api.bling.com.br/Api/v3"
REDIRECT = "http://localhost:8080/callback"


def env():
    d = {}
    for l in open(os.path.join(DIR, ".env"), encoding="utf-8"):
        if "=" in l and not l.startswith("#"):
            k, v = l.strip().split("=", 1)
            d[k] = v
    return d["BLING_CLIENT_ID"], d["BLING_CLIENT_SECRET"]


def token_request(data):
    cid, sec = env()
    basic = base64.b64encode(f"{cid}:{sec}".encode()).decode()
    req = urllib.request.Request(
        f"{API}/oauth/token",
        data=urllib.parse.urlencode(data).encode(),
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "1.0"},
    )
    try:
        r = json.load(urllib.request.urlopen(req))
    except urllib.error.HTTPError as e:
        sys.exit(f"Erro {e.code}: {e.read().decode()}")
    r["obtido_em"] = int(time.time())
    json.dump(r, open(TOKENS, "w"), indent=2)
    return r


def auth():
    cid, _ = env()
    state = base64.urlsafe_b64encode(os.urandom(12)).decode()
    got = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got["code"] = q.get("code", [None])[0]
            got["state"] = q.get("state", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h2>Autorizado. Pode fechar esta aba.</h2>".encode())

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 8080), H)
    url = f"{API}/oauth/authorize?response_type=code&client_id={cid}&state={state}"
    print("Abrindo o navegador para autorizar...")
    webbrowser.open(url)
    while "code" not in got:
        srv.handle_request()
    if got["state"] != state or not got["code"]:
        sys.exit("State invalido ou sem codigo.")
    token_request({"grant_type": "authorization_code", "code": got["code"],
                   "redirect_uri": REDIRECT})
    print("OK. tokens.json salvo.")


def access_token():
    t = json.load(open(TOKENS))
    if time.time() > t["obtido_em"] + t["expires_in"] - 60:
        t = token_request({"grant_type": "refresh_token",
                           "refresh_token": t["refresh_token"]})
    return t["access_token"]


def get(path, params=None):
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token()}"})
    try:
        return json.load(urllib.request.urlopen(req))
    except urllib.error.HTTPError as e:
        sys.exit(f"Erro {e.code}: {e.read().decode()}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:2] == ["auth"]:
        auth()
    elif sys.argv[1:2] == ["get"]:
        print(json.dumps(get(sys.argv[2]), ensure_ascii=False, indent=2))
    else:
        print(__doc__)
