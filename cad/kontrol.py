"""Servo kol — geometri, baskı, cıvata ve tork kontrolleri. STEP/STL üretmeden önce çalıştır.
python kontrol.py   → tüm satırlar GEÇTİ olmalı (BİLGİ satırları karar gerektirmez).
Çakışma taraması ayrı: python model.py
"""
import itertools
import math
import os
import sys

import geometri as G
import parcalar as P

sonuc = []


def kontrol(ad, deger, sart, birim="mm", aciklama="", bilgi=False):
    ok = True if bilgi else bool(sart(deger))
    if not bilgi:
        sonuc.append((ad, ok))
    etiket = "BİLGİ" if bilgi else ("GEÇTİ" if ok else "KALDI")
    print(f"[{etiket}] {ad:58s} {deger:9.2f} {birim:4s} {aciklama}")


MG, SG = G.MG, G.SG

print("=== MG996R ÇATAL EKLEMLER (J2, J3) ===")
kontrol("Servo tabanı ↔ yanak iç yüzü (eksenel)", G.Y_SERVO_TABAN - G.Y_YANAK[1], lambda v: v >= 0.8)
kontrol("Yanak kalınlığı", G.Y_YANAK[1] - G.Y_YANAK[0], lambda v: v >= 6)
kontrol("Yanak ↔ çatal B (eksenel, pulla ayarlanır)", G.Y_YANAK[0] - G.CATAL_B[1], lambda v: v >= 0.8)
kontrol("Kulak levhası −y yüzü ↔ J1 merkez vidası başı (Ø7)", G.Y_KULAK - G.T_KULAK - 3.5, lambda v: v >= 0.3,
        aciklama="J1 horn vidası gövde diskinden takılabilmeli")
kontrol("Horn yüzü ↔ mil üstü (horn göbeği payı)", MG["HORN_UST"] - MG["HORN_T"] - MG["MIL_UST"], lambda v: v >= 0)
kontrol("Kulak levhası alt deliği ↔ pencere alt kenarı (et)",
        (MG["UC"] - MG["L"] - G.BOS) - (-(MG["L"] - MG["UC"]) + (MG["L"] - MG["UC"] + MG["UC"]) / 2 - MG["DELIK_ARA"] / 2) - 1.3,
        lambda v: v >= 1.5, aciklama="Ø2,6 pilot")
z_alt_kulak = G.H0 - (MG["KULAK_L"] - MG["L"]) / 2 - (MG["L"] - MG["UC"])
kontrol("J2 servo alt kulağı ↔ gövde diski üstü", z_alt_kulak - G.DISK_Z1, lambda v: v >= 1.0)
kontrol("Kulak levhası yuvarlatması ↔ çatal köprüsü (radyal)", G.KOPRU_R[0] - G.KULAK_LEVHA_R, lambda v: v >= 2)
ust_kulak_r = math.hypot(MG["UC"] + (MG["KULAK_L"] - MG["L"]) / 2, MG["W"] / 2)
kontrol("Servo üst kulak köşesi ↔ kulak levhası yuvarlatması", G.KULAK_LEVHA_R - ust_kulak_r, lambda v: v >= 2)
kontrol("Horn süpürme zarfı ↔ çatal köprüsü", G.KOPRU_R[0] - MG["HORN_R"], lambda v: v >= 3)
# cıvata: burç ucu → yanaktaki somun
bas = G.CATAL_B[0] - 0.3
for boy in (16,):
    uc = bas + boy
    kontrol(f"J2/J3 mil cıvatası M3×{boy}: uç ↔ servo tabanı", G.Y_SERVO_TABAN - uc, lambda v: v >= 0.8)
    yc = sum(G.Y_YANAK) / 2
    kontrol(f"J2/J3 mil cıvatası M3×{boy}: somun boyunca diş", uc - (yc - G.SOMUN_YUVA_T / 2), lambda v: v >= G.SOMUN_T)
kontrol("Yanak somun kanalı yan et kalınlığı", (G.Y_YANAK[1] - G.Y_YANAK[0] - G.SOMUN_YUVA_T) / 2, lambda v: v >= 1.5)

