"""Basılacak parçalar + servo/horn zarfları (CadQuery). Her parça kendi gövde çerçevesinde kurulur
(model.py çerçeveleri FK ile yerleştirir). Ölçüler: geometri.py.

Gövde çerçeveleri:
  taban   dünya                         gövde   J1 ile z ekseninde döner
  ust_kol J2 ekseni (0,0,H0) orijin; z kol boyunca, y eklem ekseni, x yanal (q=0'da ileri)
  on_kol  J3 ekseni orijin              bilek   J5 ekseni orijin; z alet ekseni
  tutucu  dönüş horn yüzü orijin; Z alet ekseni, X çene açılma yönü, Y dişli ekseni
  cene_A / cene_B  dişli merkezi orijin; çene +Z yönünde (açı 0)
"""
import math
import cadquery as cq
from cadquery import Vector as V
import geometri as G


# ----------------------------------------------------------------- temel katılar
def kutu(x, y, z):
    """x, y, z: (min, max) aralıkları."""
    return cq.Solid.makeBox(x[1] - x[0], y[1] - y[0], z[1] - z[0], pnt=V(x[0], y[0], z[0]))


_EKSEN = {"x": V(1, 0, 0), "y": V(0, 1, 0), "z": V(0, 0, 1)}


def sil(eksen, r, a, c=(0.0, 0.0)):
    """Silindir: eksen 'x'/'y'/'z' boyunca a=(min,max); c = diğer iki koordinat (x için (y,z), y için (x,z), z için (x,y))."""
    if eksen == "x":
        p = V(a[0], c[0], c[1])
    elif eksen == "y":
        p = V(c[0], a[0], c[1])
    else:
        p = V(c[0], c[1], a[0])
    return cq.Solid.makeCylinder(r, a[1] - a[0], pnt=p, dir=_EKSEN[eksen])


def oluk(eksen, r, a, c1, c2):
    """Uzun delik: eksen boyunca a aralığında, düzlemde c1→c2 arasında (iki silindir + kutu)."""
    s = sil(eksen, r, a, c1).fuse(sil(eksen, r, a, c2))
    d = (c2[0] - c1[0], c2[1] - c1[1])
    L = math.hypot(*d)
    if L < 1e-9:
        return s
    # düzlem içi dikdörtgen: önce eksene dik düzlemde kur, sonra döndür
    ang = math.degrees(math.atan2(d[1], d[0]))
    if eksen == "z":
        b = kutu((0, L), (-r, r), a).rotate(V(0, 0, 0), V(0, 0, 1), ang).translate(V(c1[0], c1[1], 0))
    elif eksen == "y":       # düzlem (x, z); x'ten z'ye açı = y ekseni etrafında −açı
        b = kutu((0, L), a, (-r, r)).rotate(V(0, 0, 0), V(0, 1, 0), -ang).translate(V(c1[0], 0, c1[1]))
    else:                    # düzlem (y, z)
        b = kutu(a, (0, L), (-r, r)).rotate(V(0, 0, 0), V(1, 0, 0), ang).translate(V(0, c1[0], c1[1]))
    return s.fuse(b)


def birlesik(*sekiller):
    s = sekiller[0]
    for t in sekiller[1:]:
        s = s.fuse(t)
    return s.clean()


def kes(s, *sekiller):
    for t in sekiller:
        s = s.cut(t)
    return s.clean()


def horn_baglanti(eksen, a, desen, merkez=(0.0, 0.0), ic=None):
    """Horn bağlantısı (kesilecek): merkez delik + radyal oluklar (+ ic=(yüz, +1/−1) verilirse göbek havşası).
    Düzlem açısı 0 = düzlemin 1. koordinatı (y ekseni için x, z ekseni için x)."""
    s = sil(eksen, desen["merkez"] / 2, a, merkez)
    if ic and desen.get("havsa"):
        d, h = desen["havsa"]
        aralik = (ic[0] - 0.01, ic[0] + h) if ic[1] > 0 else (ic[0] - h, ic[0] + 0.01)
        s = s.fuse(sil(eksen, d / 2, aralik, merkez))
    r = desen["en"] / 2
    for aci in desen["acilar"]:
        u, v = math.cos(math.radians(aci)), math.sin(math.radians(aci))
        p1 = (merkez[0] + desen["r0"] * u, merkez[1] + desen["r0"] * v)
        p2 = (merkez[0] + desen["r1"] * u, merkez[1] + desen["r1"] * v)
        s = s.fuse(oluk(eksen, r, a, p1, p2))
    return s


