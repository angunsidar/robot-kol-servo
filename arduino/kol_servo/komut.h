// Servo kolun donanımdan bağımsız mantığı: komut ayrıştırma, yumuşak hareket, poz kaydı ve oynatma.
// PC'de derlenip test edilir: ../../test/test_komut.cpp. Arduino'da kol_servo.ino bu dosyayı kullanır.
// Simülasyondaki karşılığı: ../../sim/servo_hareket.js (test_hareket.py ikisini adım adım karşılaştırır).
//
// Komutlar (How To Mechatronics telefon uygulamasıyla uyumlu; sonlandırıcı gerekmez, büyük/küçük harf fark etmez):
//   s1..s6<açı>   ör. "s290"  -> 2. servo 90°
//   ss<ms>        oynatma hızı: 1° başına ms (20 -> 50°/s)
//   SAVE          o anki hedef pozu kaydet (EEPROM: elektrik kesilince silinmez)
//   RUN           kayıtlı pozları döngüde oynat (PAUSE sonrası kaldığı yerden devam)
//   PAUSE         oynatmayı durdur
//   RESET         kayıtları sil
// Bilgisayar için ek komutlar (simülasyon sayfası kullanır):
//   a1..a6<onda bir derece>   ör. "a2905" -> 2. servoya 90,5° hedefi hazırla (hemen hareket etmez)
//   GO                        hazırlanan hedeflere tüm eklemler birlikte gider, aynı anda varır
//   PUT                       hazırlanan hedefleri kolu KIPIRDATMADAN poz olarak kaydet (programı kola yüklemek için)
// Mesajlar yapışık ("s190s2100") ya da parça parça gelebilir; ayrıştırıcı ikisini de çözer.
//
// Hareket: her eklem hızı ve ivmesi sınırlı bir takipçi (yavaş kalkış, yavaş duruş). Birden çok eklem
// birlikte gönderildiğinde (GO, oynatma) her eklemin hız ve ivme sınırı yol uzunluğuyla orantılı
// küçültülür: hepsi aynı anda yola çıkar ve aynı anda varır.
#pragma once
#include <math.h>
#include <stdint.h>
#include <string.h>

namespace kol {

static const uint8_t N_SERVO = 6;
static const uint8_t MAX_POZ = 50;            // EEPROM'da 4 + 50 x 12 = 604 bayt (Uno'da 1024)
static const float DT = 0.01f;                // adim() aralığı, s (kol_servo.ino 10 ms'de bir çağırır)
static const float V_ELLE = 1000.0f / 15;     // elle komutlarda en yüksek hız, °/s (eski 15 ms/° ile aynı)
static const float A_MAX = 200.0f;            // en yüksek ivme, °/s² (tahmin; titreme olursa düşür)

enum class Tip : uint8_t { YOK, SERVO, HIZ, KAYDET, OYNAT, DURAKLAT, SIFIRLA, INCE, GIT, EKLE };

struct Komut {
  Tip tip = Tip::YOK;
  uint8_t servo = 0;    // 0..5
  int16_t deger = 0;
};

// ------------------------------------------------------------------ ayrıştırıcı
class Ayristirici {
 public:
  explicit Ayristirici(uint16_t zaman_asimi_ms = 25) : zaman_asimi_(zaman_asimi_ms) {}

  // Gelen karakter. Tamamlanan komutlar kuyruğa girer; al() ile okunur.
  void besle(char c, uint32_t simdi_ms) {
    son_ = simdi_ms;
    if (c >= 'a' && c <= 'z') c = (char)(c - 32);
    if (n_ >= sizeof(buf_) - 1) n_ = 0;          // taşma: çöpü at
    buf_[n_++] = c;
    buf_[n_] = 0;
    cikar(false);
  }

  // Karakter gelmediğinde düzenli çağrılır: zaman aşımında yarım kalan sayıyı tamamlar.
  void bekle(uint32_t simdi_ms) {
    if (n_ && simdi_ms - son_ >= zaman_asimi_) cikar(true);
  }

  bool al(Komut& k) {
    if (q_n_ == 0) return false;
    k = q_[q_bas_];
    q_bas_ = (uint8_t)((q_bas_ + 1) % Q);
    q_n_--;
    return true;
  }

 private:
  static const uint8_t Q = 12;                     // "Git" tek seferde 5 x "a" + GO gönderir
  char buf_[24] = {0};
  uint8_t n_ = 0;
  Komut q_[Q];
  uint8_t q_bas_ = 0, q_n_ = 0;
  uint32_t son_ = 0;
  uint16_t zaman_asimi_;

