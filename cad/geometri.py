"""Servo kol — tek ölçü kaynağı (mm, derece). Parçalar (parcalar.py), montaj/çakışma (model.py) ve
kontroller (kontrol.py) ölçüleri yalnızca buradan okur.

Kaynaklar:
  MG996R: Handson Technology MG996R kılavuzu (40,3 × 20 gövde, 53,6 kulak, 26,6 kulak yüksekliği, 36,6 kasa,
          47,6 horn üstü) + TowerPro tablosu (40,7–40,9 × 19,7–20, 54 kulak, 42,9 mil dahil).
  SG90:   auselectronicsdirect SG90 çizimi (22,7 × 12,1 gövde, 32,4 kulak, 15,9 kulak yüksekliği, 2,4 kulak
          kalınlığı, 27,1 tümsek üstü, 30,7 mil üstü, kulak çentikleri uçtan 1,9).
  "TAHMİN" yazan ölçüler kaynakta yok: servolar gelince kumpasla ölç, buraya yaz, model.py'yi yeniden çalıştır.
  Tasarım bu belirsizlikleri boşluk/oluk ile karşılar (kontrol.py hangi ölçünün ne kadar oynayabileceğini yazar).

Eksen takımı (dünya): z yukarı, x ileri (J1 = 0 iken kolun uzandığı yön), y = omuz/dirsek/bilek ekseni.
Kol düzlemi y = 0 (kinematik modelde yanal kaçıklık yok).
"""
import math

# ======================= SERVO ÖLÇÜLERİ =======================
# Servo yerel ekseni: Zs = mil yönü (z=0 gövde tabanı), Xs = uzun eksen (mil Xs=0'da, gövde Xs ∈ [−(L−UC), UC]),
# Ys = gövde eni.
MG = dict(
    L=40.7, W=20.0,          # gövde boy × en
    UC=10.0,                 # mil ekseni ↔ yakın gövde ucu (TAHMİN ±1; oluk + boşluk karşılar)
    H=36.8,                  # kasa üstü (36,6–37)
    KULAK_Z=26.6,            # kulak alt yüzü (26,6–26,8)
    KULAK_T=2.5,             # kulak kalınlığı (TAHMİN)
    KULAK_L=53.8,            # kulak uçtan uca (53,6–54)
    DELIK_ARA=48.75,         # aynı eksendeki kulak delikleri arası (TAHMİN 48–49,5 → oluk ±1,75)
    DELIK_EN=10.0,           # bir kulaktaki iki delik arası (TAHMİN)
    TUMSEK_D=14.0, TUMSEK_UST=39.8,   # mil çevresindeki dişli tümseği (TAHMİN)
    MIL_D=6.0, MIL_UST=42.8,
    HORN_UST=47.6,           # horn dış yüzü (kutudaki yuvarlak horn ile, Handson)
    HORN_R=20.0, HORN_T=4.0, # horn süpürme zarfı (uzun kollu horn dahil, TAHMİN)
    KUTLE=0.055,
)
SG = dict(
    L=22.7, W=12.1,
    UC=5.9,                  # mil ↔ yakın uç (çizimden ölçek ile ~5,8–6)
    H=22.8,                  # tam kesitli kasa üstü (TAHMİN; 27,1 tümsek üstü)
    KULAK_Z=15.9, KULAK_T=2.4, KULAK_L=32.4,
    DELIK_ARA=28.6,          # kulak çentikleri (uçtan 1,9 → 32,4 − 3,8; çizimde 29 yazıyor)
    TUMSEK_D=11.8, TUMSEK_UST=27.1,
    MIL_D=4.8, MIL_UST=30.7,
    HORN_UST=31.5,           # horn dış yüzü (TAHMİN ±1)
    HORN_R=17.0, HORN_T=2.0, # 32 mm çift kollu horn zarfı
    KUTLE=0.009,
)

# ======================= GENEL =======================
VIDA_D = 3.4            # M3 geçiş deliği
SOMUN_AF = 5.5          # M3 somun anahtar ağzı
SOMUN_YUVA = 5.9        # somun yuvası (ağız + 0,4)
SOMUN_T = 2.4
SOMUN_YUVA_T = 2.7
BURC_D = 6.0            # karşı yatak burcu dış çapı (baskı)
BURC_DELIK = 6.4        # burcun döndüğü delik
BOS = 0.4               # servo gövdesi yan boşluğu (her yan)
MG_YUZER = 1.5          # MG996R uzun eksende yüzme payı (mil yeri belirsizliği + karşı yatak hizası)
SG_YUZER = 0.8
SG_PILOT = 1.7          # SG90 kulak vidası (kutudan çıkan sac vida) pilot deliği
G_SERVO = 1.0           # servo tabanı ↔ yanak (sabit, servo gövdesine göre)
G_CATAL_MG = 2.0        # MG çatal B levhası ↔ yanak: horn yüksekliği belirsizliği (±1,5) + pul payı
G_CATAL_SG = 1.5        # SG çatal B levhası ↔ yanak

