// arduino/kol_servo/komut.h içindeki Kol'un (hareket + kayıt) JS karşılığı. Simülasyon sayfası bunu çalıştırır.
// Arduino float (32 bit) kullandığı için her işlem Math.fround ile 32 bite yuvarlanır: sonuç C++ ile bit bit aynı
// çıkar. test_hareket.py rastgele komut senaryolarında ikisini adım adım karşılaştırır.
(function (root) {
  "use strict";
  const f = Math.fround;
  const N = 6, MAX_POZ = 50, DEPO_BAS = 4, POZ_BAYT = 12, DEPO_SURUM = 1;
  const DT = f(0.01), V_ELLE = f(1000 / 15), A_MAX = f(200), F01 = f(0.1), KMIN = f(0.02), EPS = f(1e-3);
  const TIPLER = ["YOK", "SERVO", "HIZ", "KAYDET", "OYNAT", "DURAKLAT", "SIFIRLA", "INCE", "GIT", "EKLE"];   // komut.h Tip sırası
  const yuvarla = (x) => Math.trunc(x >= 0 ? f(x + 0.5) : f(x - 0.5));

  // depo: { oku(adres) -> bayt, yaz(adres, bayt) }  (Arduino'da EEPROM)
  function Kol(ev, mn, mx, depo) {
    this.depo = depo;
    this.minOnda = mn.map((x) => x * 10); this.maxOnda = mx.map((x) => x * 10);
    this.hedef = ev.map((x, i) => this.sinirla(i, x * 10));
    this.bekleyen = this.hedef.slice(); this.maske = 0;
    this.p = this.hedef.map((h) => f(h * F01)); this.v = [0, 0, 0, 0, 0, 0];
    this.vlim = Array(N).fill(V_ELLE); this.alim = Array(N).fill(A_MAX);
    this.oynatilan = 0; this.oynuyor = false; this.ssMs = 20; this.vOynat = f(50);
    if (depo.oku(0) !== 75 || depo.oku(1) !== 83 || depo.oku(2) !== DEPO_SURUM || depo.oku(3) > MAX_POZ) {
      depo.yaz(0, 75); depo.yaz(1, 83); depo.yaz(2, DEPO_SURUM); depo.yaz(3, 0);   // 'K' 'S'
    }
    this.pozSayisi = depo.oku(3);
  }
  Kol.prototype = {
    sinirla(i, onda) { return Math.max(this.minOnda[i], Math.min(this.maxOnda[i], onda)); },
    konumOnda(i) { return yuvarla(f(this.p[i] * 10)); },
    hedefte() { for (let i = 0; i < N; i++) if (this.v[i] !== 0 || this.p[i] !== f(this.hedef[i] * F01)) return false; return true; },
    pozOku(n) {
      const a = DEPO_BAS + n * POZ_BAYT, out = [];
      for (let i = 0; i < N; i++) { const u = this.depo.oku(a + 2 * i) | (this.depo.oku(a + 2 * i + 1) << 8); out.push(u >= 32768 ? u - 65536 : u); }
      return out;
    },
    pozYaz(n, t) {
      const a = DEPO_BAS + n * POZ_BAYT;
      for (let i = 0; i < N; i++) { const u = t[i] & 0xffff; this.depo.yaz(a + 2 * i, u & 0xff); this.depo.yaz(a + 2 * i + 1, u >> 8); }
    },
    hareket(t, vmax) {
      const d = []; let dmax = 0;
      for (let i = 0; i < N; i++) { this.hedef[i] = t[i]; d.push(Math.abs(f(f(t[i] * F01) - this.p[i]))); if (d[i] > dmax) dmax = d[i]; }
      for (let i = 0; i < N; i++) {
        let k = dmax > 0 ? f(d[i] / dmax) : 1;
        if (k < KMIN) k = KMIN;
        this.vlim[i] = f(vmax * k); this.alim[i] = f(A_MAX * k);
      }
    },
    pozGit(n) { this.hareket(this.pozOku(n).map((x, i) => this.sinirla(i, x)), this.vOynat); },
    dur() {
      for (let i = 0; i < N; i++) {
        const v = this.v[i], s = this.alim[i] > 0 ? f(f(v * Math.abs(v)) / f(2 * this.alim[i])) : 0;
        this.hedef[i] = this.sinirla(i, yuvarla(f(f(this.p[i] + s) * 10)));
      }
    },
    // k: { tip: "SERVO" | ... | sayı (komut.h sırası), servo: 0..5, deger }. Dönüş kodları komut.h ile aynı.
    uygula(k) {
      const tip = typeof k.tip === "number" ? TIPLER[k.tip] : k.tip, s = k.servo || 0, deger = k.deger || 0;
      switch (tip) {
        case "SERVO":
          if (this.oynuyor) return 1;
          this.hedef[s] = this.sinirla(s, deger * 10); this.vlim[s] = V_ELLE; this.alim[s] = A_MAX;
          return 0;
        case "INCE":
          if (this.oynuyor) return 1;
          this.bekleyen[s] = this.sinirla(s, deger); this.maske |= 1 << s;
          return 0;
        case "GIT": {
          if (this.oynuyor) return 1;
          if (!this.maske) return 0;
          const t = this.hedef.map((h, i) => ((this.maske >> i) & 1 ? this.bekleyen[i] : h));
          this.maske = 0; this.hareket(t, V_ELLE);
          return 0;
        }
        case "HIZ":
          this.ssMs = deger < 2 ? 2 : deger > 500 ? 500 : deger; this.vOynat = f(1000 / this.ssMs);
          return 0;
        case "EKLE": {
          if (this.oynuyor) return 1;
          if (this.pozSayisi >= MAX_POZ) return 2;
          const t = this.hedef.map((h, i) => ((this.maske >> i) & 1 ? this.bekleyen[i] : h));
          this.maske = 0; this.pozYaz(this.pozSayisi, t); this.pozSayisi++; this.depo.yaz(3, this.pozSayisi);
          return 3;
        }
        case "KAYDET":
          if (this.oynuyor) return 1;
          if (this.pozSayisi >= MAX_POZ) return 2;
          this.pozYaz(this.pozSayisi, this.hedef); this.pozSayisi++; this.depo.yaz(3, this.pozSayisi);
          return 3;
        case "OYNAT":
          if (this.pozSayisi === 0) return 4;
          if (!this.oynuyor) { this.oynuyor = true; if (this.oynatilan >= this.pozSayisi) this.oynatilan = 0; this.pozGit(this.oynatilan); }
          return 5;
        case "DURAKLAT":
          this.oynuyor = false; this.dur();
          return 6;
        case "SIFIRLA":
          this.oynuyor = false; this.pozSayisi = 0; this.oynatilan = 0; this.maske = 0; this.depo.yaz(3, 0); this.dur();
          return 7;
        default:
          return 0;
      }
    },
    adim() {
      for (let i = 0; i < N; i++) {
        const t = f(this.hedef[i] * F01), d = f(t - this.p[i]);
        let v = this.v[i];
        if (d === 0 && v === 0) continue;
        const da = f(this.alim[i] * DT);
        let vd = f(f(da * f(f(Math.sqrt(f(1 + f(f(8 * Math.abs(d)) / f(da * DT))))) - 1)) * 0.5);
        if (vd > this.vlim[i]) vd = this.vlim[i];
        if (d < 0) vd = -vd;
        if (v < vd) { v = f(v + da); if (v > vd) v = vd; } else { v = f(v - da); if (v < vd) v = vd; }
        const yeni = f(this.p[i] + f(v * DT));
        if (f(f(t - yeni) * d) <= 0 && Math.abs(v) <= f(f(4 * da) + EPS)) { this.p[i] = t; this.v[i] = 0; }
        else { this.p[i] = yeni; this.v[i] = v; }
      }
      if (this.oynuyor && this.hedefte()) { this.oynatilan = (this.oynatilan + 1) % this.pozSayisi; this.pozGit(this.oynatilan); }
    },
  };

  const api = { Kol, N, MAX_POZ, DT, V_ELLE, A_MAX, TIPLER };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ServoHareket = api;
})(typeof window !== "undefined" ? window : this);