  void it(const Komut& k) {
    if (q_n_ == Q) return;                         // kuyruk dolu: en yeni komutu at
    q_[(q_bas_ + q_n_) % Q] = k;
    q_n_++;
  }
  void kes(uint8_t k) {                            // tamponun başından k karakter at
    memmove(buf_, buf_ + k, (size_t)(n_ - k + 1));
    n_ = (uint8_t)(n_ - k);
  }
  static bool rakam(char c) { return c >= '0' && c <= '9'; }
  static bool ayrac(char c) { return c == '\r' || c == '\n' || c == ' ' || c == ',' || c == ';'; }

  // Bir kelimenin tamamı mı (1), öneki mi (2), değil mi (0)?
  uint8_t kelime(const char* w) const {
    uint8_t i = 0;
    for (; w[i] && i < n_; ++i) if (buf_[i] != w[i]) return 0;
    return w[i] == 0 ? 1 : 2;
  }

  // Tampon başından tamamlanan komutları çıkar. son=true: zaman aşımı, yarım sayıyı da bitir.
  void cikar(bool son) {
    while (n_) {
      if (ayrac(buf_[0])) { kes(1); continue; }
      static const char* const KELIMELER[] = {"SAVE", "RUN", "PAUSE", "RESET", "GO", "PUT"};
      static const Tip TIPLER[] = {Tip::KAYDET, Tip::OYNAT, Tip::DURAKLAT, Tip::SIFIRLA, Tip::GIT, Tip::EKLE};
      bool bekle_kelime = false, bulundu = false;
      for (uint8_t w = 0; w < 6; ++w) {
        uint8_t r = kelime(KELIMELER[w]);
        if (r == 1) { Komut k; k.tip = TIPLER[w]; it(k); kes((uint8_t)strlen(KELIMELER[w])); bulundu = true; break; }
        if (r == 2) bekle_kelime = true;
      }
      if (bulundu) continue;
      if (buf_[0] == 'S' || buf_[0] == 'A') {
        if (n_ < 2) { if (son) n_ = 0; return; }                 // "S" tek başına: devamını bekle
        Tip tip; uint8_t servo = 0;
        if (buf_[0] == 'S' && buf_[1] == 'S') tip = Tip::HIZ;
        else if (buf_[1] >= '1' && buf_[1] <= '6') { tip = buf_[0] == 'S' ? Tip::SERVO : Tip::INCE; servo = (uint8_t)(buf_[1] - '1'); }
        else if (bekle_kelime) { if (son) { kes(1); continue; } return; }   // "SA", "SAV" ...
        else { kes(1); continue; }
        uint8_t i = 2;
        while (i < n_ && buf_[i] == ' ') i++;                     // elle yazımda "s1 30" da olsun
        if (i == n_ && !son) return;
        uint8_t ilk = i;
        int32_t v = 0;
        while (i < n_ && rakam(buf_[i]) && i < ilk + 5) { v = v * 10 + (buf_[i] - '0'); i++; }
        bool sayi_var = i > ilk;
        bool bitti = i < n_ || son;                               // sayıdan sonra başka karakter ya da zaman aşımı
        if (!bitti) return;
        if (sayi_var) { Komut k; k.tip = tip; k.servo = servo; k.deger = (int16_t)v; it(k); }
        kes(i);
        continue;
      }
      if (bekle_kelime) { if (son) { kes(1); continue; } return; }
      kes(1);                                                      // tanınmayan karakter
    }
  }
};

// ------------------------------------------------------------------ kalıcı kayıt
// Arduino'da EEPROM, testte bir dizi. Düzen: 'K' 'S' sürüm poz_sayısı | her poz 6 x int16 (onda bir derece, LE)
struct Depo {
  uint8_t (*oku)(uint16_t adres);
  void (*yaz)(uint16_t adres, uint8_t deger);   // Arduino'da EEPROM.update: aynı değeri yeniden yazmaz
};
static const uint16_t DEPO_BAS = 4, POZ_BAYT = 2 * N_SERVO;
static const uint8_t DEPO_SURUM = 1;

static inline int32_t yuvarla(float x) { return (int32_t)(x >= 0 ? x + 0.5f : x - 0.5f); }

// ------------------------------------------------------------------ hareket + kayıt
struct Kol {
  float p[N_SERVO];               // konum, °
  float v[N_SERVO];               // hız, °/s
  float vlim[N_SERVO], alim[N_SERVO];
  int16_t hedef[N_SERVO];         // onda bir derece
  int16_t bekleyen[N_SERVO];      // "a" komutlarıyla hazırlanan, GO bekleyen hedefler
  uint8_t bekleyen_maske = 0;
  int16_t min_onda[N_SERVO], max_onda[N_SERVO];
  uint8_t poz_sayisi = 0;
  uint8_t oynatilan = 0;
  bool oynuyor = false;
  uint16_t ss_ms = 20;            // "ss" ile değişir
  float v_oynat = 50.0f;          // 1000 / ss_ms, °/s
  Depo depo = {nullptr, nullptr};

