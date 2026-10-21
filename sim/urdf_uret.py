"""
Servo kolun URDF'si (ROS / RViz / MoveIt robot tanımı): servo_model.py ölçüleri ve servo sınırlarından üretilir.
Eklem açıları servo_model'deki eklem açılarıyla aynıdır (0 = referans pozu: kol dik yukarı ve düz), sınırlar
kalibrasyon (ofset/yön) dahil servo sınırlarından gelir. test_urdf.py, URDF zincirinin FK'sının servo_model.fk ile
aynı olduğunu denetler.

    python urdf_uret.py                                   # -> ../ros2/servo_kol_description/urdf/servo_kol.urdf
    python urdf_uret.py --kalibrasyon ../pc/kalibrasyon.json

ÖLÇÜLER ve KÜTLELER TAHMİN (servo_model.py). STL'ler gelince güncellenip yeniden üretilecek.
"""
import argparse
import json
import math
from pathlib import Path

import servo_model as sm

HERE = Path(__file__).resolve().parent
CIKIS = HERE.parent / "ros2" / "servo_kol_description" / "urdf" / "servo_kol.urdf"

# Eklem adları (ROS joint_states sırası) -> servo numarası
EKLEMLER = ["j1_govde", "j2_omuz", "j3_dirsek", "j4_bilek_donus", "j5_bilek_egim"]
TUTUCU = "tutucu"                         # prismatik: parmak açıklığı (m), servo 6'dan
PARMAK_MIN, PARMAK_MAX = 0.004, 0.020     # sim/sayfa_sablon.html ile aynı (parmak başına, merkezden)
PARMAK_Z = 0.036                          # tutucu tabanından parmak başlangıcı


def parmak_aciklik(servo6_deg):
    """Tutucu servo açısı -> parmak konumu (m)."""
    a = (servo6_deg - sm.SERVO_MIN[5]) / (sm.SERVO_MAX[5] - sm.SERVO_MIN[5])
    return PARMAK_MIN + max(0.0, min(1.0, a)) * (PARMAK_MAX - PARMAK_MIN)


def _f(v):
    return f"{v:.6g}"


def _kutu_atalet(m, x, y, z):
    return dict(ixx=m * (y * y + z * z) / 12, iyy=m * (x * x + z * z) / 12, izz=m * (x * x + y * y) / 12)


def _link(ad, gorsel, kutle, kutu, merkez_z, renk):
    i = _kutu_atalet(kutle, *kutu)
    return f"""  <link name="{ad}">
    <visual>
      <origin xyz="0 0 {_f(merkez_z)}" rpy="0 0 0"/>
      <geometry>{gorsel}</geometry>
      <material name="{renk}"/>
    </visual>
    <collision>
      <origin xyz="0 0 {_f(merkez_z)}" rpy="0 0 0"/>
      <geometry><box size="{_f(kutu[0])} {_f(kutu[1])} {_f(kutu[2])}"/></geometry>
    </collision>
    <inertial>
      <origin xyz="0 0 {_f(merkez_z)}" rpy="0 0 0"/>
      <mass value="{_f(kutle)}"/>
      <inertia ixx="{_f(i['ixx'])}" ixy="0" ixz="0" iyy="{_f(i['iyy'])}" iyz="0" izz="{_f(i['izz'])}"/>
    </inertial>
  </link>
"""


def _eklem(ad, ust, alt, z, eksen, lim, tork, hiz):
    lo, hi = (math.radians(v) for v in lim)
    return f"""  <joint name="{ad}" type="revolute">
    <parent link="{ust}"/>
    <child link="{alt}"/>
    <origin xyz="0 0 {_f(z)}" rpy="0 0 0"/>
    <axis xyz="{eksen}"/>
    <limit lower="{_f(lo)}" upper="{_f(hi)}" effort="{_f(tork)}" velocity="{_f(hiz)}"/>
  </joint>
"""


