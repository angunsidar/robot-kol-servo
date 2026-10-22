"""Servo kol montajı (CadQuery): FK ile yerleştirme, eklem taramalı katı çakışma kontrolü, STEP/STL çıktısı.
Çalıştır:  python model.py            # parçalar + çakışma taraması + STEP/STL
           python model.py --hizli    # kaba tarama (geliştirirken)
Ölçüler: geometri.py.  Parçalar: parcalar.py.
"""
import argparse
import json
import math
import os
import sys
import time

import cadquery as cq
from cadquery import Vector as V

import geometri as G
import parcalar as P

KOK = os.path.dirname(os.path.abspath(__file__))
STEP_DIR = os.path.join(KOK, "step")
STL_DIR = os.path.join(KOK, "stl")

ESIK_MM3 = 0.05     # bundan büyük ortak hacim = çakışma


# ----------------------------------------------------------------- konumlar
def _L(t=(0, 0, 0), eksen=(0, 0, 1), aci=0.0):
    return cq.Location(V(*t), V(*eksen), aci)


def cerceveler(q, tut_servo=35.0, phi0=0.0):
    """q = [J1, J2, J3, J4, J5] eklem açıları (derece, model sırası). Gövde çerçeveleri (cq.Location)."""
    q1, q2, q3, q4, q5 = q
    phi = G.cene_aci(tut_servo, phi0)
    T0 = _L()
    T1 = _L(aci=q1)
    T2 = T1 * _L((0, 0, G.H0)) * _L(eksen=(0, 1, 0), aci=q2)
    T3 = T2 * _L((0, 0, G.L2)) * _L(eksen=(0, 1, 0), aci=q3)
    T4 = T3 * _L((0, 0, G.L3)) * _L(eksen=(0, 1, 0), aci=q5)
    T5 = T4 * _L((0, 0, G.T_DONUS_HORN)) * _L(aci=q4)
    c2 = G.DIS_C / 2
    T6 = T5 * _L((-c2, 0, G.Z_SERVO_MIL)) * _L(eksen=(0, 1, 0), aci=-phi)
    T7 = T5 * _L((c2, 0, G.Z_SERVO_MIL)) * _L(eksen=(0, 1, 0), aci=phi)
    return [T0, T1, T2, T3, T4, T5, T6, T7]


GOVDE_ADI = ["taban", "govde", "ust_kol", "on_kol", "bilek", "tutucu", "cene_A", "cene_B"]


def _burc_y(boy, y_dis, x, z):
    """y ekseninde burç: y_dis (yanağın dış yüzü) → y_dis − boy."""
    return P.burc(boy).rotate(V(0, 0, 0), V(1, 0, 0), 90).translate(V(x, y_dis, z))


