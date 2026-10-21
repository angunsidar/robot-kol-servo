"""
Servo kolu bilgisayardan Python ile sür. Simülasyon sayfasıyla aynı USB protokolünü (arduino/kol_servo/komut.h)
kullanır; kamera (OpenCV) ya da ROS köprüsü bunun üstüne kurulur.

    pip install pyserial
    from kol_istemci import Kol
    kol = Kol.ac("COM5", kalibrasyon="kalibrasyon.json")   # Arduino açılırken ~2 sn bekler
    kol.git(180, 0, 60)          # uç bu noktaya (mm), eklemler birlikte döner
    kol.duz_git(180, 0, 30)      # düz çizgide in
    kol.tutucu_kapa()
    print(kol.durum())           # {'konum': [...6 servo °], 'poz': 0, 'oynuyor': False, 'ss': 20}
    kol.kapat()

kalibrasyon.json: simülasyon sayfası -> Kalibrasyon sekmesi -> "Dışa aktar" çıktısı.
Koordinatlar mm; X ileri, Y sola, Z yukarı (taban merkezi, masa yüzeyi). Alet açısı dikeyden: 180 = dik aşağı.
Seri port Arduino IDE'nin seri monitörü ya da simülasyon sayfası açıkken açılamaz (tek program kullanabilir).
"""
import json
import math
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sim"))
import servo_model as sm  # noqa: E402

ARA_MM, ARA_DER, ARA_TOL = 5.0, 5.0, 15   # düz yol: sim/servo_program.js ile aynı
DURUM_RE = re.compile(r"^@((?:\s+-?\d+){6})(?:.*?poz\s+(\d+))?(?:.*?oynuyor\s+(\d))?(?:.*?ss\s+(\d+))?")


class KolHatasi(Exception):
    pass


class ErisimDisi(KolHatasi):
    pass


