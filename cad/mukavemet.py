"""Servo kol — mukavemet (statik) hesabı. Yükler CAD'den: her parçanın kütlesi ve ağırlık merkezi model.py'den.
python mukavemet.py      → konsol özeti + MUKAVEMET.md raporu; bir kesit izin değerini aşarsa çıkış kodu 1.

Yöntem (el hesabı, kiriş/levha teorisi; FEA değil):
  1. Yük durumları: YD1 yerçekimi + 50 g yük × dinamik çarpan 1,5; YD2 200 g aşırı yük (statik);
     YD3 servo DURMA torku (kol bir engele takılı, servo tam güç); YD4 tutucu sıkma (SG90 durma torku).
  2. YD1/YD2'de eklem sınırları içindeki pozlar taranır; her eklemde uç taraftaki kütlelerden
     kuvvet F ve moment M (eklem noktasına göre) bulunur. M'nin eklem eksenine izdüşümü servo torku,
     F ise çatalın A (horn) ve B (burç) levhalarına moldan/kaldıraçla paylaştırılır.
  3. Kritik kesitlerde σ = M·c/I (+ N/A), burulmada τ = T/(α·b·t²); delik/oluk yakınında Kt. Gerilmenin baskı
     katmanına göre yönü (katman içi / katmanlar arası) parçanın baskı yönünden belirlenir.
  4. İzin değeri = dayanım / emniyet katsayısı.
Kaynaklar: PLA — Prusament PLA veri sayfası v1.1 (akma 51 MPa yatay, katmanlar arası yapışma 17 ± 3 MPa,
E 2,3 GPa). MG996R — TowerPro veri sayfası (9,4 kgf·cm @4,8 V, 11 @6 V, ölü bant 5 µs); bir satıcı 13 kgf·cm
diyor, hesapta en kötüsü (13) kullanıldı. SG90 — 1,8 kgf·cm (TowerPro).
"""
import math
import os
import sys

import cadquery as cq
from cadquery import Vector as V

import geometri as G
import model as M

KOK = os.path.dirname(os.path.abspath(__file__))
g = 9.81
KGFCM = 0.0980665

# ----------------------------------------------------------------- malzeme ve emniyet
PLA_ICI = 51.0          # MPa, katman içi (akma)
PLA_ARASI = 17.0        # MPa, katmanlar arası yapışma (en zayıf yön)
E_PLA = 2300.0          # MPa
EK = 3.0                # emniyet katsayısı (bilinmeyen filament + baskı kalitesi + yorulma payı)
IZIN = {"içi": PLA_ICI / EK, "arası": PLA_ARASI / EK}
SUNME_SINIR = 0.25      # sürekli (tutma) yükte gerilme / dayanım oranı üst sınırı (PLA sünmesi; TAHMİN, genel kural)
CELIK_IZIN = 200.0      # MPa, M3 8.8 cıvata için kaba izin (eğilme)

T_MG = 13.0 * KGFCM     # N·m, en kötü (satıcı beyanı); veri sayfası 11 @6 V
T_SG = 1.8 * KGFCM
YUK1, DAF = 0.050, 1.5
YUK2 = 0.200

# Baskı yönleri (baski.py): katman düzlemine dik eksen = baskıda "yukarı"
BASKI_YUKARI = {"taban": "z", "govde": "z", "ust_kol": "x", "on_kol": "x", "bilek": "z",
                "tutucu_govde": "z", "cene_A": "y", "cene_B": "y"}


def yon(parca, gerilme_ekseni):
    """Normal gerilme ekseni baskı yukarı ekseniyle aynıysa katmanlar arası, değilse katman içi."""
    return "arası" if BASKI_YUKARI[parca] == gerilme_ekseni else "içi"


# ----------------------------------------------------------------- CAD'den kütleler
def kutleler(o):
    PLA, DOLGU = 1.24, 0.6
    km = []
    for ad, gv, k, tur in o:
        if tur == "parca":
            m = k.Volume() / 1e6 * PLA * DOLGU          # kg (cm³ → g → kg)
        elif tur == "servo":
            m = G.MG["KUTLE"] if ad in ("servo_J1", "servo_J2", "servo_J3") else G.SG["KUTLE"]
        else:
            m = 0.002 if tur == "horn" else 0.0003
        km.append((ad, gv, m, k.Center()))
    return km


def dunya(T, p):
    return V(*(T * cq.Location(p)).toTuple()[0])


def eksen(T, e):
    o = dunya(T, V(0, 0, 0))
    return dunya(T, V(*e)) - o