def ogeler():
    """[(ad, gövde, katı, tür)] — tür: 'parca' (basılır), 'servo', 'horn', 'burc'."""
    MG, SG = G.MG, G.SG
    c2 = G.DIS_C / 2
    yatay = ((0, 0, 1), (0, 1, 0))       # Xs → +z, Zs → +y (J2, J3, J5)
    o = []
    t0 = time.time()
    o.append(("taban", 0, P.taban(), "parca"))
    o.append(("servo_J1", 0, P.yerlestir(P.servo(MG), (1, 0, 0), (0, 0, 1), (0, 0, G.J1_SERVO_TABAN)), "servo"))
    o.append(("govde", 1, P.govde(), "parca"))
    o.append(("horn_J1", 1, P.yerlestir(P.horn(MG), (1, 0, 0), (0, 0, 1), (0, 0, G.J1_SERVO_TABAN)), "horn"))
    o.append(("servo_J2", 1, P.yerlestir(P.servo(MG), *yatay, (0, G.Y_SERVO_TABAN, G.H0)), "servo"))
    o.append(("burc_J2", 1, _burc_y(P.BURC_MG, G.Y_YANAK[0], 0, G.H0), "burc"))
    o.append(("ust_kol", 2, P.ust_kol(), "parca"))
    o.append(("horn_J2", 2, P.yerlestir(P.horn(MG), *yatay, (0, G.Y_SERVO_TABAN, 0)), "horn"))
    o.append(("servo_J3", 2, P.yerlestir(P.servo(MG), *yatay, (0, G.Y_SERVO_TABAN, G.L2)), "servo"))
    o.append(("burc_J3", 2, _burc_y(P.BURC_MG, G.Y_YANAK[0], 0, G.L2), "burc"))
    o.append(("on_kol", 3, P.on_kol(), "parca"))
    o.append(("horn_J3", 3, P.yerlestir(P.horn(MG), *yatay, (0, G.Y_SERVO_TABAN, 0)), "horn"))
    o.append(("servo_J5", 3, P.yerlestir(P.servo(SG), *yatay, (0, G.Y_SERVO5_TABAN, G.L3)), "servo"))
    o.append(("burc_J5", 3, _burc_y(P.BURC_SG, G.Y_YANAK5[0], 0, G.L3), "burc"))
    o.append(("bilek", 4, P.bilek(), "parca"))
    o.append(("horn_J5", 4, P.yerlestir(P.horn(SG), *yatay, (0, G.Y_SERVO5_TABAN, 0)), "horn"))
    o.append(("servo_J4", 4, P.yerlestir(P.servo(SG), (1, 0, 0), (0, 0, 1), (0, 0, G.R0_DONUS)), "servo"))
    o.append(("tutucu_govde", 5, P.tutucu_govde(), "parca"))
    o.append(("horn_J4", 5, P.yerlestir(P.horn(SG), (1, 0, 0), (0, 0, 1), (0, 0, -SG["HORN_UST"])), "horn"))
    o.append(("servo_tutucu", 5, P.yerlestir(P.servo(SG), (0, 0, -1), (0, 1, 0), (-c2, G.Y_TUT_SERVO_TABAN, G.Z_SERVO_MIL)), "servo"))
    o.append(("burc_tutucu", 5, _burc_y(P.BURC_TUT, G.Y_DISLI[1] + 0.3, c2, G.Z_SERVO_MIL), "burc"))
    o.append(("cene_A", 6, P.cene(-1), "parca"))
    o.append(("horn_tutucu", 6, P.sil("y", 11.0, (G.Y_DISLI[0] - 2.0, G.Y_DISLI[0])), "horn"))
    o.append(("cene_B", 7, P.cene(+1), "parca"))
    print(f"  parçalar kuruldu ({time.time() - t0:.1f} s)")
    return o


# ----------------------------------------------------------------- çakışma
def _bb_kesisir(a, b, pay=0.05):
    A, B = a.BoundingBox(), b.BoundingBox()
    return not (A.xmax < B.xmin - pay or B.xmax < A.xmin - pay or A.ymax < B.ymin - pay or
                B.ymax < A.ymin - pay or A.zmax < B.zmin - pay or B.zmax < A.zmin - pay)


def ortak_hacim(a, b):
    if not _bb_kesisir(a, b):
        return 0.0
    try:
        return a.intersect(b).Volume()
    except Exception:                       # OCC boolean hatası: güvenli tarafta kal
        return float("inf")


def konumla(o, T):
    return [(ad, g, k.moved(T[g]), tur) for ad, g, k, tur in o]


def ic_kontrol(o):
    """Aynı gövdedeki öğeler (sabit) — tek sefer."""
    sonuc = []
    for i in range(len(o)):
        for j in range(i + 1, len(o)):
            if o[i][1] != o[j][1] or frozenset((o[i][0], o[j][0])) in MUAF:
                continue
            v = ortak_hacim(o[i][2], o[j][2])
            if v > ESIK_MM3:
                sonuc.append((o[i][0], o[j][0], v))
    return sonuc


# Tasarım gereği iç içe olan çiftler: horn, kendi servosunun miline oturur.
MUAF = {frozenset(p) for p in [("servo_J1", "horn_J1"), ("servo_J2", "horn_J2"), ("servo_J3", "horn_J3"),
                               ("servo_J5", "horn_J5"), ("servo_J4", "horn_J4"), ("servo_tutucu", "horn_tutucu")]}
EN_DAR_PAY = 6.0    # bu mesafeden yakın çiftlerde en dar boşluk ölçülür


