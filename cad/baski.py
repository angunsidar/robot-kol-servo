"""Baskı analizi (FDM, 0,4 mm meme, PLA, baskı hizmeti varsayımı).
python baski.py            # bütün parçalar, 6 yön
python baski.py ust_kol    # tek parça, ayrıntılı

1) Destek: parça 0,5 mm'lik vokseller hâlinde örneklenir (OCC ışın kesişimi, tam geometriden). Her yön için katman
   katman ilerlenir: bir katmandaki voksel, alt katmanda kendisinin ya da bir komşusunun (45° kuralı) üstündeyse
   desteklidir. Desteksiz kalan bölgeler (2B bağlı bileşen) şöyle sınıflanır:
     - KÖPRÜ: desteklenen kenarlara en az iki karşı yönden bağlı ve her noktası desteğe ≤ KOPRU_MAX/2 → desteksiz basılır
     - ÇIKINTI: tek yönden bağlı (konsol) ya da çok geniş → destek ister. ≤ CIKINTI_MAX boyundaki küçük dudaklar sayılmaz.
2) Duvar: her yüzeyden içeri ışın, karşı yüzeye en kısa mesafe (tam geometri). < DUVAR_MIN uyarı.
"""
import math
import sys

import numpy as np
from scipy import ndimage

import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepIntCurveSurface import BRepIntCurveSurface_Inter
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCP.gp import gp_Dir, gp_Lin, gp_Pnt

import parcalar as P

VOKSEL = 0.5
KOPRU_MAX = 45.0      # mm, iki uçtan dayalı köprü açıklığı (PLA, iyi soğutma; sarkma payı pencere kenarında bırakılır)
CIKINTI_MAX = 1.5     # mm, tek taraflı dudak (havşa kenarı gibi; 45°'nin ötesinde, kabul)
DUVAR_MIN = 1.2
YONLER = ["-z", "+z", "-x", "+x", "-y", "+y"]     # tablaya yatan yüz


# ----------------------------------------------------------------- voksel
def voksellestir(k, h=VOKSEL):
    """Katıyı z ekseni boyunca ışınlarla ızgaraya çevirir: V[ix, iy, iz] bool, eksen koordinatları (x, y, z)."""
    bb = k.BoundingBox()
    x = np.arange(bb.xmin + h / 2, bb.xmax, h)
    y = np.arange(bb.ymin + h / 2, bb.ymax, h)
    z = np.arange(bb.zmin + h / 2, bb.zmax, h)
    V = np.zeros((len(x), len(y), len(z)), bool)
    sh = k.wrapped
    d = gp_Dir(0, 0, 1)
    z0 = bb.zmin - 1.0
    it = BRepIntCurveSurface_Inter()
    def kesisimler(px, py):
        it.Init(sh, gp_Lin(gp_Pnt(px, py, z0), d), 1e-7)
        w = []
        while it.More():
            w.append(it.W())
            it.Next()
        w = sorted(w)
        t = w[:1]
        for v in w[1:]:
            if v - t[-1] > 1e-4:                           # yakın tekrarları ayıkla (kenar)
                t.append(v)
        return t

    zz = z - z0
    for i, xi in enumerate(x):
        for j, yj in enumerate(y):
            t = kesisimler(xi, yj)
            for dx, dy in ((0.0013, 0.0007), (-0.0011, 0.0017), (0.0021, -0.0013)):
                if len(t) % 2 == 0:
                    break
                t = kesisimler(xi + dx, yj + dy)          # teğet ışın (delik kenarı): azıcık kaydırıp yeniden
            if not t or len(t) % 2:
                continue
            for a, b in zip(t[0::2], t[1::2]):
                V[i, j, (zz > a) & (zz < b)] = True
    return V, (x, y, z)


def yone_cevir(V, yon):
    """V'yi, verilen yüz tablada ve katman ekseni son eksen (yukarı) olacak şekilde döndürür."""
    eks = "xyz".index(yon[1])
    W = np.moveaxis(V, eks, 2)
    if yon[0] == "+":
        W = W[:, :, ::-1]
    return W


def destek_analizi(W, h=VOKSEL, C=None):
    """W[:, :, k] katmanlar (k=0 tabla). C: W ile aynı biçimde dünya koordinatları (3 dizi).
    Döner: (sorun alanı mm², [(tür, alan, en uzak, katman, (x, y, z) merkez)], köprü sayısı)."""
    yapi = ndimage.generate_binary_structure(2, 2)        # 8 komşu
    sorun_alan = 0.0
    kayit = []
    kopru_n = 0
    for k in range(1, W.shape[2]):
        A, B = W[:, :, k], W[:, :, k - 1]
        if not A.any():
            continue
        destek = A & ndimage.binary_dilation(B, yapi)     # 45°: bir voksel yana
        O = A & ~destek
        if not O.any():
            continue
        etk, n = ndimage.label(O, yapi)
        # desteğe uzaklık (desteklenen vokseller kaynak)
        dist = ndimage.distance_transform_edt(~destek) * h
        for c in range(1, n + 1):
            m = etk == c
            alan = m.sum() * h * h
            dmax = dist[m].max()
            if dmax <= CIKINTI_MAX + 1e-9:
                continue                                  # küçük dudak
            # bileşenin çevresindeki destekli vokseller: hangi yönlerden?
            cevre = ndimage.binary_dilation(m, yapi, iterations=2) & destek
            yer = tuple(round(float(c[:, :, k][m].mean()), 1) for c in C) if C is not None else None
            if not cevre.any():
                kayit.append(("ADA", alan, dmax, k, yer))   # havada başlayan bölge
                sorun_alan += alan
                continue
            ci, cj = np.nonzero(m)
            si, sj = np.nonzero(cevre)
            cx, cy = ci.mean(), cj.mean()
            aci = np.arctan2(sj - cy, si - cx)
            # karşılıklı destek: açıların dairesel yayılımı (en büyük boşluk < 180° ise çok yönlü)
            a = np.sort(aci)
            bosluk = np.max(np.diff(np.concatenate([a, a[:1] + 2 * np.pi]))) if len(a) > 1 else 2 * np.pi
            iki_taraf = bosluk < math.radians(200)
            if iki_taraf and dmax <= KOPRU_MAX / 2:
                kopru_n += 1
                continue
            kayit.append(("UZUN KÖPRÜ" if iki_taraf else "ÇIKINTI", alan, dmax, k, yer))
            sorun_alan += alan
    return sorun_alan, kayit, kopru_n