# ----------------------------------------------------------------- eklem tepkileri
def eklem_yukleri(km, phi0, yuk, carpan):
    """Eklem sınırları içinde pozlar taranır. Döner: {eklem: en kötü değerler sözlüğü}."""
    L4 = G.L4_hesap(G.cene_aci(35, phi0))
    EK_GOVDE = {"J2": 2, "J3": 3, "J5": 4}
    YA = {"J2": (G.CATAL_A[0] + G.CATAL_A[1]) / 2, "J3": (G.CATAL_A[0] + G.CATAL_A[1]) / 2,
          "J5": (G.CATAL5_A[0] + G.CATAL5_A[1]) / 2}
    YB = {"J2": (G.CATAL_B[0] + G.CATAL_B[1]) / 2, "J3": (G.CATAL_B[0] + G.CATAL_B[1]) / 2,
          "J5": (G.CATAL5_B[0] + G.CATAL5_B[1]) / 2}
    sonuc = {k: dict(T=0.0, F=0.0, FA=0.0, FB=0.0, Fx=0.0, poz=None, Tpoz=None) for k in EK_GOVDE}
    sonuc["J1"] = dict(Mdev=0.0, F=0.0, poz=None)
    for q2 in range(-75, 76, 15):
        for q3 in range(-80, 81, 20):
            for q5 in range(-90, 91, 30):
                q = [0, q2, q3, 0, q5]
                T = M.cerceveler(q, 35, phi0)
                tcp = dunya(T[4], V(0, 0, L4))
                noktalar = [(gv, m, dunya(T[gv], c)) for ad, gv, m, c in km]
                # J1: devrilme momenti (gövde ve üstü) disk/horn düzleminde
                o1 = V(0, 0, G.J1_HORN_UST)
                Mx = My = 0.0
                Ft = 0.0
                for gv, m, p in noktalar:
                    if gv >= 1:
                        Ft += m * g * carpan
                        Mx += m * g * carpan * (p.y - o1.y)
                        My += m * g * carpan * (p.x - o1.x)
                Ft += yuk * g * carpan
                Mx += yuk * g * carpan * (tcp.y - o1.y)
                My += yuk * g * carpan * (tcp.x - o1.x)
                Md = math.hypot(Mx, My)
                if Md > sonuc["J1"]["Mdev"]:
                    sonuc["J1"].update(Mdev=Md, F=Ft, poz=(q2, q3, q5))
                for ek, b in EK_GOVDE.items():
                    o = dunya(T[b], V(0, 0, 0))
                    ey, ex, ez = eksen(T[b], (0, 1, 0)), eksen(T[b], (1, 0, 0)), eksen(T[b], (0, 0, 1))
                    F = V(0, 0, 0)
                    Mo = V(0, 0, 0)
                    ym = 0.0
                    mt = 0.0
                    for gv, m, p in noktalar:
                        if gv >= b:
                            f = V(0, 0, -m * g * carpan)
                            F = F + f
                            Mo = Mo + (p - o).cross(f)
                            ym += m * (p - o).dot(ey)
                            mt += m
                    f = V(0, 0, -yuk * g * carpan)
                    F = F + f
                    Mo = Mo + (tcp - o).cross(f)
                    ym += yuk * (tcp - o).dot(ey)
                    mt += yuk
                    Tq = abs(Mo.dot(ey)) / 1000                      # N·m (mm·N → N·m)
                    # kuvvetin A / B levhasına paylaşımı (y konumuna göre kaldıraç) + eksene dik momentin çifti
                    yc = ym / mt
                    ya, yb = YA[ek], YB[ek]
                    pay_a = (yc - yb) / (ya - yb)
                    Mperp = Mo - ey * Mo.dot(ey)
                    cift = Mperp.Length / (ya - yb)                  # N
                    FA = F.Length * abs(pay_a) + cift
                    FB = F.Length * abs(1 - pay_a) + cift
                    Fx = abs(F.dot(ex))                              # kol doğrultusuna dik (yanal) bileşen
                    s = sonuc[ek]
                    if Tq > s["T"]:
                        s.update(T=Tq, Tpoz=q)
                    if F.Length > s["F"]:
                        s.update(F=F.Length, poz=q)
                    s["FA"] = max(s["FA"], FA)
                    s["FB"] = max(s["FB"], FB)
                    s["Fx"] = max(s["Fx"], Fx)
    return sonuc


# ----------------------------------------------------------------- kesit yardımcıları
def dikdortgen_W(b, h):
    """Eğilme direnç momenti: h eğilme doğrultusundaki boyut."""
    return b * h * h / 6


