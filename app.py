from flask import Flask, request, render_template, jsonify
from geopy.geocoders import Nominatim
import re
import time
import undetected_chromedriver.v2 as uc  # ✅ correcto
from selenium.webdriver.chrome.options import Options

# Configurar opciones de Chrome
options = Options()
options.binary_location = "/usr/bin/chromium-browser"  # Ruta del binario de Chromium en Render

app = Flask(__name__)

# Utilidades compartidas
def dms_to_decimal(dms_str):
    match = re.match(r"(\d+)\u00b0(\d+)'([\d.]+)\"?([NSEW])", dms_str.strip(), re.IGNORECASE)
    if not match:
        raise ValueError("Formato DMS no válido")
    degrees, minutes, seconds, direction = match.groups()
    decimal = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
    if direction.upper() in ['S', 'W']:
        decimal *= -1
    return round(decimal, 7)

def procesar_linea(linea):
    try:
        if "°" in linea:
            dms_parts = re.findall(r'\d+°\d+\'[\d.]+\"?[NSEW]', linea.replace("″", '"').replace("’", "'").replace("‘", "'").replace(" ", ""))
            if len(dms_parts) != 2:
                raise ValueError("Coordenadas DMS mal formateadas.")
            lat = dms_to_decimal(dms_parts[0])
            lon = dms_to_decimal(dms_parts[1])
        else:
            partes = linea.split('#')[0].strip().split(',')
            lat = round(float(partes[0].strip()), 7)
            lon = round(float(partes[1].strip()), 7)
        return lat, lon
    except Exception as e:
        return None, None, f"Error: {e}"

# Ruta principal (formulario web)
@app.route('/')
def index():
    return render_template('index.html')

# Ruta para coordenadas a dirección
@app.route('/coordenadas-a-direccion', methods=['POST'])
def coordenadas_a_direccion():
    data = request.json
    lineas = data.get('coordenadas', [])
    geolocator = Nominatim(user_agent="geoapi_web")
    resultados = []

    for linea in lineas:
        lat, lon, *error = procesar_linea(linea)
        if error:
            resultados.append({"entrada": linea, "error": error[0]})
            continue
        try:
            ubicacion = geolocator.reverse((lat, lon), language='en')
            if ubicacion:
                datos = ubicacion.raw.get('address', {})
                resultados.append({
                    "entrada": linea,
                    "lat": lat,
                    "lon": lon,
                    "direccion": ubicacion.address,
                    "ciudad": datos.get('city') or datos.get('town') or datos.get('village', ''),
                    "codigo_postal": datos.get('postcode', ''),
                    "estado": datos.get('state') or datos.get('region') or datos.get('state_district', ''),
                    "pais": datos.get('country', ''),
                    "maps": f"https://www.google.com/maps?q={lat},{lon}"
                })
            else:
                resultados.append({"entrada": linea, "error": "No encontrada"})
            time.sleep(1)
        except Exception as e:
            resultados.append({"entrada": linea, "error": str(e)})
    return jsonify(resultados)

# Ruta para dirección a coordenadas (usando webdriver-manager)
@app.route('/direccion-a-coordenadas', methods=['POST'])
def direccion_a_coordenadas():
    direcciones = request.json.get('direcciones', [])
    resultados = []

    # Configuración de opciones de Chrome
    options = Options()
    options.headless = True
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.binary_location = "/usr/bin/chromium-browser"  # Ruta del binario de Chromium en Render

    # Crear el driver con las opciones configuradas
    driver = uc.Chrome(options=options)

    for direccion in direcciones:
        try:
            driver.get(f"https://www.google.com/maps/place/{direccion}")
            time.sleep(4)
            url = driver.current_url
            coordenadas = re.findall(r"3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", url)
            if coordenadas:
                lat, lon = coordenadas[0]
                resultados.append({"direccion": direccion, "lat": lat, "lon": lon, "url": url})
            else:
                resultados.append({"direccion": direccion, "error": "No encontrada"})
        except Exception as e:
            resultados.append({"direccion": direccion, "error": str(e)})

    driver.quit()
    return jsonify(resultados)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
