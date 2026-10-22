"""Tasarım parçalarını simülasyon sayfası için ağa (mesh) çevirir → sim/servo_mesh.js
Her gövde (taban, gövde, üst kol, ...) kendi çerçevesinde, türe göre (parça / servo / horn / burç) birleştirilir.
Konumlar 0,01 mm'lik Int32 (base64), üçgenler Uint32 (base64). Sayfa bunları three.js BufferGeometry'ye çevirir.
python sim_mesh.py   (model.py'den sonra; build_page.py sayfaya gömer)
"""
import base64
import json
import os

import numpy as np

import geometri as G
import model as M

KOK = os.path.dirname(os.path.abspath(__file__))
CIKTI = os.path.join(KOK, "..", "sim", "servo_mesh.js")
TOL = 0.15


def main():
    o = M.ogeler()
    phi0 = M.phi0_bul()
    govdeler = {}
    for ad, g, k, tur in o:
        v, t = k.tessellate(TOL, 0.3)
        P = np.array([[p.x, p.y, p.z] for p in v], dtype=np.float64)
        T = np.array(t, dtype=np.uint32)
        d = govdeler.setdefault(M.GOVDE_ADI[g], {}).setdefault(tur, [[], [], 0])
        d[0].append(P)
        d[1].append(T + d[2])
        d[2] += len(P)
    veri = {}
    for gad, turler in govdeler.items():
        veri[gad] = {}
        for tur, (Ps, Ts, _) in turler.items():
            P = np.round(np.vstack(Ps) * 100).astype("<i4")
            T = np.vstack(Ts).astype("<u4")
            veri[gad][tur] = {"p": base64.b64encode(P.tobytes()).decode(), "i": base64.b64encode(T.tobytes()).decode()}
    # tutucu ağzı tablosu (servo° → iki ped arası mm) ve çene açısı
    agiz = [[s, round(M.cene_boslugu(s, phi0), 2)] for s in range(int(G.TUT_SERVO_MIN), int(G.TUT_SERVO_MAX) + 1, 5)]
    meta = {"phi0": round(phi0, 3), "kapali_servo": G.TUT_SERVO_KAPALI, "c": G.DIS_C, "z_mil": G.Z_SERVO_MIL,
            "t_horn": G.T_DONUS_HORN, "olcek": 0.01, "agiz": agiz}
    js = ("// Otomatik üretildi: cad/sim_mesh.py (cad/ tasarımından). Elle düzenleme.\n"
          f"window.KolMesh = {json.dumps({'govde': veri, 'meta': meta}, separators=(',', ':'))};\n")
    with open(CIKTI, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"yazıldı: {os.path.normpath(CIKTI)} ({len(js) / 1e3:.0f} kB)")
    for s, a in agiz:
        print(f"  tutucu {s:3d}° → ağız {a:5.1f} mm")


if __name__ == "__main__":
    main()