def burulma_tau(T_Nm, b, t):
    """Dikdörtgen kesit burulması (b ≥ t): τ = T / (α b t²), α ≈ (1 − 0,63 t/b) / 3."""
    a = (1 - 0.63 * t / b) / 3
    return T_Nm * 1000 / (a * b * t * t)


# ----------------------------------------------------------------- kesit listesi
def kesitler(Y1, Y2):
    """Her kesit: (ad, parça, gerilme ekseni, sürekli mi, σ_YD (MPa) sözlüğü, açıklama)."""
    K = []
    J2, J3, J5, J1 = Y1["J2"], Y1["J3"], Y1["J5"], Y1["J1"]
    J2b, J3b, J5b, J1b = Y2["J2"], Y2["J3"], Y2["J5"], Y2["J1"]

    def ekle(ad, parca, eks, Kt, s_yuk, s_durma, aciklama, surekli=True):
        K.append(dict(ad=ad, parca=parca, yon=yon(parca, eks), Kt=Kt, yd=s_yuk, durma=s_durma,
                      surekli=surekli, aciklama=aciklama))

    # S1 üst kol A levhası, horn halkasının hemen dışı (z = 18): servo torku + A kuvvetinin kolu
    b, t = G.UST_X[1] - G.UST_X[0], G.T_CATAL
    W = dikdortgen_W(t, b)
    f = lambda T, FA: (T * 1000 + FA * 18) / W
    ekle("S1 Üst kol A levhası, horn çevresi (z=18)", "ust_kol", "z", 1.5,
         max(f(J2["T"], J2["FA"]), f(J2b["T"], J2b["FA"])), f(T_MG, 0), "eğilme, levha düzleminde; yakında oluklar (Kt 1,5)")
    # S2 üst kol, hafifletme penceresi kesiti: iki levha × iki şerit
    p, en = G.HAFIF_PAY, G.UST_X[1] - G.UST_X[0]
    d = (en - p) / 2
    I = 4 * (t * p ** 3 / 12 + t * p * d * d)
    f2 = lambda Mn: Mn * 1000 * (en / 2) / I
    ekle("S2 Üst kol pencereli kesit (iki levha)", "ust_kol", "z", 1.3, max(f2(J2["T"]), f2(J2b["T"])), f2(T_MG),
         "eğilme; pencere köşeleri 45° (Kt 1,3)")
    # S3 köprüler burulması: eklem momenti köprü boyunca (y) burulma olarak A levhasına (horn) geçer.
    # Kötümser: momentin TAMAMI tek köprüden geçer. Kayma katman ara yüzünde (katmanlar ⊥ x) → katmanlar arası, √3·τ
    import parcalar as P
    kb = G.KOPRU_R[1] - G.KOPRU_R[0]
    tau = lambda Mn, b, t_: burulma_tau(Mn, b, t_) * math.sqrt(3)
    ekle("S3 Üst kol köprü 1 burulması (J2 momenti)", "ust_kol", "x", 1.2,
         max(tau(J2["T"], en, kb), tau(J2b["T"], en, kb)), tau(T_MG, en, kb), "tamamı tek köprüden (kötümser)")
    kb2 = P.UST_KOPRU2[1] - P.UST_KOPRU2[0]
    ekle("S3b Üst kol köprü 2 burulması (J3 tepkisi)", "ust_kol", "x", 1.2,
         max(tau(J3["T"], en, kb2), tau(J3b["T"], en, kb2)), tau(T_MG, en, kb2), "J3 servo tepki torku kulak levhasından çatala")
    bon = G.ON_X[1] - G.ON_X[0]
    ekle("S3c Ön kol köprüsü burulması (J3 momenti)", "on_kol", "x", 1.2,
         max(tau(J3["T"], bon, kb), tau(J3b["T"], bon, kb)), tau(T_MG, bon, kb), "kutu kirişten A levhasına, tamamı")
    # S4 üst kol J3 kulak levhası tabanı: J3 servo tepki torku
    ekle("S4 Üst kol J3 kulak levhası tabanı", "ust_kol", "z", 1.5,
         max(J3["T"], J3b["T"]) * 1000 / dikdortgen_W(G.T_KULAK, en), T_MG * 1000 / dikdortgen_W(G.T_KULAK, en),
         "servo kulaklarından gelen tepki torku, levha düzleminde eğilme")
    # S5 üst kol J3 yanağı: B kuvveti, köprü 2'ye 49 mm kol
    kol = G.L2 - 71.0
    Wy = dikdortgen_W(G.Y_YANAK[1] - G.Y_YANAK[0], en)
    ekle("S5 Üst kol J3 yanağı (burç kuvveti)", "ust_kol", "z", 2.0, max(J3["FB"], J3b["FB"]) * kol / Wy,
         (T_MG / (G.L3 / 1000) / 2) * kol / Wy, "oluklu cıvata deliği (Kt 2)")
    # S6 ön kol A levhası, horn çevresi
    b6 = G.ON_X[1] - G.ON_X[0]
    W6 = dikdortgen_W(t, b6)
    f6 = lambda T, FA: (T * 1000 + FA * 18) / W6
    ekle("S6 Ön kol A levhası, horn çevresi", "on_kol", "z", 1.5, max(f6(J3["T"], J3["FA"]), f6(J3b["T"], J3b["FA"])),
         f6(T_MG, 0), "eğilme, levha düzleminde")
    # S7 ön kol kutu kiriş: yan duvarlar (flanş) + kulak duvarı ve yanak (gövde)
    yk0, yk1 = G.Y_KULAK5 - G.T_KULAK_SG, G.Y_KULAK5
    ya, yb = G.Y_YANAK5
    bb = -G.ON_X[0]
    fl_t, fl_w = G.ONKOL_DUVAR, yk1 - ya
    I7 = 2 * (fl_w * fl_t ** 3 / 12 + fl_w * fl_t * (bb - fl_t / 2) ** 2) + \
        ((yk1 - yk0) + (yb - ya)) * (2 * bb) ** 3 / 12
    f7 = lambda Mn: Mn * 1000 * bb / I7
    ekle("S7 Ön kol kutu kiriş", "on_kol", "z", 1.2, max(f7(J3["T"]), f7(J3b["T"])), f7(T_MG),
         "J3 ile J5 arası; en büyük moment J3'te")
    # S8 gövde kulak levhası tabanı: J2 tepki torku + A kuvveti × eksen yüksekliği (gövde diskte basılır → katmanlar arası)
    hz = G.H0 - G.DISK_Z1
    W8 = dikdortgen_W(G.T_KULAK, 44.0)
    f8 = lambda T, FA: (T * 1000 + FA * hz) / W8
    ekle("S8 Gövde kulak levhası tabanı", "govde", "z", 1.5, max(f8(J2["T"], J2["FA"]), f8(J2b["T"], J2b["FA"])),
         f8(T_MG, 0), "disk tablada basılır: z yönü gerilme katmanlar arası")
    # S9 gövde yanağı tabanı: B kuvveti × 40 mm
    W9 = dikdortgen_W(G.Y_YANAK[1] - G.Y_YANAK[0], 24.0)
    ekle("S9 Gövde yanağı tabanı (burç kuvveti)", "govde", "z", 1.5, max(J2["FB"], J2b["FB"]) * hz / W9,
         (T_MG / (G.L2 / 1000) / 2) * hz / W9, "katmanlar arası")
    # S10 gövde diski: devrilme momenti kulak levhası–yanak çiftiyle diske, oradan horn halkasına
    kol_cift = (G.Y_KULAK - G.T_KULAK / 2) - sum(G.Y_YANAK) / 2
    Fc = max(J1["Mdev"], J1b["Mdev"]) / kol_cift                           # N (M N·mm / mm)
    Mdisk = Fc * 10.0                                                       # yanak ↔ horn halkası ~10 mm
    W10 = dikdortgen_W(24.0, G.DISK_T)
    ekle("S10 Gövde diski (devrilme momenti)", "govde", "x", 1.5, Mdisk / W10, Mdisk / W10,
         "disk tablada: gerilme katman içinde")
    # S11 taban direkleri: J1 durma torku kulaklardan teğetsel kuvvet, 27 mm boy (dik basılır → katmanlar arası)
    r = [math.hypot(x, y) for x, y in ((-34.7, 5), (-34.7, -5), (14.0, 5), (14.0, -5))]
    Fk = T_MG * max(r) / sum(ri * ri for ri in r) * 1000                   # N
    h11 = G.J1_KULAK_Z - G.TABAN_T
    W11 = dikdortgen_W(9.5, 20.0)
    Fdev = max(J1["Mdev"], J1b["Mdev"]) / 48.75 / 2                         # N, devrilmeden kulak başına
    ekle("S11 Taban direkleri (J1 tepki)", "taban", "z", 1.5, Fdev * 2 / (9.5 * 20.0), Fk * h11 / W11,
         "durma: teğetsel kuvvet × direk boyu; yük: devrilmeden çekme")
    # S12 bilek A levhası (SG J5 torku), bilek ters basılır (katmanlar ⊥ z) → katmanlar arası
    W12 = dikdortgen_W(G.T_CATAL_SG, 2 * G.BILEK_A_EN)
    ekle("S12 Bilek A levhası (J5)", "bilek", "z", 1.5, max(J5["T"], J5b["T"]) * 1000 / W12, T_SG * 1000 / W12,
         "katmanlar arası")
    # S13 bilek B levhası: burç kuvveti, levha kökü
    W13 = dikdortgen_W(G.T_CATAL_SG, 2 * G.BILEK_B_EN)
    ekle("S13 Bilek B levhası (burç)", "bilek", "z", 2.0, max(J5["FB"], J5b["FB"]) * G.T_DONUS_KULAK_Z / W13,
         T_SG / 0.095 / 2 * G.T_DONUS_KULAK_Z / W13, "delik (Kt 2), katmanlar arası")
    # S14 çene kökü (SG90 durma ile sıkma)
    Fped = T_SG / ((G.CENE_L - G.PED_L / 2) / 1000)
    W14 = dikdortgen_W(G.DIS_T, G.CENE_EN)
    ekle("S14 Çene kökü (sıkma)", "cene_A", "x", 1.5, Fped * (G.CENE_L - G.PED_L / 2) / W14 * 0.5,
         Fped * (G.CENE_L - G.PED_L / 2) / W14, "düz basılır: katman içi", surekli=False)
    # S15 dişli kökü (Lewis)
    F_dis = T_SG / (G.DIS_M * G.DIS_Z / 2 / 1000)
    ekle("S15 Dişli kökü (Lewis)", "cene_A", "x", 1.0, F_dis * 0.5 / (G.DIS_T * G.DIS_M * 0.296),
         F_dis / (G.DIS_T * G.DIS_M * 0.296), "Y = 0,296 (z = 16); katman içi", surekli=False)
    # S16 dişli B göbeği / sütunu: diş kuvveti + çene tepkisi, Y boyunca konsol
    Fg = F_dis + Fped
    kol16 = 0.0 - G.Y_TUT_KULAK
    W16 = math.pi * (2 * G.TUTUCU_BOSS_R) ** 3 / 32 - math.pi * G.VIDA_D ** 3 / 32
    ekle("S16 Dişli B göbeği", "tutucu_govde", "y", 2.0, Fg * kol16 / W16 * 0.5, Fg * kol16 / W16,
         "tabanda basılır: Y yönü gerilme katman içi; somun yuvası (Kt 2)", surekli=False)
    return K


