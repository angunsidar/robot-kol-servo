// servo_program.js testi:  node test_program.js
// Programı simülasyondaki kolla (servo_hareket.js = Arduino'daki hareket kodu) sahte saatle çalıştırır.
"use strict";
const assert = require("assert");
const S = require("./servo_kinematik.js");
const H = require("./servo_hareket.js");
const P = require("./servo_program.js");

const O = S.olcu();
const EV = [90, 100, 80, 90, 90, 60];
const BASLA = EV.map((v) => v * 10);
let gecen = 0;
const test = async (ad, f) => { await f(); gecen++; console.log("ok  " + ad); };

// Simülasyon kolu + sahte saat: uyku(ms) kolu ms/10 adım ilerletir; her adımda uç konumu kaydedilir
function sanal() {
  const mem = new Uint8Array(1024).fill(0xff);
  const kol = new H.Kol(EV, S.SERVO_MIN, S.SERVO_MAX, { oku: (a) => mem[a], yaz: (a, v) => { mem[a] = v; } });
  let t = 0, dur = false;
  const varislar = [], iz = [];
  const io = {
    git(onda) { onda.forEach((v, i) => kol.uygula({ tip: "INCE", servo: i, deger: v })); kol.uygula({ tip: "GIT" }); },
    vardi(onda) {
      const ok = kol.hedefte() && onda.every((v, i) => kol.hedef[i] === v);
      if (ok) varislar.push({ t, p: kol.p.slice() });
      return ok;
    },
    yakin: (onda, tol) => onda.every((v, i) => Math.abs(kol.p[i] * 10 - v) <= tol),
    async uyku(ms) {
      for (let k = 0; k < ms / 10; k++) { kol.adim(); iz.push(P.uc(S, O, kol.p.map((x) => x * 10))); }
      t += ms;
    },
    simdi: () => t,
    durdu: () => dur,
  };
  return { kol, io, varislar, iz, durdur: () => { dur = true; }, saat: () => t };
}
const AL = { x: 170, y: -60, z: 30 }, BIRAK = { x: 150, y: 90, z: 30 };
const anaHedefler = (h) => h.filter((x) => x.tip !== "eklem" || !x.ara);
// p noktasının a-b doğru parçasına uzaklığı (mm)
function parcayaUzaklik(p, a, b) {
  const ab = [b.x - a.x, b.y - a.y, b.z - a.z], ap = [p.x - a.x, p.y - a.y, p.z - a.z];
  const L2 = ab[0] ** 2 + ab[1] ** 2 + ab[2] ** 2;
  const t = Math.max(0, Math.min(1, (ap[0] * ab[0] + ap[1] * ab[1] + ap[2] * ab[2]) / L2));
  return Math.hypot(ap[0] - t * ab[0], ap[1] - t * ab[1], ap[2] - t * ab[2]);
}
// Kolu bir noktaya götür, sonra oradan hedefe (düz ya da eklemle) git; yol boyunca en büyük sapma
async function yolSapmasi(A, B, dogrusal) {
  const v = sanal();
  const ilk = P.coz([{ tip: "git", ...A, alet: 180 }], S, O, BASLA);
  await P.calistir(ilk.hedefler, v.io);
  const bas = v.kol.hedef.slice();
  const { hedefler, hatalar } = P.coz([{ tip: "git", ...B, alet: 180, dogrusal }], S, O, bas);
  assert.deepStrictEqual(hatalar, []);
  v.iz.length = 0;
  const t0 = v.saat();
  assert.deepStrictEqual(await P.calistir(hedefler, v.io), { bitti: true });
  const a = { ...A }, b = { ...B };
  return { sapma: Math.max(...v.iz.map((p) => parcayaUzaklik(p, a, b))), sure: v.saat() - t0, ara: hedefler.length - 1 };
}

