"""Precificador Bling -> Loja Integrada Varejo.
Roda local (127.0.0.1:8765). Sem custo de tokens.
Preco promocional = base x (1+pct_promo) arredondado p/ cima no final ,90
Preco cheio       = base x (1+pct_promo) x (1+pct_cheio) arredondado p/ cima no final ,90
"""
import sys, os, json, time, threading, datetime, urllib.request, urllib.parse, urllib.error, webbrowser
from decimal import Decimal, ROUND_CEILING
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(APP))
import bling  # noqa: E402

BACKUPS = os.path.join(APP, "backups")
os.makedirs(BACKUPS, exist_ok=True)
CFG_PATH = os.path.join(APP, "config.json")
DEFAULT_CFG = {"loja_id": 206338624, "pct_promo": 30, "pct_cheio": 15, "terminacao": "0.90"}
PORT = 8765

JOB = {"state": "idle", "msg": "", "rows": [], "feitos": 0, "total": 0}
LOCK = threading.Lock()


def cfg():
    c = dict(DEFAULT_CFG)
    if os.path.exists(CFG_PATH):
        c.update(json.load(open(CFG_PATH, encoding="utf-8")))
    return c


def up_term(valor, term="0.90"):
    """menor valor >= valor terminando em ,term"""
    t = Decimal(term)
    v = Decimal(str(valor))
    inteiro = ((v - t).to_integral_value(rounding=ROUND_CEILING)) + t
    return float(inteiro.quantize(Decimal("0.01")))


def calcula(base, c):
    b = Decimal(str(base))
    promo_bruto = b * (1 + Decimal(str(c["pct_promo"])) / 100)
    cheio_bruto = promo_bruto * (1 + Decimal(str(c["pct_cheio"])) / 100)
    return up_term(cheio_bruto, c["terminacao"]), up_term(promo_bruto, c["terminacao"])


def call(method, path, params=None, body=None, tentativas=5):
    url = bling.API + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    for i in range(tentativas):
        req = urllib.request.Request(
            url, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": "Bearer " + bling.access_token(),
                     "Content-Type": "application/json"})
        try:
            r = urllib.request.urlopen(req, timeout=60)
            time.sleep(0.4)  # limite do Bling: 3 req/s
            txt = r.read().decode()
            return json.loads(txt) if txt else {}
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < tentativas - 1:
                time.sleep(2 + i * 2)
                continue
            raise RuntimeError(f"Bling {e.code}: {e.read().decode()[:300]}")


def set_job(**kw):
    with LOCK:
        JOB.update(kw)


# ---------- varredura ----------
def scan(codigos):
    try:
        c = cfg()
        set_job(state="running", msg="Lendo vinculos da loja...", rows=[], feitos=0, total=0)
        vinculos, pag = [], 1
        while True:
            d = call("GET", "/produtos/lojas", {"idLoja": c["loja_id"], "pagina": pag, "limite": 100}).get("data", [])
            vinculos += d
            set_job(msg=f"Lendo vinculos da loja... {len(vinculos)}")
            if len(d) < 100:
                break
            pag += 1
        por_prod = {v["produto"]["id"]: v for v in vinculos}
        ids = list(por_prod)
        set_job(msg="Lendo precos base...", total=len(ids))
        rows = []
        filtros = [x.strip().lower() for x in codigos.replace(",", "\n").split("\n") if x.strip()]
        for i in range(0, len(ids), 100):
            lote = ids[i:i + 100]
            for p in call("GET", "/produtos", {"idsProdutos[]": lote, "limite": 100, "criterio": 5}).get("data", []):
                cod = (p.get("codigo") or "")
                if filtros and not any(cod.lower().startswith(f) for f in filtros):
                    continue
                v = por_prod[p["id"]]
                base = p.get("preco") or 0
                if base <= 0:
                    continue
                cheio, promo = calcula(base, c)
                rows.append({
                    "vinculo": v["id"], "produto": p["id"], "codigo": cod, "nome": p["nome"],
                    "base": base, "atual_cheio": v["preco"], "atual_promo": v["precoPromocional"],
                    "novo_cheio": cheio, "novo_promo": promo,
                    "muda": abs(v["preco"] - cheio) > 0.001 or abs(v["precoPromocional"] - promo) > 0.001,
                    "vinc": v})
            set_job(feitos=min(i + 100, len(ids)), msg=f"Lendo precos base... {min(i + 100, len(ids))}/{len(ids)}")
        rows.sort(key=lambda r: r["codigo"])
        set_job(state="done", msg=f"{len(rows)} produtos lidos, {sum(r['muda'] for r in rows)} precisam mudar.", rows=rows)
    except Exception as e:
        set_job(state="error", msg=str(e))