def baglantilar(Y1, Y2):
    """Bağlantılar: (ad, değer, izin, birim, açıklama)."""
    B = []
    J2, J5 = max(Y1["J2"]["FB"], Y2["J2"]["FB"]), max(Y1["J5"]["FB"], Y2["J5"]["FB"])
    # horn vidaları (2 vida varsayımı) PLA yatak
    r = (G.HORN_MG["r0"] + G.HORN_MG["r1"]) / 2 / 1000
    F = T_MG / (2 * r)
    B.append(("MG horn vidası PLA yatak gerilmesi (durma)", F / (3.0 * G.T_CATAL), IZIN["içi"], "MPa", f"vida başına {F:.0f} N"))
    r = (G.HORN_SG["r0"] + G.HORN_SG["r1"]) / 2 / 1000
    F = T_SG / (2 * r)
    B.append(("SG horn vidası PLA yatak gerilmesi (durma)", F / (2.0 * G.T_CATAL_SG), IZIN["içi"], "MPa", f"vida başına {F:.0f} N"))
    # MG kulak vidaları: servo tepki torku 4 vidaya (2 kol), Ø3 × 5 mm PLA
    F = T_MG / (G.MG["DELIK_ARA"] / 1000) / 2
    B.append(("MG kulak vidası PLA yatak gerilmesi (durma)", F / (3.0 * G.T_KULAK), IZIN["içi"], "MPa", f"vida başına {F:.0f} N"))
    # burç ↔ çatal B deliği (Ø6 × levha)
    B.append(("J2 burç yatak gerilmesi", J2 / (G.BURC_D * G.T_CATAL), IZIN["içi"], "MPa", f"F_B = {J2:.1f} N"))
    B.append(("J5 burç yatak gerilmesi", J5 / (G.BURC_D * G.T_CATAL_SG), IZIN["içi"], "MPa", f"F_B = {J5:.1f} N"))
    # M3 cıvata eğilmesi: kuvvet levha ortasında, kol = boşluk + levha/2 (diş dibi Ø2,39)
    kol = G.G_CATAL_MG + G.T_CATAL / 2
    s = 32 * J2 * kol / (math.pi * 2.39 ** 3)
    B.append(("J2/J3 M3 cıvata eğilmesi", s, CELIK_IZIN, "MPa", f"kol {kol:.1f} mm"))
    # sac vida sökülme kapasitesi (M3, PLA, 5 mm diş): F ≈ π·d·L·τ, τ ≈ 0,5·katman içi / EK
    kap = math.pi * 3.0 * G.T_KULAK * (0.5 * PLA_ICI / EK)
    dev = max(Y1["J1"]["Mdev"], Y2["J1"]["Mdev"]) / 48.75 / 2
    B.append(("J1 kulak vidası çekme (devrilme) / sökülme kapasitesi", dev, kap, "N", "taban direğinde 12 mm diş: daha da güvenli"))
    return B