print("\n=== SG90 ÇATAL (J5) ===")
kontrol("Servo tabanı ↔ yanak iç yüzü", G.Y_SERVO5_TABAN - G.Y_YANAK5[1], lambda v: v >= 0.8)
kontrol("Yanak kalınlığı", G.Y_YANAK5[1] - G.Y_YANAK5[0], lambda v: v >= 4.5)
bas5 = G.CATAL5_B[0] - 0.3
uc5 = bas5 + 10
yc5 = sum(G.Y_YANAK5) / 2
kontrol("J5 mil cıvatası M3×10: uç ↔ servo tabanı", G.Y_SERVO5_TABAN - uc5, lambda v: v >= 0.5)
kontrol("J5 mil cıvatası M3×10: somun boyunca diş", uc5 - (yc5 - G.SOMUN_YUVA_T / 2), lambda v: v >= G.SOMUN_T)
kontrol("Yanak somun kanalı yan et kalınlığı", (G.Y_YANAK5[1] - G.Y_YANAK5[0] - G.SOMUN_YUVA_T) / 2, lambda v: v >= 1.5)
on_ulasim = math.hypot(SG["UC"] + (SG["KULAK_L"] - SG["L"]) / 2, SG["W"] / 2)
kontrol("J5 servo öne uzanımı (kulak köşesi) ↔ ön kol uç yarıçapı", G.ONKOL_UC_R - on_ulasim, lambda v: v >= 0.5)
kontrol("Ön kol uç yarıçapı ↔ dönüş servosu tabanı", G.R0_DONUS - G.ONKOL_UC_R, lambda v: v >= 1.5)
kontrol("Ön kol iç yan duvar ↔ SG90 gövdesi", (G.ONKOL_KUTU_YAN - G.ONKOL_DUVAR) - SG["W"] / 2, lambda v: v >= 0.5)

print("\n=== TUTUCU ===")
m, z, a = G.DIS_M, G.DIS_Z, math.radians(G.DIS_ALFA)
r, ra = m * z / 2, m * z / 2 + m
rb = r * math.cos(a)
c = G.DIS_C
ra_max = math.sqrt(rb ** 2 + (c * math.sin(a)) ** 2)
kontrol("Diş ucu ↔ girişim sınırı (evolvent dışı temas yok)", ra_max - ra, lambda v: v >= 0)
eps = (2 * math.sqrt(ra ** 2 - rb ** 2) - c * math.sin(a)) / (math.pi * m * math.cos(a))
kontrol("Kavrama oranı", eps, lambda v: v >= 1.2, "")
kontrol("Dişli alt ucu ↔ tutucu tabanı", G.Z_SERVO_MIL - ra - G.TUT_TABAN_T, lambda v: v >= 0.5)
kontrol("Servo çapraz horn (R≈10,2) ↔ dişli B göbeği", c - 10.2 - G.TUTUCU_BOSS_R, lambda v: v >= 2)
kontrol("Servo horn üst yüzü ↔ dişli B alt yüzü (eksenel)", G.DISLI_B_KADEME, lambda v: v >= 0.8)
kontrol("Göbek somun yuvası et kalınlığı", G.TUTUCU_BOSS_R - math.hypot(G.SOMUN_YUVA / 2, G.SOMUN_AF / 2 / math.sqrt(3)),
        lambda v: v >= 1.2)
uc_b = G.Y_DISLI[1] + 0.3 - 16
kontrol("Dişli B cıvatası M3×16: uç somunun öbür yüzünü geçer", -9.5 - uc_b, lambda v: v >= 0.5)
kontrol("Dişli B cıvatası M3×16: uç ↔ kulak levhası arka yüzü (taşmaz)", uc_b - (G.Y_TUT_KULAK - G.T_TUT_KULAK),
        lambda v: v >= 0)

print("\n=== DAYANIM (servo DURMA torkunda, yani en kötü durumda; PLA, katman yönü dahil) ===")
# PLA: katman içinde ~50 MPa, katmanlar arası ~25 MPa çekme (tipik). Emniyet için izin verilen 10 MPa alındı.
PLA_IZIN = 10.0
MG_DURMA_NM = 9.4 * 0.0980665
SG_DURMA_NM = 1.8 * 0.0980665        # yüksek değer (en kötü durum için)
# 1) Tutucu dişlisi, Lewis: σ = F / (b · m · Y), z = 16 için Y ≈ 0,296
F_dis = SG_DURMA_NM / (G.DIS_M * G.DIS_Z / 2 / 1000)
s_dis = F_dis / (G.DIS_T * G.DIS_M * 0.296)
kontrol("Tutucu dişli kökü eğilme gerilmesi (SG90 durma torku)", s_dis, lambda v: v <= PLA_IZIN, "MPa",
        f"F = {F_dis:.0f} N; baskıda düz yatar, diş katman içinde")
