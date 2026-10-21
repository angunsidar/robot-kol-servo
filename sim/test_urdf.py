"""
urdf_uret.py testi: URDF zincirini XML'den okuyup kendi FK'mızla çözer ve servo_model.fk ile karşılaştırır
(rastgele 2000 poz, dirsek/bilek/uç noktaları ve alet yönü). Ek paket gerekmez.
Çalıştır:  python test_urdf.py
"""
import math
import random
import unittest
import xml.etree.ElementTree as ET

import servo_model as sm
import urdf_uret as uu


def matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def oteleme(x, y, z):
    return [[1, 0, 0, x], [0, 1, 0, y], [0, 0, 1, z], [0, 0, 0, 1]]


def rpy(r, p, y):
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return [[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr, 0],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr, 0],
            [-sp, cp * sr, cp * cr, 0], [0, 0, 0, 1]]


def eksen_acisi(ax, t):                       # Rodrigues
    x, y, z = ax
    n = math.sqrt(x * x + y * y + z * z); x, y, z = x / n, y / n, z / n
    c, s, C = math.cos(t), math.sin(t), 1 - math.cos(t)
    return [[c + x * x * C, x * y * C - z * s, x * z * C + y * s, 0],
            [y * x * C + z * s, c + y * y * C, y * z * C - x * s, 0],
            [z * x * C - y * s, z * y * C + x * s, c + z * z * C, 0], [0, 0, 0, 1]]


class Urdf:
    def __init__(self, xml):
        self.kok = ET.fromstring(xml)
        self.eklem = {j.get("name"): j for j in self.kok.findall("joint")}
        self.ust = {j.find("child").get("link"): j for j in self.kok.findall("joint")}

    def zincir(self, link):
        yol = []
        while link in self.ust:
            j = self.ust[link]; yol.append(j); link = j.find("parent").get("link")
        return list(reversed(yol))

    def fk(self, link, q):
        """q: {eklem_adı: rad}. link çerçevesinin dünya dönüşümü."""
        T = oteleme(0, 0, 0)
        for j in self.zincir(link):
            o = j.find("origin")
            xyz = [float(v) for v in o.get("xyz").split()] if o is not None else [0, 0, 0]
            r = [float(v) for v in o.get("rpy", "0 0 0").split()] if o is not None else [0, 0, 0]
            T = matmul(matmul(T, oteleme(*xyz)), rpy(*r))
            if j.get("type") == "revolute":
                ax = [float(v) for v in j.find("axis").get("xyz").split()]
                T = matmul(T, eksen_acisi(ax, q.get(j.get("name"), 0.0)))
        return T


class UrdfTest(unittest.TestCase):
    def tearDown(self):
        sm.kalibrasyon({"yon": [1] * 5, "ofset": [0] * 5})

    def karsilastir(self):
        u = Urdf(uu.urdf_xml())
        L = sm.eklem_limit()
        rnd = random.Random(3)
        en_buyuk = 0.0
        for _ in range(2000):
            q = [rnd.uniform(lo, hi) for lo, hi in L]
            qd = {uu.EKLEMLER[i]: math.radians(q[i]) for i in range(5)}
            (b, s, e, w, t), alet = sm.fk(q)
            for link, beklenen in (("ust_kol", s), ("on_kol", e), ("bilek", w), ("uc", t)):
                T = u.fk(link, qd)
                d = math.dist([T[0][3], T[1][3], T[2][3]], beklenen)
                en_buyuk = max(en_buyuk, d)
                self.assertLess(d, 1e-9, f"{link} {q}")
            T = u.fk("uc", qd)
            self.assertAlmostEqual(T[2][2], math.cos(math.radians(alet)), places=9)   # alet ekseni dikeyden 'alet' kadar
        return u, en_buyuk

    def test_fk_servo_model_ile_ayni(self):
        u, d = self.karsilastir()
        print(f"\n  2000 rastgele pozda URDF ile servo_model FK farkı en fazla {d:.1e} m")

    def test_sinirlar_ve_adlar(self):
        u = Urdf(uu.urdf_xml())
        L = sm.eklem_limit()
        for i, ad in enumerate(uu.EKLEMLER):
            lim = u.eklem[ad].find("limit")
            self.assertAlmostEqual(float(lim.get("lower")), math.radians(L[i][0]), places=5)
            self.assertAlmostEqual(float(lim.get("upper")), math.radians(L[i][1]), places=5)
        self.assertEqual(u.eklem["tutucu_ayna"].find("mimic").get("joint"), "tutucu")
        self.assertEqual({j.get("type") for j in u.eklem.values()}, {"revolute", "prismatic", "fixed"})
        # her link tek bir ebeveyne bağlı, kök 'taban'
        linkler = {l.get("name") for l in u.kok.findall("link")}
        self.assertEqual(linkler - set(u.ust), {"taban"})
        for l in u.kok.findall("link"):
            m = l.find("inertial/mass")
            if m is not None:
                self.assertGreater(float(m.get("value")), 0)

    def test_kalibrasyonlu_sinirlar(self):
        sm.kalibrasyon({"yon": [1, -1, 1, 1, 1], "ofset": [5, -4.5, 0, 0, 10]})
        u, _ = self.karsilastir()
        lim = u.eklem["j1_govde"].find("limit")
        self.assertAlmostEqual(float(lim.get("upper")), math.radians(180 - 90 - 5), places=5)   # servo 180 -> eklem 85°

    def test_tutucu_eslemesi(self):
        self.assertAlmostEqual(uu.parmak_aciklik(sm.SERVO_MIN[5]), uu.PARMAK_MIN)
        self.assertAlmostEqual(uu.parmak_aciklik(sm.SERVO_MAX[5]), uu.PARMAK_MAX)
        self.assertAlmostEqual(uu.parmak_aciklik(500), uu.PARMAK_MAX)


if __name__ == "__main__":
    unittest.main(verbosity=2)
