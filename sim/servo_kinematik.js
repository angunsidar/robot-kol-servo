// servo_model.py'nin JS karşılığı (test_servo_model.py birebir karşılaştırır). Açılar derece, uzunluklar metre.
(function (root) {
  "use strict";
  const R = Math.PI / 180;
  const G = 9.81;
  const MG996R_KG = 0.055, SG90_KG = 0.009;
  const PARCA = { ust_kol: 0.045, on_kol: 0.040, bilek: 0.025, tutucu: 0.035 };
  // Montaj kalibrasyonu: servo = 90 + yön · eklem + ofset. Varsayılanlar servo_model.py ile aynı; sayfa
  // kalibrasyon sekmesinden kalibrasyon() ile değiştirir (eklem 0° = referans pozu, bkz. README).
  const SERVO_YON = [1, 1, 1, 1, 1, 1], SERVO_OFSET = [0, 0, 0, 0, 0, 0];
  const SERVO_MIN = [0, 15, 10, 0, 0, 20], SERVO_MAX = [180, 165, 170, 180, 180, 110];
  const KAPASITE = { J2: 9.4 * 0.0980665, J3: 9.4 * 0.0980665, J5: 1.2 * 0.0980665 };

  const olcu = () => ({ H0: 0.09, L2: 0.12, L3: 0.10, L4: 0.08 });

  function servoAci(q) { const out = []; for (let i = 0; i < 5; i++) out.push(90 + SERVO_YON[i] * q[i] + SERVO_OFSET[i]); return out; }
  function eklemAci(s) { const out = []; for (let i = 0; i < 5; i++) out.push((s[i] - 90 - SERVO_OFSET[i]) * SERVO_YON[i]); return out; }
  // k verilirse uygular ({ yon: [±1 x5], ofset: [° x5] }), her durumda geçerli değerleri döndürür
  function kalibrasyon(k) {
    if (k) for (let i = 0; i < 5; i++) {
      if (k.yon) SERVO_YON[i] = +k.yon[i] < 0 ? -1 : 1;
      if (k.ofset) SERVO_OFSET[i] = Number.isFinite(+k.ofset[i]) ? +k.ofset[i] : 0;
    }
    return { yon: SERVO_YON.slice(0, 5), ofset: SERVO_OFSET.slice(0, 5) };
  }
  function eklemLimit() {
    const lim = [];
    for (let i = 0; i < 5; i++) {
      const a = (SERVO_MIN[i] - 90 - SERVO_OFSET[i]) * SERVO_YON[i], b = (SERVO_MAX[i] - 90 - SERVO_OFSET[i]) * SERVO_YON[i];
      lim.push([Math.min(a, b), Math.max(a, b)]);
    }
    return lim;
  }
  function limitIcinde(q) { const L = eklemLimit(); return L.every(([lo, hi], i) => q[i] >= lo - 1e-9 && q[i] <= hi + 1e-9); }

  function fk(q, o) {
    const q1 = q[0] * R, q2 = q[1] * R, q3 = q[2] * R, q5 = q[4] * R;
    const a2 = q2, a3 = q2 + q3, a5 = q2 + q3 + q5;
    const e = [o.L2 * Math.sin(a2), o.H0 + o.L2 * Math.cos(a2)];
    const w = [e[0] + o.L3 * Math.sin(a3), e[1] + o.L3 * Math.cos(a3)];
    const t = [w[0] + o.L4 * Math.sin(a5), w[1] + o.L4 * Math.cos(a5)];
    const rz = [[0, 0], [0, o.H0], e, w, t];
    const c = Math.cos(q1), s = Math.sin(q1);
    return { noktalar: rz.map(([r, z]) => [r * c, r * s, z]), alet: a5 / R };
  }

  function ik(xyz, aletDikeydenDeg, o, dirsekYukari) {
    const [x, y, z] = xyz;
    const q1 = Math.atan2(y, x), r = Math.hypot(x, y), a5 = aletDikeydenDeg * R;
    const wr = r - o.L4 * Math.sin(a5), wz = z - o.L4 * Math.cos(a5);
    const dr = wr, dz = wz - o.H0, d2 = dr * dr + dz * dz;
    const c3 = (d2 - o.L2 * o.L2 - o.L3 * o.L3) / (2 * o.L2 * o.L3);
    if (Math.abs(c3) > 1) return null;
    const q3 = Math.acos(c3) * (dirsekYukari ? 1 : -1);
    const gamma = Math.atan2(dr, dz);
    const q2 = gamma - Math.atan2(o.L3 * Math.sin(q3), o.L2 + o.L3 * Math.cos(q3));
    const q5 = a5 - q2 - q3;
    const q = [q1, q2, q3, 0, q5].map((v) => v / R);
    q[4] = ((((q[4] + 180) % 360) + 360) % 360) - 180;
    return q;
  }

  function tork(q, yuk, o) {
    const P = fk(q, o).noktalar, s = P[1], e = P[2], w = P[3], t = P[4];
    const rh = (p, ref) => Math.hypot(p[0], p[1]) - Math.hypot(ref[0], ref[1]);
    const mid = (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2];
    const K = [[PARCA.ust_kol, mid(s, e), 2], [MG996R_KG, e, 2], [PARCA.on_kol, mid(e, w), 3],
               [2 * SG90_KG + PARCA.bilek, w, 3], [SG90_KG + PARCA.tutucu, mid(w, t), 5], [yuk, t, 5]];
    let t2 = 0, t3 = 0, t5 = 0;
    for (const [m, p, j] of K) {
      t2 += m * G * rh(p, s);
      if (j >= 3) t3 += m * G * rh(p, e);
      if (j >= 5) t5 += m * G * rh(p, w);
    }
    return [Math.abs(t2), Math.abs(t3), Math.abs(t5)];
  }

  const api = { olcu, fk, ik, tork, servoAci, eklemAci, kalibrasyon, eklemLimit, limitIcinde, KAPASITE, SERVO_MIN, SERVO_MAX };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.ServoKol = api;
})(typeof window !== "undefined" ? window : globalThis);
