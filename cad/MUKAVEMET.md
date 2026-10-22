# Servo kol — mukavemet hesabı

`cad/mukavemet.py` üretir; yükler CAD'deki gerçek kütle ve ağırlık merkezlerinden. El hesabı (kiriş/levha teorisi), FEA değil. Kesitler bilerek kötümser seçildi.

## Varsayımlar

- **PLA:** katman içi akma 51 MPa, katmanlar arası yapışma 17 MPa, E 2.3 GPa ([Prusament PLA veri sayfası](https://www.matterhackers.com/r/xFvGl8)). Baskı hizmetinin filamenti bilinmiyor.
- **Emniyet katsayısı 3** → izin: katman içi 17.0 MPa, katmanlar arası 5.7 MPa. Delik/oluk/köşe yakınında gerilme ayrıca Kt ile çarpıldı.
- **Servo torku:** MG996R 1.27 N·m (13 kgf·cm, satıcı beyanlarının en yükseği; veri sayfası 9,4 @4,8 V, 11 @6 V — [TowerPro](https://courses.ece.cornell.edu/ece5990/ECE5725_Spring2020_Projects/May_15_Demo/Smart%20Lock/W_pp445_yl656/datasheet/MG996R_Tower-Pro.pdf)), SG90 0.177 N·m (1,8 kgf·cm).
- **Yük durumları:** YD1 yerçekimi + 50 g yük × dinamik çarpan 1.5; YD2 200 g aşırı yük (statik); ikisinde de eklem sınırları içindeki pozlar (J2 ±75°, J3 ±80°, J5 ±90°) 15–30° adımla tarandı. **Durma:** kol bir engele takılı ve servo tam güçte (parçanın göreceği en büyük tork).
- **Sünme:** sürekli tutma yükünde gerilme dayanımın %25'ini geçmesin (genel kural, TAHMİN).

## Eklem tepkileri (CAD kütleleriyle)

| Eklem | YD1 tork (N·m) | YD2 tork (N·m) | Kuvvet YD1 / YD2 (N) | A levhası / servo mili (N) | B levhası / burç (N) | En kötü poz (J2, J3, J4, J5) |
|---|---|---|---|---|---|---|
| J2 | 0.659 | 0.896 | 3.90 / 4.07 | 2.04 | 2.16 | (75, 20, 0, 0) |
| J3 | 0.278 | 0.472 | 2.09 / 2.86 | 1.43 | 1.51 | (-30, -60, 0, 0) |
| J5 | 0.102 | 0.208 | 1.43 / 2.42 | 1.21 | 1.31 | (0, -60, 0, -30) |
| J1 | devrilme momenti 0.659 / 0.896 N·m | | 5.30 / 5.00 | | | (75, 20, 0) |

Omuz servosu YD1'de veri sayfası durma torkunun %71'ini görüyor (dinamik çarpan dahil). Servo mili radyal yükü A levhası sütunundaki kuvvet; MG996R için radyal yük sınırı yayımlanmamış, değerler küçük.

## Kesitler

| Kesit | Yön | Kt | YD1/YD2 σ (MPa) | Durma σ (MPa) | İzin (MPa) | Emniyet (durma) | Sürekli yük / dayanım | Sonuç |
|---|---|---|---|---|---|---|---|---|
| S1 Üst kol A levhası, horn çevresi (z=18) | katman içi | 1.5 | 1.45 | 1.99 | 17.0 | 25.7 | %2.8 | ✅ |
| S2 Üst kol pencereli kesit (iki levha) | katman içi | 1.3 | 0.83 | 1.18 | 17.0 | 43.2 | %1.6 | ✅ |
| S3 Üst kol köprü 1 burulması (J2 momenti) | katman arası | 1.2 | 2.02 | 2.87 | 5.7 | 5.9 | %11.9 | ✅ |
| S3b Üst kol köprü 2 burulması (J3 tepkisi) | katman arası | 1.2 | 1.06 | 2.87 | 5.7 | 5.9 | %6.3 | ✅ |
| S3c Ön kol köprüsü burulması (J3 momenti) | katman arası | 1.2 | 1.46 | 3.94 | 5.7 | 4.3 | %8.6 | ✅ |
| S4 Üst kol J3 kulak levhası tabanı | katman içi | 1.5 | 0.74 | 1.99 | 17.0 | 25.7 | %1.4 | ✅ |
| S5 Üst kol J3 yanağı (burç kuvveti) | katman içi | 2.0 | 0.13 | 0.54 | 17.0 | 94.4 | %0.3 | ✅ |
| S6 Ön kol A levhası, horn çevresi | katman içi | 1.5 | 1.28 | 3.27 | 17.0 | 15.6 | %2.5 | ✅ |
| S7 Ön kol kutu kiriş | katman içi | 1.2 | 0.41 | 1.09 | 17.0 | 46.6 | %0.8 | ✅ |
| S8 Gövde kulak levhası tabanı | katman arası | 1.5 | 0.91 | 1.19 | 5.7 | 14.3 | %5.3 | ✅ |
| S9 Gövde yanağı tabanı (burç kuvveti) | katman arası | 1.5 | 0.22 | 0.55 | 5.7 | 30.8 | %1.3 | ✅ |
| S10 Gövde diski (devrilme momenti) | katman içi | 1.5 | 4.27 | 4.27 | 17.0 | 12.0 | %8.4 | ✅ |
| S11 Taban direkleri (J1 tepki) | katman arası | 1.5 | 0.15 | 0.99 | 5.7 | 17.2 | %0.9 | ✅ |
| S12 Bilek A levhası (J5) | katman arası | 1.5 | 0.41 | 0.35 | 5.7 | 48.5 | %2.4 | ✅ |
| S13 Bilek B levhası (burç) | katman arası | 2.0 | 0.35 | 0.25 | 5.7 | 69.1 | %2.0 | ✅ |
| S14 Çene kökü (sıkma) | katman içi | 1.5 | 2.48 | 4.96 | 17.0 | 10.3 | – | ✅ |
| S15 Dişli kökü (Lewis) | katman içi | 1.0 | 3.31 | 6.63 | 17.0 | 7.7 | – | ✅ |
| S16 Dişli B göbeği | katman içi | 2.0 | 2.91 | 5.82 | 17.0 | 8.8 | – | ✅ |

Emniyet (durma) = dayanım / (Kt × durma gerilmesi): servo tam güçle zorlasa bile kalan pay.

## Bağlantılar

| Bağlantı | Değer | İzin / kapasite | Sonuç | Not |
|---|---|---|---|---|
| MG horn vidası PLA yatak gerilmesi (durma) | 3.78 MPa | 17.0 MPa | ✅ | vida başına 57 N |
| SG horn vidası PLA yatak gerilmesi (durma) | 1.15 MPa | 17.0 MPa | ✅ | vida başına 8 N |
| MG kulak vidası PLA yatak gerilmesi (durma) | 0.87 MPa | 17.0 MPa | ✅ | vida başına 13 N |
| J2 burç yatak gerilmesi | 0.07 MPa | 17.0 MPa | ✅ | F_B = 2.2 N |
| J5 burç yatak gerilmesi | 0.06 MPa | 17.0 MPa | ✅ | F_B = 1.3 N |
| J2/J3 M3 cıvata eğilmesi | 7.25 MPa | 200.0 MPa | ✅ | kol 4.5 mm |
| J1 kulak vidası çekme (devrilme) / sökülme kapasitesi | 9.19 N | 400.6 N | ✅ | taban direğinde 12 mm diş: daha da güvenli |

## Sehim ve hassasiyet

- Kol yatay uzanmışken (YD1) üst kol + ön kol eğilmesinden uçta **0.271 mm** sehim (üst kol I = 23880 mm⁴, ön kol I = 13283 mm⁴, E = 2.3 GPa).
- Karşılaştırma: MG996R ölü bandı 5 µs ≈ 0.45° → uçta tek bir eklemden **2.5 mm**. Yani hassasiyeti parçaların esnemesi değil, servoların ölü bandı ve dişli boşluğu belirliyor.

## Taşıma kapasitesi: sınırı servo koyuyor

- Kol tam uzanıkken (omuz 75°) omuz servosu: 50 g yükte statik 48%, dinamik çarpanla 71% · 200 g yükte 97% (veri sayfası durma torku 9,4 kgf·cm @4,8 V'a göre).
- Yani **200 g kol tam uzanıkken kaldırılamaz**, parçalar sağlam kalsa bile servo durur. Önerilen yük ~50 g; kola yakın çalışırken daha fazlası mümkün. Simülasyondaki tork göstergesi pozdaki gerçek oranı verir.

## En kritik yerler

- S3c Ön kol köprüsü burulması (J3 momenti): durma torkunda gerilme / izin = %69 (katman arası).
- S3b Üst kol köprü 2 burulması (J3 tepkisi): durma torkunda gerilme / izin = %51 (katman arası).
- S3 Üst kol köprü 1 burulması (J2 momenti): durma torkunda gerilme / izin = %51 (katman arası).
- Köprüler 10 mm: eklem momenti köprüden burulmayla geçiyor ve bu kayma yan yatık baskıda katmanlar arasına düşüyor. Kolları **en az 4 duvarla** bastır; dolgulu köprü kapalı kabuk gibi çalışır.
- Baskı kesitlerinden önce kopma ihtimali olanlar satın alınan parçalar: **plastik horn'ların 25T dişi** (MG996R durma torkunda sıyırabilir; metal 25T disk horn bu riski kaldırır) ve **horn'u parçaya bağlayan küçük sac vidalar**. Servo milinin radyal yük sınırı yayımlanmamış; karşı yatak sayesinde mil yalnız A levhası payını taşıyor.

**Doğrulanmayanlar:** gerçek filament ve baskı kalitesi, katman yapışması (veri sayfasındaki değerden düşük olabilir), yorulma ve sünme; bunlar emniyet katsayısıyla karşılanmaya çalışıldı, ilk montajda gözle kontrol gerekir.