# ----------------------------------------------------------------- servo zarfları (servo yerel ekseninde)
def servo(S):
    """Servo zarfı: gövde + kulaklar + tümsek + mil (horn ayrı). Yerel: Zs mil, Xs uzun eksen, mil Xs=0."""
    x0, x1 = -(S["L"] - S["UC"]), S["UC"]
    w = S["W"] / 2
    g = kutu((x0, x1), (-w, w), (0, S["H"]))
    k_uzun = (S["KULAK_L"] - S["L"]) / 2
    kul = kutu((x0 - k_uzun, x1 + k_uzun), (-w, w), (S["KULAK_Z"], S["KULAK_Z"] + S["KULAK_T"]))
    tum = sil("z", S["TUMSEK_D"] / 2, (S["H"] - 0.01, S["TUMSEK_UST"]))
    mil = sil("z", S["MIL_D"] / 2, (S["TUMSEK_UST"] - 0.01, S["MIL_UST"]))
    return birlesik(g, kul, tum, mil)


def horn(S):
    """Horn süpürme zarfı (yerel servo ekseninde). Sürülen parçayla birlikte döner."""
    return sil("z", S["HORN_R"], (S["HORN_UST"] - S["HORN_T"], S["HORN_UST"]))


def yerlestir(sekil, Xs, Zs, o):
    """Servo yerel ekseni → çerçeve: Xs, Zs birim vektörler (tuple), Ys = Zs × Xs; o = servo taban-mil noktası."""
    X, Z = V(*Xs), V(*Zs)
    Y = Z.cross(X)
    from OCP.gp import gp_Trsf
    t = gp_Trsf()
    t.SetValues(X.x, Y.x, Z.x, o[0],
                X.y, Y.y, Z.y, o[1],
                X.z, Y.z, Z.z, o[2])
    return sekil.moved(cq.Location(t))


def servo_kulak_delikleri(S):
    """Kulak delik merkezleri (Xs, Ys) — yerel."""
    xc = (-(S["L"] - S["UC"]) + S["UC"]) / 2
    a = S["DELIK_ARA"] / 2
    if S is G.MG:
        e = S["DELIK_EN"] / 2
        return [(xc - a, -e), (xc - a, e), (xc + a, -e), (xc + a, e)]
    return [(xc - a, 0.0), (xc + a, 0.0)]


# ----------------------------------------------------------------- TABAN
def taban():
    S = G.MG
    zt = G.TABAN_T
    s = sil("z", G.TABAN_R, (0, zt))
    halka = sil("z", G.HALKA_RO, (zt - 0.01, G.HALKA_UST)).cut(sil("z", G.HALKA_RI, (0, G.HALKA_UST + 1)))
    x0, x1 = -(S["L"] - S["UC"]), S["UC"]          # J1 servo Xs → +x
    w = S["W"] / 2
    zk = G.J1_KULAK_Z
    direk1 = kutu((-G.HALKA_RI - 0.5, x0 - G.BOS), (-w, w), (zt - 0.01, zk))
    direk2 = kutu((x1 + G.BOS, 22.0), (-w, w), (zt - 0.01, zk))
    kaburga = kutu((21.0, G.HALKA_RI + 0.5), (-3, 3), (zt - 0.01, zk))
    s = birlesik(s, halka, direk1, direk2, kaburga)
    # J1 kulak vidaları: M3 sac/makine vidası doğrudan direğe (Ø2,6 pilot, 12 derin)
    for xs, ys in servo_kulak_delikleri(S):
        s = s.cut(sil("z", 1.3, (zk - 12, zk + 1), (xs, ys)))
    # kablo çıkışı (−x)
    s = s.cut(kutu((-G.HALKA_RO - 1, -G.HALKA_RI + 3), (-7, 7), (zt, zt + 13)))
    # masaya vidalama delikleri
    for a in (0, 120, 240):
        c = (G.TABAN_AYAK_R * math.cos(math.radians(a)), G.TABAN_AYAK_R * math.sin(math.radians(a)))
        s = s.cut(sil("z", 2.25, (-1, zt + 1), c))
    return s.clean()


