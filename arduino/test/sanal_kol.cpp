// Sanal Arduino: kol_servo.ino'nun USB tarafını (komut.h + bildirim/durum satırları) bir DLL olarak verir.
// pc/test_kol_istemci.py bunu sahte seri port olarak kullanır: Python istemcisi gerçek Arduino koduyla konuşur.
// Zaman sanaldır: sk_zaman() ile ilerletilir. EEPROM, sk_yeni() çağrıları arasında korunur (elektrik kesilmesi
// benzetimi); sk_eeprom_sil() fabrika durumuna (0xFF) döndürür.
//
// Derleme (test kendisi yapar):  zig c++ -std=c++17 -O2 -shared -I../kol_servo sanal_kol.cpp -o sanal_kol.dll
#include <cstdio>
#include <cstring>
#include <string>

#include "komut.h"

#ifdef _WIN32
#define DISA extern "C" __declspec(dllexport)
#else
#define DISA extern "C" __attribute__((visibility("default")))
#endif

using namespace kol;

static uint8_t eeprom[1024];
static bool eeprom_hazir = false;
static uint8_t e_oku(uint16_t a) { return eeprom[a]; }
static void e_yaz(uint16_t a, uint8_t v) { eeprom[a] = v; }

// kol_servo.ino ile aynı değerler ve metinler (test, .ino dosyasını okuyup aynı olduklarını denetler)
static const uint8_t EV[N_SERVO] = {90, 100, 80, 90, 90, 60};
static const uint8_t MIN_ACI[N_SERVO] = {0, 15, 10, 0, 0, 20};
static const uint8_t MAX_ACI[N_SERVO] = {180, 165, 170, 180, 180, 110};
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

struct Sanal {
  Ayristirici ayr;
  Kol kol;
  std::string cikis;
  uint32_t simdi = 0, son_adim = 0;

  void yaz_satir(const std::string& s) { cikis += s; cikis += "\r\n"; }
  void bildir(int kod) {
    const char* m = mesaj(kod);
    if (!m) return;
    yaz_satir(m);
    if (kod == 3) yaz_satir("  toplam poz: " + std::to_string(kol.poz_sayisi));
  }
  void durum() {
    std::string s = "@";
    for (uint8_t i = 0; i < N_SERVO; ++i) s += " " + std::to_string(kol.konum_onda(i));
    s += " | poz " + std::to_string(kol.poz_sayisi) + " | oynuyor " + (kol.oynuyor ? "1" : "0") + " | ss " + std::to_string(kol.ss_ms);
    yaz_satir(s);
  }
  void isle() { Komut k; while (ayr.al(k)) bildir(kol.uygula(k)); }
  // Bir loop() turu (1 ms)
  void tur() {
    ayr.bekle(simdi);
    isle();
    uint8_t n = 0;
    while (simdi - son_adim >= 10) { son_adim += 10; kol.adim(); if (++n == 5) { son_adim = simdi; break; } }
  }
};

DISA void* sk_yeni() {
  if (!eeprom_hazir) { std::memset(eeprom, 0xFF, sizeof eeprom); eeprom_hazir = true; }
  Sanal* s = new Sanal();
  s->kol.basla(EV, MIN_ACI, MAX_ACI, Depo{e_oku, e_yaz});
  s->yaz_satir("Servo kol hazir. Komutlar: s1..s6<aci>, ss<ms>, SAVE, RUN, PAUSE, RESET, a1..a6<onda> + GO, ?");
  s->yaz_satir("Kayitli poz: " + std::to_string(s->kol.poz_sayisi));
  return s;
}
DISA void sk_sil(void* p) { delete static_cast<Sanal*>(p); }
DISA void sk_eeprom_sil() { std::memset(eeprom, 0xFF, sizeof eeprom); eeprom_hazir = true; }

// Bilgisayardan gelen baytlar (o anki sanal zamanda, kol_servo.ino loop()'undaki gibi)
DISA void sk_yaz(void* p, const char* veri, int n) {
  Sanal* s = static_cast<Sanal*>(p);
  for (int i = 0; i < n; ++i) {
    if (veri[i] == '?') { s->durum(); continue; }
    s->ayr.besle(veri[i], s->simdi);
  }
  s->isle();
}
// Sanal zamanı ms'ye kadar 1 ms'lik loop() turlarıyla ilerlet
DISA void sk_zaman(void* p, uint32_t ms) {
  Sanal* s = static_cast<Sanal*>(p);
  while (s->simdi < ms) { s->simdi++; s->tur(); }
}
DISA uint32_t sk_simdi(void* p) { return static_cast<Sanal*>(p)->simdi; }
// Arduino'dan bilgisayara giden baytları al (en fazla n); kalan sonraki çağrıya
DISA int sk_oku(void* p, char* buf, int n) {
  Sanal* s = static_cast<Sanal*>(p);
  int k = (int)s->cikis.size() < n ? (int)s->cikis.size() : n;
  std::memcpy(buf, s->cikis.data(), (size_t)k);
  s->cikis.erase(0, (size_t)k);
  return k;
}
// Servoların o anki konumu (derece) ve hedefleri (onda bir derece), test denetimi için
DISA void sk_konum(void* p, float* out6) { Sanal* s = static_cast<Sanal*>(p); for (int i = 0; i < 6; ++i) out6[i] = s->kol.p[i]; }
DISA void sk_hedef(void* p, int16_t* out6) { Sanal* s = static_cast<Sanal*>(p); for (int i = 0; i < 6; ++i) out6[i] = s->kol.hedef[i]; }
