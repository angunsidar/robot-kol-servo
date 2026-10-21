"""
Bütün testleri tek komutla çalıştırır (yerelde ve GitHub Actions'ta):  python testleri_calistir.py
Gerekenler: Python 3.10+, Node.js 18+, bir C++ derleyici (g++ / clang++ ya da `pip install ziglang`).
Bir test takımı başarısız olursa çıkış kodu 1 olur.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent


def derleyici():
    try:
        import ziglang  # noqa: F401
        return [sys.executable, "-m", "ziglang", "c++"]
    except ImportError:
        pass
    for c in ("g++", "clang++"):
        if shutil.which(c):
            return [c]
    return None


def calistir(ad, komut, cwd):
    t0 = time.time()
    r = subprocess.run(komut, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    sure = time.time() - t0
    ok = r.returncode == 0
    son = [l for l in (r.stdout + r.stderr).strip().splitlines() if l.strip()]
    print(f"{'GEÇTİ' if ok else 'KALDI'}  {ad:<46} {sure:5.1f} sn  {son[-1][:70] if son else ''}")
    if not ok:
        print("\n".join("      " + l for l in son[-25:]))
    return ok


def main():
    cxx, node = derleyici(), shutil.which("node")
    if not cxx or not node:
        print("Eksik: " + ", ".join(x for x, v in (("C++ derleyici", cxx), ("node", node)) if not v))
        return 1
    sonuc = []
    with tempfile.TemporaryDirectory() as tmp:
        exe = str(Path(tmp) / ("test_komut.exe" if os.name == "nt" else "test_komut"))
        for o in ("-O0", "-O2"):
            ok = calistir(f"derle: Arduino komut.h ({o})", cxx + ["-std=c++17", o, "-Wall", "-Wextra", "-ffp-contract=off",
                          "-I", "kol_servo", "test/test_komut.cpp", "-o", exe], KOK / "arduino")
            sonuc.append(ok and calistir(f"Arduino komut.h testleri ({o})", [exe], KOK / "arduino"))
    py = sys.executable
    sonuc += [
        calistir("JS = C++ hareket eşliği (test_hareket.py)", [py, "test_hareket.py"], KOK / "sim"),
        calistir("Kinematik model (test_servo_model.py)", [py, "test_servo_model.py"], KOK / "sim"),
        calistir("URDF (test_urdf.py)", [py, "test_urdf.py"], KOK / "sim"),
        calistir("Program (test_program.js)", [node, "test_program.js"], KOK / "sim"),
        calistir("Kamera (test_kamera.js)", [node, "test_kamera.js"], KOK / "sim"),
        calistir("Python istemcisi (test_kol_istemci.py)", [py, "test_kol_istemci.py"], KOK / "pc"),
    ]
    print(f"\n{sum(sonuc)}/{len(sonuc)} takım geçti")
    return 0 if all(sonuc) else 1


if __name__ == "__main__":
    sys.exit(main())