# ----------------------------------------------------------------- baskı dostu levha
def pah45(s, xa, z_t, uc):
    """Yan yatık baskı (x = xa tablada): (xa, z_t) noktasından geçen 45° düzlemin tabla tarafını keser.
    uc='alt': −z yönündeki uç (kalan bölge x + z ≥ xa + z_t); uc='ust': +z ucu (x − z ≥ xa − z_t)."""
    kesici = kutu((-400, 0), (-400, 400), (-400, 400))
    kesici = kesici.rotate(V(0, 0, 0), V(0, 1, 0), -45 if uc == "alt" else 45).translate(V(xa, 0, z_t))
    return s.cut(kesici)


def uc_levha(y, x, z0, z1, R, uc, pah=True):
    """y'ye dik levha: x aralığında, z0..z1 gövde + yuvarlak uç (R, merkez (0, z0) 'alt' / (0, z1) 'ust').
    pah=True: tabla tarafındaki (x = x[0]) çeyrek yay yerine 45° pah (desteksiz basılır)."""
    xa, xb = x
    gov = kutu(x, y, (z0, z1))
    zc = z0 if uc == "alt" else z1
    zr = (zc - R - 1, zc) if uc == "alt" else (zc, zc + R + 1)
    s = gov.fuse(sil("y", R, y, (0, zc)).intersect(kutu(x, (y[0] - 1, y[1] + 1), zr)))
    if pah:
        d = math.sqrt(max(R * R - xa * xa, 0.0))
        s = pah45(s, xa, zc - d if uc == "alt" else zc + d, uc)
    return s


# ----------------------------------------------------------------- ortak: MG çatal eklem tutucusu
def _mg_tutucu(z_alt, z_eksen, kulak_x=(-17.0, 17.0), yanak_x=(-12.0, 12.0), ust_r=G.KULAK_LEVHA_R, pah=False,
               sarkma=0.0):
    """MG996R tutucu: kulak levhası (pencere + pilot delikler) + karşı yatak yanağı.
    Servo: Xs → +z (gövde aşağı sarkar), Zs → +y. z_eksen = eklem ekseni z'si (çerçevede).
    pah=True (yan yatık baskı): kulak levhası ucu pahlı, yanak düz kesik (yuvarlak uç yok → ince şerit kalmaz).
    sarkma: pencerenin baskıda köprü olan (+x) kenarına ek boşluk."""
    S = G.MG
    y0, y1 = G.Y_KULAK - G.T_KULAK, G.Y_KULAK
    lev = uc_levha((y0, y1), kulak_x, z_alt, z_eksen, ust_r, "ust", pah)
    x0, x1 = -(S["L"] - S["UC"]), S["UC"]
    w = S["W"] / 2 + G.BOS
    lev = lev.cut(kutu((-w, w + sarkma), (y0 - 1, y1 + 1), (z_eksen + x0 - G.BOS, z_eksen + x1 + G.BOS)))
    for xs, ys in servo_kulak_delikleri(S):      # Ys → x, Xs → z
        lev = lev.cut(sil("y", 1.3, (y0 - 1, y1 + 1), (ys, z_eksen + xs)))
    # yanak + karşı yatak: burç cıvatası için z yönünde oluk (±1,5), somun kanalı üstten
    ya, yb = G.Y_YANAK
    if pah:
        yan = kutu(yanak_x, (ya, yb), (z_alt, z_eksen + G.YANAK_UST))   # düz uçlu: köşe r = √(17² + 10²) ≈ 19,7
    else:
        yan = uc_levha((ya, yb), yanak_x, z_alt, z_eksen, max(-yanak_x[0], yanak_x[1]), "ust", False)
    yan = yan.cut(oluk("y", G.VIDA_D / 2, (ya - 1, yb + 1), (0, z_eksen - 1.5), (0, z_eksen + 1.5)))
    yc = (ya + yb) / 2
    yan = yan.cut(kutu((-G.SOMUN_YUVA / 2, G.SOMUN_YUVA / 2), (yc - G.SOMUN_YUVA_T / 2, yc + G.SOMUN_YUVA_T / 2),
                       (z_eksen - 1.5 - G.SOMUN_YUVA / 2 - 0.3, z_eksen + 30)))
    return lev, yan


