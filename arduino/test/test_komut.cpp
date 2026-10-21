// komut.h masaüstü testi:  zig c++ -std=c++17 -ffp-contract=off -I../kol_servo test_komut.cpp -o t && ./t
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "komut.h"

#define CHECK(cond) do { if (!(cond)) { std::printf("HATA %s:%d: %s\n", __FILE__, __LINE__, #cond); std::exit(1); } } while (0)

using namespace kol;

// EEPROM yerine dizi
static uint8_t eeprom[1024];
static int yazma_sayisi = 0;
static uint8_t e_oku(uint16_t a) { return eeprom[a]; }
static void e_yaz(uint16_t a, uint8_t v) { if (eeprom[a] != v) yazma_sayisi++; eeprom[a] = v; }
static const Depo DEPO = {e_oku, e_yaz};

static const uint8_t EV[6] = {90, 90, 90, 90, 90, 90}, MN[6] = {0, 15, 0, 0, 0, 20}, MX[6] = {180, 165, 180, 180, 180, 110};

static Komut kmt(Tip t, uint8_t servo = 0, int16_t deger = 0) { Komut k; k.tip = t; k.servo = servo; k.deger = deger; return k; }

// Hareket kuralları: hız sınırı, ivme sınırı (oturma anı hariç), hedefi geçmeme. n adım ya da hedefe kadar.
static int yuru(Kol& kol, int n, bool hedefe_kadar = true) {
  for (int s = 0; s < n; ++s) {
    // adim() içinde oynatma sıradaki pozu yükleyebilir: sınırları adımdan önceki değerlerle denetle
    float v0[6], vl[6], al[6]; int16_t h0[6];
    for (int i = 0; i < 6; ++i) { v0[i] = kol.v[i]; vl[i] = kol.vlim[i]; al[i] = kol.alim[i]; h0[i] = kol.hedef[i]; }
    kol.adim();
    for (int i = 0; i < 6; ++i) {
      CHECK(std::fabs(kol.v[i]) <= vl[i] + 1e-3f || std::fabs(kol.v[i]) < std::fabs(v0[i]));
      bool oturdu = kol.v[i] == 0 && kol.p[i] == h0[i] * 0.1f;
      if (!(oturdu || std::fabs(kol.v[i] - v0[i]) <= al[i] * DT * 1.001f + 1e-4f))
        std::printf("ivme i=%d v0=%f v=%f p=%f hedef=%d alim=%f\n", i, v0[i], kol.v[i], kol.p[i], h0[i], al[i]);
      CHECK(oturdu || std::fabs(kol.v[i] - v0[i]) <= al[i] * DT * 1.001f + 1e-4f);
      CHECK(kol.p[i] >= kol.min_onda[i] * 0.1f - 0.01f && kol.p[i] <= kol.max_onda[i] * 0.1f + 0.01f);
    }
    if (hedefe_kadar && kol.hedefte()) return s + 1;
  }
  return n;
}

// Metni t0'dan başlayarak 1 ms aralıkla besle, sonunda zaman aşımı ver, komutları topla
static std::vector<Komut> ayristir(const std::string& s, uint32_t aralik_ms = 1) {
  Ayristirici a;
  std::vector<Komut> out;
  uint32_t t = 1000;
  Komut k;
  for (char c : s) { a.besle(c, t); t += aralik_ms; while (a.al(k)) out.push_back(k); }
  a.bekle(t + 100);
  while (a.al(k)) out.push_back(k);
  return out;
}

