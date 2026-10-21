// servo_kamera.js testi:  node test_kamera.js
// Sentetik görüntülerle: homografi, renk, leke bulma, eğik "laptop" bakışında masa koordinatı, tutuş ve plan.
"use strict";
const assert = require("assert");
const S = require("./servo_kinematik.js");
const H = require("./servo_hareket.js");
const P = require("./servo_program.js");
const K = require("./servo_kamera.js");

const O = S.olcu(), R = Math.PI / 180;
const BASLA = [900, 1000, 800, 900, 900, 600];
let gecen = 0;
const test = async (ad, f) => { await f(); gecen++; console.log("ok  " + ad); };
const rnd = (() => { let s = 7; return () => (s = (s * 16807) % 2147483647) / 2147483647; })();

// Masa (mm) -> görüntü (px) için "laptop" bakışı: masanın önü geniş, arkası dar (perspektif)
const W = 640, Hh = 480;
const MASA_KOSE = [[100, -150], [300, -150], [300, 150], [100, 150]];          // kolun önündeki 200 x 300 mm alan
const GORUNTU_KOSE = [[40, 460], [190, 120], [450, 120], [600, 460]];           // eğik bakış: uzak kenar dar
const H_mg = K.homografi(MASA_KOSE.map(([x, y]) => [-y, -x]).map(([a, b]) => [a, b]), GORUNTU_KOSE);
const masadanGoruntuye = (x, y) => K.uygula(H_mg, [-y, -x]);
const goruntudenMasaya = (u, v) => { const t = K.uygula(K.ters(H_mg), [u, v]); return [-t[1], -t[0]]; };

// Sentetik görüntü: gri masa, düz (yüksekliksiz) renkli dikdörtgenler. Her piksel masaya izdüşürülüp boyanır.
function goruntu(nesneler) {
  const d = new Uint8ClampedArray(W * Hh * 4);
  for (let v = 0; v < Hh; v++) for (let u = 0; u < W; u++) {
    const [x, y] = goruntudenMasaya(u + 0.5, v + 0.5), k = (v * W + u) * 4;
    let c = [118, 120, 122];
    for (const n of nesneler) {
      const dx = x - n.x, dy = y - n.y, a = -n.aci, lx = dx * Math.cos(a) - dy * Math.sin(a), ly = dx * Math.sin(a) + dy * Math.cos(a);
      if (Math.abs(lx) <= n.uzun / 2 && Math.abs(ly) <= n.kisa / 2) c = n.renk;
    }
    d[k] = c[0]; d[k + 1] = c[1]; d[k + 2] = c[2]; d[k + 3] = 255;
  }
  return d;
}
const KIRMIZI = [200, 40, 35], MAVI = [40, 80, 200], YESIL = [40, 170, 70];

