// komut.h Kol'unu bir komut senaryosuyla çalıştırıp her adımın konum ve hızını yazar.
// sim/test_hareket.py aynı senaryoyu sim/servo_hareket.js'e de verir ve çıktıları karşılaştırır.
// Girdi (stdin):  ilk satır adım sayısı, sonra "adim tip servo deger" satırları (tip: komut.h Tip sırası)
// Çıktı: komut başına "R adim kod", adım başına "P adim p0 v0 ... p5 v5"
#include <cstdio>
#include <cstring>

#include "komut.h"

using namespace kol;

static uint8_t eeprom[1024];
static uint8_t e_oku(uint16_t a) { return eeprom[a]; }
static void e_yaz(uint16_t a, uint8_t v) { eeprom[a] = v; }

int main() {
  std::memset(eeprom, 0xFF, sizeof eeprom);
  const uint8_t EV[6] = {90, 100, 80, 90, 90, 60}, MN[6] = {0, 15, 10, 0, 0, 20}, MX[6] = {180, 165, 170, 180, 180, 110};
  Kol kol;
  kol.basla(EV, MN, MX, Depo{e_oku, e_yaz});
  int n = 0;
  if (std::scanf("%d", &n) != 1) return 1;
  int ka = -1, kt = 0, ks = 0, kd = 0;
  bool var = std::scanf("%d %d %d %d", &ka, &kt, &ks, &kd) == 4;
  for (int s = 0; s < n; ++s) {
    while (var && ka == s) {
      Komut k; k.tip = (Tip)kt; k.servo = (uint8_t)ks; k.deger = (int16_t)kd;
      std::printf("R %d %d\n", s, kol.uygula(k));
      var = std::scanf("%d %d %d %d", &ka, &kt, &ks, &kd) == 4;
    }
    kol.adim();
    std::printf("P %d", s);
    for (int i = 0; i < 6; ++i) std::printf(" %.9g %.9g", (double)kol.p[i], (double)kol.v[i]);
    std::printf("\n");
  }
  return 0;
}