def urdf_xml(o=sm.Olcu()):
    L = sm.eklem_limit()
    v_max = math.radians(1000 / 15)       # komut.h V_ELLE (°/s)
    mg, sg = sm.MG996R_DURMA, sm.SG90_DURMA
    P = sm.PARCA
    kutu = lambda x, y, z: f'<box size="{_f(x)} {_f(y)} {_f(z)}"/>'
    s = ['<?xml version="1.0"?>',
         '<!-- urdf_uret.py ile üretildi; elle düzenleme. Ölçü ve kütleler TAHMİN. -->',
         '<robot name="servo_kol">',
         '  <material name="mavi"><color rgba="0.12 0.37 0.75 1"/></material>',
         '  <material name="gri"><color rgba="0.73 0.76 0.78 1"/></material>',
         '  <material name="beyaz"><color rgba="0.94 0.94 0.94 1"/></material>',
         '  <material name="turuncu"><color rgba="0.85 0.4 0.1 1"/></material>',
         '']
    s.append(_link("taban", '<cylinder radius="0.055" length="0.06"/>', 0.20, (0.11, 0.11, 0.06), 0.03, "gri"))
    s.append(_eklem(EKLEMLER[0], "taban", "govde", 0.0, "0 0 1", L[0], mg, v_max))
    s.append(_link("govde", kutu(0.04, 0.056, o.H0 - 0.06), sm.MG996R_KG + 0.05, (0.04, 0.056, o.H0 - 0.06), 0.06 + (o.H0 - 0.06) / 2, "mavi"))
    s.append(_eklem(EKLEMLER[1], "govde", "ust_kol", o.H0, "0 1 0", L[1], mg, v_max))
    s.append(_link("ust_kol", kutu(0.026, 0.018, o.L2), P["ust_kol"] + sm.MG996R_KG, (0.026, 0.018, o.L2), o.L2 / 2, "mavi"))
    s.append(_eklem(EKLEMLER[2], "ust_kol", "on_kol", o.L2, "0 1 0", L[2], mg, v_max))
    s.append(_link("on_kol", kutu(0.024, 0.016, o.L3), P["on_kol"] + 2 * sm.SG90_KG, (0.024, 0.016, o.L3), o.L3 / 2, "mavi"))
    s.append(_eklem(EKLEMLER[4], "on_kol", "bilek", o.L3, "0 1 0", L[4], sg, v_max))
    s.append(_link("bilek", kutu(0.022, 0.022, 0.012), 0.010, (0.022, 0.022, 0.012), 0.006, "mavi"))
    s.append(_eklem(EKLEMLER[3], "bilek", "tutucu_govde", 0.0, "0 0 1", L[3], sg, v_max))
    s.append(_link("tutucu_govde", kutu(0.046, 0.014, 0.024), P["bilek"] + sm.SG90_KG, (0.046, 0.014, 0.024), 0.024, "beyaz"))
    boy = o.L4 - PARMAK_Z
    for ad, carpan in (("parmak_sag", 1), ("parmak_sol", -1)):
        s.append(_link(ad, kutu(0.006, 0.012, boy), P["tutucu"] / 2, (0.006, 0.012, boy), boy / 2, "beyaz"))
        mimic = "" if carpan == 1 else f'\n    <mimic joint="{TUTUCU}" multiplier="-1" offset="0"/>'
        s.append(f"""  <joint name="{TUTUCU if carpan == 1 else TUTUCU + '_ayna'}" type="prismatic">
    <parent link="tutucu_govde"/>
    <child link="{ad}"/>
    <origin xyz="0 0 {_f(PARMAK_Z)}" rpy="0 0 0"/>
    <axis xyz="1 0 0"/>
    <limit lower="{_f(PARMAK_MIN if carpan == 1 else -PARMAK_MAX)}" upper="{_f(PARMAK_MAX if carpan == 1 else -PARMAK_MIN)}" effort="{_f(sg)}" velocity="0.05"/>{mimic}
  </joint>
""")
    s.append('  <link name="uc"/>')
    s.append(f"""  <joint name="uc_sabit" type="fixed">
    <parent link="tutucu_govde"/>
    <child link="uc"/>
    <origin xyz="0 0 {_f(o.L4)}" rpy="0 0 0"/>
  </joint>
""")
    s.append("</robot>\n")
    return "\n".join(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kalibrasyon", help="simülasyon sayfasından dışa aktarılan kalibrasyon JSON'u")
    ap.add_argument("-o", "--cikis", default=str(CIKIS))
    a = ap.parse_args()
    if a.kalibrasyon:
        sm.kalibrasyon(json.loads(Path(a.kalibrasyon).read_text(encoding="utf-8")))
    yol = Path(a.cikis)
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(urdf_xml(), encoding="utf-8")
    print(f"yazıldı: {yol}  (kalibrasyon: {sm.kalibrasyon()})")


if __name__ == "__main__":
    main()