def sehim(Y1, km):
    """Uç sehimi (yerçekimi + 50 g, kol yatay): üst kol ve ön kol kiriş eğilmesi. Servo boşluğuyla karşılaştırma."""
    p, en, t = G.HAFIF_PAY, G.UST_X[1] - G.UST_X[0], G.T_CATAL
    d = (en - p) / 2
    I2 = 4 * (t * p ** 3 / 12 + t * p * d * d)
    yk0, yk1 = G.Y_KULAK5 - G.T_KULAK_SG, G.Y_KULAK5
    ya, yb = G.Y_YANAK5
    bb = -G.ON_X[0]
    I3 = 2 * ((yk1 - ya) * G.ONKOL_DUVAR ** 3 / 12 + (yk1 - ya) * G.ONKOL_DUVAR * (bb - G.ONKOL_DUVAR / 2) ** 2) + \
        ((yk1 - yk0) + (yb - ya)) * (2 * bb) ** 3 / 12
    M2, M3 = Y1["J2"]["T"] * 1000, Y1["J3"]["T"] * 1000           # N·mm (kök momentleri)
    L2, L3, L4 = G.L2, G.L3, 95.0
    # her kirişte moment kökten uca doğrusal azalır varsayımı: θ = M L / (2EI), δ = M L² / (3EI)
    th2 = M2 * L2 / (2 * E_PLA * I2)
    d2 = M2 * L2 ** 2 / (3 * E_PLA * I2)
    th3 = M3 * L3 / (2 * E_PLA * I3)
    d3 = M3 * L3 ** 2 / (3 * E_PLA * I3)
    uc = d2 + th2 * (L3 + L4) + d3 + th3 * L4
    # servo ölü bandı: 5 µs; MG996R ~ 2000 µs / 180° → 11,1 µs/°
    olu = 5.0 / (2000 / 180)
    uc_olu = math.radians(olu) * (L2 + L3 + L4)
    return dict(I2=I2, I3=I3, uc=uc, olu_derece=olu, uc_olu=uc_olu)


