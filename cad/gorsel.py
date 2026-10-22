"""Belge görselleri: docs/parcalar.png (her parça baskı yönünde, tablada) ve docs/montaj.png (iki poz).
python gorsel.py     (matplotlib gerekir)
"""
import os

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

import model as M
import parcalar as P

KOK = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(KOK, "..", "docs")
RENK = {"parca": "#2f6fd0", "servo": "#2a2a2a", "horn": "#d8d8d8", "burc": "#e08a1e"}
# baski.py'nin bulduğu desteksiz yönler: tablaya yatan yüz → döndürme (eksen, açı)
BASKI_YONU = {"taban": ("-z", None), "govde": ("-z", None), "ust_kol": ("-x", ((0, 1, 0), -90)),
              "on_kol": ("-x", ((0, 1, 0), -90)), "bilek": ("+z", ((1, 0, 0), 180)),
              "tutucu_govde": ("-z", None), "cene_A": ("-y", ((1, 0, 0), 90)), "cene_B": ("+y", ((1, 0, 0), -90)),
              "burc_MG": ("-z", None), "burc_SG": ("-z", None), "burc_tutucu": ("-z", None)}


def ag(k, tol=0.2):
    v, t = k.tessellate(tol, 0.3)
    v = np.array([[p.x, p.y, p.z] for p in v])
    return v, np.array(t)


def ciz(ax, parcalar, elev=22, azim=-55, isik=(0.4, -0.5, 0.75)):
    l = np.array(isik) / np.linalg.norm(isik)
    hepsi = []
    for v, t, renk in parcalar:
        tri = v[t]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        g = 0.35 + 0.65 * np.abs(n @ l)
        base = np.array(matplotlib.colors.to_rgb(renk))
        pc = Poly3DCollection(tri, facecolors=np.clip(base[None] * g[:, None] + 0.06, 0, 1), edgecolor="none")
        ax.add_collection3d(pc)
        hepsi.append(v)
    Pn = np.vstack(hepsi)
    c = (Pn.max(0) + Pn.min(0)) / 2
    r = (Pn.max(0) - Pn.min(0)).max() / 2 * 1.02
    ax.set_xlim(c[0] - r, c[0] + r)
    ax.set_ylim(c[1] - r, c[1] + r)
    ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev, azim)
    ax.set_axis_off()


def parcalar_gorseli():
    adlar = list(P.PARCALAR)
    fig = plt.figure(figsize=(16, 9.5))
    for i, ad in enumerate(adlar):
        k = P.PARCALAR[ad]()
        yuz, don = BASKI_YONU[ad]
        if don:
            k = k.rotate((0, 0, 0), don[0], don[1])
        bb = k.BoundingBox()
        k = k.translate((-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))
        v, t = ag(k)
        ax = fig.add_subplot(3, 4, i + 1, projection="3d")
        # tabla
        bb = k.BoundingBox()
        s = max(bb.xlen, bb.ylen) * 0.65
        tabla = np.array([[-s, -s, 0], [s, -s, 0], [s, s, 0], [-s, s, 0]])
        kapali = np.vstack([tabla, tabla[:1]])
        ax.plot(kapali[:, 0], kapali[:, 1], kapali[:, 2], color="#a89f8c", lw=1.2)   # tabla (çizgi: derinlik sırası bozulmasın)
        ciz(ax, [(v, t, RENK["burc"] if ad.startswith("burc") else RENK["parca"])], elev=24, azim=-60)
        ax.set_title(f"{ad}  ({yuz} yüzü tablada)\n{bb.xlen:.0f}×{bb.ylen:.0f}×{bb.zlen:.0f} mm, desteksiz", fontsize=9)
    ax = fig.add_subplot(3, 4, 12)
    ax.axis("off")
    ax.text(0.0, 0.6, "Baskı: PLA, 0,2 mm katman, 3–4 duvar,\n%30–40 dolgu; çene ve burçlar %100.\n"
            "Yönler cad/baski.py ile bulundu:\nhepsi destek gerektirmiyor.", fontsize=10, va="center")
    plt.tight_layout()
    out = os.path.join(DOCS, "parcalar.png")
    plt.savefig(out, dpi=80)
    plt.close(fig)
    return out


def montaj_gorseli():
    o = M.ogeler()
    phi0 = M.phi0_bul()
    pozlar = [([0, 0, 0, 0, 0], 35, "Referans pozu (bütün eklemler 0°)", 18, -60),
              ([30, 45, 55, 0, 70], 70, "Masaya uzanmış, tutucu açık", 18, -75)]
    fig = plt.figure(figsize=(13, 8))
    for i, (q, tut, baslik, e, a) in enumerate(pozlar):
        ax = fig.add_subplot(1, 2, i + 1, projection="3d")
        oo = M.konumla(o, M.cerceveler(q, tut, phi0))
        ciz(ax, [(*ag(k, 0.3), RENK[tur]) for ad, g, k, tur in oo], elev=e, azim=a)
        ax.set_title(baslik, fontsize=11)
    plt.tight_layout()
    out = os.path.join(DOCS, "montaj.png")
    plt.savefig(out, dpi=80)
    plt.close(fig)
    return out


if __name__ == "__main__":
    print(parcalar_gorseli())
    print(montaj_gorseli())