# 2) Horn vidaları: tork en az 2 vidayla, oluk ortası yarıçapta; vida PLA'ya yatak gerilmesi (Ø3 × levha)
for ad, desen, tork, t in (("MG çatal (J2/J3)", G.HORN_MG, MG_DURMA_NM, G.T_CATAL),
                           ("SG bilek (J5)", G.HORN_SG, SG_DURMA_NM, G.T_CATAL_SG)):
    r = (desen["r0"] + desen["r1"]) / 2 / 1000
    F = tork / (2 * r)
    s_v = F / (min(desen["en"], 3.0) * t)
    kontrol(f"{ad} horn vidası PLA yatak gerilmesi (2 vida)", s_v, lambda v: v <= PLA_IZIN, "MPa", f"vida başına {F:.0f} N")
# 3) Üst kol A levhası: durma torku horn'dan köprüye levha düzleminde eğilme (en kesit: 34 × 5, pencere düşülür)
# pencereli kesitte iki şerit (HAFIF_PAY genişlik) kenarlarda: atalet ≈ 2·t·p·(d/2)², d ≈ en − p
en = G.UST_X[1] - G.UST_X[0]
I = 2 * (G.T_CATAL * G.HAFIF_PAY ** 3 / 12 + G.T_CATAL * G.HAFIF_PAY * ((en - G.HAFIF_PAY) / 2) ** 2)
s_lev = MG_DURMA_NM * 1000 * (en / 2) / I
kontrol("Üst kol A levhası pencereli kesitte eğilme (J2 durma torku)", s_lev, lambda v: v <= PLA_IZIN, "MPa",
        "yan yatık baskı: gerilme katman düzleminde")
# 4) Karşı yatak burcu: kol ağırlığının yarısı + yük, M3 cıvata üzerinde PLA burç yatak gerilmesi
F_b = (0.35 * 9.81) / 2
s_b = F_b / (G.VIDA_D * G.T_CATAL)
kontrol("J2 burç ↔ cıvata yatak gerilmesi (statik)", s_b, lambda v: v <= PLA_IZIN, "MPa", f"{F_b:.1f} N")

print("\n=== BASKI (tabla 220×220×250, en uygun yön) ===")
TABLA = sorted(G.BASKI_TABLA)
PLA, DOLGU = 1.24, 0.6
kutle = {}
for ad, f in P.PARCALAR.items():
    k = f()
    bb = k.BoundingBox()
    d = sorted([bb.xlen, bb.ylen, bb.zlen])
    sig = all(d[i] <= TABLA[i] for i in range(3))
    g = k.Volume() / 1000 * PLA * DOLGU * P.ADET.get(ad, 1)
    kutle[ad] = g
    kontrol(f"{ad} ({d[2]:.0f}×{d[1]:.0f}×{d[0]:.0f}) tablaya sığar", d[2], lambda v, s=sig: s)
toplam_g = sum(kutle.values())
kontrol("Toplam baskı kütlesi (PLA, %60 doluluk varsayımı)", toplam_g, None, "g", "dilimleyici kesinleştirir", bilgi=True)

print("\n=== STATİK TORK (eklem sınırları içinde en kötü poz, 50 g yük) ===")
import model as M
o = M.ogeler()
phi0 = M.phi0_bul()
# her öğenin kütlesi (kg) ve gövde çerçevesindeki ağırlık merkezi
km = []
for ad, g, k, tur in o:
    if tur == "parca":
        mk = k.Volume() / 1e6 * PLA * 1000 * DOLGU / 1000
    elif tur == "servo":
        mk = MG["KUTLE"] if ad in ("servo_J1", "servo_J2", "servo_J3") else SG["KUTLE"]
    else:
        mk = 0.002 if tur == "horn" else 0.0003
    cm = k.Center()
    km.append((ad, g, mk, cm))
YUK = 0.050
DURMA = {2: 9.4 * 0.0980665, 3: 9.4 * 0.0980665, 4: 1.2 * 0.0980665}   # gövde no → servo durma torku (4,8 V)
import cadquery as cq
from cadquery import Vector as V


def dunya(T, p):
    """Gövde çerçevesindeki nokta → dünya (x, y, z)."""
    return (T * cq.Location(p)).toTuple()[0]


