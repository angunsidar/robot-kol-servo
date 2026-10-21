"""
Cults3D'den indirilen STL'leri ölçer: her parçanın boyutu, hacmi, baskı kütlesi ve hizmet maliyeti.
Kullanım:  ZIP'i bu klasöre aç (stl/ içinde .stl dosyaları), sonra:
           python stl_olc.py               # varsayılan 2 TL/g
           python stl_olc.py --tl-g 0.25   # farklı hizmet fiyatı
Çıktı ayrıca parcalar.csv olarak yazılır. Kol ölçüleri (omuz-dirsek mesafesi vb.) parçaların boylarından okunup
sim/servo_model.py ve sim/servo_kinematik.js içindeki Olcu değerlerine girilir.
"""
import argparse
import csv
import struct
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
PLA, PETG = 1.24, 1.27          # g/cm³ (tipik)
DOLGU = 0.6                     # 2–3 duvar + %20–40 dolgu: dolu hacmin ~%60'ı (tahmin, dilimleyici kesinleştirir)


def oku(path: Path):
    data = path.read_bytes()
    if len(data) >= 84:
        n = struct.unpack("<I", data[80:84])[0]
        if 84 + n * 50 == len(data):                       # binary STL
            rec = np.frombuffer(data[84:], dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")], count=n)
            return rec["v"].astype(float)
    tris, cur = [], []
    for line in data.decode(errors="ignore").splitlines():   # ASCII STL
        s = line.strip().split()
        if s[:1] == ["vertex"]:
            cur.append([float(x) for x in s[1:4]])
            if len(cur) == 3:
                tris.append(cur)
                cur = []
    return np.array(tris, float)


def hacim_cm3(t):
    return abs(np.sum(np.einsum("ij,ij->i", t[:, 0], np.cross(t[:, 1], t[:, 2]))) / 6) / 1000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tl-g", type=float, default=2.0, help="baskı hizmeti fiyatı TL/g")
    ap.add_argument("--malzeme", choices=["PLA", "PETG"], default="PLA")
    a = ap.parse_args()
    rho = PLA if a.malzeme == "PLA" else PETG
    # Windows büyük/küçük harf ayırmaz: iki desen aynı dosyayı bulabilir, tekrarları ayıkla
    files = sorted({p.resolve() for p in HERE.rglob("*") if p.suffix.lower() == ".stl"})
    if not files:
        print("Bu klasörde .stl yok. Cults3D'den indirdiğin ZIP'i buraya aç.")
        return
    rows, top_g = [], 0.0
    print(f"{'parça':<38} {'X×Y×Z mm':>22} {'hacim cm³':>10} {'baskı g':>8}")
    for f in files:
        t = oku(f)
        v = t.reshape(-1, 3)
        boy = v.max(0) - v.min(0)
        h = hacim_cm3(t)
        g = h * rho * DOLGU
        top_g += g
        rows.append([f.name, *np.round(boy, 1), round(h, 2), round(g, 1)])
        print(f"{f.name[:38]:<38} {boy[0]:6.1f}×{boy[1]:6.1f}×{boy[2]:6.1f} {h:10.2f} {g:8.1f}")
    print(f"\nToplam baskı ~{top_g:.0f} g ({a.malzeme}, dolu hacmin %{DOLGU * 100:.0f}'ı) "
          f"-> {a.tl_g:.2f} TL/g ile ~{top_g * a.tl_g:.0f} TL")
    print("En büyük parça boyu 180 mm'yi geçiyorsa küçük tablalı yazıcılarda sığmayabilir; hizmete belirt.")
    with open(HERE / "parcalar.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["dosya", "x_mm", "y_mm", "z_mm", "hacim_cm3", "baski_g"])
        w.writerows(rows)


if __name__ == "__main__":
    main()
