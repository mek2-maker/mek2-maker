import sys
import threading
import numpy as np
import pyvista as pv
import geopandas as gpd
import time
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLineEdit, QPushButton, QLabel, QHBoxLayout
from pyvistaqt import QtInteractor  # PyQt용 PyVista 렌더링 지원

# Flask 앱 생성
app = Flask(__name__)
socketio = SocketIO(app)

# --- 좌표 변환 함수 ---
def latlon_to_xyz(lat, lon, radius=1.0):
    """위도, 경도를 3D 좌표로 변환"""
    lat_rad = np.radians(lat)
    theta = np.radians(lon)
    phi = np.pi/2 - lat_rad
    x = radius * np.sin(phi) * np.cos(theta)
    y = radius * np.sin(phi) * np.sin(theta)
    z = radius * np.cos(phi)
    return x, y, z

def get_country_boundary(countries, country_code, radius=1.0):
    """ISO_A3 코드에 해당하는 국가의 국경선을 3D 좌표로 변환"""
    try:
        rec = countries[countries["ISO_A3"] == country_code].iloc[0]
    except IndexError:
        print(f"❌ Country code {country_code} not found.")
        return None
    geom = rec.geometry
    if geom.geom_type == 'Polygon':
        poly = geom
    elif geom.geom_type == 'MultiPolygon':
        poly = list(geom.geoms)[0]
    else:
        return None
    coords = np.array(poly.exterior.coords)
    lons = coords[:, 0]
    lats = coords[:, 1]
    x, y, z = latlon_to_xyz(lats, lons, radius)
    pts = np.column_stack((x, y, z))
    if not np.allclose(pts[0], pts[-1]):
        pts = np.vstack([pts, pts[0]])
    return pts

# --- Shapefile 데이터 불러오기 ---
shapefile_path = "ne_10m_admin_0_countries.shp"
countries = gpd.read_file(shapefile_path)
if countries.crs is not None and countries.crs.to_string() != "EPSG:4326":
    countries = countries.to_crs("EPSG:4326")

# 대한민국 경계선 (기본 표시)
korea_boundary = get_country_boundary(countries, "KOR", radius=1.0)

# --- 3D 지구본 생성 ---
n_longitude = 80  # 해상도 조정
n_latitude = 40
theta_grid = np.linspace(0, 2*np.pi, n_longitude)
phi_grid = np.linspace(0, np.pi, n_latitude)
theta, phi = np.meshgrid(theta_grid, phi_grid)
x = np.sin(phi) * np.cos(theta)
y = np.sin(phi) * np.sin(theta)
z = np.cos(phi)
points = np.column_stack((x.ravel(), y.ravel(), z.ravel()))
faces = []
for i in range(n_latitude-1):
    for j in range(n_longitude-1):
        p1 = i * n_longitude + j
        p2 = p1 + 1
        p3 = p1 + n_longitude
        p4 = p3 + 1
        faces.append([3, p1, p2, p3])
        faces.append([3, p2, p4, p3])
faces = np.hstack(faces)
globe = pv.PolyData(points, faces)
uv = np.column_stack(((theta.ravel()/(2*np.pi) + 0.5) % 1, 1 - phi.ravel()/np.pi))
globe.point_data["t_coords"] = uv
globe.active_texture_coordinates = uv

# --- PyQt + PyVista UI 생성 ---
class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt + PyVista 국가 선택")
        self.setGeometry(100, 100, 1200, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        input_layout = QHBoxLayout()

        central_widget.setLayout(main_layout)

        self.label = QLabel("ISO_A3 코드 입력 (예: USA, CHN, IND):", self)
        input_layout.addWidget(self.label)

        self.input_box = QLineEdit(self)
        input_layout.addWidget(self.input_box)

        self.submit_btn = QPushButton("국가 선택", self)
        self.submit_btn.clicked.connect(self.update_country_globe)
        input_layout.addWidget(self.submit_btn)

        main_layout.addLayout(input_layout)

        self.plotter = QtInteractor(self)
        main_layout.addWidget(self.plotter.interactor)

        self.init_globe()
        self.selected_actor = None

    def init_globe(self):
        """기본 지구본"""
        self.plotter.add_mesh(globe, color="lightblue", smooth_shading=False)

        if korea_boundary is not None:
            korea_line = pv.PolyData(korea_boundary)
            self.plotter.add_mesh(korea_line, color="red", line_width=3)

            korea_center = np.mean(korea_boundary, axis=0)

            self.plotter.camera.position = (korea_center[0] * 2, korea_center[1] * 2, korea_center[2] * 2)
            self.plotter.camera.focal_point = (0, 0, 0)
            self.plotter.camera.up = (0, 0, 1)

        self.plotter.show()

    def update_country_globe(self):
        """선택한 국가로 카메라 이동"""
        country_code = self.input_box.text().strip().upper()

        if not country_code:
            return

        new_boundary = get_country_boundary(countries, country_code, radius=1.0)
        if new_boundary is None:
            print(f"❌ Country code {country_code} 경계선 데이터 없음.")
            return

        if self.selected_actor:
            self.plotter.remove_actor(self.selected_actor)

        center_x, center_y, center_z = np.mean(new_boundary, axis=0)

        self.animate_camera((center_x * 2, center_y * 2, center_z * 2))

        time.sleep(0.5)
        self.selected_actor = self.plotter.add_mesh(pv.PolyData(new_boundary), color="blue", line_width=3)
        self.plotter.render()

    def animate_camera(self, new_position, steps=60):
        """부드러운 카메라 이동"""
        old_position = self.plotter.camera.position
        dx = (new_position[0] - old_position[0]) / steps
        dy = (new_position[1] - old_position[1]) / steps
        dz = (new_position[2] - old_position[2]) / steps

        for i in range(steps):
            new_pos = (old_position[0] + dx * i, old_position[1] + dy * i, old_position[2] + dz * i)
            self.plotter.camera.position = new_pos
            self.plotter.render()
            time.sleep(0.03)

# Flask 웹 페이지
@app.route('/')
def home():
    return render_template("index.html")

# PyQt 실행
def run_qt():
    qt_app = QApplication(sys.argv)
    main_window = MainApp()
    main_window.show()
    qt_app.exec_()

# Flask + PyQt 실행
if __name__ == '__main__':
    threading.Thread(target=run_qt).start()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