def apply_rows(vinc_ids):
    try:
        c = cfg()
        with LOCK:
            rows = [r for r in JOB["rows"] if r["vinculo"] in set(vinc_ids)]
        stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        arq = os.path.join(BACKUPS, f"backup_{stamp}.json")
        json.dump([r["vinc"] for r in rows], open(arq, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        set_job(state="running", msg="Gravando...", feitos=0, total=len(rows))
        erros = []
        for i, r in enumerate(rows, 1):
            v = r["vinc"]
            body = {"codigo": v.get("codigo", ""), "preco": r["novo_cheio"], "precoPromocional": r["novo_promo"],
                    "produto": {"id": r["produto"]}, "loja": {"id": c["loja_id"]},
                    "fornecedorLoja": v.get("fornecedorLoja", {"id": 0}), "marcaLoja": v.get("marcaLoja", {"id": 0}),
                    "categoriasProdutos": v.get("categoriasProdutos", [])}
            try:
                call("PUT", f"/produtos/lojas/{v['id']}", body=body)
                r.update(atual_cheio=r["novo_cheio"], atual_promo=r["novo_promo"], muda=False)
            except Exception as e:
                erros.append(f"{r['codigo']}: {e}")
            set_job(feitos=i, msg=f"Gravando... {i}/{len(rows)}")
        ok = len(rows) - len(erros)
        set_job(state="done", msg=f"{ok} gravados, {len(erros)} erros. Backup: {os.path.basename(arq)}. " + " | ".join(erros[:3]))
    except Exception as e:
        set_job(state="error", msg=str(e))


def undo(nome):
    try:
        c = cfg()
        arq = os.path.join(BACKUPS, os.path.basename(nome))
        itens = json.load(open(arq, encoding="utf-8"))
        set_job(state="running", msg="Restaurando...", feitos=0, total=len(itens))
        erros = []
        for i, v in enumerate(itens, 1):
            body = {"codigo": v.get("codigo", ""), "preco": v["preco"], "precoPromocional": v["precoPromocional"],
                    "produto": v["produto"], "loja": {"id": c["loja_id"]},
                    "fornecedorLoja": v.get("fornecedorLoja", {"id": 0}), "marcaLoja": v.get("marcaLoja", {"id": 0}),
                    "categoriasProdutos": v.get("categoriasProdutos", [])}
            try:
                call("PUT", f"/produtos/lojas/{v['id']}", body=body)
            except Exception as e:
                erros.append(str(e))
            set_job(feitos=i)
        set_job(state="done", msg=f"Restaurados {len(itens) - len(erros)} de {len(itens)}. Rode a varredura de novo.", rows=[])
    except Exception as e:
        set_job(state="error", msg=str(e))


def run(fn, *a):
    with LOCK:
        if JOB["state"] == "running":
            return False
    threading.Thread(target=fn, args=a, daemon=True).start()
    return True


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, obj, code=200, ctype="application/json"):
        data = obj.encode() if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if self.path == "/":
            self.send(open(os.path.join(APP, "index.html"), encoding="utf-8").read(), ctype="text/html")
        elif self.path == "/api/config":
            self.send(cfg())
        elif self.path == "/api/job":
            with LOCK:
                self.send({**{k: v for k, v in JOB.items() if k != "rows"},
                           "rows": [{k: v for k, v in r.items() if k != "vinc"} for r in JOB["rows"]]})
        elif self.path == "/api/backups":
            self.send(sorted(os.listdir(BACKUPS), reverse=True))
        else:
            self.send({"erro": "nao encontrado"}, 404)

    def do_POST(self):
        b = self.body()
        if self.path == "/api/config":
            c = cfg()
            c.update({k: b[k] for k in DEFAULT_CFG if k in b})
            json.dump(c, open(CFG_PATH, "w", encoding="utf-8"))
            self.send(c)
        elif self.path == "/api/scan":
            self.send({"ok": run(scan, b.get("codigos", ""))})
        elif self.path == "/api/apply":
            self.send({"ok": run(apply_rows, b.get("ids", []))})
        elif self.path == "/api/undo":
            self.send({"ok": run(undo, b.get("arquivo", ""))})
        else:
            self.send({"erro": "nao encontrado"}, 404)


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"Precificador Bling em http://127.0.0.1:{PORT}  (Ctrl+C para fechar)")
    threading.Timer(1, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}")).start()
    srv.serve_forever()
