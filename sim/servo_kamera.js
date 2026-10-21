// Kamera ile nesne bulma: görüntü -> masa koordinatı (homografi), renkle leke bulma, nesne başına al-bırak planı.
// Sayfadan ve node testinden (test_kamera.js) aynı şekilde kullanılır. Görüntü: RGBA bayt dizisi (ImageData.data).
//
// Masa kalibrasyonu: masadaki en az 4 noktanın görüntüdeki pikseli ve masadaki konumu (mm, kolun çerçevesi:
// X ileri, Y sola, taban merkezi). Düzlemden düzleme dönüşüm perspektifi de düzeltir: kamera masaya eğik
// baksa da (laptop) çalışır. Yalnız masa düzlemi için kesindir: yüksek nesnelerin üst yüzü eğik bakışta
// kameradan uzağa kaymış görünür (bkz. README).
(function (root) {
  "use strict";
  const R = Math.PI / 180;
  // Yaklaşık düzeltme (nesneBul tabanı bulamazsa, ör. çok ince nesne): leke ağırlık merkezinin etkin yüksekliği =
  // katsayı x nesne yüksekliği. Işın izlemeli ölçümde 20°–60° eğimlerde, 15–30 mm küplerde en iyi katsayı 0,48–0,60
  // (ortanca ~0,55); tepeden bakışta yalnız üst yüz görünür: 1.
  const YUKSEKLIK_KATSAYI = 0.55;

  // ---------------------------------------------------------------- homografi
  // Doğrusal denklem çözümü (kısmi pivotlu Gauss). A: n x n, b: n
  function coz(A, b) {
    const n = b.length, M = A.map((r, i) => [...r, b[i]]);
    for (let c = 0; c < n; c++) {
      let p = c;
      for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r;
      if (Math.abs(M[p][c]) < 1e-12) return null;
      [M[c], M[p]] = [M[p], M[c]];
      for (let r = 0; r < n; r++) {
        if (r === c) continue;
        const f = M[r][c] / M[c][c];
        for (let k = c; k <= n; k++) M[r][k] -= f * M[c][k];
      }
    }
    return M.map((r, i) => r[n] / r[i]);
  }
  // Noktaları ağırlık merkezine taşı, ortalama uzaklık √2 olacak şekilde ölçekle (sayısal kararlılık)
  function normalle(p) {
    const n = p.length, cx = p.reduce((s, q) => s + q[0], 0) / n, cy = p.reduce((s, q) => s + q[1], 0) / n;
    const d = p.reduce((s, q) => s + Math.hypot(q[0] - cx, q[1] - cy), 0) / n || 1, k = Math.SQRT2 / d;
    return { T: [k, 0, -k * cx, 0, k, -k * cy, 0, 0, 1], p: p.map(([x, y]) => [k * (x - cx), k * (y - cy)]) };
  }
  const carp = (A, B) => { const C = []; for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) C.push(A[i * 3] * B[j] + A[i * 3 + 1] * B[3 + j] + A[i * 3 + 2] * B[6 + j]); return C; };
  function ters(H) {
    const [a, b, c, d, e, f, g, h, i] = H, A = e * i - f * h, B = -(d * i - f * g), C = d * h - e * g;
    const det = a * A + b * B + c * C;
    if (Math.abs(det) < 1e-15) return null;
    return [A, -(b * i - c * h), b * f - c * e, B, a * i - c * g, -(a * f - c * d), C, -(a * h - b * g), a * e - b * d].map((v) => v / det);
  }
  // kaynak[i] -> hedef[i] (n >= 4, üçü aynı doğru üstünde olmayan). En küçük kareler (h33 = 1). Dönüş: 9 sayı ya da null.
  function homografi(kaynak, hedef) {
    if (kaynak.length < 4 || kaynak.length !== hedef.length) return null;
    const a = normalle(kaynak), b = normalle(hedef);
    const N = Array.from({ length: 8 }, () => Array(8).fill(0)), v = Array(8).fill(0);
    a.p.forEach(([x, y], k) => {
      const [X, Y] = b.p[k];
      for (const [r, t] of [[[x, y, 1, 0, 0, 0, -X * x, -X * y], X], [[0, 0, 0, x, y, 1, -Y * x, -Y * y], Y]]) {
        for (let i = 0; i < 8; i++) { v[i] += r[i] * t; for (let j = 0; j < 8; j++) N[i][j] += r[i] * r[j]; }
      }
    });
    const h = coz(N, v);
    if (!h) return null;
    const Tb = ters(b.T); if (!Tb) return null;
    const H = carp(carp(Tb, [...h, 1]), a.T);
    return H.map((x) => x / H[8]);
  }
  function uygula(H, [x, y]) {
    const w = H[6] * x + H[7] * y + H[8];
    if (Math.abs(w) < 1e-12) return null;
    return [(H[0] * x + H[1] * y + H[2]) / w, (H[3] * x + H[4] * y + H[5]) / w];
  }
  // Kalibrasyon kalitesi: noktaların geri izdüşüm hatası (hedef birimi, mm)
  function hata(H, kaynak, hedef) {
    return Math.max(...kaynak.map((p, i) => { const q = uygula(H, p); return q ? Math.hypot(q[0] - hedef[i][0], q[1] - hedef[i][1]) : Infinity; }));
  }

  // ---------------------------------------------------------------- renk
  function hsv(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
    let h = 0;
    if (d > 0) h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
    h *= 60; if (h < 0) h += 360;
    return [h, mx ? d / mx : 0, mx];
  }
  const tonFarki = (a, b) => { const d = Math.abs(a - b) % 360; return d > 180 ? 360 - d : d; };
  // Görüntüden renk örneği: (x, y) çevresindeki r yarıçaplı karenin ortanca rengi
  function ornek(data, w, h, x, y, r = 3) {
    const rs = [], gs = [], bs = [];
    for (let j = Math.max(0, y - r); j <= Math.min(h - 1, y + r); j++)
      for (let i = Math.max(0, x - r); i <= Math.min(w - 1, x + r); i++) { const k = (j * w + i) * 4; rs.push(data[k]); gs.push(data[k + 1]); bs.push(data[k + 2]); }
    const ort = (a) => a.sort((p, q) => p - q)[a.length >> 1];
    return hsv(ort(rs), ort(gs), ort(bs));
  }
  // Rengin eşleşme kuralı: ton yakın, doygunluk ve parlaklık yeterli (gri masa, gölge ve beyaz parlama elenir)
  function renkKurali(hedef, tol = {}) {
    const dh = tol.ton ?? 18, minS = Math.max(0.25, hedef[1] * (tol.doygunluk ?? 0.45)), minV = Math.max(0.15, hedef[2] * (tol.parlaklik ?? 0.35));
    return (r, g, b) => { const [h, s, v] = hsv(r, g, b); return s >= minS && v >= minV && tonFarki(h, hedef[0]) <= dh; };
  }

  // ---------------------------------------------------------------- lekeler
  // İkinci momentlerden ana eksen açısı ve boylar (dikdörtgen varsayımı: boy = √(12 · varyans))
  function eksenler(n, sx, sy, sxx, syy, sxy) {
    const cx = sx / n, cy = sy / n, a = sxx / n - cx * cx, b = syy / n - cy * cy, c = sxy / n - cx * cy;
    const ort = (a + b) / 2, fark = Math.sqrt(((a - b) / 2) ** 2 + c * c);
    return { cx, cy, aci: 0.5 * Math.atan2(2 * c, a - b), uzun: Math.sqrt(12 * (ort + fark)), kisa: Math.sqrt(12 * Math.max(0, ort - fark)) };
  }

  // Renk kuralına uyan bitişik piksel grupları (4 komşuluk). o.adim > 1: her adim. pikseli tara (hız için).
  // Dönüş: [{ alan (piksel), cx, cy (sürekli piksel koordinatı: piksel i'nin merkezi i + 0,5, tıklamayla aynı),
  //          aci (ana eksen, rad), uzun, kisa (piksel), kutu, masa? }]
  // o.H (görüntü -> masa homografisi) verilirse her leke için masa: { x, y, aci, uzun, kisa (mm), alan (mm²) } da
  // hesaplanır: pikseller masaya izdüşürülüp masada kapladıkları alanla (|det H| / w³) ağırlıklandırılır. Eğik
  // bakışta görüntüdeki ağırlık merkezi masadaki merkezin izdüşümü değildir (uzak yarı küçük görünür); bu onu düzeltir.
  function lekeler(data, w, h, kural, o = {}) {
    const s = o.adim || 1, W = Math.ceil(w / s), Hh = Math.ceil(h / s), minAlan = o.minAlan ?? 40, Hm = o.H;
    const detH = Hm ? Math.abs(Hm[0] * (Hm[4] * Hm[8] - Hm[5] * Hm[7]) - Hm[1] * (Hm[3] * Hm[8] - Hm[5] * Hm[6]) + Hm[2] * (Hm[3] * Hm[7] - Hm[4] * Hm[6])) : 0;
    const m = new Uint8Array(W * Hh);
    for (let j = 0; j < Hh; j++) for (let i = 0; i < W; i++) { const k = ((j * s) * w + i * s) * 4; if (kural(data[k], data[k + 1], data[k + 2])) m[j * W + i] = 1; }
    const sonuc = [], yigin = new Int32Array(W * Hh), etiket = new Int32Array(W * Hh);
    let id = 0;
    for (let bas = 0; bas < m.length; bas++) {
      if (m[bas] !== 1) continue;
      let n = 0, sx = 0, sy = 0, sxx = 0, syy = 0, sxy = 0, x0 = W, y0 = Hh, x1 = 0, y1 = 0, t = 0;
      let mW = 0, mX = 0, mY = 0, mXX = 0, mYY = 0, mXY = 0;
      const hucre = [];
      id++;
      yigin[t++] = bas; m[bas] = 2;
      while (t) {
        const p = yigin[--t], x = p % W, y = (p / W) | 0;
        etiket[p] = id; hucre.push(p);
        const u = x * s + 0.5, v = y * s + 0.5;
        n++; sx += u; sy += v; sxx += u * u; syy += v * v; sxy += u * v;
        if (Hm) {
          const ww = Hm[6] * u + Hm[7] * v + Hm[8], X = (Hm[0] * u + Hm[1] * v + Hm[2]) / ww, Y = (Hm[3] * u + Hm[4] * v + Hm[5]) / ww;
          const a = 1 / Math.abs(ww * ww * ww);
          mW += a; mX += a * X; mY += a * Y; mXX += a * X * X; mYY += a * Y * Y; mXY += a * X * Y;
        }
        if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
        if (x > 0 && m[p - 1] === 1) { m[p - 1] = 2; yigin[t++] = p - 1; }
        if (x < W - 1 && m[p + 1] === 1) { m[p + 1] = 2; yigin[t++] = p + 1; }
        if (y > 0 && m[p - W] === 1) { m[p - W] = 2; yigin[t++] = p - W; }
        if (y < Hh - 1 && m[p + W] === 1) { m[p + W] = 2; yigin[t++] = p + W; }
      }
      const alan = n * s * s;
      if (alan < minAlan) continue;
      const e = eksenler(n, sx, sy, sxx, syy, sxy);
      const l = { alan, cx: e.cx, cy: e.cy, aci: e.aci, uzun: e.uzun, kisa: e.kisa, kutu: [x0 * s, y0 * s, (x1 + 1) * s, (y1 + 1) * s] };
      Object.defineProperty(l, "_hucre", { value: hucre }); Object.defineProperty(l, "_id", { value: id });
      if (Hm && mW > 0) {
        const me = eksenler(mW, mX, mY, mXX, mYY, mXY);
        l.masa = { x: me.cx, y: me.cy, aci: me.aci, uzun: me.uzun, kisa: me.kisa, alan: mW * detH * s * s };
      }
      sonuc.push(l);
    }
    sonuc.sort((a, b) => b.alan - a.alan);
    Object.defineProperty(sonuc, "etiket", { value: { etiket, W, Hh, s, detH } });
    return sonuc;
  }

  // Leke -> masa: merkez (mm), uzun eksen açısı (masada, rad) ve boyutlar (mm). lekeler(..., { H }) ile bulunan
  // lekede kesin (alan ağırlıklı) değerleri, yoksa merkez ve eksen uçlarının izdüşümüyle yaklaşık değerleri verir.
  function masaya(H, l) {
    if (l.masa) return l.masa;
    const c = uygula(H, [l.cx, l.cy]);
    if (!c) return null;
    const ex = [Math.cos(l.aci), Math.sin(l.aci)], ey = [-ex[1], ex[0]];
    const u = (v, k) => uygula(H, [l.cx + v[0] * k, l.cy + v[1] * k]);
    const a1 = u(ex, l.uzun / 2), a2 = u(ex, -l.uzun / 2), b1 = u(ey, l.kisa / 2), b2 = u(ey, -l.kisa / 2);
    return { x: c[0], y: c[1], aci: Math.atan2(a1[1] - a2[1], a1[0] - a2[0]),
             uzun: Math.hypot(a1[0] - a2[0], a1[1] - a2[1]), kisa: Math.hypot(b1[0] - b2[0], b1[1] - b2[1]) };
  }

  // ---------------------------------------------------------------- kamera konumu ve yükseklik düzeltmesi
  // Masa kalibrasyonunun homografisinden (görüntü -> masa) kameranın masadaki konumu (mm). Kare piksel ve optik
  // merkezin görüntü ortası olduğu varsayılır (webcam'lerde makul); odak uzaklığı f ve konum C buradan çıkar
  // (Zhang, tek görünüş). Kamera masaya dik bakıyorsa (tepeden) perspektif bilgisi yoktur: null döner; o zaman
  // C = görüntü ortasının masadaki yeri + elle verilen yükseklik kullanılır (kameraElle).
  function kameraKonumu(H, w, h) {
    const G = ters(H);
    if (!G) return null;
    const cx = w / 2, cy = h / 2, g = [0, 1, 2].map((j) => [G[j] - cx * G[6 + j], G[3 + j] - cy * G[6 + j], G[6 + j]]);
    const [a, b] = g, adaylar = [];
    if (Math.abs(a[2] * b[2]) > 1e-12) adaylar.push(-(a[0] * b[0] + a[1] * b[1]) / (a[2] * b[2]));                         // r1 ⟂ r2
    const dz = b[2] * b[2] - a[2] * a[2];
    if (Math.abs(dz) > 1e-12) adaylar.push((a[0] * a[0] + a[1] * a[1] - b[0] * b[0] - b[1] * b[1]) / dz);                 // |r1| = |r2|
    const iyi = adaylar.filter((v) => Number.isFinite(v) && v > 0);
    if (!iyi.length) return null;
    const f = Math.sqrt(iyi.reduce((s, v) => s + v, 0) / iyi.length);
    const Ki = (v) => [v[0] / f, v[1] / f, v[2]];
    let r1 = Ki(g[0]), r2 = Ki(g[1]), t = Ki(g[2]);
    let lam = 2 / (Math.hypot(...r1) + Math.hypot(...r2));
    if (t[2] * lam < 0) lam = -lam;                                 // masa kameranın önünde
    [r1, r2, t] = [r1, r2, t].map((v) => v.map((x) => x * lam));
    const r3 = [r1[1] * r2[2] - r1[2] * r2[1], r1[2] * r2[0] - r1[0] * r2[2], r1[0] * r2[1] - r1[1] * r2[0]];
    const C = [r1, r2, r3].map((r) => -(r[0] * t[0] + r[1] * t[1] + r[2] * t[2]));   // C = -Rᵀ t, R = [r1 r2 r3]
    if (C[2] < 0) return null;
    // Görüş eğimi küçükse (tepeden bakışa yakın) f ve C güvenilmez
    const egim = Math.acos(Math.min(1, Math.abs(r3[2]))) / R;
    if (egim < 8 || C[2] < 20) return null;
    return { f, C, egim };
  }
  function kameraElle(H, w, h, yukseklik) {
    const c = uygula(H, [w / 2, h / 2]);
    return c ? { f: null, C: [c[0], c[1], yukseklik], egim: 0, elle: true } : null;
  }
  const etkinYukseklik = (kam, h) => h * (!kam || kam.elle || kam.egim < 8 ? 1 : YUKSEKLIK_KATSAYI);
  // Masa düzlemindeki izdüşümden (P0) yüksekliği hEtkin olan noktanın gerçek yerine: kameradan geçen doğru üstünde
  function yukseklikDuzelt(kam, p, hEtkin) {
    if (!kam || !(hEtkin > 0)) return { x: p.x, y: p.y };
    const k = (kam.C[2] - hEtkin) / kam.C[2];
    return { x: kam.C[0] + (p.x - kam.C[0]) * k, y: kam.C[1] + (p.y - kam.C[1]) * k };
  }

  // Kareye yakın şeklin yönü (mod 90°): ikinci momentler karede her yönde eşittir, yön vermez. Dördüncü açısal
  // moment c4 = Σ w (dx + i dy)⁴ köşeleri görür: kenarları eksenlere paralel bir karede arg(c4) = π (köşeler 45°'de).
  const KARE_ORAN = 1.3;
  function kareYonu(nok, cx, cy) {
    let re = 0, im = 0;
    for (let i = 0; i < nok.length; i += 3) {
      const x = nok[i] - cx, y = nok[i + 1] - cy, w = nok[i + 2], x2 = x * x, y2 = y * y;
      re += w * (x2 * x2 - 6 * x2 * y2 + y2 * y2); im += w * (4 * x * y * (x2 - y2));
    }
    return (Math.atan2(im, re) - Math.PI) / 4;
  }

  // Nesnelerin TABANI: yüksekliği hN olan dışbükey bir nesnenin masaya izdüşürülmüş görüntüsü F, tabanın
  // 0..hN yüksekliklerindeki kopyalarının birleşimidir; her kopya kameradan uzağa biraz daha kaymıştır
  // (z yüksekliğindeki noktanın izdüşümü: C + (B − C) · Cz / (Cz − z)). F ile "hN kadar geri itilmiş" F'nin
  // kesişimi tam tabandır. Uygulama: lekenin her pikselini hN yüksekliğindeymiş gibi kameradan uzağa it; itilen
  // nokta hâlâ lekedeyse piksel tabana aittir. Tabandan (alan ağırlıklı) konum, yön ve boylar mm olarak çıkar.
  // o: { H (görüntü -> masa), kam (kameraKonumu / kameraElle), yukseklik (mm), adim, minAlan }
  // Dönüş: lekeler() gibi; her lekede nesne: { x, y, aci, uzun, kisa, alan, taban (bool) }.
  function nesneBul(data, w, h, kural, o = {}) {
    const L = lekeler(data, w, h, kural, o), Hm = o.H, kam = o.kam, hN = o.yukseklik;
    if (!Hm) return L;
    const G = ters(Hm), { etiket, W, Hh, s, detH } = L.etiket;
    for (const l of L) {
      l.nesne = { ...l.masa, taban: false };
      if (!kam || !(hN > 0) || kam.C[2] <= hN || !G) continue;
      const k = kam.C[2] / (kam.C[2] - hN);
      let mW = 0, mX = 0, mY = 0, mXX = 0, mYY = 0, mXY = 0;
      const nok = [];                                              // tabandaki noktalar (X, Y, ağırlık): kare yönü için
      for (const p of l._hucre) {
        const u = (p % W) * s + 0.5, v = ((p / W) | 0) * s + 0.5;
        const ww = Hm[6] * u + Hm[7] * v + Hm[8], X = (Hm[0] * u + Hm[1] * v + Hm[2]) / ww, Y = (Hm[3] * u + Hm[4] * v + Hm[5]) / ww;
        const q = uygula(G, [kam.C[0] + (X - kam.C[0]) * k, kam.C[1] + (Y - kam.C[1]) * k]);
        if (!q) continue;
        const i = Math.floor(q[0] / s), j = Math.floor(q[1] / s);
        if (i < 0 || j < 0 || i >= W || j >= Hh || etiket[j * W + i] !== l._id) continue;
        const a = 1 / Math.abs(ww * ww * ww);
        mW += a; mX += a * X; mY += a * Y; mXX += a * X * X; mYY += a * Y * Y; mXY += a * X * Y;
        nok.push(X, Y, a);
      }
      if (mW > 0) {
        const e = eksenler(mW, mX, mY, mXX, mYY, mXY);
        l.nesne = { x: e.cx, y: e.cy, aci: e.aci, uzun: e.uzun, kisa: e.kisa, alan: mW * detH * s * s, taban: true };
        if (e.uzun / Math.max(e.kisa, 1e-6) < KARE_ORAN) l.nesne.aci = kareYonu(nok, e.cx, e.cy);
      } else {                                                    // çok ince nesne: kesişim boş kaldı, yaklaşık düzelt
        const p = yukseklikDuzelt(kam, l.masa, etkinYukseklik(kam, hN));
        l.nesne = { ...l.masa, x: p.x, y: p.y, taban: false };
      }
    }
    return L;
  }

  // ---------------------------------------------------------------- kolla otomatik masa kalibrasyonu
  // Tutucu ucuna renkli bant sarılır; kol ucu masanın h mm üstünde bilinen noktalara götürür, kamera bandı bulur.
  // Kalibrasyon noktaları: dik tutucuyla erişilen halkada, kameranın göreceği önde, geniş yayılmış (en az 4, üçü bir doğruda değil)
  function ucNoktalari(S, O, P, h = 10) {
    const out = [];
    for (const r of [175, 205]) for (const t of [-60, -25, 10, 45]) {
      const p = [r * Math.cos(t * R), r * Math.sin(t * R)];
      if (P.ikCoz(S, O, [p[0], p[1], h], 180)) out.push(p.map((v) => Math.round(v * 10) / 10));
    }
    return out;
  }
  // h yüksekliğindeki düzlemin homografisinden (görüntü -> o düzlemde x, y) masa (z = 0) homografisi ve kamera konumu.
  // Kamera konumu düzleme göre bulunur, yüksekliği h kadar kaydırılır; masa noktası, kameradan düzlemdeki noktaya giden
  // ışının z = 0'a uzatılmasıdır. elleYukseklik: tepeden bakışta (konum bulunamazsa) kameranın masadan yüksekliği.
  function duzlemdenMasaya(Hh, w, hgt, h, elleYukseklik) {
    let kam = kameraKonumu(Hh, w, hgt);
    if (kam) kam = { ...kam, C: [kam.C[0], kam.C[1], kam.C[2] + h] };
    else kam = kameraElle(Hh, w, hgt, elleYukseklik);
    if (!kam || kam.C[2] <= h) return null;
    const k = kam.C[2] / (kam.C[2] - h), px = [], mm = [];
    for (const [u, v] of [[0, 0], [w, 0], [w, hgt], [0, hgt], [w / 2, hgt / 2], [w / 4, hgt * 3 / 4], [w * 3 / 4, hgt / 4]]) {
      const q = uygula(Hh, [u, v]);
      if (!q) continue;
      px.push([u, v]); mm.push([kam.C[0] + (q[0] - kam.C[0]) * k, kam.C[1] + (q[1] - kam.C[1]) * k]);
    }
    const H0 = homografi(px, mm);
    if (!H0) return null;
    return { H: H0, kam: kam.elle ? kameraElle(H0, w, hgt, elleYukseklik) : { ...kam } };
  }

  // ---------------------------------------------------------------- tutuş ve plan
  // Tutucu çenelerinin masadaki yönü (rad), eklemler q (derece; q[3] bilek dönüşü). Çeneler aletin x ekseninde açılır.
  function ceneYonu(q) {
    const a = (q[1] + q[2] + q[4]) * R, b = q[3] * R;
    const v = [Math.cos(a) * Math.cos(b), Math.sin(b)];   // Ry(alet) · Rz(bilek) · x, yatay bileşenler
    return q[0] * R + Math.atan2(v[1], v[0]);
  }
  const mod = (x, m) => ((x % m) + m) % m;
  // Nesneyi enine kavramak için bilek dönüşü (eklem °, sınır içinde). Kareye yakın nesnede 90°'lik simetri kullanılır;
  // birden çok çözüm varsa mevcut bileğe en yakını.
  function bilekSec(S, q, nesne, mevcut = 0) {
    const simetri = nesne.kisa > 0 && nesne.uzun / nesne.kisa < KARE_ORAN ? Math.PI / 2 : Math.PI;
    const istenen = nesne.aci + Math.PI / 2;
    const [lo, hi] = S.eklemLimit()[3];
    let en = null;
    for (let b = Math.ceil(lo); b <= Math.floor(hi); b += 0.5) {
      const qq = q.slice(); qq[3] = b;
      const d = mod(ceneYonu(qq) - istenen + simetri / 2, simetri) - simetri / 2;
      const puan = Math.abs(d) * 1000 + Math.abs(b - mevcut) * 1e-3;
      if (!en || puan < en.puan) en = { b, puan, d };
    }
    return en && Math.abs(en.d) < 1.5 * R ? en.b : null;
  }

  // Bir nesne için al-bırak adımları. Alma ve bırakma tarafı için tutucu açısı ayrı aranır: önce dik aşağı (180°),
  // erişilemiyorsa daha eğik açılar (uzaktaki nesneye öne, kola yakın olana geriye eğik). Bilek, al tarafında nesneyi enine kavrayacak
  // şekilde döner; bırakırken düz (0). o: { yukseklik (nesne, mm), yaklasma (mm), acik, kapali, aletler }
  // Dönüş: { adimlar, alet, aletBirak, bilek } ya da null (erişilemiyor).
  function alPlan(nesne, birak, S, O, P, basla, o = {}) {
    const hN = o.yukseklik ?? 25, zAl = Math.min(hN, Math.max(5, hN * 0.4)), yak = Math.max(o.yaklasma ?? hN + 30, zAl + 10);
    // 180 dik aşağı; < 180 öne eğik (uzağa uzanır), > 180 tabana doğru eğik (kola yakın noktalara iner)
    const ALETLER = o.aletler || [180, 170, 190, 160, 200, 150, 210, 140, 130, 120];
    const b0 = S.eklemAci(basla.map((v) => v / 10))[3];
    let al = null;
    for (const alet of ALETLER) {                                  // al tarafı: üstüne gel ve düz in
      const qAl = P.ikCoz(S, O, [nesne.x, nesne.y, zAl], alet);
      if (!qAl) continue;
      const bilek = bilekSec(S, qAl, nesne, b0);
      if (bilek === null) continue;
      const g = [{ tip: "git", x: nesne.x, y: nesne.y, z: yak, alet, bilek }, { tip: "git", x: nesne.x, y: nesne.y, z: zAl, alet, bilek, dogrusal: true }];
      if (!P.coz(g, S, O, basla).hatalar.length) { al = { alet, bilek }; break; }
    }
    if (!al) return null;
    for (const aletB of ALETLER) {
      const adimlar = P.alBirak({ x: nesne.x, y: nesne.y, z: zAl }, { x: birak.x, y: birak.y, z: zAl + 5 },
                               { yukseklik: yak - zAl, alet: al.alet, acik: o.acik, kapali: o.kapali });
      adimlar.forEach((a, i) => { if (a.tip === "git") { if (i <= 5) a.bilek = al.bilek; else { a.alet = aletB; a.bilek = 0; } } });
      if (!P.coz(adimlar, S, O, basla).hatalar.length) return { adimlar, alet: al.alet, aletBirak: aletB, bilek: al.bilek };
    }
    return null;
  }

  const api = { homografi, uygula, ters, hata, hsv, tonFarki, ornek, renkKurali, lekeler, masaya, kameraKonumu, kameraElle,
                yukseklikDuzelt, etkinYukseklik, nesneBul, YUKSEKLIK_KATSAYI, ucNoktalari, duzlemdenMasaya, ceneYonu, bilekSec, alPlan };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ServoKamera = api;
})(typeof window !== "undefined" ? window : this);