en_kotu = {2: (0, None), 3: (0, None), 4: (0, None)}
L4_35 = G.L4_hesap(G.cene_aci(35, phi0))
for q2 in range(-75, 76, 15):
    for q3 in range(-80, 81, 20):
        for q5 in range(-90, 91, 30):
            T = M.cerceveler([0, q2, q3, 0, q5], 35, phi0)
            tcp = dunya(T[4], V(0, 0, L4_35))
            for b in (2, 3, 4):                  # b gövdesinin orijini = o eklemin ekseni
                ek = T[b].toTuple()[0]
                tork = sum(mk * 9.81 * (dunya(T[g], cm)[0] - ek[0]) for ad, g, mk, cm in km if g >= b) / 1000
                tork += YUK * 9.81 * (tcp[0] - ek[0]) / 1000
                if abs(tork) > en_kotu[b][0]:
                    en_kotu[b] = (abs(tork), (q2, q3, q5))
for b, ad in ((2, "J2 omuz (MG996R)"), (3, "J3 dirsek (MG996R)"), (4, "J5 bilek eğim (SG90)")):
    t, poz = en_kotu[b]
    oran = t / DURMA[b] * 100
    kontrol(f"{ad} en kötü tork / durma torku", oran, lambda v: v <= 75, "%",
            f"{t:.3f} N·m @ J2,J3,J5={poz}; sürekli <%50 önerilir")
hareketli = sum(mk for ad, g, mk, cm in km if g >= 1)
kontrol("Hareketli kütle (gövde ve üstü, yük hariç)", hareketli * 1000, None, "g", bilgi=True)

print("\n=== DEVRİLME (taban masaya vidalanmazsa) ===")
# Bütün kütlelerin (taban dahil) yatay ağırlık merkezi taban levhasının dışına çıkarsa kol devrilir.
en_r, en_poz = 0.0, None
for q2 in range(-75, 76, 15):
    for q3 in range(-80, 81, 20):
        for q5 in range(-90, 91, 45):
            T = M.cerceveler([0, q2, q3, 0, q5], 35, phi0)
            mx = my = mt = 0.0
            for ad, g, mk, cm in km:
                p = dunya(T[g], cm)
                mx += mk * p[0]
                my += mk * p[1]
                mt += mk
            tcp = dunya(T[4], V(0, 0, L4_35))
            mx += YUK * tcp[0]
            my += YUK * tcp[1]
            mt += YUK
            r = math.hypot(mx / mt, my / mt)
            if r > en_r:
                en_r, en_poz = r, (q2, q3, q5)
kontrol("En kötü pozda ağırlık merkezi ↔ taban kenarı (50 g yükle)", G.TABAN_R - en_r, None, "mm",
        f"AM eksenden {en_r:.0f} mm @ J2,J3,J5={en_poz}; negatifse devrilir", bilgi=True)
toplam_kg = sum(mk for ad, g, mk, cm in km) + YUK
# taban merkezine m kg eklenirse AM = toplam·r / (toplam + m) ≤ TABAN_R − 5 (pay)
sinir = G.TABAN_R - 5
gerekli = max(0.0, toplam_kg * en_r / sinir - toplam_kg)
kontrol("Vidalamadan devrilmemek için taban merkezine eklenecek kütle", gerekli * 1000, None, "g",
        "ya da 3 delikten masaya / tahtaya vidala (önerilen)", bilgi=True)

print("\n=== KİNEMATİK ÖLÇÜLER (sim/servo_model.py ile karşılaştır) ===")
L4 = G.L4_hesap(G.cene_aci(35, phi0))
for ad, v in (("H0", G.H0), ("L2", G.L2), ("L3", G.L3), ("L4 (tutucu 35°)", L4)):
    kontrol(ad, v, None, bilgi=True)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sim"))
try:
    import servo_model as sm
    o_ = sm.Olcu()
    for ad, a_, b_ in (("H0", o_.H0 * 1000, G.H0), ("L2", o_.L2 * 1000, G.L2), ("L3", o_.L3 * 1000, G.L3),
                       ("L4", o_.L4 * 1000, L4)):
        kontrol(f"sim modeli {ad} = tasarım", a_ - b_, lambda v: abs(v) <= 0.5, aciklama=f"model {a_:.1f}, tasarım {b_:.1f}")
except ImportError:
    pass

kalan = [a for a, ok in sonuc if not ok]
print(f"\n{len(sonuc) - len(kalan)}/{len(sonuc)} GEÇTİ" + (f" — KALAN: {', '.join(kalan)}" if kalan else ""))
sys.exit(1 if kalan else 0)
