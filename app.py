from flask import Flask, request, render_template, jsonify
from geopy.geocoders import Nominatim
import re
import time
import os

# Solo importa Selenium si se usa localmente
if os.getenv("LOCAL_MODE") == "1":
    import undetected_chromedriver as uc
    from selenium.webdriver.chrome.options import Options

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

# Ruta para dirección a coordenadas
@app.route('/direccion-a-coordenadas', methods=['POST'])
def direccion_a_coordenadas():
    direcciones = request.json.get('direcciones', [])
    geolocator = Nominatim(user_agent="geoapi_web")
    resultados = []

    for direccion in direcciones:
        try:
            ubicacion = geolocator.geocode(direccion, language='en')
            if ubicacion:
                resultados.append({
                    "direccion": direccion,
                    "lat": round(ubicacion.latitude, 7),
                    "lon": round(ubicacion.longitude, 7),
                    "direccion_completa": ubicacion.address,
                    "maps": f"https://www.google.com/maps?q={ubicacion.latitude},{ubicacion.longitude}"
                })
            else:
                # Backup solo si está en modo local
                if os.getenv("LOCAL_MODE") == "1":
                    opciones = Options()
                    opciones.headless = True
                    opciones.add_argument("--no-sandbox")
                    opciones.add_argument("--disable-gpu")
                    opciones.add_argument("--disable-dev-shm-usage")
                    opciones.binary_location = "/usr/bin/chromium-browser"
                    driver = uc.Chrome(options=opciones)

                    try:
                        driver.get(f"https://www.google.com/maps/place/{direccion}")
                        time.sleep(4)
                        url = driver.current_url

                        match = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url)
                        if match:
                            lat, lon = match.groups()
                            resultados.append({
                                "direccion": direccion,
                                "lat": lat,
                                "lon": lon,
                                "url": url,
                                "verificado_backup": True
                            })
                        else:
                            resultados.append({"direccion": direccion, "error": "No se encontraron coordenadas en la URL (backup)"})
                    except Exception as e:
                        resultados.append({"direccion": direccion, "error": f"Error backup: {str(e)}"})
                    finally:
                        driver.quit()
                else:
                    resultados.append({"direccion": direccion, "error": "No encontrada (sin backup habilitado)"})
            time.sleep(1)
        except Exception as e:
            resultados.append({"direccion": direccion, "error": str(e)})

    return jsonify(resultados)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