# ----------------------------------------------------------------- duvar kalınlığı
def en_ince_duvar(k, adim=3.0, sinir=6.0):
    en = (float("inf"), None)
    sh = k.wrapped
    it = BRepIntCurveSurface_Inter()
    for f in k.Faces():
        s = BRepAdaptor_Surface(f.wrapped)
        tip = s.GetType()
        if tip not in (GeomAbs_Plane, GeomAbs_Cylinder):
            continue
        u0, u1, v0, v1 = s.FirstUParameter(), s.LastUParameter(), s.FirstVParameter(), s.LastVParameter()
        ol = s.Cylinder().Radius() if tip == GeomAbs_Cylinder else 1.0
        nu = max(2, min(30, int(abs(u1 - u0) * ol / adim)))
        nv = max(2, min(30, int(abs(v1 - v0) / adim)))
        for i in range(nu):
            for j in range(nv):
                p = s.Value(u0 + (u1 - u0) * (i + 0.5) / nu, v0 + (v1 - v0) * (j + 0.5) / nv)
                pc = cq.Vector(p.X(), p.Y(), p.Z())
                # nokta gerçekten yüzün üzerinde mi (kırpılmış yüz)?
                if f.distance(cq.Vertex.makeVertex(*pc.toTuple())) > 1e-3:
                    continue
                n = f.normalAt(pc)
                d = gp_Dir(-n.x, -n.y, -n.z)
                q = gp_Pnt(p.X() + d.X() * 0.01, p.Y() + d.Y() * 0.01, p.Z() + d.Z() * 0.01)
                it.Init(sh, gp_Lin(q, d), 1e-7)
                m = float("inf")
                while it.More():
                    if it.W() > 1e-4:
                        m = min(m, it.W())
                    it.Next()
                if m < sinir and m + 0.01 < en[0]:
                    en = (m + 0.01, (round(p.X(), 1), round(p.Y(), 1), round(p.Z(), 1)))
    return en


def main():
    secim = sys.argv[1:] or list(P.PARCALAR)
    ayrinti = len(secim) == 1
    ozet = []
    for ad in secim:
        k = P.PARCALAR[ad]()
        V, (gx, gy, gz) = voksellestir(k)
        X, Y, Z = np.meshgrid(gx, gy, gz, indexing="ij")
        sonuc = {y: destek_analizi(yone_cevir(V, y), C=[yone_cevir(c, y) for c in (X, Y, Z)]) for y in YONLER}
        en_iyi = min(sonuc, key=lambda y: sonuc[y][0])
        alan, kayit, kn = sonuc[en_iyi]
        duvar, yer = en_ince_duvar(k)
        durum = "DESTEKSİZ" if alan == 0 else f"destek {alan:.0f} mm²"
        dv = "GEÇTİ" if duvar >= DUVAR_MIN else "İNCE"
        ozet.append((ad, en_iyi, alan, duvar))
        print(f"{ad:14s} en iyi: {en_iyi} yüzü tablada · {durum:18s} · köprü {kn:3d} · en ince duvar {duvar:4.2f} mm [{dv}] {yer or ''}")
        if ayrinti or alan > 0:
            for y, (a, kk, n) in sonuc.items():
                ozetk = {}
                for tur, al, dm, kat, _ in kk:
                    ozetk.setdefault(tur, [0, 0.0, 0.0, kat])
                    ozetk[tur][0] += 1
                    ozetk[tur][1] += al
                    ozetk[tur][2] = max(ozetk[tur][2], dm)
                s = ", ".join(f"{t}: {v[0]} bölge {v[1]:.0f} mm² (en uzak {v[2]:.1f} mm, ilk katman {v[3] * VOKSEL:.1f})" for t, v in ozetk.items())
                print(f"     {y} tablada: {a:6.0f} mm²  {s}")
                if y == en_iyi:
                    for tur, al, dm, kat, yer in kk:
                        print(f"          · {tur} {al:.0f} mm², en uzak {dm:.1f} mm, merkez {yer}")
    kotu = [o for o in ozet if o[2] > 0 or o[3] < DUVAR_MIN]
    print(f"\n{len(ozet) - len(kotu)}/{len(ozet)} parça desteksiz basılır ve duvarları ≥ {DUVAR_MIN} mm")
    return 0 if not kotu else 1


if __name__ == "__main__":
    sys.exit(main())