def _mg_catal(x, desen, a_boy=None, b_boy=None, z_kopru=G.KOPRU_R):
    """Sürülen çatal (eksen orijinde, kol +z), yan yatık baskı için x aralığı sabit, uçlar pahlı.
    A levhası horn bağlantılı (+ iç yüzde göbek havşası), B levhası burç delikli, aralarında köprü."""
    a_boy = a_boy or z_kopru[1]
    b_boy = b_boy or z_kopru[1]
    A = uc_levha(G.CATAL_A, x, 0, a_boy, G.CATAL_R, "alt")
    A = A.cut(horn_baglanti("y", (G.CATAL_A[0] - 1, G.CATAL_A[1] + 1), desen, ic=(G.CATAL_A[0], +1)))
    B = uc_levha(G.CATAL_B, x, 0, b_boy, G.CATAL_R, "alt")
    B = B.cut(sil("y", G.BURC_DELIK / 2, (G.CATAL_B[0] - 1, G.CATAL_B[1] + 1)))
    K = kutu(x, (G.CATAL_B[1] - 0.01, G.CATAL_A[0] + 0.01), z_kopru)
    return birlesik(A, B, K)


# ----------------------------------------------------------------- GÖVDE (J1 üstü, J2 tutucu) — disk tablada
def govde():
    disk = sil("z", G.DISK_R, (G.DISK_Z0, G.DISK_Z1))
    disk = disk.cut(horn_baglanti("z", (G.DISK_Z0 - 1, G.DISK_Z1 + 1), G.HORN_MG_J1))
    lev, yan = _mg_tutucu(G.DISK_Z1 - 0.01, G.H0, kulak_x=(-22.0, 22.0), yanak_x=(-12.0, 12.0))
    return birlesik(disk, lev, yan)


# ----------------------------------------------------------------- ÜST KOL (J2 çatalı + J3 tutucu) — yan yatık
UST_KOPRU2 = (71.0, 76.0)


def ust_kol():
    L2 = G.L2
    x = G.UST_X
    catal = _mg_catal(x, G.HORN_MG, a_boy=UST_KOPRU2[1], b_boy=G.UST_B_BOY)
    k2 = kutu(x, (G.CATAL_B[1] - 0.01, G.CATAL_A[0] + 0.01), UST_KOPRU2)
    lev, yan = _mg_tutucu(UST_KOPRU2[0], L2, kulak_x=x, yanak_x=x, pah=True, sarkma=0.4)
    dolgu = kutu(x, (G.CATAL_B[1] - 0.01, G.Y_YANAK[0] + 0.01), (UST_KOPRU2[0], G.UST_B_BOY))
    s = birlesik(catal, k2, lev, yan, dolgu)
    # hafifletme: iki çatal levhasında köprüler arası pencere. Yan yatık baskıda üst kenarı köprü (28 mm),
    # alt/üst uçları 45° (sivri) → desteksiz
    p = G.HAFIF_PAY
    z0, z1 = G.KOPRU_R[1] + p, UST_KOPRU2[0] - p
    xa, xb = x[0] + p, x[1] - p
    for y in (G.CATAL_A, G.CATAL_B):
        s = s.cut(_hafif_pencere(y, (xa, xb), (z0, z1)))
    return s.clean()


def _hafif_pencere(y, x, z):
    """y'ye dik levhada pencere: dikdörtgen, z uçları 45° sivri (yan yatık baskıda kendini taşır)."""
    xa, xb = x
    h = (xb - xa) / 2
    xc = (xa + xb) / 2
    pts = [(xa, z[0] + h), (xc, z[0]), (xb, z[0] + h), (xb, z[1] - h), (xc, z[1]), (xa, z[1] - h)]
    if z[1] - z[0] < 2 * h:
        pts = [(xc, z[0]), (xb, (z[0] + z[1]) / 2), (xc, z[1]), (xa, (z[0] + z[1]) / 2)]
    w = cq.Workplane("XY").polyline(pts).close().extrude(y[1] - y[0] + 2).val()
    # (x, z) → XY'de (x, y=z); X ekseni etrafında +90° → (x, −z, y): y → z
    return w.rotate(V(0, 0, 0), V(1, 0, 0), 90).translate(V(0, y[1] + 1, 0))


