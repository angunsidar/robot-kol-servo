# Basılabilir parçalar (kendi tasarımımız)

How To Mechatronics'in STL'lerini satın almak yerine, kolu **bizim MG996R / SG90 ölçülerimize göre** baştan tasarladık.
Fikir HTM ve benzeri açık kaynak kollardan (5 eksen + tutucu, MG996R omuz/dirsek, SG90 bilek/tutucu, dişli çeneler),
ölçüler ve yapı bizim.

- **Onshape:** [Servo Kol - basilabilir parcalar v1](https://cad.onshape.com/documents/07bb5b398428e26948303ebf/w/7504388708d5db1c149c24d5) (montaj sekmesi `servo_kol`, özel belge)
- **Simülasyon:** sayfadaki 3B kol artık bu parçaların kendisi ([servo-kol.html](../sim/servo-kol.html))
- **Baskı dosyaları:** [stl/](stl/) (bastırılacak), [step/](step/) (CAD; `servo_kol_montaj.step` servo zarflarıyla birlikte montaj)

| Dosya | Ne yapar |
|---|---|
| [geometri.py](geometri.py) | **Tek ölçü kaynağı.** Servo ölçüleri (kaynaklı), boşluklar, kol uzunlukları |
| [parcalar.py](parcalar.py) | Parçaların CadQuery modelleri (evolvent dişli dahil) |
| [model.py](model.py) | Montaj (FK), eklem taramalı **katı çakışma kontrolü**, STEP/STL çıktısı |
| [kontrol.py](kontrol.py) | Et kalınlıkları, cıvata boyları, dişli kavraması, tabla sığma, tork, simülasyon ölçüleriyle eşleşme |
| [sim_mesh.py](sim_mesh.py) | Parçaları simülasyon sayfasına ağ olarak gömer (`sim/servo_mesh.js`) |
| [../onshape/onshape_yukle.py](../onshape/onshape_yukle.py) | STEP'i API ile Onshape'e yükler (anahtarlar `.env`'de). API kotası dolunca arayüzden "Import" ile yüklenir |

```bash
pip install cadquery
python kontrol.py      # 47/47 GEÇTİ olmalı
python model.py        # 142 eklem konumunda çakışma taraması + STEP/STL (~1,5 dk)
python sim_mesh.py     # simülasyon ağları; sonra: python ../sim/build_page.py
```

## Doğrulananlar (2026-10-22)

- **Çakışma:** J1 ±90°, J2 ±75°, J3 ±80°, J5 ±90° (J4 = 0 ve 90), J4 ±90° (J5 = −90, 0, 90), tutucu 20–110° — her biri 5–10° adımla, servo zarfları ve horn süpürme alanı dahil: **0 çakışma**. Hareketli parçalar arasında en dar yer 1 mm eksenel boşluk (pulla ayarlanır).
- **Dişliler:** m 1,5, 16 diş, 20°: bütün tutucu aralığında dişler arası 0,14 mm boşluk, kavrama oranı 1,50, evolvent dışı temas yok.
- **Baskı:** 11 parça 220 × 220 mm tablaya sığıyor (en büyüğü üst kol, 166 mm). Toplam ~225 g PLA (%60 doluluk varsayımı; dilimleyici kesinleştirir).
- **Tork** (eklem sınırları içinde en kötü poz, 50 g yük): omuz MG996R durma torkunun %46'sı, dirsek %20'si, bilek SG90 %57'si (muhafazakâr 1,2 kgf·cm ile; 1,8 kgf·cm alınırsa %38).
- **Kinematik:** masa → omuz 96, üst kol 120, ön kol 100, bilek → tutma noktası 95 mm. Simülasyon, Python istemcisi ve URDF bu ölçülere geçirildi; testler 8/8.
- Bilek eğim (J5) dönüşten (J4) önce: dönüş aletin kendi ekseninde. Kinematik model bunu varsayıyordu, tasarım buna uyuyor.

**Doğrulanmayanlar:** gerçek baskı toleransı, PLA'nın dayanımı ve sünmesi, servo ölçülerinin TAHMİN olanları (aşağıda). Yazılım kontrolü fiziksel denemenin yerini tutmaz.

## Servolar gelince, baskıdan ÖNCE ölç

`geometri.py`'de "TAHMİN" yazanlar kaynaklarda yoktu. Kumpasla ölç, değiştir, `kontrol.py` + `model.py` çalıştır, sonra bastır:

| Ölçü | Şu an | Nerede kullanılıyor |
|---|---|---|
| MG996R kulak delikleri arası (aynı uç, uzun eksen boyunca) `DELIK_ARA` | 48,75 | gövde/üst kol/taban pilot delikleri |
| MG996R bir kulaktaki iki delik arası `DELIK_EN` | 10 | aynı |
| MG996R mil ↔ yakın gövde ucu `UC` | 10 | pencere yeri (karşı yatak oluğu ±1,5 mm'yi zaten karşılar) |
| MG996R horn dış yüzü (tabandan) `HORN_UST` | 47,6 | çatal genişliği (±1 mm pulla karşılanır) |
| SG90 horn dış yüzü `HORN_UST` | 31,5 | bilek ve tutucu |
| Kutudan çıkan horn'ların delik çapı ve yarıçapları | – | horn olukları M2–M3 sac vida / M3 için |

## Parçalar ve baskı

| Parça | Adet | Boyut (mm) | Önerilen yön |
|---|---|---|---|
| taban | 1 | 124 × 124 × 49 | alt levha tablada |
| govde | 1 | 96 × 96 × 69 | disk tablada |
| ust_kol | 1 | 166 × 70 × 44 | yan yatık (çatal levhaları dik, 24 mm'lik kenar tablada) |
| on_kol | 1 | 135 × 70 × 44 | yan yatık |
| bilek | 1 | 49 × 46 × 42 | yan yatık |
| tutucu_govde | 1 | 42 × 41 × 39 | servo levhası tablada |
| cene_A, cene_B | 1+1 | 51 × 27 × 5 | düz |
| burc_MG / burc_SG / burc_tutucu | 2 / 1 / 1 | Ø6 | dik |

PLA, 0,2 mm katman, 3–4 duvar, %30–40 dolgu. Çeneler ve burçlar %100 dolgu. Destek: kulak levhası pencerelerinin üstü 20–45 mm köprü (desteksiz basılabilir; hizmet isterse destek koyabilir).

## Cıvatalar (M3 seti)

| Yer | Ne | Adet |
|---|---|---|
| J2, J3 karşı yatak | M3×16 + somun + pul (burç içinden yanaktaki somun kanalına) | 2 |
| J5 karşı yatak | M3×10 + somun + pul | 1 |
| Tutucu dişli B mili | M3×16 + somun + pul | 1 |
| MG996R kulakları (J1, J2, J3) | M3×10–12, Ø2,6 pilot deliğe doğrudan (sac vida gibi) | 12 |
| SG90 kulakları | kutudan çıkan sac vidalar, Ø1,7 pilot | 6 |
| Horn bağlantıları | kutudan çıkan küçük sac vidalar (plastik horn) ya da M3 (metal 25T disk horn) | 2–4 / eklem |
| Taban → masa | Ø4 ağaç vidası ya da işkence (3 delik, Ø4,5) | 3 |

Set içeriğindeki boylar ürün sayfasında yazmıyor; geldiğinde 10 ve 16 mm olduğunu kontrol et.

## Montaj sırası (kısaca)

1. **Taban:** J1 servosunu tabandaki yuvaya oturt, kulakları direklere vidala, kabloyu kablo yuvasından çıkar.
2. **Servoları ortala** (README §2.5), sonra J1 horn'unu gövde diskinin altına vidala, diski mile tak ve **merkez vidasını şimdi** sık (J2 servosu takılınca erişim kalmıyor).
3. **J2 servosu:** gövdedeki kulak levhasının penceresinden geçir, kulakları vidala. Üst kolun A levhasına horn'u vidala, horn'u mile tak, merkez vidasını A levhasındaki delikten sık.
4. **Karşı yatak:** burcu B levhasının deliğine sok, M3×16'yı burçtan yanaktaki somuna vidala. Somun kanalı yukarıdan açık: önce somunu kanala bırak. Cıvatayı sıkmadan önce kolu birkaç kez çevir, burç mil hizasına otursun. Eksenel boşluğu (1 mm) gerekirse pulla al.
5. J3 ve ön kol için 3–4'ü tekrarla. J5 (SG90) aynı mantık.
6. **Bilek:** dönüş servosunu bilek levhasına vidala. Tutucu gövdesini dönüş horn'una vidala, mile tak, merkez vidasını sık.
7. **Tutucu:** servoyu tutucu gövdesine vidala, B dişlisini burç + M3×16 ile göbeğe tak. Tutucu servosunu 20°'ye getir, A çenesini çapraz horn'a çeneler neredeyse kapalıyken takacak şekilde oturt. 20° = ağız ~1 mm.

## Tasarım kararları

- **Çatal eklem + karşı yatak:** omuz, dirsek ve bilek eğimde sürülen parça servonun iki yanını sarıyor: bir yanı horn'a, öbür yanı burç üzerinden tutucunun yanağına. Servo mili yalnız tork taşıyor, eğilme yükünü yanak alıyor.
- **Ölçü belirsizliğine dayanıklılık:** karşı yatak cıvatası yanakta oluklu (MG ±1,5, SG ±0,8 mm), mil yeri tahmininden bağımsız hizalanıyor. Horn bağlantısı radyal oluklu, kutudaki farklı horn'lara ve metal diske uyuyor.
- **Devrilme halkası:** taban halkası gövde diskinin 2,5 mm altında; kol devrilmeye zorlanınca disk halkaya dayanır, J1 milini korur.
- **Tutucu:** 1:1 dişli, açısal çene. Servo 20° → ağız 1 mm, 35° → 17 mm, 70° → 47 mm, 110° → 70 mm. Çene açıldıkça tutma noktası bileğe yaklaşır (35°'de 95 mm, 70°'de 87 mm). Simülasyon bu tabloyu kullanıyor.
- **Katlanma uyarısı:** J2 = ±75°, J3 = ±80°, J5 = ±90° aynı anda (kol kendi üstüne katlanınca) çene tabana değiyor. Ters kinematik masanın altına inmediği için normal kullanımda bu poza gidilmez.