(async () => {
  await test("al-bırak şablonu: 11 adım, doğru sıra, yükseklikler, iniş/kalkışlar düz", () => {
    const a = P.alBirak(AL, BIRAK, { yukseklik: 40 });
    assert.strictEqual(a.length, 11);
    assert.deepStrictEqual(a.map((x) => x.tip), ["tutucu", "git", "git", "tutucu", "bekle", "git", "git", "git", "tutucu", "bekle", "git"]);
    assert.strictEqual(a[1].z, 70); assert.strictEqual(a[2].z, 30); assert.strictEqual(a[7].z, 30);
    assert.strictEqual(a[0].aci, P.ACIK); assert.strictEqual(a[3].aci, P.KAPALI);
    assert.deepStrictEqual(a.filter((x) => x.tip === "git").map((x) => x.dogrusal), [false, true, true, false, true, true]);
  });

  await test("çöz: her hedef sınırlar içinde, uç istenen noktaya 1 mm'den yakın, ara noktalar doğru üstünde", () => {
    const adimlar = P.alBirak(AL, BIRAK);
    const { hedefler, hatalar } = P.coz(adimlar, S, O, BASLA);
    assert.deepStrictEqual(hatalar, []);
    const ana = anaHedefler(hedefler);
    assert.strictEqual(ana.length, 11);
    assert.ok(hedefler.length > 20, `${hedefler.length} hedef`);       // 40 mm iniş = 8 parça, 4 düz hareket
    hedefler.forEach((h) => {
      if (h.tip !== "eklem") return;
      h.onda.forEach((v, i) => assert.ok(v >= S.SERVO_MIN[i] * 10 && v <= S.SERVO_MAX[i] * 10));
      const a = adimlar[h.adim], u = P.uc(S, O, h.onda);
      if (a.tip === "git" && !h.ara) assert.ok(Math.hypot(u.x - a.x, u.y - a.y, u.z - a.z) < 1, `adım ${h.adim}`);
      if (h.ara) assert.ok(Math.hypot(u.x - a.x, u.y - a.y) < 1, `ara nokta düşey doğrudan saptı`);   // iniş/kalkış düşey
    });
    assert.strictEqual(ana[3].onda[5], P.KAPALI * 10);
    assert.deepStrictEqual(ana[3].onda.slice(0, 5), ana[2].onda.slice(0, 5));
    assert.ok(hedefler.every((h) => h.tip !== "eklem" || h.onda[3] === 900));
  });

  await test("çöz: erişim dışı nokta ve erişim dışından geçen düz yol hata verir", () => {
    let r = P.coz([{ tip: "git", x: 600, y: 0, z: 50, alet: 180 }, { tip: "tutucu", aci: 50 }], S, O, BASLA);
    assert.strictEqual(r.hatalar.length, 1); assert.strictEqual(r.hatalar[0].i, 0);
    assert.strictEqual(r.hedefler.length, 1); assert.strictEqual(r.hedefler[0].onda[5], 500);
    // iki uç erişilebilir, ama aradaki düz çizgi kola fazla yakından geçiyor (dirsek o kadar katlanamaz)
    const A = { tip: "git", x: 100, y: 150, z: 40, alet: 180 }, B = { tip: "git", x: 100, y: -150, z: 40, alet: 180 };
    assert.deepStrictEqual(P.coz([A, B], S, O, BASLA).hatalar, []);          // eklemle gidilebilir (yay çizer)
    r = P.coz([A, { ...B, dogrusal: true }], S, O, BASLA);
    assert.ok(r.hatalar.length === 1 && /düz yol/.test(r.hatalar[0].mesaj), JSON.stringify(r.hatalar));
  });

  await test("düz yol: uç çizgiden 1 mm'den az sapar; aynı hareket eklemle çok daha fazla sapar", async () => {
    const A = { x: 200, y: -60, z: 40 }, B = { x: 150, y: 80, z: 50 };
    const duz = await yolSapmasi(A, B, true), eklem = await yolSapmasi(A, B, false);
    console.log(`    ${Math.round(Math.hypot(B.x - A.x, B.y - A.y, B.z - A.z))} mm: düz ${duz.sapma.toFixed(2)} mm sapma (${duz.ara} ara nokta, ${(duz.sure / 1000).toFixed(1)} sn) · eklemle ${eklem.sapma.toFixed(1)} mm (${(eklem.sure / 1000).toFixed(1)} sn)`);
    assert.ok(duz.sapma < 1, `düz sapma ${duz.sapma}`);
    assert.ok(eklem.sapma > 5 * duz.sapma);
    const inis = await yolSapmasi({ x: 170, y: -60, z: 70 }, { x: 170, y: -60, z: 30 }, true);
    console.log(`    40 mm düşey iniş: ${inis.sapma.toFixed(2)} mm sapma`);
    assert.ok(inis.sapma < 0.5);
  });

  await test("yol(): başlangıçtan son hedefe; eklem hareketinin öngörülen yolu gerçek hareketle örtüşür", async () => {
    const A = { x: 200, y: -60, z: 40 }, B = { x: 150, y: 80, z: 50 };
    const v = sanal();
    await P.calistir(P.coz([{ tip: "git", ...A, alet: 180 }], S, O, BASLA).hedefler, v.io);
    const bas = v.kol.hedef.slice();
    const { hedefler } = P.coz([{ tip: "git", ...B, alet: 180 }], S, O, bas);
    const yol = P.yol(hedefler, S, O, bas);
    assert.strictEqual(yol.length, 17);
    v.iz.length = 0;
    await P.calistir(hedefler, v.io);
    // gerçek iz noktalarının öngörülen kırık çizgiye uzaklığı
    const uz = (p) => Math.min(...yol.slice(1).map((b, k) => parcayaUzaklik(p, { x: yol[k][0], y: yol[k][1], z: yol[k][2] }, { x: b[0], y: b[1], z: b[2] })));
    const enBuyuk = Math.max(...v.iz.map(uz));
    console.log(`    gerçek iz öngörülen yoldan en fazla ${enBuyuk.toFixed(2)} mm uzak`);
    assert.ok(enBuyuk < 1.5);
  });

  await test("çalıştır: simülasyon kolu her adıma sırayla varır, beklemeler süreyi uzatır", async () => {
    const adimlar = P.alBirak(AL, BIRAK);
    const { hedefler } = P.coz(adimlar, S, O, BASLA);
    const v = sanal(), sira = [];
    v.io.adim = (i) => { const a = hedefler[i].adim; if (sira[sira.length - 1] !== a) sira.push(a); };
    const r = await P.calistir(hedefler, v.io);
    assert.deepStrictEqual(r, { bitti: true });
    assert.deepStrictEqual(sira, [...Array(11).keys()]);
    const ana = hedefler.filter((y) => y.tip === "eklem" && !y.ara);
    assert.strictEqual(v.varislar.length, 9);                      // 9 ana eklem hedefinde durur, ara noktalarda durmaz
    v.varislar.forEach((x, k) => x.p.forEach((pv, i) => assert.strictEqual(pv, Math.fround(ana[k].onda[i] * Math.fround(0.1)))));
    assert.ok(v.saat() > 600 && v.saat() < 20000, `süre ${v.saat()} ms`);
    console.log(`    al-bırak (düz iniş/kalkışlarla) simülasyonda ${(v.saat() / 1000).toFixed(1)} sn sürdü`);
  });

  await test("çalıştır: durdurulunca o adımda biter", async () => {
    const { hedefler } = P.coz(P.alBirak(AL, BIRAK), S, O, BASLA);
    const v = sanal();
    const k = hedefler.findIndex((h) => h.tip === "bekle");
    v.io.adim = (i) => { if (i === k) v.durdur(); };
    const r = await P.calistir(hedefler, v.io);
    assert.strictEqual(r.durdu, true); assert.strictEqual(r.i, k);
  });

  await test("çalıştır: kol hiç varmazsa zaman aşımı hatası", async () => {
    const v = sanal();
    v.io.vardi = () => false;
    const r = await P.calistir([{ tip: "eklem", onda: [900, 1000, 800, 900, 900, 600], adim: 0 }], v.io, 2000);
    assert.ok(r.hata && /varmadı/.test(r.hata));
  });

  await test("çalıştır: döngü seçiliyse yeniden başlar, boş program hata", async () => {
    const { hedefler } = P.coz([{ tip: "tutucu", aci: 100 }, { tip: "tutucu", aci: 40 }], S, O, BASLA);
    const v = sanal(); let tur = 0;
    v.io.dongu = () => ++tur < 3;
    assert.deepStrictEqual(await P.calistir(hedefler, v.io), { bitti: true });
    assert.strictEqual(v.varislar.length, 6);
    assert.ok((await P.calistir([], v.io)).hata);
  });

  await test("kola yükleme: ana hedefler 'a1..a6 PUT' bloğu, ara noktalar ve beklemeler atlanır; yüklenen pozlar aynı", () => {
    const { hedefler } = P.coz(P.alBirak(AL, BIRAK), S, O, BASLA);
    const k = P.yuklemeKomutlari(hedefler);
    assert.strictEqual(k.length, 9);
    assert.ok(k.every((b) => /^a1-?\d+\na2-?\d+\na3-?\d+\na4-?\d+\na5-?\d+\na6-?\d+\nPUT$/.test(b)));
    const v = sanal();
    v.kol.uygula({ tip: "SIFIRLA" });
    for (const blok of k) for (const l of blok.split("\n")) {
      const m = l.match(/^a(\d)(-?\d+)$/);
      if (m) v.kol.uygula({ tip: "INCE", servo: +m[1] - 1, deger: +m[2] });
      else assert.strictEqual(v.kol.uygula({ tip: "EKLE" }), 3);
    }
    assert.strictEqual(v.kol.pozSayisi, 9);
    hedefler.filter((h) => h.tip === "eklem" && !h.ara).forEach((h, n) => assert.deepStrictEqual(v.kol.pozOku(n), h.onda));
    assert.ok(v.kol.hedefte() && v.kol.hedef.every((x, i) => x === EV[i] * 10));
  });

  await test("kalibrasyon: ofset/yön servo açılarını kaydırır, uç yine aynı noktaya gider; eklemAci servoAci'nin tersi", () => {
    const adim = [{ tip: "git", x: 180, y: 40, z: 50, alet: 180 }];
    const once = P.coz(adim, S, O, BASLA).hedefler[0].onda;
    try {
      S.kalibrasyon({ yon: [1, -1, 1, 1, -1], ofset: [3, -4.5, 2, 0, 6] });
      const q = [12.3, -20, 45, 5, -30];
      S.eklemAci(S.servoAci(q)).forEach((v, i) => assert.ok(Math.abs(v - q[i]) < 1e-9));
      const sonra = P.coz(adim, S, O, BASLA).hedefler[0].onda;
      assert.ok(Math.abs(sonra[0] - (once[0] + 30)) <= 1);                 // yön +1, ofset +3°
      assert.ok(Math.abs(sonra[2] - (once[2] + 20)) <= 1);                 // yön +1, ofset +2°
      assert.ok(Math.abs((sonra[1] - 900) + (once[1] - 900) + 45) <= 1);   // yön −1: 90'ın öbür yanına, ofset −4,5°
      const u = P.uc(S, O, sonra);
      assert.ok(Math.hypot(u.x - 180, u.y - 40, u.z - 50) < 1);
    } finally {
      S.kalibrasyon({ yon: [1, 1, 1, 1, 1], ofset: [0, 0, 0, 0, 0] });
    }
    assert.deepStrictEqual(P.coz(adim, S, O, BASLA).hedefler[0].onda, once);
  });

  console.log(`\n${gecen} test geçti`);
})().catch((e) => { console.error("HATA:", e.message); process.exit(1); });