# ----------------------------------------------------------------- ÖN KOL (J3 çatalı + J5 SG90 tutucu) — yan yatık
def on_kol():
    S = G.SG
    L3 = G.L3
    x = G.ON_X
    b = -G.ON_X[0]                                               # J5 ucunda yarı en (9,5)
    catal = _mg_catal(x, G.HORN_MG_ON)
    yk0, yk1 = G.Y_KULAK5 - G.T_KULAK_SG, G.Y_KULAK5            # kulak duvarı
    ya, yb = G.Y_YANAK5                                          # yanak
    z0 = G.KOPRU_R[1] - 0.01
    kd = uc_levha((yk0, yk1), (-b, b), z0, L3, G.ONKOL_UC_R, "ust")
    yd = uc_levha((ya, yb), (-b, b), z0, L3, b, "ust")
    on_kes = kutu((-b - 1, b + 1), (ya - 1, yk1 + 1), (L3, L3 + 20)).cut(sil("y", G.ONKOL_UC_R, (ya - 2, yk1 + 2), (0, L3)))
    yan_d = [kutu((b - G.ONKOL_DUVAR, b), (ya, yk1), (z0, L3 + 8.0)).cut(on_kes),
             kutu((-b, -b + G.ONKOL_DUVAR), (ya, yk1), (z0, L3 + 8.0)).cut(on_kes)]
    s = birlesik(catal, kd, yd, *yan_d)
    # SG90 penceresi (Ys → x, Xs → z) ve gövdenin geçtiği iç boşluk
    x0, x1 = -(S["L"] - S["UC"]), S["UC"]
    w = S["W"] / 2 + G.BOS
    s = s.cut(kutu((-w, w), (yb, yk1 + 1), (L3 + x0 - G.SG_YUZER, L3 + x1 + G.SG_YUZER)))
    for xs, ys in servo_kulak_delikleri(S):
        s = s.cut(sil("y", G.SG_PILOT / 2, (yk0 - 1, yk1 + 1), (ys, L3 + xs)))
    # J5 karşı yatak: z yönünde oluk ±0,8 + somun kanalı önden (z boyunca)
    s = s.cut(oluk("y", G.VIDA_D / 2, (ya - 1, yb + 1), (0, L3 - G.SG_YUZER), (0, L3 + G.SG_YUZER)))
    yc = (ya + yb) / 2
    s = s.cut(kutu((-G.SOMUN_YUVA / 2, G.SOMUN_YUVA / 2), (yc - G.SOMUN_YUVA_T / 2, yc + G.SOMUN_YUVA_T / 2),
                   (L3 - G.SG_YUZER - G.SOMUN_YUVA / 2 - 0.3, L3 + 20)))
    return s.clean()


# ----------------------------------------------------------------- BİLEK (J5 çatalı + J4 dönüş servosu) — kulak levhası tablada
def bilek():
    S = G.SG
    zk1 = G.T_DONUS_KULAK_Z
    zk0 = zk1 - G.T_DONUS_KULAK
    ea, eb = G.BILEK_A_EN, G.BILEK_B_EN
    A = uc_levha(G.CATAL5_A, (-ea, ea), 0, zk1, ea, "alt", pah=False)
    A = A.cut(horn_baglanti("y", (G.CATAL5_A[0] - 1, G.CATAL5_A[1] + 1), G.HORN_SG, ic=(G.CATAL5_A[0], +1)))
    B = uc_levha(G.CATAL5_B, (-eb, eb), 0, zk1, eb, "alt", pah=False)
    B = B.cut(sil("y", G.BURC_DELIK / 2, (G.CATAL5_B[0] - 1, G.CATAL5_B[1] + 1)))
    lev = kutu((-24.0, 13.5), (G.CATAL5_B[0], G.CATAL5_A[1]), (zk0, zk1))
    s = birlesik(A, B, lev)
    # dönüş servosu: Xs → +x, Zs → +z, mil alet ekseninde
    x0, x1 = -(S["L"] - S["UC"]), S["UC"]
    w = S["W"] / 2 + 0.3
    s = s.cut(kutu((x0 - 0.3, x1 + 0.3), (-w, w), (zk0 - 1, zk1 + 1)))
    for xs, ys in servo_kulak_delikleri(S):
        s = s.cut(sil("z", G.SG_PILOT / 2, (zk0 - 1, zk1 + 1), (xs, ys)))
    return s.clean()


