"""
kol_istemci.py testi: istemci, Arduino'nun kendi kodunu (komut.h, DLL olarak derlenmiş: arduino/test/sanal_kol.cpp)
çalıştıran sahte bir seri portla, sanal zamanda konuşur. Donanım gerekmez.
Gerekenler: C++ derleyici (zig: `pip install ziglang`, ya da PATH'te clang++/g++).
Çalıştır:  python test_kol_istemci.py
"""
import ctypes
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARD = HERE.parent / "arduino"
sys.path.insert(0, str(HERE))
import kol_istemci as ki  # noqa: E402

sm = ki.sm
EV = [90, 100, 80, 90, 90, 60]


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
DLL = None


def setUpModule():
    global DLL, TMP
    if not CXX:
        return
    TMP = Path(tempfile.mkdtemp())
    yol = TMP / ("sanal_kol.dll" if os.name == "nt" else "sanal_kol.so")
    subprocess.run(CXX + ["-std=c++17", "-O2", "-shared", "-fPIC", f"-I{ARD / 'kol_servo'}",
                          str(ARD / "test" / "sanal_kol.cpp"), "-o", str(yol)], check=True)
    DLL = ctypes.CDLL(str(yol))
    DLL.sk_yeni.restype = ctypes.c_void_p
    for f, a in {"sk_sil": [ctypes.c_void_p], "sk_yaz": [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int],
                 "sk_zaman": [ctypes.c_void_p, ctypes.c_uint32], "sk_simdi": [ctypes.c_void_p],
                 "sk_oku": [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int],
                 "sk_konum": [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float)],
                 "sk_hedef": [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int16)]}.items():
        getattr(DLL, f).argtypes = a
    DLL.sk_simdi.restype = ctypes.c_uint32


class SanalPort:
    """pyserial yerine: yazılan baytlar sanal Arduino'ya gider, okunanlar ondan gelir. Zaman sanal."""

    def __init__(self):
        self.p = ctypes.c_void_p(DLL.sk_yeni())
        self.iz = []                 # (ms, 6 servo konumu °) her uyu() sonunda
        self.yazilan = b""

    def write(self, b):
        self.yazilan += b
        DLL.sk_yaz(self.p, b, len(b))
        return len(b)

    def read(self, n):
        buf = ctypes.create_string_buffer(n)
        k = DLL.sk_oku(self.p, buf, n)
        return buf.raw[:k]

    def saat(self):
        return DLL.sk_simdi(self.p) / 1000

    def uyu(self, s):
        DLL.sk_zaman(self.p, DLL.sk_simdi(self.p) + max(1, round(s * 1000)))
        self.iz.append((DLL.sk_simdi(self.p), self.konum()))

    def konum(self):
        a = (ctypes.c_float * 6)()
        DLL.sk_konum(self.p, a)
        return list(a)

    def kol(self, **kw):
        return ki.Kol(self, saat=self.saat, uyu=self.uyu, **kw)

    def close(self):
        DLL.sk_sil(self.p)


def uc_mm(servo_deg):
    pts, _ = sm.fk(sm.eklem_aci(servo_deg), sm.Olcu())
    return tuple(c * 1000 for c in pts[4])


