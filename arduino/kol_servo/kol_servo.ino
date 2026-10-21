// Servo robot kol – Arduino Uno + 3x MG996R + 3x SG90 + HC-05
// Mekanik: How To Mechatronics "DIY Arduino Robot Arm" (Cults3D'den satın alınan STL'ler).
// Kod: bu projeye özel yazıldı; orijinal Android uygulamasının komutlarıyla uyumlu (komut.h).
//
// Pinler (orijinal projeyle aynı):
//   D5 gövde (MG996R) · D6 omuz (MG996R) · D7 dirsek (MG996R)
//   D8 bilek dönüş (SG90) · D9 bilek eğim (SG90) · D10 tutucu (SG90)
//   D3 <- HC-05 TX · D4 -> HC-05 RX (1k/2k bölücü ile, HC-05 RX 3,3 V)
// Servolar AYRI 5 V (en az 3 A, önerilen 5 A) adaptörden beslenir; GND'ler ortak.
//
// USB seri port (115200) aynı komutları kabul eder: "s290", "SAVE", "RUN" ... ve "a1905" + "GO" (komut.h).
// Ek USB komutu: "?" -> durum satırı. Simülasyon sayfası kola bağlanınca bunu okuyup 3B modeli gerçek kola göre çizer:
//   @ 900 1000 800 900 900 600 | poz 3 | oynuyor 0 | ss 20     (açılar onda bir derece)
// Kayıtlı pozlar EEPROM'da durur: elektrik kesilince silinmez, RESET ile silinir.

#include <EEPROM.h>
#include <Servo.h>

// HC-05 için yazılımsal seri port: NeoSWSerial (Arduino IDE -> Kütüphane Yöneticisi -> "NeoSWSerial" kur).
// SoftwareSerial her karakteri alırken kesmeleri kapatır; Servo kütüphanesi darbe zamanlaması için kesmelere
// dayandığından, telefon kaydırıcıları veri akıtırken servolar ara sıra seğirir (Arduino forumu ve PJRC Servo
// belgesinde bilinen sorun). NeoSWSerial kesmeleri karakter boyunca kapatmaz, 9600 / 19200 / 38400'ü destekler;
// Uno'da yalnız Timer0 sayacını okur (Servo Timer1'i kullanır, çakışma yok). Kütüphaneyi kuramazsan 0 yap.
#define NEOSWSERIAL_KULLAN 1
#if NEOSWSERIAL_KULLAN
#include <NeoSWSerial.h>
#else
#include <SoftwareSerial.h>
#endif

#include "komut.h"

// HC-05 veri modu hızı. Orijinal proje 38400 kullanıyor; modülün fabrika ayarı genelde 9600'dür.
// Telefonla bağlanıp komutlar işlenmiyorsa bu değeri 9600 yap.
static const long HC05_BAUD = 38400;

static const uint8_t SERVO_PIN[kol::N_SERVO] = {5, 6, 7, 8, 9, 10};
// Açılış pozu ve güvenli sınırlar (derece). Montajdan sonra kendi koluna göre ayarla:
// özellikle tutucu sınırı, parmaklar kapanınca servo zorlanıp ısınmayacak şekilde olmalı.
static const uint8_t EV[kol::N_SERVO] = {90, 100, 80, 90, 90, 60};
static const uint8_t MIN_ACI[kol::N_SERVO] = {0, 15, 10, 0, 0, 20};
static const uint8_t MAX_ACI[kol::N_SERVO] = {180, 165, 170, 180, 180, 110};

#if NEOSWSERIAL_KULLAN
NeoSWSerial bt(3, 4);      // RX, TX
#else
SoftwareSerial bt(3, 4);   // RX, TX
#endif
Servo servo[kol::N_SERVO];
kol::Ayristirici ayr_bt, ayr_usb;
kol::Kol kolumuz;
int16_t yazilan[kol::N_SERVO];
uint32_t son_adim = 0;