# Horn bağlantısı: radyal oluklar (kutudaki plastik kollar M2/M2,5 sac vidayla, metal 25T disk M3 ile)
# r0: oluk ucu ↔ merkez delik / havşa arası ≥ 1,2 mm et. Oluk açıları her parçanın baskı yönüne göre (pahlı uçtan uzak).
HORN_MG = dict(merkez=8.5, en=3.4, r0=9.0, r1=13.5, acilar=(45, 135, 315), havsa=(12.0, 1.2))       # üst kol (J2)
HORN_MG_ON = dict(merkez=8.5, en=3.4, r0=9.0, r1=13.5, acilar=(45, 90, 270, 315), havsa=(12.0, 1.2))  # ön kol (J3)
HORN_MG_J1 = dict(merkez=8.5, en=3.4, r0=7.5, r1=15.0, acilar=(0, 180, 270), havsa=None)  # +y: J2 kulak levhası
HORN_SG = dict(merkez=5.5, en=2.2, r0=7.0, r1=15.0, acilar=(0, 90, 180, 270), havsa=(9.0, 1.0))
HORN_SG_TUT = dict(HORN_SG, acilar=(90, 180, 270))   # tutucu tabanı: +X'te dişli B sütunu (tornavida erişimi)
# havsa: horn göbeği için iç yüzde (Ø, derinlik) — göbek çıkıntılıysa levha yine kollara oturur

# ======================= KİNEMATİK ÖLÇÜLER =======================
# (sim/servo_model.py Olcu ile aynı olmalı — kontrol.py denetler)
H0 = 96.0               # masa → omuz (J2) ekseni
L2 = 120.0              # omuz → dirsek
L3 = 100.0              # dirsek → bilek eğim (J5)
# L4 aşağıda tutucu ölçülerinden hesaplanır

# ======================= TABAN + J1 =======================
TABAN_R = 62.0          # taban levhası
TABAN_T = 3.0
TABAN_AYAK_R = 56.0     # masaya vidalama delikleri (3 adet, Ø4,5)
J1_SERVO_TABAN = 3.5    # J1 servo tabanı z (levha üstünden 0,5 boşluk)
J1_KULAK_Z = J1_SERVO_TABAN + MG["KULAK_Z"]          # kulak alt yüzü = direk üstü
J1_HORN_UST = J1_SERVO_TABAN + MG["HORN_UST"]        # gövde diski alt yüzü
HALKA_RI, HALKA_RO = 41.0, 46.0                      # devrilme halkası (J1 servo kulak köşeleri r≈38,7)
HALKA_BOSLUK = 2.5                                    # halka üstü ↔ gövde diski
HALKA_UST = J1_HORN_UST - HALKA_BOSLUK

# ======================= GÖVDE (J1 üstü) + J2 =======================
DISK_R = 48.0
DISK_T = 5.0
DISK_Z0 = J1_HORN_UST
DISK_Z1 = DISK_Z0 + DISK_T

# Çatal eklem modülü (J2, J3 aynı): horn +y tarafında, karşı yatak −y tarafında.
WI_MG = 60.0            # çatal iç açıklığı (J1 merkez vidasına erişim için kulak levhası y ≥ 4 olmalı)
# Üst kol / ön kol yan yatırılarak basılır (x yukarı): tablaya bakan yüz düz, uçlar 45° pahlı (baski.py)
T_CATAL = 5.0           # çatal levha kalınlığı
T_KULAK = 5.0           # kulak levhası kalınlığı
Y_HORN = WI_MG / 2                                    # horn dış yüzü = çatal A iç yüzü
Y_SERVO_TABAN = Y_HORN - MG["HORN_UST"]               # servo tabanı (−17,6)
Y_KULAK = Y_SERVO_TABAN + MG["KULAK_Z"]               # kulak alt yüzü (9,0)
T_YANAK_MG = 6.0        # yanak: somun kanalı (2,7) iki yanında 1,65 mm et; servo tabanıyla arada boşluk kalır
Y_YANAK = (-WI_MG / 2 + G_CATAL_MG, -WI_MG / 2 + G_CATAL_MG + T_YANAK_MG)   # karşı yatak yanağı (−28 .. −22)
CATAL_A = (Y_HORN, Y_HORN + T_CATAL)
CATAL_B = (-WI_MG / 2 - T_CATAL, -WI_MG / 2)
UST_X = (-17.0, 17.0)   # üst kolun yanal (x) aralığı: bütün elemanlar aynı → yan yatık baskıda düz taban
ON_X = (-9.5, 17.0)     # ön kol: J5 ucu ±9,5 olmak zorunda (dönüş servosu süpürmesi) → tablaya bakan yüz −9,5
CATAL_R = 17.0          # çatal levha uç yarıçapı
UST_B_BOY = L2 - 30.0   # üst kol B levhası J3'ün 30 mm altında biter (ön kol çatal ucu r ≤ 17 + pay)
KOPRU_R = (28.0, 33.0)  # çatal köprüsü (eksenden radyal)
HAFIF_PAY = 6.0         # hafifletme penceresi ↔ levha kenarı / köprü arası et
KULAK_LEVHA_R = 24.0    # kulak levhasının eklem çevresindeki yuvarlatması (köprü 28'den başlar)
YANAK_UST = 10.0        # yan yatık basılan yanağın eksenden üst kesiği (düz)