def tarama(o, ad, eklem_i, degerler, sabit, gruplar, phi0, tut=35.0):
    """eklem_i: q dizinindeki eklem (tutucu için None). gruplar: (yakın gövdeler, uzak gövdeler).
    Döner: (çakışmalar, en dar boşluk (mm, açı, öğe1, öğe2))."""
    yakin, uzak = gruplar
    hatalar = []
    en_dar = (float("inf"), None, None, None)
    for d in degerler:
        q = list(sabit)
        t = tut
        if eklem_i is None:
            t = d
        else:
            q[eklem_i] = d
        oo = konumla(o, cerceveler(q, t, phi0))
        A = [x for x in oo if x[1] in yakin]
        B = [x for x in oo if x[1] in uzak]
        for a in A:
            for b in B:
                if frozenset((a[0], b[0])) in MUAF:
                    continue
                v = ortak_hacim(a[2], b[2])
                if v > ESIK_MM3:
                    hatalar.append((d, a[0], b[0], v))
                elif _bb_kesisir(a[2], b[2], EN_DAR_PAY) and not ("burc" in a[0] or "burc" in b[0]
                                                                   or {a[0], b[0]} == {"cene_A", "cene_B"}):
                    # burç ↔ delik (0,2 mm) ve dişli kavraması (0,14 mm) tasarım gereği dar; burada sayılmaz
                    m = a[2].distance(b[2])
                    if m < en_dar[0]:
                        en_dar = (m, d, a[0], b[0])
    return hatalar, en_dar


# ----------------------------------------------------------------- tornavida erişimi
def _yol(eksen, nokta, a0, a1, r):
    """Tornavida yolu: eksen ('x'/'y'/'z', ±) boyunca a0 → a1, verilen noktadan (diğer iki koordinat)."""
    e = eksen[-1]
    c = {"x": (nokta[1], nokta[2]), "y": (nokta[0], nokta[2]), "z": (nokta[0], nokta[1])}[e]
    return P.sil(e, r, (min(a0, a1), max(a0, a1)), c)


def _oluk_noktalari(desen):
    """Her oluğun iç ucu, ortası ve dış ucu (vida bu aralıkta herhangi bir yerde olabilir)."""
    r0, r1 = desen["r0"], desen["r1"]
    return [(a, r) for a in desen["acilar"] for r in (r0, (r0 + r1) / 2, r1)]