# ----------------------------------------------------------------- TUTUCU GÖVDE — taban levhası tablada
def tutucu_govde():
    S = G.SG
    c2 = G.DIS_C / 2
    zs = G.Z_SERVO_MIL
    yk1 = G.Y_TUT_KULAK
    yk0 = yk1 - G.T_TUT_KULAK
    rb = G.TUTUCU_BOSS_R
    taban = kutu((-18.0, 18.0), (yk0, 17.5), (0, G.TUT_TABAN_T))
    taban = taban.cut(horn_baglanti("z", (-1, G.TUT_TABAN_T + 1), G.HORN_SG_TUT, ic=(0.0, +1)))
    lev = kutu((-24.0, 17.5), (yk0, yk1), (0, 41.0))
    # dişli B göbeği + altında tabana inen sütun (yatay silindir havada kalmasın)
    boss = sil("y", rb, (yk1 - 0.01, G.Y_BOSS_UST), (c2, zs)).fuse(
        kutu((c2 - rb, c2 + rb), (yk1 - 0.01, G.Y_BOSS_UST), (0, zs)))
    s = birlesik(taban, lev, boss)
    # tutucu servosu: Zs → +Y, Xs → −Z, mil (X = −c/2, Z = zs); Ys → −X
    x0, x1 = -(S["L"] - S["UC"]), S["UC"]
    w = S["W"] / 2 + 0.3
    s = s.cut(kutu((-c2 - w, -c2 + w), (yk0 - 1, yk1 + 1), (zs - x1 - 0.3, zs - x0 + 0.3)))
    for xs, ys in servo_kulak_delikleri(S):
        s = s.cut(sil("y", G.SG_PILOT / 2, (yk0 - 1, yk1 + 1), (-c2 - ys, zs - xs)))
    # dişli B mili: M3 delik + yandan somun yuvası (+X'ten)
    s = s.cut(sil("y", G.VIDA_D / 2, (yk0 - 1, G.Y_BOSS_UST + 0.01), (c2, zs)))
    yn = (-9.5, -9.5 + G.SOMUN_YUVA_T)
    s = s.cut(kutu((c2 - G.SOMUN_YUVA / 2 - 0.4, c2 + 10), yn, (zs - G.SOMUN_YUVA / 2, zs + G.SOMUN_YUVA / 2)))
    return s.clean()


# ----------------------------------------------------------------- DİŞLİ + ÇENE
def _inv(a):
    return math.tan(a) - a


def disli_profil(m, z, alfa_deg, bosluk=0.0, faz=0.0, n=8):
    """Evolvent dişli dış hattı (X, Z düzleminde noktalar). faz: ilk diş merkez açısı (rad)."""
    r = m * z / 2
    rb = r * math.cos(math.radians(alfa_deg))
    ra = r + m
    rf = r - 1.25 * m
    a0 = math.radians(alfa_deg)
    yarim = (math.pi * m / 2 - bosluk) / (2 * r)          # hatve dairesinde yarım diş açısı
    def teta(rho):
        ap = math.acos(min(1.0, rb / rho))
        return yarim + _inv(a0) - _inv(ap)
    r_bas = max(rb, rf)
    pts = []
    for k in range(z):
        c = faz + 2 * math.pi * k / z
        t_b = teta(r_bas)
        if rf < rb:
            pts.append((rf * math.cos(c - t_b), rf * math.sin(c - t_b)))
        for i in range(n + 1):
            rho = r_bas + (ra - r_bas) * i / n
            t = teta(rho)
            pts.append((rho * math.cos(c - t), rho * math.sin(c - t)))
        t_a = teta(ra)
        for i in range(1, 3):                                   # uç yayı: c − t_a → c + t_a
            t = -t_a + 2 * t_a * i / 3
            pts.append((ra * math.cos(c + t), ra * math.sin(c + t)))
        for i in range(n, -1, -1):
            rho = r_bas + (ra - r_bas) * i / n
            t = teta(rho)
            pts.append((rho * math.cos(c + t), rho * math.sin(c + t)))
        if rf < rb:
            pts.append((rf * math.cos(c + t_b), rf * math.sin(c + t_b)))
        # kök yayı (sonraki dişe)
        c2 = faz + 2 * math.pi * (k + 1) / z
        a_bas, a_son = c + t_b, c2 - t_b
        for i in range(1, 3):
            a = a_bas + (a_son - a_bas) * i / 3
            pts.append((rf * math.cos(a), rf * math.sin(a)))
    return pts


