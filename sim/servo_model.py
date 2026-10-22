"""
5 eksen + tutucu servo kol modeli (How To Mechatronics kolu): FK, analitik IK, servo açısı eşlemesi, statik tork.

Eksenler: J1 gövde (dikey eksen) · J2 omuz · J3 dirsek · J4 bilek dönüş · J5 bilek eğim · tutucu.
Model varsayımı: J4 bilek dönüşü, aletin kendi ekseni etrafında döner (konumu değiştirmez); J2, J3, J5 dikey düzlemde.
Açılar (eklem): J2 = 0 üst kol dik, + öne; J3 = 0 ön kol üst kolla aynı doğrultuda, + öne/aşağı; J5 = 0 düz, + aşağı.

ÖLÇÜLER ve PARÇA KÜTLELERİ kendi tasarımımızdan (cad/geometri.py, cad/kontrol.py). Tasarım değişirse buradaki
Olcu, PARCA ve TUTUCU_AGIZ_MM de güncellenir (cad/kontrol.py farkı yakalar).
"""
import math
from dataclasses import dataclass, field

G = 9.81


@dataclass
class Olcu:
    H0: float = 0.096   # masa -> omuz ekseni [m] (cad/geometri.py H0)
    L2: float = 0.120   # omuz -> dirsek (L2)
    L3: float = 0.100   # dirsek -> bilek eğim ekseni (L3)
    L4: float = 0.095   # bilek eğim ekseni -> tutma noktası (ped merkezi, tutucu 35°'de; açınca kısalır)


# Servo eşlemesi: servo_açısı = 90 + yön * eklem_açısı (+ ofset). Montajda kalibre edilir.
SERVO_YON = [1, 1, 1, 1, 1, 1]
SERVO_OFSET = [0, 0, 0, 0, 0, 0]
# kol_servo.ino ile aynı güvenli servo sınırları
SERVO_MIN = [0, 15, 10, 0, 0, 20]
SERVO_MAX = [180, 165, 170, 180, 180, 110]

# Kütleler [kg]: servolar veri sayfasından; baskı parçaları tasarımdan (hacim × PLA 1,24 g/cm³ × %60 doluluk)
MG996R_KG, SG90_KG = 0.055, 0.009
PARCA = dict(ust_kol=0.050, on_kol=0.027, bilek=0.009, tutucu=0.014)
# Tutucu ağzı (iki ped arası, mm) — servo açısına göre, cad/sim_mesh.py tablosundan (dişli 1:1 açısal çene)
TUTUCU_AGIZ_MM = [(20, 1.0), (25, 7.5), (30, 12.6), (35, 16.9), (40, 21.3), (45, 25.6), (50, 30.0), (55, 34.3),
                  (60, 38.5), (65, 42.6), (70, 46.6), (75, 50.4), (80, 54.0), (85, 57.4), (90, 60.5), (95, 63.3),
                  (100, 65.9), (105, 68.1), (110, 70.0)]


def tutucu_agiz(servo_deg):
    """Tutucu servo açısı -> iki ped arası açıklık (mm), tablo arası doğrusal."""
    t = TUTUCU_AGIZ_MM
    s = max(t[0][0], min(t[-1][0], servo_deg))
    for (a, x), (b, y) in zip(t, t[1:]):
        if s <= b:
            return x + (y - x) * (s - a) / (b - a)
    return t[-1][1]
# Tork kapasitesi: durma torku (veri sayfası), Nm
MG996R_DURMA = 9.4 * 0.0980665     # 4,8 V
SG90_DURMA = 1.2 * 0.0980665       # muhafazakâr (bazı listeler 1,8 kgf·cm)


def kalibrasyon(k=None):
    """Montaj kalibrasyonu (servo_kinematik.js kalibrasyon() ile aynı). k: {"yon": [±1 x5], "ofset": [° x5]}
    (simülasyon sayfasının Kalibrasyon sekmesinden dışa aktarılan JSON). Geçerli değerleri döndürür."""
    if k:
        for i in range(5):
            if "yon" in k:
                SERVO_YON[i] = -1 if float(k["yon"][i]) < 0 else 1
            if "ofset" in k:
                v = float(k["ofset"][i])
                SERVO_OFSET[i] = v if math.isfinite(v) else 0.0
    return {"yon": SERVO_YON[:5], "ofset": SERVO_OFSET[:5]}


def servo_aci(eklem_deg):
    return [90 + SERVO_YON[i] * eklem_deg[i] + SERVO_OFSET[i] for i in range(5)]