def erisim_listesi():
    """(vida, gövde, yol katısı (gövde çerçevesinde), o adımda takılı olup engel olabilecek öğeler).
    Montaj sırası cad/README.md ile aynı. Tornavida + vida başı için Ø6 (SG vidaları için Ø4,5)."""
    MG, SG = G.MG, G.SG
    L = []
    # 2) J1 merkez vidası ve horn vidaları: gövde diski takılıyken, J2 servosu henüz yok
    L.append(("J1 horn merkez vidası", 1, _yol("z", (0, 0, 0), G.J1_HORN_UST, 260, 3.0), {"govde"}))
    for a, r in _oluk_noktalari(G.HORN_MG_J1):
        n = (r * math.cos(math.radians(a)), r * math.sin(math.radians(a)), 0)
        L.append((f"J1 horn vidası ({a}°, r{r:.1f})", 1, _yol("z", n, G.DISK_Z1, 260, 3.0), {"govde"}))
    # 3) J2 kulak vidaları (+y'den), sonra J2 horn merkez vidası (A levhası deliğinden)
    for xs, ys in P.servo_kulak_delikleri(MG):
        L.append((f"J2 kulak vidası ({ys:+.0f}, {xs:+.1f})", 1,
                  _yol("y", (ys, 0, G.H0 + xs), G.Y_KULAK + MG["KULAK_T"], 200, 3.0), {"govde", "servo_J2"}))
    L.append(("J2 horn merkez vidası", 2, _yol("y", (0, 0, 0), G.Y_HORN, 200, 3.0), {"ust_kol", "govde"}))
    L.append(("J2 burç cıvatası", 1, _yol("y", (0, 0, G.H0), G.CATAL_B[0] - 0.3, -200, 3.0), {"ust_kol", "govde"}))
    for xs, ys in P.servo_kulak_delikleri(MG):
        L.append((f"J3 kulak vidası ({ys:+.0f}, {xs:+.1f})", 2,
                  _yol("y", (ys, 0, G.L2 + xs), G.Y_KULAK + MG["KULAK_T"], 200, 3.0), {"ust_kol", "servo_J3"}))
    L.append(("J3 horn merkez vidası", 3, _yol("y", (0, 0, 0), G.Y_HORN, 200, 3.0), {"on_kol", "ust_kol"}))
    L.append(("J3 burç cıvatası", 2, _yol("y", (0, 0, G.L2), G.CATAL_B[0] - 0.3, -200, 3.0), {"on_kol", "ust_kol"}))
    for xs, ys in P.servo_kulak_delikleri(SG):
        L.append((f"J5 kulak vidası ({xs:+.1f})", 3,
                  _yol("y", (ys, 0, G.L3 + xs), G.Y_KULAK5 + SG["KULAK_T"], 200, 2.25), {"on_kol", "servo_J5"}))
    L.append(("J5 horn merkez vidası", 4, _yol("y", (0, 0, 0), G.Y_HORN5, 200, 2.25), {"bilek", "on_kol"}))
    L.append(("J5 burç cıvatası", 3, _yol("y", (0, 0, G.L3), G.CATAL5_B[0] - 0.3, -200, 3.0), {"bilek", "on_kol"}))
    # 6) dönüş servosu kulak vidaları (+z'den, tutucu yokken), tutucu gövdesi merkez + horn vidaları
    for xs, ys in P.servo_kulak_delikleri(SG):
        L.append((f"J4 kulak vidası ({xs:+.1f})", 4,
                  _yol("z", (xs, ys, 0), G.T_DONUS_KULAK_Z + SG["KULAK_T"], 200, 2.25), {"bilek", "servo_J4"}))
    L.append(("J4 horn merkez vidası", 5, _yol("z", (0, 0, 0), G.TUT_TABAN_T, 200, 2.25), {"tutucu_govde"}))
    for a, r in _oluk_noktalari(G.HORN_SG_TUT):
        n = (r * math.cos(math.radians(a)), r * math.sin(math.radians(a)), 0)
        L.append((f"J4 horn vidası ({a}°, r{r:.1f})", 5, _yol("z", n, G.TUT_TABAN_T, 200, 2.25), {"tutucu_govde"}))
    # 7) tutucu servosu kulak vidaları (+Y'den), dişli B cıvatası, A çenesinin horn vidası
    c2 = G.DIS_C / 2
    for xs, ys in P.servo_kulak_delikleri(SG):
        L.append((f"Tutucu kulak vidası ({xs:+.1f})", 5,
                  _yol("y", (-c2 - ys, 0, G.Z_SERVO_MIL - xs), G.Y_TUT_KULAK + SG["KULAK_T"], 200, 2.25),
                  {"tutucu_govde", "servo_tutucu"}))
    L.append(("Dişli B cıvatası", 5, _yol("y", (c2, 0, G.Z_SERVO_MIL), G.Y_DISLI[1] + 0.3, 200, 3.0),
              {"tutucu_govde", "cene_A", "cene_B", "burc_tutucu"}))
    L.append(("Çene A horn merkez vidası", 6, _yol("y", (0, 0, 0), G.Y_DISLI[0], 200, 2.25), {"cene_A", "cene_B"}))
    return L


def erisim_kontrol(o, phi0):
    T = cerceveler([0, 0, 0, 0, 0], G.TUT_SERVO_KAPALI, phi0)
    oo = {ad: k for ad, g, k, tur in konumla(o, T)}
    hatalar = []
    for ad, g, yol, engel in erisim_listesi():
        y = yol.moved(T[g])
        for e in engel:
            v = ortak_hacim(y, oo[e])
            if v > ESIK_MM3:
                hatalar.append((ad, e, v))
    return hatalar


# ----------------------------------------------------------------- çene açısı
def ped_kati(taraf):
    h = G.CENE_EN / 2
    ic = -taraf
    px = (h, h + G.PED_T) if ic > 0 else (-h - G.PED_T, -h)
    return P.kutu(px, G.Y_DISLI, (G.CENE_L - G.PED_L, G.CENE_L))


def cene_boslugu(tut_servo, phi0):
    T = cerceveler([0, 0, 0, 0, 0], tut_servo, phi0)
    a = ped_kati(-1).moved(T[6])
    b = ped_kati(+1).moved(T[7])
    return a.distance(b) if not _bb_kesisir(a, b, 0) or a.intersect(b).Volume() < 1e-6 else -a.intersect(b).Volume()


