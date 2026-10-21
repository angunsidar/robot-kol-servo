"""Tek dosyalık sayfa: sayfa_sablon.html + servo_kinematik.js + servo_hareket.js + servo_program.js + servo_kamera.js -> servo-kol.html"""
from pathlib import Path

HERE = Path(__file__).parent


def main():
    tpl = (HERE / "sayfa_sablon.html").read_text(encoding="utf-8")
    kin = (HERE / "servo_kinematik.js").read_text(encoding="utf-8")
    har = (HERE / "servo_hareket.js").read_text(encoding="utf-8")
    prg = (HERE / "servo_program.js").read_text(encoding="utf-8")
    kam = (HERE / "servo_kamera.js").read_text(encoding="utf-8")
    assert all(k in tpl for k in ("__KINEMATIK__", "__HAREKET__", "__PROGRAM__", "__KAMERA__"))
    out = HERE / "servo-kol.html"
    out.write_text(tpl.replace("__KINEMATIK__", kin).replace("__HAREKET__", har).replace("__PROGRAM__", prg).replace("__KAMERA__", kam), encoding="utf-8")
    print(f"yazıldı: {out} ({out.stat().st_size / 1e3:.0f} kB)")


if __name__ == "__main__":
    main()
