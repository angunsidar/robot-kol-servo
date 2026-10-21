// Kol programı: adım listesi -> eklem hedefleri -> çalıştırma (simülasyon ya da USB'deki kol) ve kola yükleme.
// Sayfadan ve node testinden (test_program.py) aynı şekilde kullanılır; zamanlama ve kol erişimi dışarıdan verilir.
//
// Adımlar (JSON olarak saklanır):
//   { tip: "git", x, y, z, alet, dogrusal?, bilek? }  uç noktası mm, alet açısı dikeyden ° (180 = dik aşağı, 90 = yatay ileri).
//        bilek: bilek dönüşü eklem açısı ° (yoksa önceki adımdaki gibi kalır).
//        dogrusal: uç önceki noktadan buraya DÜZ çizgide gider (5 mm'lik ara noktalarla). Yoksa eklemler birlikte
//        döner: senkron hareket eklem uzayında düz çizgi olduğu için uç eğri bir yol izler (yol() bunu çizer).
//   { tip: "tutucu", aci }          tutucu servosu °
//   { tip: "bekle", ms }
(function (root) {
  "use strict";
  const ACIK = 100, KAPALI = 35;   // tutucu varsayılanları (°); nesneye göre ayarlanır, kapalıda servo zorlanmasın
  const ARA_MM = 5, ARA_DER = 5;   // düz yolda ara nokta aralığı
  const ARA_TOL = 15;              // ara noktayı "geçti" saymak için en büyük eklem farkı (onda bir derece)

  // Al-bırak şablonu: aç, üstüne gel, DÜZ in, kapat, DÜZ kalk, bırakma noktasının üstüne git, DÜZ in, aç, DÜZ kalk
  function alBirak(al, birak, o = {}) {
    const h = o.yukseklik ?? 40, alet = o.alet ?? 180, acik = o.acik ?? ACIK, kapali = o.kapali ?? KAPALI;
    const g = (p, dz = 0, dogrusal = false) => ({ tip: "git", x: p.x, y: p.y, z: p.z + dz, alet, dogrusal });
    return [
      { tip: "tutucu", aci: acik }, g(al, h), g(al, 0, true), { tip: "tutucu", aci: kapali }, { tip: "bekle", ms: 300 },
      g(al, h, true), g(birak, h), g(birak, 0, true), { tip: "tutucu", aci: acik }, { tip: "bekle", ms: 300 }, g(birak, h, true),
    ];
  }

  // Ters kinematik (S = ServoKol): önce dirsek yukarı, olmazsa dirsek aşağı çözüm
  function ikCoz(S, O, xyzMm, alet) {
    const xyz = xyzMm.map((v) => v / 1000);
    const q = S.ik(xyz, alet, O, true);
    if (q && S.limitIcinde(q)) return q;
    const q2 = S.ik(xyz, alet, O, false);
    return q2 && S.limitIcinde(q2) ? q2 : null;
  }

  // Servo hedefinin (onda bir derece) uç noktası, mm, ve alet açısı
  function uc(S, O, onda) {
    const f = S.fk(S.eklemAci(onda.map((v) => v / 10)), O), p = f.noktalar[4];
    return { x: p[0] * 1000, y: p[1] * 1000, z: p[2] * 1000, alet: f.alet };
  }

  // Adımları eklem hedeflerine çevir. basla: başlangıçtaki servo hedefleri (onda bir derece, 6 eleman).
  // Bilek dönüşü (servo 4): adımda bilek varsa o, yoksa önceki gibi kalır. Düz yolun ara noktaları ara: true taşır.
  function coz(adimlar, S, O, basla) {
    const sin = (i, v) => Math.max(S.SERVO_MIN[i] * 10, Math.min(S.SERVO_MAX[i] * 10, v));
    let cur = basla.slice(), once = uc(S, O, basla);
    const hedefler = [], hatalar = [];
    const coz1 = (p) => {                                         // bir uç noktası -> servo hedefi ya da null
      const q = ikCoz(S, O, [p.x, p.y, p.z], p.alet);
      if (!q) return null;
      q[3] = Number.isFinite(p.bilek) ? p.bilek : S.eklemAci(cur.map((v) => v / 10))[3];
      const sv = S.servoAci(q), o = cur.slice();
      for (let j = 0; j < 5; j++) o[j] = sin(j, Math.round(sv[j] * 10));
      return o;
    };
    adimlar.forEach((a, i) => {
      if (a.tip === "git") {
        const hedef = { x: +a.x, y: +a.y, z: +a.z, alet: +a.alet, bilek: a.bilek === undefined || a.bilek === null || a.bilek === "" ? undefined : +a.bilek };
        if (!coz1(hedef)) { hatalar.push({ i, mesaj: `Adım ${i + 1}: nokta erişim dışında ya da bir servo sınırını aşıyor` }); return; }
        const n = a.dogrusal ? Math.max(1, Math.ceil(Math.max(
          Math.hypot(hedef.x - once.x, hedef.y - once.y, hedef.z - once.z) / ARA_MM, Math.abs(hedef.alet - once.alet) / ARA_DER))) : 1;
        const parca = [];
        for (let k = 1; k <= n; k++) {
          const t = k / n, p = {};
          for (const e of ["x", "y", "z", "alet"]) p[e] = once[e] + (hedef[e] - once[e]) * t;
          p.bilek = hedef.bilek;
          const o = coz1(p);
          if (!o) { hatalar.push({ i, mesaj: `Adım ${i + 1}: düz yol erişim dışından geçiyor (yolun %${Math.round(t * 100)} noktası). "Düz"ü kapat ya da araya nokta ekle` }); return; }
          parca.push({ tip: "eklem", onda: o, adim: i, ara: k < n });
          cur = o;
        }
        hedefler.push(...parca);
        once = hedef;
      } else if (a.tip === "tutucu") {
        cur = cur.slice(); cur[5] = sin(5, Math.round(+a.aci * 10));
        hedefler.push({ tip: "eklem", onda: cur.slice(), adim: i });
      } else if (a.tip === "bekle") {
        hedefler.push({ tip: "bekle", ms: Math.max(0, Math.round(+a.ms || 0)), adim: i });
      } else {
        hatalar.push({ i, mesaj: `Adım ${i + 1}: bilinmeyen adım türü` });
      }
    });
    return { hedefler, hatalar };
  }

  // Kola yükleme: her eklem hedefi bir poz ("a1..a6" + PUT: kol kıpırdamadan EEPROM'a). Bekleme adımları
  // kolda saklanamaz, atlanır. Düz yolun ara noktaları da atlanır (kol her pozda durduğu için 50 poz sınırını
  // doldururdu): kolda oynatılınca o hareketler düz değil eklemlerle birlikte yapılır. Kol RUN ile döngüde oynatır.
  function yuklemeKomutlari(hedefler) {
    return hedefler.filter((h) => h.tip === "eklem" && !h.ara).map((h) => h.onda.map((v, i) => `a${i + 1}${v}`).join("\n") + "\nPUT");
  }

  // Programın öngörülen uç yolu (mm): senkron hareket eklem uzayında düz çizgi olduğu için iki hedef arası
  // eklem açılarının doğrusal ara değerleriyle çizilir. Dönüş: [[x, y, z], ...]
  function yol(hedefler, S, O, basla) {
    const pts = [], ekle = (o) => { const u = uc(S, O, o); pts.push([u.x, u.y, u.z]); };
    let cur = basla.slice();
    ekle(cur);
    for (const h of hedefler) {
      if (h.tip !== "eklem") continue;
      const n = h.ara ? 1 : 16;
      for (let k = 1; k <= n; k++) ekle(cur.map((v, i) => v + (h.onda[i] - v) * (k / n)));
      cur = h.onda;
    }
    return pts;
  }

  // Çalıştır. io: { git(onda), vardi(onda) -> bool, uyku(ms) -> Promise, simdi() -> ms, durdu() -> bool,
  //                 yakin?(onda, tol) -> bool, dongu?() -> bool, adim?(i) }
  // Düz yolun ara noktalarında kolun durması beklenmez: tüm eklemler hedefe ARA_TOL'den yakınsa sıradakine geçilir
  // (io.yakin yoksa vardi beklenir).
  // Dönüş: { bitti } | { durdu, i } | { hata, i }
  async function calistir(hedefler, io, zamanAsimi = 15000) {
    if (!hedefler.length) return { hata: "Program boş", i: -1 };
    do {
      for (let i = 0; i < hedefler.length; i++) {
        if (io.durdu()) return { durdu: true, i };
        const h = hedefler[i];
        if (io.adim) io.adim(i);
        if (h.tip === "bekle") {                                   // parça parça: Durdur hemen duyulsun
          for (let k = 0; k < h.ms; k += 50) { if (io.durdu()) return { durdu: true, i }; await io.uyku(Math.min(50, h.ms - k)); }
          continue;
        }
        io.git(h.onda);
        const t0 = io.simdi(), ara = h.ara && io.yakin;
        while (!(ara ? io.yakin(h.onda, ARA_TOL) : io.vardi(h.onda))) {
          if (io.durdu()) return { durdu: true, i };
          if (io.simdi() - t0 > zamanAsimi) return { hata: `Adım ${h.adim + 1}: kol ${zamanAsimi / 1000} sn içinde hedefe varmadı`, i };
          await io.uyku(ara ? 20 : 50);
        }
      }
    } while (io.dongu && io.dongu() && !io.durdu());
    return { bitti: true };
  }

  const api = { ACIK, KAPALI, ARA_MM, ARA_TOL, alBirak, ikCoz, uc, coz, yol, yuklemeKomutlari, calistir };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ServoProgram = api;
})(typeof window !== "undefined" ? window : this);
