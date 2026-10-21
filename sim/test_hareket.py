"""
servo_hareket.js (simülasyon) ile arduino/kol_servo/komut.h (Arduino) aynı hareketi mi üretiyor?
Rastgele komut senaryoları ikisine de verilir, her 10 ms'lik adımdaki konum ve hız karşılaştırılır.
Gerekenler: node ve bir C++ derleyici (zig: `pip install ziglang`, ya da PATH'te clang++/g++).
Çalıştır:  python test_hareket.py
"""
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).parent
ARD = HERE.parent / "arduino"
NODE = shutil.which("node")

JS_KOSUCU = r"""
const H = require(process.argv[2]);
const satirlar = require("fs").readFileSync(0, "utf8").trim().split(/\s+/).map(Number);
const n = satirlar[0], kmt = [];
for (let i = 1; i + 3 < satirlar.length + 1; i += 4) kmt.push(satirlar.slice(i, i + 4));
const mem = new Uint8Array(1024).fill(0xff);
const kol = new H.Kol([90, 100, 80, 90, 90, 60], [0, 15, 10, 0, 0, 20], [180, 165, 170, 180, 180, 110],
                      { oku: (a) => mem[a], yaz: (a, v) => { mem[a] = v; } });
const out = []; let j = 0;
for (let s = 0; s < n; s++) {
  while (j < kmt.length && kmt[j][0] === s) { const [, t, sv, d] = kmt[j++]; out.push(`R ${s} ${kol.uygula({ tip: t, servo: sv, deger: d })}`); }
  kol.adim();
  let l = `P ${s}`;
  for (let i = 0; i < 6; i++) l += ` ${kol.p[i]} ${kol.v[i]}`;
  out.push(l);
}
process.stdout.write(out.join("\n") + "\n");
"""


def derleyici():
    try:
        import ziglang  # noqa: F401
        return [sys.executable, "-m", "ziglang", "c++"]
    except ImportError:
        pass
    for c in ("clang++", "g++"):
        if shutil.which(c):
            return [c]
    return None


CXX = derleyici()


def senaryo(seed, n=3000):
    rnd = random.Random(seed)
    satir = []
    for s in range(n):
        if rnd.random() > 0.03:
            continue
        r = rnd.random()
        if r < 0.30:
            satir.append((s, 1, rnd.randrange(6), rnd.randint(-20, 200)))           # SERVO (sınır dışı da)
        elif r < 0.50:
            for i in rnd.sample(range(6), rnd.randint(1, 6)):
                satir.append((s, 7, i, rnd.randint(-50, 1900)))                    # INCE
            satir.append((s, 8, 0, 0))                                            # GIT
        elif r < 0.56:
            satir.append((s, 3, 0, 0))                                            # KAYDET
        elif r < 0.62:
            for i in rnd.sample(range(6), rnd.randint(0, 6)):
                satir.append((s, 7, i, rnd.randint(-50, 1900)))                    # INCE
            satir.append((s, 9, 0, 0))                                            # EKLE (PUT)
        elif r < 0.74:
            satir.append((s, 4, 0, 0))                                            # OYNAT
        elif r < 0.84:
            satir.append((s, 5, 0, 0))                                            # DURAKLAT
        elif r < 0.94:
            satir.append((s, 2, 0, rnd.randint(0, 80)))                           # HIZ
        else:
            satir.append((s, 6, 0, 0))                                            # SIFIRLA
    return n, satir


def f32(x):
    # C++ %.9g, JS tam değer yazar; ikisi de aynı 32 bit float'a döner
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def coz(metin):
    return [l.split() for l in metin.strip().splitlines()]


@unittest.skipUnless(NODE and CXX, "node ya da C++ derleyici yok")
class HareketEsdegerlik(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.exe = cls.tmp / ("iz.exe" if os.name == "nt" else "iz")
        subprocess.run(CXX + ["-std=c++17", "-O2", "-ffp-contract=off", f"-I{ARD / 'kol_servo'}",
                              str(ARD / "test" / "iz.cpp"), "-o", str(cls.exe)], check=True)
        cls.js = cls.tmp / "kosucu.js"
        cls.js.write_text(JS_KOSUCU, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def calistir(self, n, satir):
        girdi = f"{n}\n" + "".join(f"{a} {t} {s} {d}\n" for a, t, s, d in satir)
        c = subprocess.run([str(self.exe)], input=girdi, capture_output=True, text=True, check=True).stdout
        j = subprocess.run([NODE, str(self.js), str(HERE / "servo_hareket.js")], input=girdi,
                           capture_output=True, text=True, check=True).stdout
        return coz(c), coz(j)

    def test_rastgele_senaryolar_bit_bit_ayni(self):
        toplam_adim = toplam_kmt = hareketli = 0
        for seed in range(25):
            n, satir = senaryo(seed)
            c, j = self.calistir(n, satir)
            self.assertEqual(len(c), len(j), f"seed {seed}: satır sayısı")
            for a, b in zip(c, j):
                self.assertEqual(a[:2], b[:2], f"seed {seed}")
                if a[0] == "R":
                    self.assertEqual(a[2], b[2], f"seed {seed} adım {a[1]}: dönüş kodu")
                    toplam_kmt += 1
                    continue
                ca, ja = list(map(f32, a[2:])), list(map(f32, b[2:]))
                self.assertEqual(ca, ja, f"seed {seed} adım {a[1]}")
                hareketli += any(x != 0 for x in ca[1::2])
                toplam_adim += 1
        print(f"\n  {toplam_adim} adım, {toplam_kmt} komut; {hareketli} adımda en az bir eklem hareketli -> birebir aynı")
        self.assertGreater(hareketli, toplam_adim * 0.3)   # senaryo gerçekten hareket içeriyor

    def test_oynatma_dongusu(self):
        # İki poz kaydet, oynat: konum iki poz arasında gidip gelmeli (iki tarafta da aynı)
        satir = [(0, 1, 0, 30), (200, 3, 0, 0), (201, 1, 0, 150), (202, 1, 1, 40), (500, 3, 0, 0), (501, 4, 0, 0)]
        c, j = self.calistir(2000, satir)
        self.assertEqual([[l[0], l[1]] + list(map(f32, l[2:])) for l in c], [[l[0], l[1]] + list(map(f32, l[2:])) for l in j])
        p0 = [f32(l[2]) for l in c if l[0] == "P"][600:]
        self.assertIn(30.0, p0)
        self.assertIn(150.0, p0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