  void basla(const uint8_t ev[N_SERVO], const uint8_t mn[N_SERVO], const uint8_t mx[N_SERVO], const Depo& d) {
    depo = d;
    for (uint8_t i = 0; i < N_SERVO; ++i) {
      min_onda[i] = (int16_t)(mn[i] * 10); max_onda[i] = (int16_t)(mx[i] * 10);
      hedef[i] = bekleyen[i] = sinirla(i, ev[i] * 10);
      p[i] = hedef[i] * 0.1f; v[i] = 0; vlim[i] = V_ELLE; alim[i] = A_MAX;
    }
    if (depo.oku(0) != 'K' || depo.oku(1) != 'S' || depo.oku(2) != DEPO_SURUM || depo.oku(3) > MAX_POZ) {
      depo.yaz(0, 'K'); depo.yaz(1, 'S'); depo.yaz(2, DEPO_SURUM); depo.yaz(3, 0);   // ilk açılış ya da bozuk kayıt
    }
    poz_sayisi = depo.oku(3);
  }
  int16_t sinirla(uint8_t i, int32_t onda) const {
    if (onda < min_onda[i]) onda = min_onda[i];
    if (onda > max_onda[i]) onda = max_onda[i];
    return (int16_t)onda;
  }
  int16_t konum_onda(uint8_t i) const { return (int16_t)yuvarla(p[i] * 10); }
  bool hedefte() const {
    for (uint8_t i = 0; i < N_SERVO; ++i) if (v[i] != 0 || p[i] != hedef[i] * 0.1f) return false;
    return true;
  }

  void poz_oku(uint8_t n, int16_t out[N_SERVO]) const {
    uint16_t a = (uint16_t)(DEPO_BAS + n * POZ_BAYT);
    for (uint8_t i = 0; i < N_SERVO; ++i)
      out[i] = (int16_t)(depo.oku((uint16_t)(a + 2 * i)) | (depo.oku((uint16_t)(a + 2 * i + 1)) << 8));
  }
  void poz_yaz(uint8_t n, const int16_t in[N_SERVO]) {
    uint16_t a = (uint16_t)(DEPO_BAS + n * POZ_BAYT);
    for (uint8_t i = 0; i < N_SERVO; ++i) {
      depo.yaz((uint16_t)(a + 2 * i), (uint8_t)(in[i] & 0xFF));
      depo.yaz((uint16_t)(a + 2 * i + 1), (uint8_t)((uint16_t)in[i] >> 8));
    }
  }

  // Tüm eklemleri birlikte hedefe götür: en uzun yolu gidecek eklem vmax ve A_MAX ile, diğerleri yolları
  // oranında yavaş -> hepsi aynı anda varır.
  void hareket(const int16_t t[N_SERVO], float vmax) {
    float d[N_SERVO], dmax = 0;
    for (uint8_t i = 0; i < N_SERVO; ++i) {
      hedef[i] = t[i];
      d[i] = fabsf(t[i] * 0.1f - p[i]);
      if (d[i] > dmax) dmax = d[i];
    }
    for (uint8_t i = 0; i < N_SERVO; ++i) {
      float k = dmax > 0 ? d[i] / dmax : 1.0f;
      if (k < 0.02f) k = 0.02f;                    // hareketsiz eklem de kalan hızını sönümleyebilsin
      vlim[i] = vmax * k; alim[i] = A_MAX * k;
    }
  }
  void poz_git(uint8_t n) {
    int16_t t[N_SERVO];
    poz_oku(n, t);
    for (uint8_t i = 0; i < N_SERVO; ++i) t[i] = sinirla(i, t[i]);   // sınırlar kayıttan sonra değişmiş olabilir
    hareket(t, v_oynat);
  }
  // Ani durma yerine: her eklem kendi ivmesiyle yavaşlayıp duracağı yere hedeflenir
  void dur() {
    for (uint8_t i = 0; i < N_SERVO; ++i) {
      float s = alim[i] > 0 ? v[i] * fabsf(v[i]) / (2 * alim[i]) : 0;
      hedef[i] = sinirla(i, yuvarla((p[i] + s) * 10));
    }
  }

