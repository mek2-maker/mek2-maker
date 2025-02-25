import sys
import threading
import numpy as np
import geopandas as gpd
import pyvista as pv
from flask import Flask, jsonify
from pyvistaqt import QtInteractor
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from xvfbwrapper import Xvfb  # Xvfb 사용

# Flask 앱 생성
app = Flask(__name__)

# Xvfb 실행 (Render 환경에서 가상 디스플레이 제공)
vdisplay = Xvfb(width=1920, height=1080)
vdisplay.start()

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

# --- Shapefile 데이터 불러오기 ---
shapefile_path = "ne_10m_admin_0_countries.shp"
countries = gpd.read_file(shapefile_path)
if countries.crs is not None and countries.crs.to_string() != "EPSG:4326":
    countries = countries.to_crs("EPSG:4326")

# PyQt5 + PyVista UI 생성
class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt5 + PyVista 서버 실행")
        self.setGeometry(100, 100, 1200, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        self.plotter = QtInteractor(self)
        layout.addWidget(self.plotter.interactor)

        self.init_globe()

    def init_globe(self):
        """기본 지구본 생성"""
        globe = pv.Sphere(radius=1.0)
        self.plotter.add_mesh(globe, color="lightblue")
        self.plotter.show()

# PyQt5 실행
def run_qt():
    global qt_app, main_window
    qt_app = QApplication(sys.argv)
    main_window = MainApp()
    main_window.show()
    qt_app.exec_()

# Flask 웹 API
@app.route('/')
def home():
    return jsonify({"message": "PyQt5 + Flask 서버가 Render에서 실행 중입니다!"})

# PyQt5 + Flask 실행
if __name__ == '__main__':
    threading.Thread(target=run_qt, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=True)