# ======================= ÖN KOL + J5 (SG90 çatal) =======================
T_CATAL_SG = 3.5
T_KULAK_SG = 3.5
T_YANAK_SG = 6.0        # somun kanalı (2,7) iki yanında ≥ 1,6 mm et
WI_SG = SG["HORN_UST"] + G_SERVO + T_YANAK_SG + G_CATAL_SG    # 40
Y_HORN5 = WI_SG / 2                                   # 19,25
Y_SERVO5_TABAN = Y_HORN5 - SG["HORN_UST"]             # −12,25
Y_KULAK5 = Y_SERVO5_TABAN + SG["KULAK_Z"]             # 3,65
Y_YANAK5 = (-WI_SG / 2 + G_CATAL_SG, Y_SERVO5_TABAN - G_SERVO)   # −18,5 .. −12,5
CATAL5_A = (Y_HORN5, Y_HORN5 + T_CATAL_SG)
CATAL5_B = (-WI_SG / 2 - T_CATAL_SG, -WI_SG / 2)
ONKOL_KUTU_YAN = 9.5    # ön kol kutu kirişi yarı eni
ONKOL_DUVAR = 2.5
ONKOL_UC_R = 13.0       # J5 tutucunun ön ucu (bilek dönüş servosu r0'dan başlar)

# ======================= BİLEK (J5 → J4 dönüş servosu) =======================
R0_DONUS = 15.0         # J5 ekseni → dönüş servosu tabanı (alet ekseni boyunca)
BILEK_A_EN = 18.0       # bilek A levhası yarı eni = uç yarıçapı (baskıda genişleyen çıkıntı yok)
BILEK_B_EN = 10.0
T_DONUS_KULAK = 3.5
T_DONUS_KULAK_Z = R0_DONUS + SG["KULAK_Z"]            # dönüş servosu kulak alt yüzü (alet ekseninde)
T_DONUS_HORN = R0_DONUS + SG["HORN_UST"]              # tutucu tabanı alt yüzü

# ======================= TUTUCU =======================
# Tutucu çerçevesi: Z = alet ekseni (0 = dönüş horn yüzü), X = çene açılma yönü, Y = dişli ekseni.
TUT_TABAN_T = 3.5
DIS_M, DIS_Z, DIS_ALFA = 1.5, 16, 20.0
DIS_C = DIS_M * DIS_Z                                  # dişli merkez aralığı = 24
DIS_T = 5.0
DIS_BOSLUK = 0.15       # diş boşluğu (backlash)
Y_DISLI = (-DIS_T / 2, DIS_T / 2)                      # dişliler/çeneler alet ekseni üzerinde ortalı
DISLI_B_KADEME = 1.0    # B dişlisinin alt yüzü bu kadar yukarıda: A'nın horn kolları B'nin altından sürtünmeden geçer
Y_BOSS_UST = Y_DISLI[0] + DISLI_B_KADEME - 0.3          # dişli B göbeği üstü (0,3 eksenel boşluk)
Z_SERVO_MIL = 18.0      # tutucu servo mili (dişli A ekseni) Z
Y_TUT_SERVO_TABAN = Y_DISLI[0] - SG["HORN_UST"]       # −34
Y_TUT_KULAK = Y_TUT_SERVO_TABAN + SG["KULAK_Z"]       # −18,1
T_TUT_KULAK = 3.5
CENE_L = 38.0           # dişli merkezi → çene ucu
CENE_EN = 8.0
PED_L, PED_T = 14.0, 3.0
TUT_SERVO_KAPALI = 20.0 # bu servo açısında çene ağzı ≈ CENE_KAPALI_BOSLUK (fiziksel kapanma)
CENE_KAPALI_BOSLUK = 1.0
TUT_SERVO_MIN, TUT_SERVO_MAX = 20.0, 110.0
TUTUCU_BOSS_R = 5.5


def cene_aci(servo_deg, phi0):
    """Tutucu servo açısı → çene açısı (dışa +, alet ekseninden). Dişliler 1:1."""
    return phi0 + (servo_deg - TUT_SERVO_KAPALI)


def ped_merkez_z(phi_deg):
    """Çene ped merkezinin tutucu çerçevesinde Z'si (alet ekseni boyunca)."""
    a = math.radians(phi_deg)
    s = CENE_L - PED_L / 2
    return Z_SERVO_MIL + s * math.cos(a)


def L4_hesap(phi_deg):
    """J5 ekseni → tutma noktası (ped merkezi) mesafesi, verilen çene açısında."""
    return T_DONUS_HORN + ped_merkez_z(phi_deg)


# Baskı
BASKI_TABLA = (220.0, 220.0, 250.0)   # yaygın hizmet yazıcısı (Ender-3/Bambu: 220–256)