def eklem_aci(servo_deg):
    return [(servo_deg[i] - 90 - SERVO_OFSET[i]) * SERVO_YON[i] for i in range(5)]


def eklem_limit():
    """Servo sınırlarından eklem sınırları (derece)."""
    lim = []
    for i in range(5):
        a = (SERVO_MIN[i] - 90 - SERVO_OFSET[i]) * SERVO_YON[i]
        b = (SERVO_MAX[i] - 90 - SERVO_OFSET[i]) * SERVO_YON[i]
        lim.append((min(a, b), max(a, b)))
    return lim


def fk(q_deg, o: Olcu = Olcu()):
    """Eklem açıları (derece) -> noktalar: taban, omuz, dirsek, bilek, uç (x, y, z metre) ve alet açısı."""
    q1, q2, q3, _, q5 = [math.radians(v) for v in q_deg[:5]]
    a2, a3, a5 = q2, q2 + q3, q2 + q3 + q5          # dikeyden açılar
    pts_rz = [(0.0, 0.0), (0.0, o.H0)]
    e = (o.L2 * math.sin(a2), o.H0 + o.L2 * math.cos(a2))
    w = (e[0] + o.L3 * math.sin(a3), e[1] + o.L3 * math.cos(a3))
    t = (w[0] + o.L4 * math.sin(a5), w[1] + o.L4 * math.cos(a5))
    pts_rz += [e, w, t]
    c, s = math.cos(q1), math.sin(q1)
    return [(r * c, r * s, z) for r, z in pts_rz], math.degrees(a5)


def ik(xyz, alet_dikeyden_deg=180.0, o: Olcu = Olcu(), dirsek_yukari=True):
    """
    Uç konumu (m) + alet açısı (dikeyden; 180 = dik aşağı, 90 = yatay ileri) -> eklem açıları (derece) ya da None.
    J4 (bilek dönüş) 0 döner; tutucu ayrı.
    """
    x, y, z = xyz
    q1 = math.atan2(y, x)
    r = math.hypot(x, y)
    a5 = math.radians(alet_dikeyden_deg)
    wr, wz = r - o.L4 * math.sin(a5), z - o.L4 * math.cos(a5)
    dr, dz = wr, wz - o.H0
    d2 = dr * dr + dz * dz
    c3 = (d2 - o.L2 ** 2 - o.L3 ** 2) / (2 * o.L2 * o.L3)
    if abs(c3) > 1:
        return None
    q3 = math.acos(c3) * (1 if dirsek_yukari else -1)
    gamma = math.atan2(dr, dz)                                   # dikeyden
    q2 = gamma - math.atan2(o.L3 * math.sin(q3), o.L2 + o.L3 * math.cos(q3))
    q5 = a5 - q2 - q3
    q = [math.degrees(v) for v in (q1, q2, q3, 0.0, q5)]
    q[4] = (q[4] + 180) % 360 - 180
    return q


def limit_icinde(q_deg):
    return all(lo - 1e-9 <= q_deg[i] <= hi + 1e-9 for i, (lo, hi) in enumerate(eklem_limit()))


def tork(q_deg, yuk_kg=0.05, o: Olcu = Olcu()):
    """Omuz (J2), dirsek (J3), bilek eğim (J5) statik torkları [Nm] (mutlak)."""
    (b, s, e, w, t), _ = fk(q_deg, o)
    rh = lambda p, ref: math.hypot(p[0], p[1]) - math.hypot(ref[0], ref[1])   # yatay kol (aynı düzlem)
    mid = lambda a, b: tuple((a[i] + b[i]) / 2 for i in range(3))
    kutleler = [  # (kütle, konum, hangi eklemlerden sonra)
        (PARCA["ust_kol"], mid(s, e), 2),
        (MG996R_KG, e, 2),                         # dirsek servosu dirsekte
        (PARCA["on_kol"], mid(e, w), 3),
        (2 * SG90_KG + PARCA["bilek"], w, 3),     # bilek dönüş + eğim servoları
        (SG90_KG + PARCA["tutucu"], mid(w, t), 5),  # tutucu servosu + parmaklar
        (yuk_kg, t, 5),
    ]
    t2 = sum(m * G * rh(p, s) for m, p, _ in kutleler)
    t3 = sum(m * G * rh(p, e) for m, p, j in kutleler if j >= 3)
    t5 = sum(m * G * rh(p, w) for m, p, j in kutleler if j >= 5)
    return abs(t2), abs(t3), abs(t5)


KAPASITE = dict(J2=MG996R_DURMA, J3=MG996R_DURMA, J5=SG90_DURMA)
