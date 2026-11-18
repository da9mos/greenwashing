"""Скачивание 92 отчётов из reports.csv (итерация 3).

Вход:  ../01_итерация_1_сбор_данных/выборка_30/reports.csv
Выход: data/reports/<report_id>.pdf и data/reports/download_log.csv
Уже скачанные файлы (валидный PDF) не перекачиваются и не перезаписываются.
Капчу не обходим: если вместо файла пришла страница с капчей/запретом — пишем ошибку.
"""
import csv, hashlib, html, re, shutil, sys, time, zipfile, http.cookiejar
import urllib.request, urllib.parse, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS_CSV = ROOT.parent / "01_итерация_1_сбор_данных" / "выборка_30" / "reports.csv"
OUT = ROOT / "data" / "reports"
LOG = OUT / "download_log.csv"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
PAUSE, RETRIES, TIMEOUT = 1.0, 3, 180


def opener():
    cj = http.cookiejar.CookieJar()
    o = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    o.addheaders = [("User-Agent", UA), ("Accept-Language", "ru,en;q=0.8")]
    return o


def fetch(url, op=None):
    """Возвращает (bytes, final_url, content_type). 3 повтора с паузой."""
    op = op or opener()
    err = None
    for attempt in range(RETRIES + 1):
        time.sleep(PAUSE)
        try:
            with op.open(url, timeout=TIMEOUT) as r:
                return r.read(), r.geturl(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            err = f"HTTP {e.code}"
            if e.code in (403, 404, 410):
                break
        except Exception as e:  # сеть, таймаут
            err = f"{type(e).__name__}: {e}"
        time.sleep(PAUSE * (attempt + 1))
    raise RuntimeError(err)


def is_pdf(b):
    return b[:1024].lstrip().startswith(b"%PDF")


def is_zip(b):
    return b[:4] == b"PK\x03\x04"


def looks_like_captcha(text):
    t = text.lower()
    return any(k in t for k in ("captcha", "recaptcha", "smartcaptcha", "я не робот", "are you a robot"))


def drive_download(drive_id, want):
    """Скачать файл с Google Drive. want: 'pdf' | 'zip'. -> (bytes, url, note)."""
    check = is_pdf if want == "pdf" else is_zip
    op = opener()
    url1 = f"https://drive.usercontent.google.com/download?id={drive_id}&export=download&confirm=t"
    b, u, _ = fetch(url1, op)
    if check(b):
        return b, url1, ""
    page = b.decode("utf-8", "replace")
    # страница подтверждения: форма с hidden-полями или токен confirm
    form = re.search(r'<form[^>]+action="([^"]+)"', page)
    if form:
        fields = dict(re.findall(r'name="([^"]+)"\s+value="([^"]*)"', page))
        if fields:
            url2 = html.unescape(form.group(1)) + "?" + urllib.parse.urlencode(fields)
            b, u, _ = fetch(url2, op)
            if check(b):
                return b, url2, "через форму подтверждения"
    m = re.search(r"confirm=([0-9A-Za-z_\-]+)", page)
    token = m.group(1) if m else "t"
    url3 = f"https://drive.google.com/uc?export=download&id={drive_id}&confirm={token}"
    b, u, _ = fetch(url3, op)
    if check(b):
        return b, url3, "через drive.google.com/uc"
    t = b.decode("utf-8", "replace")
    title = re.search(r"<title>(.*?)</title>", t, re.S)
    raise RuntimeError("пришёл не файл: " + (html.unescape(title.group(1)).strip()[:120] if title else t[:120].strip()))


def find_report_pdf_url(page_html, base_url, year):
    """На странице сайта ищем ссылку на PDF; предпочитаем с нужным годом и словами отчёта."""
    links = re.findall(r'href=["\']([^"\']+)["\']', page_html, re.I)
    cands = []
    for href in links:
        full = urllib.parse.urljoin(base_url, html.unescape(href))
        if ".pdf" not in full.lower():
            continue
        s = urllib.parse.unquote(full).lower()
        score = 0
        if str(year) in s:
            score += 3
        if any(k in s for k in ("annual", "годов", "report", "отчет", "отчёт", "go_", "ar_")):
            score += 1
        cands.append((score, full))
    cands.sort(key=lambda x: -x[0])
    return [c for _, c in cands]


def site_download(drive_id, year):
    doc_url = f"https://docs.google.com/document/d/{drive_id}/export?format=txt"
    b, _, _ = fetch(doc_url)
    text = b.decode("utf-8-sig", "replace")
    urls = re.findall(r"https?://[^\s<>\"')\]]+", text)
    if not urls:
        raise RuntimeError("в Google-документе нет ссылки")
    notes = []
    for url in urls:
        url = url.rstrip(".,;")
        try:
            b, final, ctype = fetch(url)
        except Exception as e:
            notes.append(f"{url}: {e}")
            continue
        if is_pdf(b):
            return b, url, "ссылка из Google-документа"
        page = b.decode("utf-8", "replace")
        if looks_like_captcha(page):
            notes.append(f"{url}: на сайте капча, не обходим")
            continue
        for pdf_url in find_report_pdf_url(page, final, year)[:5]:
            try:
                b2, _, _ = fetch(pdf_url)
            except Exception as e:
                notes.append(f"{pdf_url}: {e}")
                continue
            if is_pdf(b2):
                return b2, pdf_url, f"найдено на странице {url}"
        notes.append(f"{url}: на странице не найден PDF отчёта за {year}")
    raise RuntimeError(" | ".join(notes)[:500])


def save_new(path, data):
    """Не перезаписывать существующий файл."""
    if path.exists():
        return
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(data)
    tmp.rename(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with open(REPORTS_CSV, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    only = set(sys.argv[1:])
    log = []
    for i, r in enumerate(rows, 1):
        rid, st, did = r["report_id"], r["status"].strip(), r["drive_id"].strip()
        if only and rid not in only:
            continue
        pdf_path = OUT / f"{rid}.pdf"
        rec = {"report_id": rid, "status": "", "bytes": "", "sha256": "", "source_url": "", "note": ""}
        try:
            if pdf_path.exists() and is_pdf(pdf_path.read_bytes()[:1024]):
                data, src, note = pdf_path.read_bytes(), "", "уже был скачан"
            elif st == "pdf":
                data, src, note = drive_download(did, "pdf")
                save_new(pdf_path, data)
            elif st.startswith("архив"):
                zdata, src, note = drive_download(did, "zip")
                zpath = OUT / f"{rid}.zip"
                save_new(zpath, zdata)
                zdir = OUT / f"{rid}_zip"
                zdir.mkdir(exist_ok=True)
                with zipfile.ZipFile(zpath) as z:
                    for m in z.infolist():
                        # имена в zip бывают в cp866
                        name = m.filename
                        if not (m.flag_bits & 0x800):
                            try:
                                name = m.filename.encode("cp437").decode("cp866")
                            except Exception:
                                pass
                        target = (zdir / name).resolve()
                        if zdir.resolve() not in target.parents or m.is_dir():
                            continue
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if not target.exists():
                            target.write_bytes(z.read(m))
                pdfs = sorted(zdir.rglob("*.pdf"), key=lambda p: p.stat().st_size, reverse=True)
                if not pdfs:
                    raise RuntimeError("в архиве нет PDF")
                data = pdfs[0].read_bytes()
                if not is_pdf(data):
                    raise RuntimeError(f"главный файл архива не PDF: {pdfs[0].name}")
                save_new(pdf_path, data)
                note = (note + "; " if note else "") + f"из архива: {pdfs[0].relative_to(zdir)} (PDF в архиве: {len(pdfs)})"
            elif st.startswith("ссылка"):
                data, src, note = site_download(did, r["year"])
                save_new(pdf_path, data)
            else:
                raise RuntimeError(f"неизвестный статус: {st}")
            rec.update(status="ok", bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                       source_url=src, note=note)
        except Exception as e:
            rec.update(status="ошибка", note=str(e)[:500])
        log.append(rec)
        print(f"[{i}/{len(rows)}] {rid}: {rec['status']} {rec['bytes']} {rec['note'][:100]}", flush=True)

    # при частичном запуске дописываем к старому логу (заменяя строки тех же отчётов)
    old = []
    if only and LOG.exists():
        with open(LOG, encoding="utf-8-sig", newline="") as f:
            old = [x for x in csv.DictReader(f, delimiter=";") if x["report_id"] not in only]
    order = {r["report_id"]: k for k, r in enumerate(rows)}
    allrecs = sorted(old + log, key=lambda x: order.get(x["report_id"], 999))
    with open(LOG, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(log[0].keys()) if log else list(rec.keys()), delimiter=";")
        w.writeheader()
        w.writerows(allrecs)
    ok = sum(1 for x in allrecs if x["status"] == "ok")
    print(f"Итог: ok {ok} из {len(allrecs)}")


if __name__ == "__main__":
    main()
