from flask import Flask, request, jsonify
import numpy as np

app = Flask(__name__)

def latlon_to_xyz(lat, lon, radius=1.0):
    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)
    phi = np.pi / 2 - lat_rad
    x = radius * np.sin(phi) * np.cos(lon_rad)
    y = radius * np.sin(phi) * np.sin(lon_rad)
    z = radius * np.cos(phi)
    return {"x": x, "y": y, "z": z}

@app.route("/")
def home():
    return "Flask 서버 실행 중 🚀"

@app.route("/convert", methods=["POST"])
def convert():
    data = request.json
    lat, lon = data["lat"], data["lon"]
    result = latlon_to_xyz(lat, lon, radius=2.0)
    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
