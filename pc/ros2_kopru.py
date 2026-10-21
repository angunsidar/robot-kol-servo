"""
Gerçek kol <-> ROS 2 köprüsü (DENENMEDİ: ROS 2 ortamında çalıştırılmadı).
  - /joint_states (sensor_msgs/JointState): kolun bildirdiği konum, 25 Hz. URDF eklem adlarıyla (sim/urdf_uret.py).
  - /kol/hedef (sensor_msgs/JointState): gelen eklem açılarına (rad; tutucu: parmak açıklığı m) kol birlikte gider.

    pip install pyserial
    python3 ros2_kopru.py --port /dev/ttyUSB0 --kalibrasyon kalibrasyon.json
    ros2 launch servo_kol_description goster.launch.py gercek_kol:=true
"""
import argparse
import math
import sys
from pathlib import Path

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kol_istemci import Kol, KolHatasi, sm  # noqa: E402
import urdf_uret as uu  # noqa: E402  (kol_istemci sim/ klasörünü yola ekler)


class Kopru(Node):
    def __init__(self, kol):
        super().__init__("servo_kol_kopru")
        self.kol = kol
        self.yayin = self.create_publisher(JointState, "joint_states", 10)
        self.create_subscription(JointState, "kol/hedef", self.hedef_geldi, 10)
        self.create_timer(0.04, self.yayinla)

    def yayinla(self):
        try:
            k = self.kol.durum()["konum"]
        except KolHatasi as e:
            self.get_logger().warning(str(e))
            return
        m = JointState()
        m.header.stamp = self.get_clock().now().to_msg()
        q = sm.eklem_aci(k[:5])
        m.name = uu.EKLEMLER + [uu.TUTUCU]
        m.position = [math.radians(v) for v in q] + [uu.parmak_aciklik(k[5])]
        self.yayin.publish(m)

    def hedef_geldi(self, m):
        h = list(self.kol.hedef)
        q = sm.eklem_aci([v / 10 for v in h])
        for ad, deger in zip(m.name, m.position):
            if ad in uu.EKLEMLER:
                q[uu.EKLEMLER.index(ad)] = math.degrees(deger)
            elif ad == uu.TUTUCU:                              # parmak açıklığı -> servo 6
                a = (deger - uu.PARMAK_MIN) / (uu.PARMAK_MAX - uu.PARMAK_MIN)
                h[5] = (sm.SERVO_MIN[5] + max(0.0, min(1.0, a)) * (sm.SERVO_MAX[5] - sm.SERVO_MIN[5])) * 10
        sv = sm.servo_aci(q)
        for i in range(5):
            h[i] = sv[i] * 10
        self.kol.eklemler(h, bekle=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--kalibrasyon")
    a, ros_args = ap.parse_known_args()
    kol = Kol.ac(a.port, kalibrasyon=a.kalibrasyon)
    rclpy.init(args=ros_args)
    dugum = Kopru(kol)
    try:
        rclpy.spin(dugum)
    except KeyboardInterrupt:
        pass
    finally:
        dugum.destroy_node()
        rclpy.shutdown()
        kol.kapat()


if __name__ == "__main__":
    main()