@unittest.skipUnless(CXX, "C++ derleyici yok")
class Istemci(unittest.TestCase):
    def setUp(self):
        DLL.sk_eeprom_sil()
        self.port = SanalPort()
        self.k = self.port.kol()

    def tearDown(self):
        sm.kalibrasyon({"yon": [1] * 5, "ofset": [0] * 5})
        self.port.close()

    def test_sanal_arduino_ino_ile_ayni(self):
        ino = (ARD / "kol_servo" / "kol_servo.ino").read_text(encoding="utf-8")
        sanal = (ARD / "test" / "sanal_kol.cpp").read_text(encoding="utf-8")
        mesaj = lambda s: dict(re.findall(r'case (\d): return "([^"]+)"', s))
        dizi = lambda s, ad: re.search(ad + r"\[kol::N_SERVO\]|" + ad + r"\[N_SERVO\]", s) and \
            re.search(ad + r"\[(?:kol::)?N_SERVO\] = \{([^}]+)\}", s).group(1).replace(" ", "")
        self.assertEqual(mesaj(ino), mesaj(sanal))
        self.assertEqual(len(mesaj(ino)), 7)
        for ad in ("EV", "MIN_ACI", "MAX_ACI"):
            self.assertEqual(dizi(ino, ad), dizi(sanal, ad), ad)
        self.assertEqual([int(v) for v in dizi(ino, "MIN_ACI").split(",")], sm.SERVO_MIN)
        self.assertEqual([int(v) for v in dizi(ino, "MAX_ACI").split(",")], sm.SERVO_MAX)

    def test_acilis(self):
        self.assertEqual(self.k.hedef, [v * 10 for v in EV])
        d = self.k.durum()
        self.assertEqual(d, {"konum": [float(v) for v in EV], "poz": 0, "oynuyor": False, "ss": 20})

    def test_servo_ve_eklemler(self):
        self.k.servo(2, 120)
        self.assertEqual(self.k.durum()["konum"][1], 120.0)
        self.k.eklemler([1000, 1105, 905, 900, 900, 600])
        self.assertEqual(self.k.durum()["konum"][:3], [100.0, 110.5, 90.5])

    def test_git_ucu_noktaya_goturur(self):
        t0 = self.port.saat()
        self.k.git(180, 0, 60)
        u = uc_mm(self.port.konum())
        self.assertLess(math.dist(u, (180, 0, 60)), 1.0)
        self.assertLess(self.port.saat() - t0, 5)

    def test_duz_git_dusey_inis(self):
        self.k.git(170, -60, 70)
        self.port.iz.clear()
        self.k.duz_git(170, -60, 30)
        yol = [uc_mm(k) for _, k in self.port.iz]
        sapma = max(math.hypot(p[0] - 170, p[1] + 60) for p in yol)
        print(f"\n  40 mm düz iniş: yatay sapma en fazla {sapma:.2f} mm (çoğu ilk mm'lerde, hızlanırken)")
        self.assertLess(sapma, 1.0, f"düşey inişte yatay sapma {sapma:.2f} mm")
        self.assertLess(math.dist(uc_mm(self.port.konum()), (170, -60, 30)), 1.0)
        self.assertGreater(self.port.yazilan.count(b"GO"), 8)            # ara noktalar gönderildi

    def test_erisim_disi_hicbir_sey_gondermez(self):
        self.k.git(180, 0, 60)
        once, gonderilen = self.port.konum(), len(self.port.yazilan)
        with self.assertRaises(ki.ErisimDisi):
            self.k.git(600, 0, 50)
        with self.assertRaises(ki.ErisimDisi):          # iki uç erişilebilir, ortası kola fazla yakın
            self.k.git(100, 150, 40)
            gonderilen = len(self.port.yazilan)
            self.k.duz_git(100, -150, 40)
        self.assertNotIn(b"GO", self.port.yazilan[gonderilen:])

    def test_tutucu_kalibrasyondan(self):
        k = SanalPort().kol(kalibrasyon={"acik": 105, "kapali": 42})
        k.tutucu_kapa()
        self.assertEqual(k.durum()["konum"][5], 42.0)
        k.tutucu_ac()
        self.assertEqual(k.durum()["konum"][5], 105.0)
        k.kapat()

    def test_kalibrasyon_ofset_ve_yon(self):
        normal = self.k.ik(180, 40, 50)
        self.k.kalibrasyon_yukle({"yon": [1, -1, 1, 1, 1], "ofset": [3, -4.5, 2, 0, 0]})
        kal = self.k.ik(180, 40, 50)
        self.assertLessEqual(abs(kal[0] - (normal[0] + 30)), 1)
        self.assertLessEqual(abs((kal[1] - 900) + (normal[1] - 900) + 45), 1)   # yön −1: 90'ın öbür yanı
        self.k.eklemler(kal)
        self.assertLess(math.dist(uc_mm(self.port.konum()), (180, 40, 50)), 1.0)   # kalibrasyonlu FK ile

    def test_kayit_oynatma_duraklatma(self):
        self.k.git(180, 0, 60)
        self.assertIn("kaydedildi", self.k.kaydet())
        self.k.git(200, -60, 40)
        self.assertIn("kaydedildi", self.k.kaydet())
        self.assertEqual(self.k.durum()["poz"], 2)
        self.k.hiz(10)
        self.assertIn("Oynatiliyor", self.k.oynat())
        self.assertTrue(self.k.durum()["oynuyor"])
        self.port.iz.clear()
        for _ in range(300):
            self.port.uyu(0.01)
        x = [uc_mm(k)[0] for _, k in self.port.iz]
        self.assertLess(min(x), 181); self.assertGreater(max(x), 195)       # iki poz arasında gidip geliyor
        self.k.duraklat()
        once = self.port.konum()
        for _ in range(50):
            self.port.uyu(0.01)
        self.assertEqual(self.port.konum(), once)
        self.assertFalse(self.k.durum()["oynuyor"])
        self.assertIn("silindi", self.k.sifirla())
        self.assertIn("poz yok", self.k.oynat())

    def test_yukle_kipirdamaz_ve_kalici(self):
        pozlar = [self.k.ik(180, 0, 60), self.k.ik(200, -60, 40), self.k.ik(170, 60, 50)]
        once = self.port.konum()
        self.assertEqual(self.k.yukle(pozlar), 3)
        for _ in range(30):
            self.port.uyu(0.01)
        self.assertEqual(self.port.konum(), once)                         # yükleme sırasında kıpırdamadı
        # elektrik kesildi, yeniden açıldı: kayıtlar EEPROM'da
        self.port.close()
        self.port = SanalPort()
        k2 = self.port.kol()
        self.assertEqual(k2.durum()["poz"], 3)
        k2.oynat()
        self.port.iz.clear()
        for _ in range(800):
            self.port.uyu(0.01)
        vardi = [any(all(round(k[i] * 10) == p[i] for i in range(6)) for _, k in self.port.iz) for p in pozlar]
        self.assertEqual(vardi, [True, True, True])                       # üç poza da tam oturdu
        with self.assertRaises(ki.KolHatasi):
            self.k.yukle([pozlar[0]] * 51)

    @unittest.skipUnless(shutil.which("node"), "node yok")
    def test_sayfa_ile_ayni_hedefler(self):
        # Sayfanın (servo_program.js) ve istemcinin aynı kalibrasyonla aynı servo hedeflerini bulması
        kal = {"yon": [1, -1, 1, 1, -1], "ofset": [3, -4.5, 2, 1, 6], "acik": 100, "kapali": 35}
        noktalar = [(180, 0, 60, 180), (200, -60, 40, 180), (170, 60, 70, 170), (230, 20, 40, 135)]   # cad ölçüleri
        js = f"""
const S=require('./servo_kinematik.js'),P=require('./servo_program.js'),O=S.olcu();
S.kalibrasyon({kal!r}); const bas=[900,1000,800,900,900,600];
const out={[list(n) for n in noktalar]!r}.map(([x,y,z,a])=>{{const r=P.coz([{{tip:'git',x,y,z,alet:a}}],S,O,bas); return r.hatalar.length?null:r.hedefler[0].onda;}});
console.log(JSON.stringify(out));"""
        import json
        sonuc = json.loads(subprocess.run(["node", "-e", js], cwd=HERE.parent / "sim", capture_output=True,
                                          text=True, check=True).stdout)
        self.assertEqual(sum(j is not None for j in sonuc), 3)          # üçü erişilebilir, biri değil: iki yol da denenir
        self.k.kalibrasyon_yukle(kal)
        self.k.hedef = [900, 1000, 800, 900, 900, 600]
        for n, j in zip(noktalar, sonuc):
            try:
                p = self.k.ik(*n)
            except ki.ErisimDisi:
                p = None
            self.assertEqual(p is None, j is None, n)
            if p:
                self.assertTrue(all(abs(a - b) <= 1 for a, b in zip(p, j)), f"{n}: python {p} js {j}")

    def test_cevap_vermeyen_port(self):
        class Sessiz:
            t = 0.0
            def write(self, b): return len(b)
            def read(self, n): return b""
        s = Sessiz()
        def uyu(x): s.t += x
        with self.assertRaises(ki.KolHatasi):
            ki.Kol(s, saat=lambda: s.t, uyu=uyu)


if __name__ == "__main__":
    unittest.main(verbosity=2)
