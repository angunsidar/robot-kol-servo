"""Servo kol modeli testleri + JS karşılığıyla birebir karşılaştırma.  python -m unittest -v test_servo_model"""
import json
import math
import random
import shutil
import subprocess
import unittest
from pathlib import Path

import servo_model as sm

HERE = Path(__file__).resolve().parent
NODE = shutil.which("node")


def rastgele_q(rng):
    lim = sm.eklem_limit()
    return [rng.uniform(lo, hi) for lo, hi in lim]


class TestModel(unittest.TestCase):
    def test_fk_zero_pose(self):
        (b, s, e, w, t), a5 = sm.fk([0, 0, 0, 0, 0])
        o = sm.Olcu()
        self.assertAlmostEqual(t[2], o.H0 + o.L2 + o.L3 + o.L4)   # her şey dik
        self.assertAlmostEqual(a5, 0.0)

    def test_ik_roundtrip(self):
        rng = random.Random(4)
        n = 0
        for _ in range(3000):
            q = rastgele_q(rng)
            q[3] = 0.0
            (_, _, _, _, tip), a5 = sm.fk(q)
            for up in (True, False):
                qi = sm.ik(tip, a5, dirsek_yukari=up)
                if qi is None:
                    continue
                (_, _, _, _, tip2), a52 = sm.fk(qi)
                self.assertLess(math.dist(tip, tip2), 1e-9)
                self.assertAlmostEqual((a52 - a5 + 180) % 360 - 180, 0.0, places=7)
                n += 1
        self.assertGreater(n, 3000)

    def test_unreachable(self):
        self.assertIsNone(sm.ik((1.0, 0, 0.1), 180))

    def test_servo_mapping_roundtrip(self):
        q = [10, -20, 30, 0, 45]
        self.assertEqual(sm.eklem_aci(sm.servo_aci(q)), q)
        self.assertTrue(sm.limit_icinde([0, 0, 0, 0, 0]))
        self.assertFalse(sm.limit_icinde([0, 80, 0, 0, 0]))     # omuz 90+80=170 > 165

    def test_torque_worst_case(self):
        """Kol yatay ileri, 50 g yük: omuz torku MG996R durma torkunun altında olmalı."""
        t2, t3, t5 = sm.tork([0, 90, 0, 0, 0], 0.05)
        self.assertLess(t2, sm.KAPASITE["J2"])
        self.assertGreater(t2, t3)
        self.assertGreater(t3, t5)


@unittest.skipUnless(NODE, "node yok")
class TestJsMatches(unittest.TestCase):
    def test_js_identical(self):
        rng = random.Random(9)
        cases = []
        for _ in range(500):
            q = rastgele_q(rng)
            q[3] = 0.0
            (_, _, _, _, tip), a5 = sm.fk(q)
            cases.append(dict(q=q, tip=tip, a5=a5, yuk=rng.uniform(0, 0.2)))
        runner = HERE / "_r.js"
        runner.write_text(r"""
const M = require(process.argv[2]);
const inp = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const o = M.olcu();
process.stdout.write(JSON.stringify(inp.map(c => ({
  fk: M.fk(c.q, o), ik: M.ik(c.tip, c.a5, o, true), tork: M.tork(c.q, c.yuk, o), servo: M.servoAci(c.q),
  lim: M.limitIcinde(c.q)
}))));
""", encoding="utf-8")
        try:
            out = json.loads(subprocess.run([NODE, str(runner), str(HERE / "servo_kinematik.js")],
                                            input=json.dumps(cases), capture_output=True, text=True, check=True).stdout)
        finally:
            runner.unlink()
        for c, r in zip(cases, out):
            pts, a5 = sm.fk(c["q"])
            for p, pj in zip(pts, r["fk"]["noktalar"]):
                for a, b in zip(p, pj):
                    self.assertAlmostEqual(a, b, places=12)
            self.assertAlmostEqual(a5, r["fk"]["alet"], places=9)
            py = sm.ik(c["tip"], c["a5"], dirsek_yukari=True)
            if py is None:
                self.assertIsNone(r["ik"])
            else:
                for a, b in zip(py, r["ik"]):
                    self.assertAlmostEqual(a, b, places=9)
            for a, b in zip(sm.tork(c["q"], c["yuk"]), r["tork"]):
                self.assertAlmostEqual(a, b, places=12)
            self.assertEqual(sm.servo_aci(c["q"]), r["servo"])
            self.assertEqual(sm.limit_icinde(c["q"]), r["lim"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