static uint8_t eeprom_oku(uint16_t a) { return EEPROM.read(a); }
static void eeprom_yaz(uint16_t a, uint8_t v) { EEPROM.update(a, v); }   // aynı değeri yeniden yazmaz (ömür)

// Onda bir derece -> darbe genişliği. Servo kütüphanesinin attach(pin) varsayılanı: 0° = 544 µs, 180° = 2400 µs.
// write(derece) yerine mikrosaniye: 1° yerine ~0,1° adım, hareket daha pürüzsüz.
static int us(int16_t onda) { return (int)(544 + (int32_t)onda * (2400 - 544) / 1800); }

static const char* mesaj(int kod) {
  switch (kod) {
    case 1: return "Oynatma suruyor, once PAUSE";
    case 2: return "Kayit dolu (50 poz)";
    case 3: return "Poz kaydedildi";
    case 4: return "Kayitli poz yok";
    case 5: return "Oynatiliyor";
    case 6: return "Duraklatildi";
    case 7: return "Kayitlar silindi";
    default: return nullptr;
  }
}

static void bildir(int kod) {
  const char* m = mesaj(kod);
  if (!m) return;
  Serial.println(m);
  if (kod == 3) { Serial.print("  toplam poz: "); Serial.println(kolumuz.poz_sayisi); }
}

static void durum() {
  Serial.print('@');
  for (uint8_t i = 0; i < kol::N_SERVO; ++i) { Serial.print(' '); Serial.print(kolumuz.konum_onda(i)); }
  Serial.print(F(" | poz ")); Serial.print(kolumuz.poz_sayisi);
  Serial.print(F(" | oynuyor ")); Serial.print(kolumuz.oynuyor ? 1 : 0);
  Serial.print(F(" | ss ")); Serial.println(kolumuz.ss_ms);
}

static void isle(kol::Ayristirici& a) {
  kol::Komut k;
  while (a.al(k)) bildir(kolumuz.uygula(k));
}

void setup() {
  Serial.begin(115200);
  bt.begin(HC05_BAUD);
  kolumuz.basla(EV, MIN_ACI, MAX_ACI, kol::Depo{eeprom_oku, eeprom_yaz});
  // Açılışta servolar bilinmeyen konumdan EV pozuna bir kerede gider: kolu açmadan önce elle
  // EV pozuna yakın tut ya da servoları 5 V'a kodu yükledikten sonra bağla.
  // Servolar 150 ms arayla devreye girer: altısı aynı anda akım çekip adaptörü çökertmesin.
  for (uint8_t i = 0; i < kol::N_SERVO; ++i) {
    yazilan[i] = kolumuz.konum_onda(i);
    servo[i].writeMicroseconds(us(yazilan[i]));   // attach'tan önce yazılan değer ilk darbede kullanılır
    servo[i].attach(SERVO_PIN[i]);
    delay(150);
  }
  Serial.println(F("Servo kol hazir. Komutlar: s1..s6<aci>, ss<ms>, SAVE, RUN, PAUSE, RESET, a1..a6<onda> + GO, ?"));
  Serial.print(F("Kayitli poz: ")); Serial.println(kolumuz.poz_sayisi);
}

void loop() {
  uint32_t simdi = millis();

  while (bt.available()) ayr_bt.besle((char)bt.read(), simdi);
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '?') { durum(); continue; }
    ayr_usb.besle(c, simdi);
  }
  ayr_bt.bekle(simdi);
  ayr_usb.bekle(simdi);
  isle(ayr_bt);
  isle(ayr_usb);

  // 10 ms'lik sabit adımlar (kol::DT). Döngü bir an tıkanırsa en fazla 5 adım telafi edilir.
  uint8_t n = 0;
  while (simdi - son_adim >= 10) {
    son_adim += 10;
    kolumuz.adim();
    if (++n == 5) { son_adim = simdi; break; }
  }
  if (n) {
    for (uint8_t i = 0; i < kol::N_SERVO; ++i) {
      int16_t o = kolumuz.konum_onda(i);
      if (o != yazilan[i]) { servo[i].writeMicroseconds(us(o)); yazilan[i] = o; }
    }
  }
}
