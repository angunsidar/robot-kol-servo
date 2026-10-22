"""cad/step/servo_kol_montaj.step'i Onshape'e yükler (REST API v6, Basic auth).
Anahtarlar: proje kökündeki .env (ONSHAPE_ACCESS_KEY / ONSHAPE_SECRET_KEY) — git'e girmez.

Yalnızca bu betiğin açtığı belgeyle çalışır: belge kimliği onshape/durum.json'da tutulur. Başka belgeleri
listelemez, açmaz, değiştirmez. Student planında API kotası var: bir yükleme ≈ 1 belge + 1 çeviri + birkaç sorgu.

python onshape_yukle.py            # belge yoksa açar, montajı yükler
python onshape_yukle.py --test     # yalnızca bağlantıyı dener (1 çağrı)
"""
import argparse
import json
import os
import sys
import time

import requests

KOK = os.path.dirname(os.path.abspath(__file__))
PROJE = os.path.dirname(KOK)
DURUM = os.path.join(KOK, "durum.json")
API = "https://cad.onshape.com/api/v6"
MONTAJ = os.path.join(PROJE, "cad", "step", "servo_kol_montaj.step")


def env():
    d = {}
    yol = os.path.join(PROJE, ".env")
    if not os.path.exists(yol):
        sys.exit(".env yok: proje köküne ONSHAPE_ACCESS_KEY ve ONSHAPE_SECRET_KEY yaz.")
    for satir in open(yol, encoding="utf-8"):
        if "=" in satir and not satir.strip().startswith("#"):
            k, v = satir.strip().split("=", 1)
            d[k.strip()] = v.strip().strip('"').strip("'")
    a, s = d.get("ONSHAPE_ACCESS_KEY"), d.get("ONSHAPE_SECRET_KEY")
    if not a or not s:
        sys.exit(".env içinde ONSHAPE_ACCESS_KEY / ONSHAPE_SECRET_KEY boş.")
    return a, s


S = requests.Session()
S.auth = env()
S.headers.update({"Accept": "application/json;charset=UTF-8; qs=0.09"})
CAGRI = 0


def istek(yontem, yol, **kw):
    global CAGRI
    for _ in range(5):
        CAGRI += 1
        r = S.request(yontem, API + yol, timeout=180, **kw)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 5)))
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"{yontem} {yol} -> {r.status_code}: {r.text[:300]}")
        return r.json() if r.content and "json" in r.headers.get("Content-Type", "") else r
    raise RuntimeError(f"{yol}: hız sınırı aşılamadı")


def bekle(url):
    for i in range(60):
        j = istek("GET", url)
        if j.get("requestState") != "ACTIVE":
            return j
        time.sleep(min(3 + i, 10))
    raise RuntimeError(f"{url}: zaman aşımı")


def durum_oku():
    return json.load(open(DURUM, encoding="utf-8")) if os.path.exists(DURUM) else {}


def durum_yaz(d):
    json.dump(d, open(DURUM, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    if a.test:
        j = istek("GET", "/users/sessioninfo")
        print("bağlantı tamam:", j.get("name"))
        return
    if not os.path.exists(MONTAJ):
        sys.exit("Önce cad/model.py'yi çalıştır (STEP yok).")
    d = durum_oku()
    if "did" not in d:
        j = istek("POST", "/documents", json={
            "name": "Servo Kol — basılabilir parçalar",
            "description": "github.com/angunsidar/robot-kol-servo · cad/ klasöründen CadQuery ile üretilir (STEP içe aktarma).",
            "isPublic": False})
        d = {"did": j["id"], "wid": j["defaultWorkspace"]["id"], "yuklemeler": []}
        durum_yaz(d)
        print("yeni belge açıldı")
    with open(MONTAJ, "rb") as f:
        j = istek("POST", f"/translations/d/{d['did']}/w/{d['wid']}",
                  files={"file": (os.path.basename(MONTAJ), f, "application/octet-stream")},
                  data={"translate": "true", "storeInDocument": "true", "flattenAssemblies": "false",
                        "yAxisIsUp": "false", "formatName": ""})
    t = bekle(f"/translations/{j['id']}")
    if t["requestState"] != "DONE":
        sys.exit(f"çeviri başarısız: {t.get('failureReason')}")
    d["yuklemeler"].append({"zaman": time.strftime("%Y-%m-%d %H:%M"), "elemanlar": t.get("resultElementIds", [])})
    durum_yaz(d)
    print(f"yüklendi: {len(t.get('resultElementIds', []))} sekme · API çağrısı: {CAGRI}")
    print(f"https://cad.onshape.com/documents/{d['did']}/w/{d['wid']}")


if __name__ == "__main__":
    main()