def _disli(faz):
    pts = disli_profil(G.DIS_M, G.DIS_Z, G.DIS_ALFA, G.DIS_BOSLUK, faz)
    # profil (X, Z) düzleminde → XY'de kur, X ekseni etrafında döndür (Y→Z), sonra Y aralığına taşı
    w = cq.Workplane("XY").polyline(pts).close().extrude(G.DIS_T)
    sol = w.val()
    # XY (x, y=Z) → (x, z): X ekseni etrafında +90° → (x, -z, y): istenen Y aralığı için ayarla
    sol = sol.rotate(V(0, 0, 0), V(1, 0, 0), 90)             # yerel z(0..T) → −y (0..−T)
    return sol.translate(V(0, G.Y_DISLI[1], 0))               # y: T/2 .. −T/2


def cene(taraf):
    """taraf = −1: çene A (servo dişlisi, X = −c/2), +1: çene B (burçlu, X = +c/2). Çene +Z yönünde.
    Ped çenenin içe bakan yüzünde (A için +X, B için −X)."""
    pitch = 2 * math.pi / G.DIS_Z
    faz = 0.0 if taraf < 0 else pitch / 2                       # A dişi B'ye bakar, B'de boşluk A'ya bakar
    d = _disli(faz)
    y = G.Y_DISLI
    h = G.CENE_EN / 2
    kol = kutu((-h, h), y, (0, G.CENE_L))
    ic = -taraf                                                  # içe bakan yön (+X A için)
    px = (h, h + G.PED_T) if ic > 0 else (-h - G.PED_T, -h)
    ped = kutu(px, y, (G.CENE_L - G.PED_L, G.CENE_L))
    s = birlesik(d, kol, ped)
    if taraf < 0:
        s = s.cut(sil("y", 5.5 / 2, (y[0] - 1, y[1] + 1)))
        for zz in (8.3, -8.3):                                   # çapraz horn delikleri (R8,3)
            s = s.cut(sil("y", 0.75, (y[0] - 1, y[1] + 1), (0, zz)))
    else:
        s = s.cut(sil("y", G.BURC_DELIK / 2, (y[0] - 1, y[1] + 1)))
        s = s.cut(sil("y", G.DIS_M * (G.DIS_Z / 2 + 1) + 0.5, (y[0] - 1, y[0] + G.DISLI_B_KADEME)))   # kademe
    return s.clean()


# ----------------------------------------------------------------- BURÇ + DEVRİLME
def burc(boy):
    """Karşı yatak burcu: Ø6 dış, Ø3,4 iç (M3 cıvata). z boyunca 0..boy."""
    return sil("z", G.BURC_D / 2, (0, boy)).cut(sil("z", G.VIDA_D / 2, (-1, boy + 1)))


BURC_MG = G.G_CATAL_MG + G.T_CATAL + 0.3       # 7,3
BURC_SG = G.G_CATAL_SG + G.T_CATAL_SG + 0.3    # 5,3
BURC_TUT = G.Y_DISLI[1] + 0.3 - G.Y_BOSS_UST    # 4,6 (göbek üstü → dişli B üstü + 0,3)


PARCALAR = {
    "taban": taban, "govde": govde, "ust_kol": ust_kol, "on_kol": on_kol, "bilek": bilek,
    "tutucu_govde": tutucu_govde, "cene_A": lambda: cene(-1), "cene_B": lambda: cene(+1),
    "burc_MG": lambda: burc(BURC_MG), "burc_SG": lambda: burc(BURC_SG), "burc_tutucu": lambda: burc(BURC_TUT),
}
ADET = {"burc_MG": 2, "burc_SG": 1, "burc_tutucu": 1}