class Kol:
    def __init__(self, port, saat=time.monotonic, uyu=time.sleep, kalibrasyon=None, olcu=None, hazir_bekle=True):
        """port: read(n) (beklemeden, yoksa b"") ve write(bayt) yapan nesne (pyserial Serial(timeout=0) ya da test portu)."""
        self.port, self.saat, self.uyu = port, saat, uyu
        self.olcu = olcu or sm.Olcu()
        self.acik, self.kapali = 100.0, 35.0
        self.mesajlar = []          # Arduino'nun "@" dışındaki satırları (sırayla)
        self.hedef = None           # kola son gönderilen hedef, onda bir derece (6)
        self._tampon = b""
        self._son_durum = None
        if kalibrasyon is not None:
            self.kalibrasyon_yukle(kalibrasyon)
        if hazir_bekle:
            self.hazir_bekle()

    @classmethod
    def ac(cls, port_adi, baud=115200, **kw):
        try:
            import serial
        except ImportError as e:
            raise KolHatasi("pyserial gerekli: pip install pyserial") from e
        return cls(serial.Serial(port_adi, baud, timeout=0), **kw)

    def kapat(self):
        close = getattr(self.port, "close", None)
        if close:
            close()

    # ------------------------------------------------------------------ kalibrasyon
    def kalibrasyon_yukle(self, k):
        """Dosya yolu ya da sözlük: {"yon": [±1 x5], "ofset": [° x5], "acik": °, "kapali": °}"""
        if not isinstance(k, dict):
            k = json.loads(Path(k).read_text(encoding="utf-8"))
        sm.kalibrasyon(k)
        if "acik" in k:
            self.acik = float(k["acik"])
        if "kapali" in k:
            self.kapali = float(k["kapali"])
        return sm.kalibrasyon()

    # ------------------------------------------------------------------ seri hat
    def _gonder(self, metin):
        self.port.write((metin + "\n").encode("ascii"))

    def _oku(self):
        veri = self.port.read(4096)
        if veri:
            self._tampon += veri
        while b"\n" in self._tampon:
            satir, self._tampon = self._tampon.split(b"\n", 1)
            satir = satir.decode("ascii", "replace").strip()
            if not satir:
                continue
            if satir.startswith("@"):
                d = self._coz(satir)
                if d:
                    self._son_durum = d
            else:
                self.mesajlar.append(satir)

    @staticmethod
    def _coz(satir):
        m = DURUM_RE.match(satir)
        if not m:
            return None
        return {"konum": [int(v) / 10 for v in m.group(1).split()],
                "poz": int(m.group(2)) if m.group(2) else None,
                "oynuyor": m.group(3) == "1",
                "ss": int(m.group(4)) if m.group(4) else None}

    def satir_bekle(self, desen, zaman_asimi=2.0):
        """Arduino'dan desene uyan satırı bekle (öncekiler atılır). Bulunan satırı döndürür."""
        re_ = re.compile(desen)
        t0 = self.saat()
        while True:
            self._oku()
            while self.mesajlar:
                l = self.mesajlar.pop(0)
                if re_.search(l):
                    return l
            if self.saat() - t0 > zaman_asimi:
                raise KolHatasi(f"Arduino cevap vermedi (beklenen: {desen})")
            self.uyu(0.005)

    def hazir_bekle(self, zaman_asimi=4.0):
        """Port açılınca Arduino yeniden başlar: açılış satırını bekle (gelmezse "?" ile yokla)."""
        try:
            self.satir_bekle(r"hazir", zaman_asimi)
        except KolHatasi:
            pass
        d = self.durum(1.0)
        self.hedef = [round(v * 10) for v in d["konum"]]
        return d

    def durum(self, zaman_asimi=1.0):
        """{'konum': [6 servo, derece], 'poz': kayıtlı poz sayısı, 'oynuyor': bool, 'ss': ms}"""
        self._son_durum = None
        self.port.write(b"?")
        t0 = self.saat()
        while self._son_durum is None:
            self._oku()
            if self._son_durum is not None:
                break
            if self.saat() - t0 > zaman_asimi:
                raise KolHatasi("Arduino durum satırı göndermedi")
            self.uyu(0.002)
        return self._son_durum

    # ------------------------------------------------------------------ eklem / servo
    @staticmethod
    def _sinirla(i, onda):
        return int(max(sm.SERVO_MIN[i] * 10, min(sm.SERVO_MAX[i] * 10, round(onda))))

    def eklemler(self, onda, bekle=True):
        """Altı servoya birlikte (aynı anda varacak şekilde) git. onda: onda bir derece, 6 değer."""
        t = [self._sinirla(i, v) for i, v in enumerate(onda)]
        self._gonder("\n".join(f"a{i + 1}{v}" for i, v in enumerate(t)) + "\nGO")
        self.hedef = t
        if bekle:
            self.bekle_var(t)
        return t

    def servo(self, no, derece, bekle=True):
        """Tek servo (no 1..6), telefon uygulaması gibi tam derece."""
        i = no - 1
        v = self._sinirla(i, round(derece) * 10)
        self._gonder(f"s{no}{v // 10}")
        if self.hedef:
            self.hedef[i] = v
        if bekle and self.hedef:
            self.bekle_var(self.hedef)

    def tutucu(self, derece, bekle=True):
        h = list(self.hedef)
        h[5] = derece * 10
        return self.eklemler(h, bekle)

    def tutucu_ac(self, bekle=True):
        return self.tutucu(self.acik, bekle)

    def tutucu_kapa(self, bekle=True):
        return self.tutucu(self.kapali, bekle)

    def bekle_var(self, onda, tol=0, zaman_asimi=15.0):
        """Kol hedefe varana dek bekle (tol: onda bir derece; kol bildirdiği konumda hedefe tam oturur)."""
        t0 = self.saat()
        while True:
            k = self.durum()["konum"]
            if all(abs(k[i] * 10 - onda[i]) <= tol for i in range(6)):
                return k
            if self.saat() - t0 > zaman_asimi:
                raise KolHatasi(f"Kol {zaman_asimi:g} sn içinde hedefe varmadı")
            self.uyu(0.04)

    # ------------------------------------------------------------------ uç (ters kinematik)
    def ik(self, x, y, z, alet=180.0):
        """Uç noktası (mm) -> servo hedefleri (onda bir derece). Bilek dönüşü ve tutucu olduğu gibi kalır."""
        xyz = (x / 1000, y / 1000, z / 1000)
        q = None
        for yukari in (True, False):
            q = sm.ik(xyz, alet, self.olcu, dirsek_yukari=yukari)
            if q is not None and sm.limit_icinde(q):
                break
            q = None
        if q is None:
            raise ErisimDisi(f"({x:g}, {y:g}, {z:g}) mm, alet {alet:g}° erişim dışında ya da bir servo sınırını aşıyor")
        h = list(self.hedef)
        q[3] = sm.eklem_aci([v / 10 for v in h])[3]
        sv = sm.servo_aci(q)
        for i in range(5):
            h[i] = self._sinirla(i, sv[i] * 10)
        return h

    def uc(self, onda=None):
        """Servo hedeflerinin (varsayılan: kolun şu anki hedefi) uç noktası: (x, y, z) mm ve alet açısı."""
        onda = onda or self.hedef
        pts, alet = sm.fk(sm.eklem_aci([v / 10 for v in onda]), self.olcu)
        return tuple(c * 1000 for c in pts[4]), alet

    def git(self, x, y, z, alet=180.0, bekle=True):
        """Uç noktaya git; eklemler birlikte döner (uç bir yay çizer)."""
        return self.eklemler(self.ik(x, y, z, alet), bekle)

    def duz_git(self, x, y, z, alet=180.0):
        """Uç şu anki hedeften buraya düz çizgide gider (5 mm'lik ara noktalar; kol ara noktalarda durmaz)."""
        (x0, y0, z0), a0 = self.uc()
        n = max(1, math.ceil(max(math.dist((x0, y0, z0), (x, y, z)) / ARA_MM, abs(alet - a0) / ARA_DER)))
        hedefler = [self.ik(x0 + (x - x0) * k / n, y0 + (y - y0) * k / n, z0 + (z - z0) * k / n, a0 + (alet - a0) * k / n)
                    for k in range(1, n + 1)]                     # önce hepsini çöz: yolun ortası erişim dışındaysa hiç başlama
        for k, h in enumerate(hedefler):
            self.eklemler(h, bekle=False)
            if k < n - 1:
                self.bekle_var(h, tol=ARA_TOL)
        return self.bekle_var(hedefler[-1])

    # ------------------------------------------------------------------ kayıt / oynatma
    def kaydet(self):
        self._gonder("SAVE")
        return self.satir_bekle(r"kaydedildi|dolu|once PAUSE")

    def oynat(self):
        self._gonder("RUN")
        return self.satir_bekle(r"Oynatiliyor|poz yok")

    def duraklat(self, zaman_asimi=5.0):
        """Oynatmayı (ya da süren hareketi) durdur; kol yavaşlayıp tamamen durunca döner."""
        self._gonder("PAUSE")
        r = self.satir_bekle(r"Duraklatildi")
        t0, once = self.saat(), None
        while True:                                       # iki ardışık durumda konum aynıysa durmuştur
            k = self.durum()["konum"]
            if k == once:
                break
            if self.saat() - t0 > zaman_asimi:
                raise KolHatasi("Kol durmadı")
            once = k
            self.uyu(0.04)
        self.hedef = [round(v * 10) for v in k]
        return r

    def sifirla(self):
        self._gonder("RESET")
        return self.satir_bekle(r"silindi")

    def hiz(self, ms_derece):
        """Oynatma hızı: 1° başına ms (2..500)."""
        self._gonder(f"ss{int(ms_derece)}")

    def yukle(self, pozlar):
        """Pozları (onda bir derece, 6'şar) kolun EEPROM'una yaz; koldaki eski kayıtlar silinir. Kol kıpırdamaz."""
        if len(pozlar) > 50:
            raise KolHatasi(f"Kol en fazla 50 poz saklar, {len(pozlar)} verildi")
        self.duraklat()
        self.sifirla()
        for k, p in enumerate(pozlar):
            self._gonder("\n".join(f"a{i + 1}{self._sinirla(i, v)}" for i, v in enumerate(p)) + "\nPUT")
            l = self.satir_bekle(r"kaydedildi|dolu|once PAUSE")
            if "kaydedildi" not in l:
                raise KolHatasi(f"{k + 1}. poz kaydedilemedi: {l}")
        return len(pozlar)