def phi0_bul():
    """Tutucu servo TUT_SERVO_KAPALI'da ped boşluğu = CENE_KAPALI_BOSLUK olacak çene açısı.
    Açık konumdan (φ = 30°) içe doğru taranır; ilk kez boşluğun altına inilen aralık ikiye bölünür
    (daha içeride çeneler çaprazlanıp boşluk yeniden artar, o kol geçersiz)."""
    hi = 30.0
    lo = hi
    while lo > -60:
        lo -= 2.0
        if cene_boslugu(G.TUT_SERVO_KAPALI, lo) < G.CENE_KAPALI_BOSLUK:
            break
    for _ in range(30):
        m = (lo + hi) / 2
        g = cene_boslugu(G.TUT_SERVO_KAPALI, m)
        if g < G.CENE_KAPALI_BOSLUK:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


# ----------------------------------------------------------------- çıktı
RENK = {"parca": (0.15, 0.4, 0.8), "servo": (0.1, 0.1, 0.1), "horn": (0.95, 0.95, 0.95), "burc": (0.9, 0.6, 0.1)}


def disa_aktar(o, phi0, q_ref=(0, 0, 0, 0, 0), tut=35.0):
    os.makedirs(STEP_DIR, exist_ok=True)
    os.makedirs(STL_DIR, exist_ok=True)
    for ad, f in P.PARCALAR.items():
        k = f()
        cq.exporters.export(cq.Workplane().add(k), os.path.join(STEP_DIR, f"{ad}.step"))
        cq.exporters.export(cq.Workplane().add(k), os.path.join(STL_DIR, f"{ad}.stl"), tolerance=0.02, angularTolerance=0.1)
    T = cerceveler(q_ref, tut, phi0)
    asm = cq.Assembly(name="servo_kol")
    for ad, g, k, tur in o:
        asm.add(k, name=ad, loc=T[g], color=cq.Color(*RENK[tur]))
    asm.save(os.path.join(STEP_DIR, "servo_kol_montaj.step"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hizli", action="store_true")
    ap.add_argument("--cikti-yok", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    print("=== Parçalar ===")
    o = ogeler()
    print("\n=== Çene kapanma açısı ===")
    phi0 = phi0_bul()
    print(f"  servo {G.TUT_SERVO_KAPALI:.0f}° → çene açısı φ0 = {phi0:.2f}° (ped boşluğu {G.CENE_KAPALI_BOSLUK} mm)")
    bos = {s: cene_boslugu(s, phi0) for s in (20, 25, 30, 35, 50, 70, 100, 110)}
    for s, g in bos.items():
        print(f"    tutucu {s:3d}° → ağız {g:6.1f} mm   (φ = {G.cene_aci(s, phi0):6.1f}°)")
    L4 = {s: G.L4_hesap(G.cene_aci(s, phi0)) for s in (20, 35, 70, 110)}
    print("  L4 (J5 → ped merkezi): " + ", ".join(f"{s}°: {v:.1f}" for s, v in L4.items()))

    print("\n=== Gövde içi çakışma (sabit) ===")
    ic = ic_kontrol(o)
    for x in ic:
        print(f"  [KALDI] {x[0]} ↔ {x[1]}: {x[2]:.2f} mm³")
    if not ic:
        print("  [GEÇTİ] gövde içinde çakışma yok")

    print("\n=== Tornavida erişimi (montaj sırasıyla) ===")
    er = erisim_kontrol(o, phi0)
    n_yol = len(erisim_listesi())
    for x in er:
        print(f"  [KALDI] {x[0]}: yol {x[1]} ile kesişiyor ({x[2]:.0f} mm³)")
    if not er:
        print(f"  [GEÇTİ] {n_yol} vidanın hepsine tornavida ulaşıyor")

    adim_mg, adim_sg = (15, 30) if a.hizli else (5, 10)
    lim = [(-90, 90), (-75, 75), (-80, 80), (-90, 90), (-90, 90)]   # servo sınırlarından (90 ± ...)
    def rng(lo, hi, s):
        n = int(round((hi - lo) / s))
        return [lo + (hi - lo) * i / n for i in range(n + 1)]
    sifir = [0, 0, 0, 0, 0]
    taramalar = [
        ("J1 gövde dönüşü", 0, rng(-90, 90, 45), sifir, ({0}, {1, 2, 3, 4, 5, 6, 7})),
        ("J2 omuz", 1, rng(*lim[1], adim_mg), sifir, ({0, 1}, {2, 3, 4, 5, 6, 7})),
        ("J3 dirsek", 2, rng(*lim[2], adim_mg), sifir, ({0, 1, 2}, {3, 4, 5, 6, 7})),
        ("J5 bilek eğim", 4, rng(*lim[4], adim_sg), sifir, ({0, 1, 2, 3}, {4, 5, 6, 7})),
        ("J5 bilek eğim (J4 = 90)", 4, rng(*lim[4], adim_sg * 2), [0, 0, 0, 90, 0], ({0, 1, 2, 3}, {4, 5, 6, 7})),
        ("J4 bilek dönüş", 3, rng(*lim[3], adim_sg * 2), sifir, ({0, 1, 2, 3, 4}, {5, 6, 7})),
        ("J4 bilek dönüş (J5 = 90)", 3, rng(*lim[3], adim_sg * 3), [0, 0, 0, 0, 90], ({0, 1, 2, 3, 4}, {5, 6, 7})),
        ("J4 bilek dönüş (J5 = −90)", 3, rng(*lim[3], adim_sg * 3), [0, 0, 0, 0, -90], ({0, 1, 2, 3, 4}, {5, 6, 7})),
        ("Tutucu", None, rng(G.TUT_SERVO_MIN, G.TUT_SERVO_MAX, adim_sg), sifir, ({5}, {6, 7})),
        ("Tutucu (çene ↔ çene)", None, rng(G.TUT_SERVO_MIN, G.TUT_SERVO_MAX, adim_sg), sifir, ({6}, {7})),
    ]
    rapor = {"phi0": phi0, "agiz_mm": bos, "L4": L4, "ic": ic, "erisim": er, "taramalar": {}}
    toplam_hata = len(ic) + len(er)
    for ad, ei, deg, sabit, gr in taramalar:
        t1 = time.time()
        h, dar = tarama(o, ad, ei, deg, sabit, gr, phi0)
        rapor["taramalar"][ad] = {"cakisma": h, "en_dar": dar}
        toplam_hata += len(h)
        durum = "GEÇTİ" if not h else "KALDI"
        dar_s = (f"en dar boşluk {dar[0]:.2f} mm ({dar[2]} ↔ {dar[3]}, {dar[1]:.0f}°)" if dar[1] is not None
                 else "yakın çift yok")
        print(f"\n[{durum}] {ad}: {len(deg)} konum, {len(h)} çakışma · {dar_s} ({time.time() - t1:.0f} s)")
        for d, x, y, v in h[:12]:
            print(f"     {d:7.1f}°  {x} ↔ {y}: {v:.1f} mm³")

    # çalışma alanı: kol katlanınca uç taban/gövdeye değer mi (bilgi; yazılım sınırı gerekir)
    print("\n=== Çalışma alanı katlanma kontrolü (bilgi) ===")
    uyar = []
    j2s = [-75, -40, 0, 40, 75] if not a.hizli else [-75, 0, 75]
    j3s = [-80, -40, 0, 40, 80] if not a.hizli else [-80, 0, 80]
    for q2 in j2s:
        for q3 in j3s:
            for q5 in (-90, 0, 90):
                oo = konumla(o, cerceveler([0, q2, q3, 0, q5], 35, phi0))
                for x in oo:
                    for y in oo:
                        if x[1] < y[1] and y[1] - x[1] >= 2 and not (x[1] >= 5 and y[1] >= 5)                                 and frozenset((x[0], y[0])) not in MUAF:
                            v = ortak_hacim(x[2], y[2])
                            if v > ESIK_MM3:
                                uyar.append(((q2, q3, q5), x[0], y[0], v))
    for u in uyar[:30]:
        print(f"  J2={u[0][0]:4d} J3={u[0][1]:4d} J5={u[0][2]:4d}: {u[1]} ↔ {u[2]} ({u[3]:.0f} mm³)")
    print(f"  {len(uyar)} katlanma çakışması (tasarım hatası değil; IK/yazılım bu pozlara gitmemeli)")
    rapor["katlanma"] = uyar

    with open(os.path.join(KOK, "model_rapor.json"), "w", encoding="utf-8") as f:
        json.dump(rapor, f, ensure_ascii=False, indent=1, default=str)

    if not a.cikti_yok:
        print("\n=== STEP / STL ===")
        disa_aktar(o, phi0)
        print(f"  {STEP_DIR}\n  {STL_DIR}")
    print(f"\nToplam tasarım çakışması: {toplam_hata}   ({time.time() - t0:.0f} s)")
    return 0 if toplam_hata == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