def main():
    o = M.ogeler()
    phi0 = M.phi0_bul()
    km = kutleler(o)
    Y1 = eklem_yukleri(km, phi0, YUK1, DAF)
    Y2 = eklem_yukleri(km, phi0, YUK2, 1.0)
    K = kesitler(Y1, Y2)
    B = baglantilar(Y1, Y2)
    S = sehim(Y1, km)

    satir = []
    yaz = satir.append
    yaz("# Servo kol — mukavemet hesabı\n")
    yaz("`cad/mukavemet.py` üretir; yükler CAD'deki gerçek kütle ve ağırlık merkezlerinden. El hesabı (kiriş/levha "
        "teorisi), FEA değil. Kesitler bilerek kötümser seçildi.\n")
    yaz("## Varsayımlar\n")
    yaz(f"- **PLA:** katman içi akma {PLA_ICI:.0f} MPa, katmanlar arası yapışma {PLA_ARASI:.0f} MPa, E {E_PLA / 1000:.1f} GPa "
        "([Prusament PLA veri sayfası](https://www.matterhackers.com/r/xFvGl8)). Baskı hizmetinin filamenti bilinmiyor.")
    yaz(f"- **Emniyet katsayısı {EK:.0f}** → izin: katman içi {IZIN['içi']:.1f} MPa, katmanlar arası {IZIN['arası']:.1f} MPa. "
        "Delik/oluk/köşe yakınında gerilme ayrıca Kt ile çarpıldı.")
    yaz(f"- **Servo torku:** MG996R {T_MG:.2f} N·m (13 kgf·cm, satıcı beyanlarının en yükseği; veri sayfası 9,4 @4,8 V, 11 @6 V — "
        "[TowerPro](https://courses.ece.cornell.edu/ece5990/ECE5725_Spring2020_Projects/May_15_Demo/Smart%20Lock/W_pp445_yl656/datasheet/MG996R_Tower-Pro.pdf)), "
        f"SG90 {T_SG:.3f} N·m (1,8 kgf·cm).")
    yaz(f"- **Yük durumları:** YD1 yerçekimi + {YUK1 * 1000:.0f} g yük × dinamik çarpan {DAF}; YD2 {YUK2 * 1000:.0f} g aşırı yük "
        "(statik); ikisinde de eklem sınırları içindeki pozlar (J2 ±75°, J3 ±80°, J5 ±90°) 15–30° adımla tarandı. "
        "**Durma:** kol bir engele takılı ve servo tam güçte (parçanın göreceği en büyük tork).")
    yaz(f"- **Sünme:** sürekli tutma yükünde gerilme dayanımın %{SUNME_SINIR * 100:.0f}'ini geçmesin (genel kural, TAHMİN).\n")

    yaz("## Eklem tepkileri (CAD kütleleriyle)\n")
    yaz("| Eklem | YD1 tork (N·m) | YD2 tork (N·m) | Kuvvet YD1 / YD2 (N) | A levhası / servo mili (N) | B levhası / burç (N) | En kötü poz (J2, J3, J4, J5) |")
    yaz("|---|---|---|---|---|---|---|")
    for ek in ("J2", "J3", "J5"):
        a, b = Y1[ek], Y2[ek]
        yaz(f"| {ek} | {a['T']:.3f} | {b['T']:.3f} | {a['F']:.2f} / {b['F']:.2f} | {max(a['FA'], b['FA']):.2f} | "
            f"{max(a['FB'], b['FB']):.2f} | {tuple(a['Tpoz'][1:])} |")
    yaz(f"| J1 | devrilme momenti {Y1['J1']['Mdev'] / 1000:.3f} / {Y2['J1']['Mdev'] / 1000:.3f} N·m | | {Y1['J1']['F']:.2f} / "
        f"{Y2['J1']['F']:.2f} | | | {Y1['J1']['poz']} |")
    yaz("")
    oran_mg = Y1["J2"]["T"] / (9.4 * KGFCM)
    yaz(f"Omuz servosu YD1'de veri sayfası durma torkunun %{oran_mg * 100:.0f}'ini görüyor (dinamik çarpan dahil). "
        "Servo mili radyal yükü A levhası sütunundaki kuvvet; MG996R için radyal yük sınırı yayımlanmamış, değerler küçük.\n")

    yaz("## Kesitler\n")
    yaz("| Kesit | Yön | Kt | YD1/YD2 σ (MPa) | Durma σ (MPa) | İzin (MPa) | Emniyet (durma) | Sürekli yük / dayanım | Sonuç |")
    yaz("|---|---|---|---|---|---|---|---|---|")
    hatalar = []
    for k in K:
        iz = IZIN[k["yon"]]
        s1, s3 = k["yd"] * k["Kt"], k["durma"] * k["Kt"]
        dayanim = PLA_ICI if k["yon"] == "içi" else PLA_ARASI
        sn = s1 / dayanim if k["surekli"] else 0.0
        emn = (dayanim / s3) if s3 > 0 else float("inf")
        ok = s3 <= iz and s1 <= iz and sn <= SUNME_SINIR
        if not ok:
            hatalar.append(k["ad"])
        yaz(f"| {k['ad']} | katman{' ' + k['yon']} | {k['Kt']} | {s1:.2f} | {s3:.2f} | {iz:.1f} | {emn:.1f} | "
            f"{'%' + format(sn * 100, '.1f') if k['surekli'] else '–'} | {'✅' if ok else '❌'} |")
    yaz("\nEmniyet (durma) = dayanım / (Kt × durma gerilmesi): servo tam güçle zorlasa bile kalan pay.\n")

    yaz("## Bağlantılar\n")
    yaz("| Bağlantı | Değer | İzin / kapasite | Sonuç | Not |")
    yaz("|---|---|---|---|---|")
    for ad, v, iz, birim, notu in B:
        ok = v <= iz
        if not ok:
            hatalar.append(ad)
        yaz(f"| {ad} | {v:.2f} {birim} | {iz:.1f} {birim} | {'✅' if ok else '❌'} | {notu} |")

    yaz("\n## Sehim ve hassasiyet\n")
    yaz(f"- Kol yatay uzanmışken (YD1) üst kol + ön kol eğilmesinden uçta **{S['uc']:.3f} mm** sehim "
        f"(üst kol I = {S['I2']:.0f} mm⁴, ön kol I = {S['I3']:.0f} mm⁴, E = {E_PLA / 1000:.1f} GPa).")
    yaz(f"- Karşılaştırma: MG996R ölü bandı 5 µs ≈ {S['olu_derece']:.2f}° → uçta tek bir eklemden **{S['uc_olu']:.1f} mm**. "
        "Yani hassasiyeti parçaların esnemesi değil, servoların ölü bandı ve dişli boşluğu belirliyor.\n")

    yaz("## Taşıma kapasitesi: sınırı servo koyuyor\n")
    durma48 = 9.4 * KGFCM
    yaz(f"- Kol tam uzanıkken (omuz 75°) omuz servosu: 50 g yükte statik {Y1['J2']['T'] / DAF / durma48 * 100:.0f}%, "
        f"dinamik çarpanla {Y1['J2']['T'] / durma48 * 100:.0f}% · 200 g yükte {Y2['J2']['T'] / durma48 * 100:.0f}% "
        "(veri sayfası durma torku 9,4 kgf·cm @4,8 V'a göre).")
    yaz("- Yani **200 g kol tam uzanıkken kaldırılamaz**, parçalar sağlam kalsa bile servo durur. Önerilen yük ~50 g; "
        "kola yakın çalışırken daha fazlası mümkün. Simülasyondaki tork göstergesi pozdaki gerçek oranı verir.\n")
    yaz("## En kritik yerler\n")
    kritik = sorted(((k["durma"] * k["Kt"] / IZIN[k["yon"]], k["ad"], k["yon"]) for k in K), reverse=True)[:3]
    for oran, ad, yn in kritik:
        yaz(f"- {ad}: durma torkunda gerilme / izin = %{oran * 100:.0f} (katman{' ' + yn}).")
    yaz("- Köprüler 10 mm: eklem momenti köprüden burulmayla geçiyor ve bu kayma yan yatık baskıda katmanlar arasına düşüyor. "
        "Kolları **en az 4 duvarla** bastır; dolgulu köprü kapalı kabuk gibi çalışır.")
    yaz("- Baskı kesitlerinden önce kopma ihtimali olanlar satın alınan parçalar: **plastik horn'ların 25T dişi** "
        "(MG996R durma torkunda sıyırabilir; metal 25T disk horn bu riski kaldırır) ve **horn'u parçaya bağlayan küçük sac "
        "vidalar**. Servo milinin radyal yük sınırı yayımlanmamış; karşı yatak sayesinde mil yalnız A levhası payını taşıyor.\n")
    yaz("**Doğrulanmayanlar:** gerçek filament ve baskı kalitesi, katman yapışması (veri sayfasındaki değerden düşük olabilir), "
        "yorulma ve sünme; bunlar emniyet katsayısıyla karşılanmaya çalışıldı, ilk montajda gözle kontrol gerekir.")

    rapor = "\n".join(satir) + "\n"
    with open(os.path.join(KOK, "MUKAVEMET.md"), "w", encoding="utf-8") as f:
        f.write(rapor)
    # konsol özeti
    print(f"Eklem torkları YD1: J2 {Y1['J2']['T']:.3f}, J3 {Y1['J3']['T']:.3f}, J5 {Y1['J5']['T']:.3f} N·m · "
          f"J1 devrilme {Y1['J1']['Mdev'] / 1000:.3f} N·m")
    for k in K:
        iz = IZIN[k["yon"]]
        s3 = k["durma"] * k["Kt"]
        print(f"  {k['ad']:44s} katman {k['yon']:6s} YD {k['yd'] * k['Kt']:5.2f}  durma {s3:5.2f} / izin {iz:4.1f} MPa")
    for ad, v, iz, birim, notu in B:
        print(f"  {ad:58s} {v:7.2f} / {iz:6.1f} {birim}")
    print(f"  uç sehimi {S['uc']:.3f} mm · ölü bant tek eklem {S['uc_olu']:.1f} mm")
    print(f"\n{'HEPSİ GEÇTİ' if not hatalar else 'KALAN: ' + ', '.join(hatalar)} → MUKAVEMET.md")
    return 1 if hatalar else 0


if __name__ == "__main__":
    sys.exit(main())
