"""ESG review workspace. Nginx provides auth; localhost worker uses SSH."""
import csv
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("ESG_DATA", ROOT / "data"))
STATE = Path(os.environ.get("ESG_STATE", "/var/lib/sber-esg-review" if ROOT == Path("/opt/sber-esg-review") else DATA))
MARKER = re.compile(rb"<!--\s*pdf_page:\s*(\d+)\s*-->")
REGISTRY = {r["report_id"]: r for r in json.loads((DATA / "registry.json").read_text())}
PILOT = json.loads((DATA / "pilot.json").read_text()) if (DATA / "pilot.json").exists() else {}


def db():
    conn = sqlite3.connect(STATE / "review.sqlite", timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    STATE.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS audits(id TEXT PRIMARY KEY, details TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reviews(
                report_id TEXT NOT NULL, claim_id TEXT NOT NULL, input_json TEXT NOT NULL,
                status TEXT NOT NULL, updated TEXT NOT NULL, details TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(report_id,claim_id));
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, status TEXT NOT NULL,
                updated TEXT NOT NULL, details TEXT NOT NULL DEFAULT '');
        """)


def audit(report_id):
    report = REGISTRY[report_id]
    content = (DATA / report["repository_path"]).read_bytes()
    pages = [int(match[1]) for match in MARKER.finditer(content)]
    digest = sha256(content).hexdigest()
    checks = {"hash": digest == report["packaged_md_sha256"],
              "positions": pages == list(range(1, report["physical_pages"] + 1)),
              "pages": len(pages), "visual_pointers": report["visual_reference_count"]}
    with db() as conn:
        conn.execute("INSERT OR REPLACE INTO audits VALUES(?,?)", (report_id, json.dumps(checks)))
    return checks


def enqueue(ids):
    if not ids or not isinstance(ids, list) or not all(isinstance(x, str) and x in REGISTRY for x in ids):
        raise ValueError("Выберите отчёты из реестра")
    with db() as conn:
        # Repeated clicks are idempotent. Completed and running jobs keep their state.
        conn.executemany("""INSERT INTO jobs(id,status,updated) VALUES(?,'queued',datetime('now'))
            ON CONFLICT(id) DO UPDATE SET status='queued',updated=datetime('now')
            WHERE jobs.status IN ('failed','partial')""", [(rid,) for rid in sorted(set(ids))])


def claim():
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("""SELECT id FROM jobs WHERE status='queued'
            OR (status='running' AND updated < datetime('now','-2 hours'))
            ORDER BY updated,id LIMIT 1""").fetchone()
        if not row:
            return None
        rid = row["id"]
        conn.execute("UPDATE jobs SET status='running',updated=datetime('now') WHERE id=?", (rid,))
        return REGISTRY[rid]


def finish(rid, result):
    status = result.get("status")
    if rid not in REGISTRY or status not in {"partial", "extracted", "failed"}:
        raise ValueError("bad job status")
    if status == "partial" and result.get("continue") is True:
        status = "queued"
    details = json.dumps(result, ensure_ascii=False)
    if len(details) > 20_000_000:
        raise ValueError("result is too large")
    with db() as conn:
        if not conn.execute("UPDATE jobs SET status=?,updated=datetime('now'),details=? WHERE id=? AND status='running'",
                            (status, details, rid)).rowcount:
            raise ValueError("job is not running")
    if status == "extracted" and result.get("queue_research") is True:
        queue_report_reviews(rid)


def rows_for(rid):
    with db() as conn:
        row = conn.execute("SELECT details FROM jobs WHERE id=?", (rid,)).fetchone()
        reviews = {r["claim_id"]: r for r in conn.execute("SELECT * FROM reviews WHERE report_id=?", (rid,))}
    live = json.loads(row["details"] or "{}").get("rows", []) if row else []
    pilot = PILOT.get(rid, [])
    pilots = {" ".join(row["statement"].split()): (index, row) for index, row in enumerate(pilot, 1)}
    output = []
    for index, row in enumerate(live or pilot, 1):
        claim = dict(row)
        cid = claim.setdefault("id", f"{rid}:pilot:{index}")
        prior = pilots.get(" ".join(claim["statement"].split()))
        review = reviews.get(cid)
        if live and prior:
            old_index, old = prior
            if old.get("searched"):
                for key in ("searched", "status", "reason", "links"):
                    claim[key] = old[key]
            if not review:
                review = reviews.get(f"{rid}:pilot:{old_index}")
        if review:
            claim["review_status"] = review["status"]
            claim.update(json.loads(review["details"] or "{}").get("display", {}))
        output.append(claim)
    return output


def queue_review(rid, cid):
    if not isinstance(rid, str) or rid not in REGISTRY or not isinstance(cid, str):
        raise ValueError("Укажите заявление из реестра")
    row = next((r for r in rows_for(rid) if r["id"] == cid), None)
    if row is None:
        raise ValueError("Заявление не найдено")
    with db() as conn:
        conn.execute("""INSERT INTO reviews VALUES(?,?,?,'queued',datetime('now'),'')
            ON CONFLICT(report_id,claim_id) DO UPDATE SET status='queued',updated=datetime('now')
            WHERE reviews.status IN ('failed','partial')""", (rid,cid,json.dumps(row,ensure_ascii=False)))


def queue_report_reviews(rid):
    if not isinstance(rid, str) or rid not in REGISTRY:
        raise ValueError("Укажите отчёт из реестра")
    rows = [row for row in rows_for(rid) if not row.get("searched")]
    with db() as conn:
        conn.executemany("""INSERT INTO reviews VALUES(?,?,?,'queued',datetime('now'),'')
            ON CONFLICT(report_id,claim_id) DO UPDATE SET status='queued',updated=datetime('now')
            WHERE reviews.status IN ('failed','partial')""",
                         [(rid,row["id"],json.dumps(row,ensure_ascii=False)) for row in rows])
    return len(rows)


def claim_review():
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("""SELECT * FROM reviews WHERE status='queued'
            OR (status='running' AND updated < datetime('now','-2 hours'))
            ORDER BY updated,report_id,claim_id LIMIT 1""").fetchone()
        if not row:
            return None
        conn.execute("UPDATE reviews SET status='running',updated=datetime('now') WHERE report_id=? AND claim_id=?",
                     (row["report_id"],row["claim_id"]))
        return {"report": REGISTRY[row["report_id"]], "claim": json.loads(row["input_json"])}


def finish_review(result):
    rid, cid, status = (result[k] for k in ("report_id", "claim_id", "status"))
    if status not in {"complete", "partial", "failed"}:
        raise ValueError("Invalid review status")
    with db() as conn:
        if not conn.execute("""UPDATE reviews SET status=?,updated=datetime('now'),details=?
             WHERE report_id=? AND claim_id=? AND status='running'""",
             (status,json.dumps(result,ensure_ascii=False),rid,cid)).rowcount:
            raise ValueError("Review is not running")


def registry_view():
    with db() as conn:
        audits = {row["id"]: json.loads(row["details"]) for row in conn.execute("SELECT * FROM audits")}
        jobs = {}
        for row in conn.execute("SELECT * FROM jobs"):
            details = json.loads(row["details"] or "{}")
            jobs[row["id"]] = {"status": row["status"], "updated": row["updated"],
                                "processed": details.get("processed", 0), "batches": details.get("batches", 0),
                                "reason": details.get("reason", "")}
    return [{**r, "audit": audits.get(rid), "job": jobs.get(rid), "pilot_rows": len(PILOT.get(rid, []))}
            for rid, r in REGISTRY.items()]


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, content_type, download=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="{download}"')
        self.end_headers()
        self.wfile.write(body)

    def reply(self, data, code=200):
        self.send(code, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def do_GET(self):
        from urllib.parse import unquote
        path = unquote(urlsplit(self.path).path)
        static = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "application/javascript"),
                  "/style.css": ("style.css", "text/css")}
        if path in static:
            filename, mime = static[path]
            self.send(200, (ROOT / "static" / filename).read_bytes(), mime + "; charset=utf-8")
        elif path == "/api/reports":
            self.reply(registry_view())
        elif path == "/health":
            self.reply({"ok": True, "reports": len(REGISTRY)})
        else:
            endpoint, _, rid = path.rpartition("/")
            if rid not in REGISTRY or endpoint not in {"/api/claims", "/api/md", "/api/csv"}:
                self.reply({"error": "Не найдено"}, 404)
                return
            if endpoint == "/api/claims":
                self.reply(rows_for(rid))
            elif endpoint == "/api/md":
                self.send(200, (DATA / REGISTRY[rid]["repository_path"]).read_bytes(), "text/plain; charset=utf-8")
            else:
                out = io.StringIO()
                writer = csv.writer(out, delimiter=";")
                writer.writerow(["№", "Заявление", "Тип", "E/S/G", "Проверка", "Пояснение"])
                for index, row in enumerate(rows_for(rid), 1):
                    values = [row.get(k, "") for k in ("statement", "type", "block", "status", "reason")]
                    writer.writerow([index, *[("'" + str(v) if str(v).lstrip().startswith(("=", "+", "-", "@")) else v) for v in values]])
                self.send(200, out.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8", "esg-claims.csv")

    def do_POST(self):
        if self.headers.get_content_type() != "application/json":
            self.reply({"error": "Требуется JSON"}, 415)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 50000:
                raise ValueError("Недопустимый размер запроса")
            data = json.loads(self.rfile.read(length))
            if self.path == "/api/review":
                queue_review(data["report_id"], data["claim_id"])
                self.reply({"queued": True})
                return
            if self.path == "/api/review-report":
                self.reply({"queued": queue_report_reviews(data["report_id"])})
                return
            ids = data["ids"]
            if not isinstance(ids, list) or not ids or not all(isinstance(x, str) and x in REGISTRY for x in ids):
                raise ValueError("Выберите отчёт из реестра")
            if self.path == "/api/audit":
                self.reply({rid: audit(rid) for rid in set(ids)})
            elif self.path == "/api/queue":
                enqueue(ids)
                self.reply({"queued": len(set(ids))})
            else:
                self.reply({"error": "Не найдено"}, 404)
        except (TypeError, ValueError, KeyError) as exc:
            self.reply({"error": str(exc)}, 400)


if __name__ == "__main__":
    init()
    args = sys.argv[1:]
    if args == ["audit-all"]:
        results = [audit(rid) for rid in REGISTRY]
        print(json.dumps({"reports": len(results), "pages": sum(r["pages"] for r in results),
                          "passed": sum(r["hash"] and r["positions"] for r in results)}))
    elif args == ["queue-all"]:
        enqueue(list(REGISTRY))
        print(json.dumps({"reports_queued": len(REGISTRY)}))
    elif args == ["claim-review"]:
        print(json.dumps(claim_review(), ensure_ascii=False))
    elif args == ["finish-review"]:
        finish_review(json.load(sys.stdin))
    elif args == ["claim"]:
        print(json.dumps(claim(), ensure_ascii=False))
    elif len(args) == 2 and args[0] == "finish":
        finish(args[1], json.load(sys.stdin))
    else:
        ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("ESG_PORT", "18496"))), Handler).serve_forever()