(async () => {
  await test("homografi: bilinen perspektif dönüşümü geri bulunur; 4'ten fazla gürültülü noktada en küçük kareler", () => {
    const Hg = [1.2, 0.1, 30, -0.05, 0.9, 12, 0.0004, -0.0002, 1];
    const src = [[0, 0], [400, 10], [380, 300], [20, 310], [200, 150], [100, 250]];
    const dst = src.map((p) => K.uygula(Hg, p));
    const Hc = K.homografi(src, dst);
    for (let i = 0; i < 200; i++) {
      const p = [rnd() * 400, rnd() * 300], a = K.uygula(Hg, p), b = K.uygula(Hc, p);
      assert.ok(Math.hypot(a[0] - b[0], a[1] - b[1]) < 1e-6);
    }
    const ti = K.ters(Hc), p = [123, 45], q = K.uygula(ti, K.uygula(Hc, p));
    assert.ok(Math.hypot(q[0] - p[0], q[1] - p[1]) < 1e-9);
    const gurultulu = dst.map(([x, y]) => [x + (rnd() - 0.5), y + (rnd() - 0.5)]);
    assert.ok(K.hata(K.homografi(src, gurultulu), src, gurultulu) < 1.5);
    assert.strictEqual(K.homografi([[0, 0], [1, 1], [2, 2], [3, 3]], [[0, 0], [1, 0], [2, 1], [5, 5]]), null);   // hepsi bir doğruda
    assert.strictEqual(K.homografi([[0, 0], [1, 0], [0, 1]], [[0, 0], [1, 0], [0, 1]]), null);                  // 3 nokta yetmez
  });

  await test("renk: HSV ve eşleşme kuralı (gri masa, gölge, beyaz elenir)", () => {
    assert.deepStrictEqual(K.hsv(255, 0, 0).map((v) => +v.toFixed(3)), [0, 1, 1]);
    assert.strictEqual(Math.round(K.hsv(0, 255, 0)[0]), 120);
    assert.strictEqual(Math.round(K.hsv(0, 0, 255)[0]), 240);
    assert.strictEqual(K.tonFarki(355, 5), 10);
    const kural = K.renkKurali(K.hsv(...KIRMIZI));
    assert.ok(kural(...KIRMIZI) && kural(170, 50, 45) && kural(230, 30, 60));       // kırmızının tonları, 350° civarı dahil
    assert.ok(!kural(118, 120, 122) && !kural(250, 250, 250) && !kural(30, 8, 8) && !kural(...MAVI) && !kural(200, 120, 30));
  });

  await test("lekeler: merkez, alan ve eksen açısı; küçük gürültü elenir", () => {
    const w = 320, h = 240, d = new Uint8ClampedArray(w * h * 4).fill(120);
    const boya = (f, c) => { for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) if (f(x + 0.5, y + 0.5)) d.set([...c, 255], (y * w + x) * 4); };
    const a = 30 * R;
    boya((x, y) => { const dx = x - 100, dy = y - 80, lx = dx * Math.cos(a) + dy * Math.sin(a), ly = -dx * Math.sin(a) + dy * Math.cos(a); return Math.abs(lx) <= 30 && Math.abs(ly) <= 10; }, KIRMIZI);
    boya((x, y) => Math.abs(x - 230) <= 15 && Math.abs(y - 170) <= 15, KIRMIZI);
    boya((x, y) => Math.abs(x - 50) <= 1 && Math.abs(y - 200) <= 1, KIRMIZI);       // 9 piksellik gürültü
    const L = K.lekeler(d, w, h, K.renkKurali(K.hsv(...KIRMIZI)));
    assert.strictEqual(L.length, 2);
    const [dik, kare] = L;
    assert.ok(Math.abs(dik.cx - 100) < 0.5 && Math.abs(dik.cy - 80) < 0.5, `${dik.cx} ${dik.cy}`);
    assert.ok(Math.abs(dik.aci - a) < 1.5 * R, `açı ${dik.aci / R}`);
    assert.ok(Math.abs(dik.alan - 60 * 20) < 60);
    assert.ok(Math.abs(kare.cx - 230) < 0.5 && Math.abs(kare.cy - 170) < 0.5 && kare.uzun / kare.kisa < 1.1);
    const L2 = K.lekeler(d, w, h, K.renkKurali(K.hsv(...KIRMIZI)), { adim: 2 });   // hızlı tarama
    assert.strictEqual(L2.length, 2);
    assert.ok(Math.abs(L2[0].cx - 100) < 1.5 && Math.abs(L2[0].cy - 80) < 1.5);
  });

  await test("eğik kamera: 4 tıklamayla kalibrasyon, nesneler masada 1 mm içinde, yönleri 3° içinde bulunur", () => {
    const nesneler = [
      { x: 190, y: -50, aci: 20 * R, uzun: 40, kisa: 20, renk: KIRMIZI },
      { x: 250, y: 80, aci: -45 * R, uzun: 25, kisa: 25, renk: MAVI },
      { x: 140, y: 30, aci: 80 * R, uzun: 50, kisa: 15, renk: YESIL },
    ];
    const img = goruntu(nesneler);
    // Kullanıcı masadaki 4 işaretin üstüne tıklar (piksele yuvarlanır), koordinatlarını yazar
    const isaret = [[120, -120], [280, -120], [280, 120], [120, 120]];
    const tik = isaret.map(([x, y]) => masadanGoruntuye(x, y).map(Math.round));
    const Hk = K.homografi(tik, isaret);
    assert.ok(K.hata(Hk, tik, isaret) < 1);
    let enKotu = 0, enKotuYaklasik = 0;
    for (const n of nesneler) {
      const L = K.lekeler(img, W, Hh, K.renkKurali(K.hsv(...n.renk)), { adim: 1, H: Hk });
      assert.strictEqual(L.length, 1, "renk başına bir nesne");
      const m = K.masaya(Hk, L[0]), hata = Math.hypot(m.x - n.x, m.y - n.y);
      enKotu = Math.max(enKotu, hata);
      assert.ok(hata < 1.0, `${n.renk}: ${hata.toFixed(2)} mm`);
      const yaklasik = K.masaya(Hk, { ...L[0], masa: undefined });   // görüntüdeki merkezin izdüşümü
      enKotuYaklasik = Math.max(enKotuYaklasik, Math.hypot(yaklasik.x - n.x, yaklasik.y - n.y));
      assert.ok(Math.abs(L[0].masa.alan - n.uzun * n.kisa) < 0.12 * n.uzun * n.kisa, `alan ${L[0].masa.alan.toFixed(0)}`);
      if (n.uzun / n.kisa > 1.5) {
        const d = Math.abs(((m.aci - n.aci + Math.PI / 2) % Math.PI + Math.PI) % Math.PI - Math.PI / 2);
        assert.ok(d < 3 * R, `açı farkı ${(d / R).toFixed(1)}°`);
        assert.ok(Math.abs(m.uzun - n.uzun) < 3 && Math.abs(m.kisa - n.kisa) < 3, `boyut ${m.uzun.toFixed(1)} x ${m.kisa.toFixed(1)}`);
      }
    }
    console.log(`    eğik bakışta en kötü konum hatası ${enKotu.toFixed(2)} mm (alan ağırlıklı); görüntü merkezinin izdüşümüyle ${enKotuYaklasik.toFixed(2)} mm`);
    assert.ok(enKotu < enKotuYaklasik);
  });

  await test("çene yönü: bağımsız dönme matrisi zinciriyle (sahnedeki kol) aynı", () => {
    const mat = (ax, t) => { const c = Math.cos(t), s = Math.sin(t); return ax === "z" ? [[c, -s, 0], [s, c, 0], [0, 0, 1]] : [[c, 0, s], [0, 1, 0], [-s, 0, c]]; };
    const mm = (A, B) => A.map((r) => B[0].map((_, j) => r.reduce((t, v, k) => t + v * B[k][j], 0)));
    for (let i = 0; i < 500; i++) {
      const q = [rnd() * 180 - 90, rnd() * 100 - 50, rnd() * 100 - 50, rnd() * 180 - 90, rnd() * 100 - 50];
      if (Math.abs(Math.sin((q[1] + q[2] + q[4]) * R)) > 0.97 && Math.abs(Math.cos(q[3] * R)) > 0.2) continue;   // çene dikeye yakın: yatay yön tanımsız
      const Rm = [["z", q[0]], ["y", q[1]], ["y", q[2]], ["y", q[4]], ["z", q[3]]].reduce((A, [ax, t]) => mm(A, mat(ax, t * R)), [[1, 0, 0], [0, 1, 0], [0, 0, 1]]);
      const beklenen = Math.atan2(Rm[1][0], Rm[0][0]), d = Math.abs(((K.ceneYonu(q) - beklenen) % (2 * Math.PI) + 3 * Math.PI) % (2 * Math.PI) - Math.PI);
      assert.ok(d < 1e-9, `${q} ${d}`);
    }
  });

  await test("bilek seçimi: çeneler nesnenin uzun eksenine dik kapanır; kare nesnede en az dönüş", () => {
    const q = P.ikCoz(S, O, [190, -50, 10], 180);
    for (const aciD of [0, 20, 45, 70, 90, 135, 170]) {
      const n = { aci: aciD * R, uzun: 40, kisa: 15 };
      const b = K.bilekSec(S, q, n);
      assert.ok(b !== null);
      const qq = q.slice(); qq[3] = b;
      const d = Math.abs(((K.ceneYonu(qq) - (n.aci + Math.PI / 2)) % Math.PI + 1.5 * Math.PI) % Math.PI - Math.PI / 2);
      assert.ok(d < 1 * R, `nesne ${aciD}°: çene farkı ${(d / R).toFixed(2)}°`);
    }
    const kare = K.bilekSec(S, q, { aci: 10 * R, uzun: 25, kisa: 24 }, 0);
    assert.ok(Math.abs(kare) <= 45, `kare nesnede bilek ${kare}`);
  });

  await test("al-bırak planı: halkadaki nesne dik tutulur, uzaktaki eğik tutucuyla, erişilmeyen null", () => {
    const birak = { x: 150, y: 120 };
    const yakin = K.alPlan({ x: 190, y: -50, aci: 0, uzun: 25, kisa: 25 }, birak, S, O, P, BASLA, { yukseklik: 25 });
    assert.ok(yakin && yakin.alet === 180, JSON.stringify(yakin && yakin.alet));
    const uzak = K.alPlan({ x: 225, y: 60, aci: 0, uzun: 25, kisa: 25 }, birak, S, O, P, BASLA, { yukseklik: 25 });
    assert.ok(uzak && uzak.alet < 180, `uzak nesne: ${uzak && uzak.alet}`);
    assert.strictEqual(K.alPlan({ x: 320, y: 0, aci: 0, uzun: 25, kisa: 25 }, birak, S, O, P, BASLA), null);
    assert.strictEqual(K.alPlan({ x: 30, y: 0, aci: 0, uzun: 25, kisa: 25 }, birak, S, O, P, BASLA), null);
    console.log(`    halkadaki nesne alet ${yakin.alet}°, 238 mm'deki nesne alet ${uzak.alet}°`);
  });

  await test("uçtan uca: görüntüden bulunan nesne simülasyon koluyla kavranır (uç nesnede, çeneler eksene dik)", async () => {
    const n0 = { x: 185, y: -40, aci: 35 * R, uzun: 40, kisa: 18, renk: KIRMIZI };
    const isaret = [[120, -120], [280, -120], [280, 120], [120, 120]];
    const tik = isaret.map(([x, y]) => masadanGoruntuye(x, y).map(Math.round));
    const Hk = K.homografi(tik, isaret);
    const L = K.lekeler(goruntu([n0]), W, Hh, K.renkKurali(K.hsv(...KIRMIZI)), { H: Hk });
    const n = K.masaya(Hk, L[0]);
    const plan = K.alPlan(n, { x: 150, y: 120 }, S, O, P, BASLA, { yukseklik: 18 });
    assert.ok(plan);
    const { hedefler } = P.coz(plan.adimlar, S, O, BASLA);
    const mem = new Uint8Array(1024).fill(0xff);
    const kol = new H.Kol([90, 100, 80, 90, 90, 60], S.SERVO_MIN, S.SERVO_MAX, { oku: (a) => mem[a], yaz: (a, v) => { mem[a] = v; } });
    let t = 0, kavrama = null;
    const io = {
      git(o) { o.forEach((v, i) => kol.uygula({ tip: "INCE", servo: i, deger: v })); kol.uygula({ tip: "GIT" }); },
      vardi: (o) => kol.hedefte() && o.every((v, i) => kol.hedef[i] === v),
      yakin: (o, tol) => o.every((v, i) => Math.abs(kol.p[i] * 10 - v) <= tol),
      async uyku(ms) { for (let k = 0; k < ms / 10; k++) kol.adim(); t += ms; },
      simdi: () => t, durdu: () => false,
      adim(i) { if (plan.adimlar[hedefler[i].adim].tip === "tutucu" && hedefler[i].adim === 3) kavrama = kol.p.slice(); },
    };
    assert.deepStrictEqual(await P.calistir(hedefler, io), { bitti: true });
    const q = S.eklemAci(kavrama), uc = S.fk(q, O).noktalar[4].map((v) => v * 1000);
    const d = Math.hypot(uc[0] - n0.x, uc[1] - n0.y);
    const cene = Math.abs(((K.ceneYonu(q) - (n0.aci + Math.PI / 2)) % Math.PI + 1.5 * Math.PI) % Math.PI - Math.PI / 2);
    console.log(`    kavrarken uç nesne merkezinden ${d.toFixed(2)} mm, çene açısı farkı ${(cene / R).toFixed(1)}°, toplam ${(t / 1000).toFixed(1)} sn`);
    assert.ok(d < 2, `uç ${d} mm`);
    assert.ok(cene < 3 * R);
    assert.ok(Math.abs(uc[2] - Math.max(5, 18 * 0.4)) < 1);
  });

  // ---------------------------------------------------------------- gerçek perspektif (ışın izleme) ve yükseklik
  const sub = (a, b) => a.map((v, i) => v - b[i]), dot = (a, b) => a.reduce((s, v, i) => s + v * b[i], 0);
  const nrm = (v) => { const n = Math.hypot(...v); return v.map((x) => x / n); };
  const cr = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  // İğne delikli kamera: C konumu, T baktığı nokta, f odak (piksel); görüntü sağı = x, aşağısı = y
  function pinhole(C, T, f, w, h, yukari = [0, 0, 1]) {
    const z = nrm(sub(T, C)), x = nrm(cr(z, yukari)), y = cr(z, x);
    return {
      C, f,
      izdus: (P) => { const d = sub(P, C), zc = dot(z, d); return [f * dot(x, d) / zc + w / 2, f * dot(y, d) / zc + h / 2]; },
      isin: (u, v) => nrm([0, 1, 2].map((i) => x[i] * (u - w / 2) / f + y[i] * (v - h / 2) / f + z[i])),
    };
  }
  // Masa (z = 0, gri) üstünde küpler (kenar k, z yönünde 0..k); üst yüz parlak, yanlar gölgeli
  function kupGoruntu(cam, kupler, w, h) {
    const d = new Uint8ClampedArray(w * h * 4);
    for (let v = 0; v < h; v++) for (let u = 0; u < w; u++) {
      const r = cam.isin(u + 0.5, v + 0.5);
      let en = r[2] < 0 ? -cam.C[2] / r[2] : Infinity, renk = [118, 120, 122];
      for (const q of kupler) {
        const c = Math.cos(-q.aci), s = Math.sin(-q.aci), o = sub(cam.C, [q.x, q.y, 0]);
        const lo = [o[0] * c - o[1] * s, o[0] * s + o[1] * c, o[2]], ld = [r[0] * c - r[1] * s, r[0] * s + r[1] * c, r[2]];
        const A = q.a ?? q.k, B = q.b ?? q.k, mn = [-A / 2, -B / 2, 0], mx = [A / 2, B / 2, q.k];
        let t0 = -Infinity, t1 = Infinity, eks = -1;
        for (let i = 0; i < 3; i++) {
          if (Math.abs(ld[i]) < 1e-12) { if (lo[i] < mn[i] || lo[i] > mx[i]) { t0 = Infinity; break; } continue; }
          let a = (mn[i] - lo[i]) / ld[i], b = (mx[i] - lo[i]) / ld[i];
          if (a > b) [a, b] = [b, a];
          if (a > t0) { t0 = a; eks = i; }
          if (b < t1) t1 = b;
        }
        if (t0 <= t1 && t0 > 0 && t0 < en) { en = t0; const g = eks === 2 ? 1 : eks === 0 ? 0.72 : 0.58; renk = q.renk.map((x) => x * g); }
      }
      d.set([...renk, 255], (v * w + u) * 4);
    }
    return d;
  }
  const ISARET = [[120, -120], [280, -120], [280, 120], [120, 120]];
  const KUPLER = [
    { x: 190, y: -50, k: 20, aci: 20 * R, renk: KIRMIZI },
    { x: 235, y: 45, k: 20, aci: -10 * R, renk: YESIL },
    { x: 150, y: 10, k: 20, aci: 40 * R, renk: [215, 185, 30] },
  ];
  function olc(cam, w, h, kam) {
    const tik = ISARET.map(([x, y]) => cam.izdus([x, y, 0]).map(Math.round));
    const Hk = K.homografi(tik, ISARET);
    const img = kupGoruntu(cam, KUPLER, w, h);
    const sonuc = { Hk, ham: 0, duz: {} };
    const kat = [0.5, 0.55, 0.6, 0.7, 1.0];
    for (const q of KUPLER) {
      const kk = kam(Hk);
      const L = K.nesneBul(img, w, h, K.renkKurali(K.hsv(...q.renk)), { H: Hk, kam: kk, yukseklik: q.k });
      assert.strictEqual(L.length, 1);
      const m = L[0].masa, n = L[0].nesne;
      assert.ok(n.taban);
      sonuc.ham = Math.max(sonuc.ham, Math.hypot(m.x - q.x, m.y - q.y));
      for (const a of kat) { const p = K.yukseklikDuzelt(kk, m, q.k * a); sonuc.duz[a] = Math.max(sonuc.duz[a] || 0, Math.hypot(p.x - q.x, p.y - q.y)); }
      sonuc.secilen = Math.max(sonuc.secilen || 0, Math.hypot(n.x - q.x, n.y - q.y));
    }
    return sonuc;
  }

  await test("kamera konumu: eğik (laptop) bakışta 4 işaretten kamera yeri ve odak uzaklığı bulunur", () => {
    const w = 640, h = 480, cam = pinhole([450, 0, 260], [190, 0, 0], 600, w, h);
    ISARET.forEach(([x, y]) => { const p = cam.izdus([x, y, 0]); assert.ok(p[0] > 0 && p[0] < w && p[1] > 0 && p[1] < h); });
    const tik = ISARET.map(([x, y]) => cam.izdus([x, y, 0]).map(Math.round));
    const kam = K.kameraKonumu(K.homografi(tik, ISARET), w, h);
    assert.ok(kam, "kamera konumu çıkmalı");
    const d = Math.hypot(...sub(kam.C, cam.C));
    console.log(`    gerçek C (450, 0, 260), bulunan (${kam.C.map((v) => v.toFixed(0)).join(", ")}), f ${kam.f.toFixed(0)} (gerçek 600), eğim ${kam.egim.toFixed(0)}°`);
    assert.ok(d < 15, `C hatası ${d.toFixed(1)} mm`);
    assert.ok(Math.abs(kam.f - 600) < 30);
  });

  await test("yükseklik düzeltmesi: eğik bakışta 20 mm küplerin hatası büyük ölçüde gider", () => {
    const w = 640, h = 480, cam = pinhole([450, 0, 260], [190, 0, 0], 600, w, h);
    const s = olc(cam, w, h, (Hk) => K.kameraKonumu(Hk, w, h));
    console.log(`    düzeltmesiz ${s.ham.toFixed(1)} mm · düzeltmeli (etkin yükseklik = katsayı x küp): ` +
      Object.entries(s.duz).map(([a, e]) => `${a}: ${e.toFixed(1)}`).join(", ") + " mm");
    assert.ok(s.ham > 6, "eğik bakışta düzeltmesiz hata büyük olmalı");
    console.log(`    taban bulma (katsayısız): ${s.secilen.toFixed(2)} mm`);
    assert.ok(s.secilen < 1.5, `taban bulma ${s.secilen.toFixed(2)} mm`);
  });

  await test("şekil düzeltmesi: eğik bakışta dikdörtgen bloğun yönü ve boyları düzelir", () => {
    const w = 640, h = 480, cam = pinhole([450, 0, 260], [190, 0, 0], 600, w, h);
    const tik = ISARET.map(([x, y]) => cam.izdus([x, y, 0]).map(Math.round));
    const Hk = K.homografi(tik, ISARET), kam = K.kameraKonumu(Hk, w, h);
    const fark = (a, b) => Math.abs(((a - b) % Math.PI + 1.5 * Math.PI) % Math.PI - Math.PI / 2) / R;
    let hamEn = 0, duzEn = 0, konEn = 0;
    for (const aciD of [0, 30, 60, 90, 120, 150]) for (const [x, y] of [[190, -50], [230, 40]]) {
      const q = { x, y, a: 40, b: 15, k: 15, aci: aciD * R, renk: KIRMIZI };
      const L = K.nesneBul(kupGoruntu(cam, [q], w, h), w, h, K.renkKurali(K.hsv(...KIRMIZI)), { H: Hk, kam, yukseklik: q.k });
      const n = L[0].nesne;
      hamEn = Math.max(hamEn, fark(L[0].masa.aci, q.aci)); duzEn = Math.max(duzEn, fark(n.aci, q.aci));
      konEn = Math.max(konEn, Math.hypot(n.x - x, n.y - y));
      assert.ok(Math.abs(n.uzun - 40) < 4 && Math.abs(n.kisa - 15) < 4, `boy ${n.uzun.toFixed(1)} x ${n.kisa.toFixed(1)} (${aciD}°)`);
    }
    console.log(`    40x15x15 blok: yön hatası düzeltmesiz ${hamEn.toFixed(1)}°, düzeltmeli ${duzEn.toFixed(1)}°; konum ${konEn.toFixed(2)} mm`);
    assert.ok(duzEn < 4 && duzEn < hamEn / 2);
    assert.ok(konEn < 1.5);
  });

  await test("küp yönü (4. moment): eğik bakışta küplerin yüz yönü 90° simetriyle bulunur; çeneler yüzlere paralel kapanır", () => {
    const w = 640, h = 480, cam = pinhole([450, 0, 260], [190, 0, 0], 600, w, h);
    const tik = ISARET.map(([x, y]) => cam.izdus([x, y, 0]).map(Math.round));
    const Hk = K.homografi(tik, ISARET), kam = K.kameraKonumu(Hk, w, h);
    const fark90 = (a, b) => Math.abs((((a - b) / R) % 90 + 135) % 90 - 45);
    let en = 0, cene = 0;
    for (const aciD of [0, 10, 25, 40, 55, 70, 85]) for (const [x, y] of [[190, -60], [215, 50]]) {
      const q = { x, y, k: 20, aci: aciD * R, renk: YESIL };
      const n = K.nesneBul(kupGoruntu(cam, [q], w, h), w, h, K.renkKurali(K.hsv(...YESIL)), { H: Hk, kam, yukseklik: 20 })[0].nesne;
      en = Math.max(en, fark90(n.aci, q.aci));
      const qk = P.ikCoz(S, O, [n.x, n.y, 8], 180);
      if (qk) { qk[3] = K.bilekSec(S, qk, n); cene = Math.max(cene, fark90(K.ceneYonu(qk), q.aci)); }
    }
    console.log(`    20 mm küp: yön hatası en fazla ${en.toFixed(1)}° (mod 90), çene-yüz farkı ${cene.toFixed(1)}°`);
    assert.ok(en < 3 && cene < 4);
  });

  await test("kola yakın nesne: tutucu tabana doğru eğilerek (alet > 180°) alınır", () => {
    const n = { x: 150, y: -60, aci: 0, uzun: 20, kisa: 20 };       // 162 mm: dik tutucunun iç sınırının içinde
    assert.strictEqual(P.ikCoz(S, O, [n.x, n.y, 8], 180), null);
    const plan = K.alPlan(n, { x: 150, y: 120 }, S, O, P, BASLA, { yukseklik: 20 });
    assert.ok(plan && plan.alet > 180, JSON.stringify(plan && plan.alet));
    console.log(`    162 mm'deki nesne: tutucu ${plan.alet}°`);
  });

  // Uçtaki renkli bant: küçük bir küre (yarıçap 4 mm), masa gri
  function bantGoruntu(cam, p, w, h, renk = [214, 51, 132]) {
    const d = new Uint8ClampedArray(w * h * 4);
    for (let v = 0; v < h; v++) for (let u = 0; u < w; u++) {
      const r = cam.isin(u + 0.5, v + 0.5), o = sub(cam.C, p), b = dot(o, r), c = dot(o, o) - 16;
      d.set([...(b * b - c >= 0 && -b > 0 ? renk : [118, 120, 122]), 255], (v * w + u) * 4);
    }
    return d;
  }
  function otoKalibrasyon(cam, w, h, hB, elle) {
    const hedef = K.ucNoktalari(S, O, P, hB), px = [];
    for (const [x, y] of hedef) {
      const L = K.lekeler(bantGoruntu(cam, [x, y, hB], w, h), w, h, K.renkKurali(K.hsv(214, 51, 132)), { minAlan: 4 });
      assert.strictEqual(L.length, 1);
      px.push([L[0].cx, L[0].cy]);
    }
    return { hedef, sonuc: K.duzlemdenMasaya(K.homografi(px, hedef), w, h, hB, elle) };
  }

  await test("kolla otomatik kalibrasyon: uçtaki bant 8 noktada bulunur, masa homografisi ve kamera konumu çıkar", () => {
    const w = 640, h = 480, cam = pinhole([450, 0, 260], [190, 0, 0], 600, w, h);
    const { hedef, sonuc } = otoKalibrasyon(cam, w, h, 10);
    assert.ok(hedef.length >= 6, `${hedef.length} nokta`);
    assert.ok(sonuc && !sonuc.kam.elle);
    const dC = Math.hypot(...sub(sonuc.kam.C, cam.C));
    // masadaki rastgele noktalar: kameranın gördüğü pikselden geri bulunan yer
    let en = 0;
    for (let i = 0; i < 200; i++) {
      const x = 130 + rnd() * 120, y = -110 + rnd() * 220, q = K.uygula(sonuc.H, cam.izdus([x, y, 0]));
      en = Math.max(en, Math.hypot(q[0] - x, q[1] - y));
    }
    console.log(`    ${hedef.length} nokta · kamera (${sonuc.kam.C.map((v) => v.toFixed(0)).join(", ")}) (gerçek 450, 0, 260) · masada en kötü hata ${en.toFixed(2)} mm`);
    assert.ok(dC < 15 && en < 1);
    // bu kalibrasyonla küp tabanları
    const img = kupGoruntu(cam, KUPLER, w, h);
    for (const q of KUPLER) {
      const n = K.nesneBul(img, w, h, K.renkKurali(K.hsv(...q.renk)), { H: sonuc.H, kam: sonuc.kam, yukseklik: q.k })[0].nesne;
      assert.ok(Math.hypot(n.x - q.x, n.y - q.y) < 1.5, `küp ${Math.hypot(n.x - q.x, n.y - q.y).toFixed(2)} mm`);
    }
  });

  await test("kolla otomatik kalibrasyon, tepeden kamera: elle yükseklikle de çalışır", () => {
    const w = 640, h = 480, cam = pinhole([200, 0, 500], [200, 0, 0], 600, w, h, [1, 0, 0]);
    const { sonuc } = otoKalibrasyon(cam, w, h, 10, 500);
    assert.ok(sonuc && sonuc.kam.elle);
    let en = 0;
    for (let i = 0; i < 200; i++) {
      const x = 130 + rnd() * 120, y = -110 + rnd() * 220, q = K.uygula(sonuc.H, cam.izdus([x, y, 0]));
      en = Math.max(en, Math.hypot(q[0] - x, q[1] - y));
    }
    console.log(`    tepeden: masada en kötü hata ${en.toFixed(2)} mm`);
    assert.ok(en < 1);
  });

  await test("tepeden kamera: konum tahmin edilemez (null), elle yükseklikle düzeltme çalışır", () => {
    const w = 640, h = 480, cam = pinhole([200, 0, 500], [200, 0, 0], 600, w, h, [1, 0, 0]);
    const tik = ISARET.map(([x, y]) => cam.izdus([x, y, 0]).map(Math.round));
    assert.strictEqual(K.kameraKonumu(K.homografi(tik, ISARET), w, h), null);
    const s = olc(cam, w, h, (Hk) => K.kameraElle(Hk, w, h, 500));
    console.log(`    tepeden: düzeltmesiz ${s.ham.toFixed(1)} mm, elle yükseklikle taban bulma ${s.secilen.toFixed(2)} mm`);
    assert.ok(s.secilen < 1);
  });

  console.log(`\n${gecen} test geçti`);
})().catch((e) => { console.error("HATA:", e.message); process.exit(1); });