  // Komutu uygula. Dönüş: bilgi kodu (0 sessiz, 1 oynatırken yok sayıldı, 2 kayıt dolu,
  // 3 kaydedildi, 4 kayıt yok, 5 oynatılıyor, 6 duraklatıldı, 7 sıfırlandı)
  int uygula(const Komut& k) {
    switch (k.tip) {
      case Tip::SERVO:
        if (oynuyor) return 1;
        hedef[k.servo] = sinirla(k.servo, (int32_t)k.deger * 10);
        vlim[k.servo] = V_ELLE; alim[k.servo] = A_MAX;
        return 0;
      case Tip::INCE:
        if (oynuyor) return 1;
        bekleyen[k.servo] = sinirla(k.servo, k.deger);
        bekleyen_maske = (uint8_t)(bekleyen_maske | (1 << k.servo));
        return 0;
      case Tip::GIT: {
        if (oynuyor) return 1;
        if (!bekleyen_maske) return 0;
        int16_t t[N_SERVO];
        for (uint8_t i = 0; i < N_SERVO; ++i) t[i] = (bekleyen_maske >> i) & 1 ? bekleyen[i] : hedef[i];
        bekleyen_maske = 0;
        hareket(t, V_ELLE);
        return 0;
      }
      case Tip::HIZ:
        ss_ms = (uint16_t)(k.deger < 2 ? 2 : (k.deger > 500 ? 500 : k.deger));
        v_oynat = 1000.0f / ss_ms;
        return 0;
      case Tip::EKLE: {
        if (oynuyor) return 1;
        if (poz_sayisi >= MAX_POZ) return 2;
        int16_t t[N_SERVO];
        for (uint8_t i = 0; i < N_SERVO; ++i) t[i] = (bekleyen_maske >> i) & 1 ? bekleyen[i] : hedef[i];
        bekleyen_maske = 0;
        poz_yaz(poz_sayisi, t);
        poz_sayisi++;
        depo.yaz(3, poz_sayisi);
        return 3;
      }
      case Tip::KAYDET:
        if (oynuyor) return 1;
        if (poz_sayisi >= MAX_POZ) return 2;
        poz_yaz(poz_sayisi, hedef);
        poz_sayisi++;
        depo.yaz(3, poz_sayisi);
        return 3;
      case Tip::OYNAT:
        if (poz_sayisi == 0) return 4;
        if (!oynuyor) {
          oynuyor = true;
          if (oynatilan >= poz_sayisi) oynatilan = 0;
          poz_git(oynatilan);
        }
        return 5;
      case Tip::DURAKLAT:
        oynuyor = false;
        dur();
        return 6;
      case Tip::SIFIRLA:
        oynuyor = false; poz_sayisi = 0; oynatilan = 0; bekleyen_maske = 0;
        depo.yaz(3, 0);
        dur();
        return 7;
      default:
        return 0;
    }
  }

  // DT'lik bir zaman adımı. Her eklem: hedefe kalan yolda durabileceği en yüksek hıza (ve vlim'e) doğru,
  // en fazla alim * DT hız değiştirerek ilerler. Oynatmada hepsi varınca sıradaki poz.
  void adim() {
    for (uint8_t i = 0; i < N_SERVO; ++i) {
      float t = hedef[i] * 0.1f, d = t - p[i];
      if (d == 0 && v[i] == 0) continue;
      // Kalan yolda, her adımda da kadar yavaşlayarak tam hedefte durulabilecek en yüksek hız:
      // vd, vd-da, ..., da hızlarıyla gidilen yol = d  ->  n(n+1)/2 · da·DT = d,  vd = n · da
      float da = alim[i] * DT;
      float vd = da * (sqrtf(1 + 8 * fabsf(d) / (da * DT)) - 1) * 0.5f;
      if (vd > vlim[i]) vd = vlim[i];
      if (d < 0) vd = -vd;
      if (v[i] < vd) { v[i] += da; if (v[i] > vd) v[i] = vd; }
      else { v[i] -= da; if (v[i] < vd) v[i] = vd; }
      float yeni = p[i] + v[i] * DT;
      // Hedefe vardı ya da geçti: yavaşsa otur. Hızlıysa (ör. hedef aniden önüne geldi) geçip geri döner.
      if ((t - yeni) * d <= 0 && fabsf(v[i]) <= 4 * da + 1e-3f) { p[i] = t; v[i] = 0; }
      else p[i] = yeni;
    }
    if (oynuyor && hedefte()) {
      oynatilan = (uint8_t)((oynatilan + 1) % poz_sayisi);
      poz_git(oynatilan);
    }
  }
};

}  // namespace kol