int main() {
  // Tek komutlar
  auto v = ayristir("s290");
  CHECK(v.size() == 1 && v[0].tip == Tip::SERVO && v[0].servo == 1 && v[0].deger == 90);
  v = ayristir("ss25");
  CHECK(v.size() == 1 && v[0].tip == Tip::HIZ && v[0].deger == 25);
  for (auto [w, t] : std::vector<std::pair<std::string, Tip>>{{"SAVE", Tip::KAYDET}, {"RUN", Tip::OYNAT},
                                                               {"PAUSE", Tip::DURAKLAT}, {"RESET", Tip::SIFIRLA}}) {
    v = ayristir(w);
    CHECK(v.size() == 1 && v[0].tip == t);
  }

  // Yapışık mesajlar (orijinal uygulamada bilinen sorun)
  v = ayristir("s190s2100s3120SAVEs645RUN");
  CHECK(v.size() == 6);
  CHECK(v[0].servo == 0 && v[0].deger == 90);
  CHECK(v[1].servo == 1 && v[1].deger == 100);
  CHECK(v[2].servo == 2 && v[2].deger == 120);
  CHECK(v[3].tip == Tip::KAYDET);
  CHECK(v[4].servo == 5 && v[4].deger == 45);
  CHECK(v[5].tip == Tip::OYNAT);

  // Küçük harf, ayraçlar, satır sonları (USB seri port)
  v = ayristir("s1 30\nsave\r\nss 5\n");   // elle yazımda önek ile sayı arasında boşluk olabilir
  CHECK(v.size() == 3 && v[0].tip == Tip::SERVO && v[0].deger == 30 && v[1].tip == Tip::KAYDET && v[2].deger == 5);
  v = ayristir("s130\nsave\nss5\n");
  CHECK(v.size() == 3 && v[0].deger == 30 && v[1].tip == Tip::KAYDET && v[2].deger == 5);

  // Parça parça gelen mesaj: "s2" ... uzun bekleme ... "90" -> zaman aşımı "s2"yi sayısız atar
  {
    Ayristirici a; Komut k; std::vector<Komut> out;
    a.besle('s', 0); a.besle('2', 1); a.besle('9', 5); a.besle('0', 10);
    a.bekle(20); while (a.al(k)) out.push_back(k);
    CHECK(out.empty());                       // 25 ms dolmadı, hâlâ bekliyor
    a.bekle(40); while (a.al(k)) out.push_back(k);
    CHECK(out.size() == 1 && out[0].deger == 90);
  }

  // Çöp ve tanınmayan karakterler
  v = ayristir("xyz!s3150??");
  CHECK(v.size() == 1 && v[0].servo == 2 && v[0].deger == 150);
  v = ayristir("s9100");                     // geçersiz servo numarası
  CHECK(v.empty());
  v = ayristir("SAVSAVE");                   // yarım kelime + tam kelime
  CHECK(v.size() == 1 && v[0].tip == Tip::KAYDET);

  // Yeni komutlar: a<servo><onda bir derece> ve GO
  v = ayristir("a2905a11200GO");
  CHECK(v.size() == 3 && v[0].tip == Tip::INCE && v[0].servo == 1 && v[0].deger == 905);
  CHECK(v[1].tip == Tip::INCE && v[1].servo == 0 && v[1].deger == 1200 && v[2].tip == Tip::GIT);
  v = ayristir("s190GOs2100");                // GO, s komutlarıyla yapışık
  CHECK(v.size() == 3 && v[1].tip == Tip::GIT && v[2].deger == 100);
  v = ayristir("a7100");
  CHECK(v.empty());

  // Kuyruk: "Git" patlaması (6 x a + GO) arada al() çağrılmadan sığmalı; 12'den fazlası atılır
  {
    Ayristirici a; Komut k; int n = 0;
    std::string s = "a1900\na21000\na3800\na4900\na5900\na6600\nGO\n";
    for (char c : s) a.besle(c, 0);
    while (a.al(k)) n++;
    CHECK(n == 7);
    for (int i = 0; i < 15; ++i) for (char c : std::string("s190\n")) a.besle(c, 0);
    n = 0; while (a.al(k)) n++;
    CHECK(n == 12);
  }

  // ---------------------------------------------------------------- hareket
  std::memset(eeprom, 0xFF, sizeof eeprom);   // boş EEPROM (fabrikadan 0xFF)
  Kol kol;
  kol.basla(EV, MN, MX, DEPO);
  CHECK(kol.poz_sayisi == 0 && eeprom[0] == 'K' && eeprom[3] == 0);   // başlık yazıldı
  CHECK(kol.hedefte());

  // Tek servo 90 -> 165 (sınır): 75° yol, 66,7°/s, 200°/s²: hızlanma 0,33 s + sabit 0,79 s + yavaşlama 0,33 s ≈ 1,46 s
  kol.uygula(kmt(Tip::SERVO, 1, 200));
  CHECK(kol.hedef[1] == 1650);
  int n = yuru(kol, 400);
  CHECK(kol.hedefte() && kol.p[1] == 165.0f);
  std::printf("90->165: %d adim (%.2f s)\n", n, n * DT);
  CHECK(n >= 140 && n <= 155);

  // Senkron hareket: farklı yol uzunlukları, hepsi aynı anda varmalı
  kol.uygula(kmt(Tip::INCE, 0, 300));          // 90 -> 30   (60°)
  kol.uygula(kmt(Tip::INCE, 2, 1100));         // 90 -> 110  (20°)
  kol.uygula(kmt(Tip::INCE, 4, 855));          // 90 -> 85,5 (4,5°)
  CHECK(kol.hedef[0] == 900);                 // GO'dan önce kıpırdamaz
  kol.uygula(kmt(Tip::GIT));
  int var[6] = {-1, -1, -1, -1, -1, -1};
  for (int s = 1; s <= 400; ++s) {
    yuru(kol, 1, false);
    for (int i = 0; i < 6; ++i) if (var[i] < 0 && kol.v[i] == 0 && kol.p[i] == kol.hedef[i] * 0.1f) var[i] = s;
    if (kol.hedefte()) break;
  }
  CHECK(kol.hedefte() && kol.p[4] == 85.5f);
  std::printf("senkron varis adimlari: %d %d %d\n", var[0], var[2], var[4]);
  CHECK(std::abs(var[0] - var[2]) <= 3 && std::abs(var[0] - var[4]) <= 3);

  // Sınır dışı onda bir derece
  kol.uygula(kmt(Tip::INCE, 5, 1500)); kol.uygula(kmt(Tip::GIT));
  yuru(kol, 400);
  CHECK(kol.p[5] == 110.0f);

  // Hedef aniden ters yöne: geçip geri döner, ivme sınırı korunur (yuru denetler)
  kol.uygula(kmt(Tip::SERVO, 0, 150));
  yuru(kol, 40, false);
  kol.uygula(kmt(Tip::SERVO, 0, 40));
  yuru(kol, 600);
  CHECK(kol.hedefte() && kol.p[0] == 40.0f);

  // PAUSE hareket ortasında: yumuşak durur, geri gitmez
  kol.uygula(kmt(Tip::SERVO, 0, 170));
  yuru(kol, 60, false);
  float v_once = kol.v[0];
  CHECK(v_once > 30);
  kol.uygula(kmt(Tip::DURAKLAT));
  float onceki = kol.p[0];
  for (int s = 0; s < 200; ++s) { yuru(kol, 1, false); CHECK(kol.p[0] >= onceki - 1e-4f); onceki = kol.p[0]; }
  CHECK(kol.hedefte() && kol.p[0] < 170.0f);

  // ---------------------------------------------------------------- kayıt (EEPROM) ve oynatma
  kol.uygula(kmt(Tip::SERVO, 0, 90)); yuru(kol, 400);
  CHECK(kol.uygula(kmt(Tip::KAYDET)) == 3);
  kol.uygula(kmt(Tip::INCE, 0, 305)); kol.uygula(kmt(Tip::INCE, 1, 600)); kol.uygula(kmt(Tip::GIT)); yuru(kol, 400);
  CHECK(kol.uygula(kmt(Tip::KAYDET)) == 3 && kol.poz_sayisi == 2 && eeprom[3] == 2);

  // Yeniden açılış: kayıtlar EEPROM'dan gelir
  Kol kol2;
  kol2.basla(EV, MN, MX, DEPO);
  CHECK(kol2.poz_sayisi == 2);
  int16_t pz[6];
  kol2.poz_oku(1, pz);
  CHECK(pz[0] == 305 && pz[1] == 600);

  CHECK(kol2.uygula(kmt(Tip::OYNAT)) == 5 && kol2.oynuyor);
  CHECK(kol2.uygula(kmt(Tip::SERVO, 2, 10)) == 1);       // oynatırken elle komut yok sayılır
  CHECK(kol2.uygula(kmt(Tip::KAYDET)) == 1);
  // Döngü: poz0 (s1 90) -> poz1 (s1 30,5) -> poz0 ... ikisine de oturmalı
  int gorulen_90 = 0, gorulen_305 = 0;
  for (int s = 0; s < 1500; ++s) {
    yuru(kol2, 1, false);
    if (kol2.hedefte() || (kol2.v[0] == 0 && kol2.v[1] == 0)) {
      if (kol2.p[0] == 90.0f && kol2.p[1] == 165.0f) gorulen_90++;
      if (kol2.p[0] == 30.5f && kol2.p[1] == 60.0f) gorulen_305++;
    }
  }
  CHECK(gorulen_90 > 0 && gorulen_305 > 0);

  kol2.uygula(kmt(Tip::DURAKLAT));
  yuru(kol2, 400);
  float dur = kol2.p[0];
  yuru(kol2, 50, false);
  CHECK(kol2.p[0] == dur && !kol2.oynuyor);

  kol2.uygula(kmt(Tip::HIZ, 0, 1));
  CHECK(kol2.ss_ms == 2);                     // alt sınır
  kol2.uygula(kmt(Tip::HIZ, 0, 40));
  CHECK(std::fabs(kol2.v_oynat - 25.0f) < 1e-4f);

  CHECK(kol2.uygula(kmt(Tip::SIFIRLA)) == 7 && kol2.poz_sayisi == 0 && eeprom[3] == 0);
  CHECK(kol2.uygula(kmt(Tip::OYNAT)) == 4);   // kayıt yokken oynatılamaz
  Kol kol3; kol3.basla(EV, MN, MX, DEPO);
  CHECK(kol3.poz_sayisi == 0);                // silme de kalıcı

  for (int i = 0; i < MAX_POZ; ++i) CHECK(kol3.uygula(kmt(Tip::KAYDET)) == 3);
  CHECK(kol3.uygula(kmt(Tip::KAYDET)) == 2);  // kayıt dolu
  CHECK(DEPO_BAS + MAX_POZ * POZ_BAYT <= 1024);

  // Bozuk başlık -> sıfırdan
  eeprom[3] = 200;
  Kol kol4; kol4.basla(EV, MN, MX, DEPO);
  CHECK(kol4.poz_sayisi == 0 && eeprom[3] == 0);

  // EEPROM ömrü: aynı pozu tekrar kaydetmek yalnız değişen baytları yazar
  kol4.uygula(kmt(Tip::KAYDET));
  yazma_sayisi = 0;
  kol4.uygula(kmt(Tip::SIFIRLA));
  kol4.uygula(kmt(Tip::KAYDET));
  CHECK(yazma_sayisi == 2);                   // yalnız poz sayısı baytı (0, sonra 1); poz baytları zaten aynı

  // PUT: hazırlanan hedefi kol kıpırdamadan kaydeder (programı kola yükleme)
  {
    Kol k5; k5.basla(EV, MN, MX, DEPO);
    k5.uygula(kmt(Tip::SIFIRLA));
    Komut c; std::vector<Komut> kv = ayristir("a11000a6400PUT\na2500PUT\n");
    CHECK(kv.size() == 5 && kv[2].tip == Tip::EKLE && kv[4].tip == Tip::EKLE);
    for (auto& x : kv) CHECK(k5.uygula(x) == (x.tip == Tip::EKLE ? 3 : 0));
    for (int s = 0; s < 50; ++s) k5.adim();
    CHECK(k5.hedefte() && k5.p[0] == 90.0f && k5.hedef[0] == 900);   // kıpırdamadı
    int16_t a0[6], a1[6];
    k5.poz_oku(0, a0); k5.poz_oku(1, a1);
    CHECK(k5.poz_sayisi == 2 && a0[0] == 1000 && a0[5] == 400 && a0[1] == 900);
    CHECK(a1[0] == 900 && a1[1] == 500 && a1[5] == 900);              // önceki PUT'un bekleyenleri temizlendi
    (void)c;
  }

  std::puts("komut testleri gecti");
  return 0;
}
