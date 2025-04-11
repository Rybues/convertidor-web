from flask import Flask, render_template, request
from geopy.geocoders import Nominatim
import re
import time

app = Flask(__name__)

def dms_to_decimal(dms_str):
    match = re.match(r"""(\d+)\u00b0(\d+)'([\d.]+)"?([NSEW])""", dms_str.strip(), re.IGNORECASE)
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
            dms_parts = re.findall(r'\d+\u00b0\d+\'[\d.]+\"?[NSEW]', linea.replace("″", '"').replace("’", "'").replace("‘", "'").replace(" ", ""))
            if len(dms_parts) != 2:
                raise ValueError("Coordenadas DMS mal formateadas.")
            lat = dms_to_decimal(dms_parts[0])
            lon = dms_to_decimal(dms_parts[1])
        else:
            partes = linea.split('#')[0].strip().split(',')
            lat = round(float(partes[0].strip()), 7)
            lon = round(float(partes[1].strip()), 7)
        return lat, lon, None
    except Exception as e:
        return None, None, str(e)

@app.route('/', methods=['GET', 'POST'])
def index():
    resultados = []
    if request.method == 'POST':
        coordenadas_texto = request.form['coordenadas']
        lineas = coordenadas_texto.strip().split('\n')
        geolocator = Nominatim(user_agent="geoapi_ejemplo_web")

        for linea in lineas:
            lat, lon, error = procesar_linea(linea)
            if error:
                resultados.append({
                    'lat': 'Err', 'lon': 'Err', 'direccion': f"❌ {error}",
                    'ciudad': '', 'codigo_postal': '', 'estado': '', 'pais': '', 'maps': ''
                })
                continue
            try:
                ubicacion = geolocator.reverse((lat, lon), language='en')
                if ubicacion:
                    datos = ubicacion.raw.get('address', {})
                    resultados.append({
                        'lat': lat,
                        'lon': lon,
                        'direccion': ubicacion.address,
                        'ciudad': datos.get('city') or datos.get('town') or datos.get('village') or '',
                        'codigo_postal': datos.get('postcode', ''),
                        'estado': datos.get('state') or datos.get('region') or datos.get('state_district') or '',
                        'pais': datos.get('country', ''),
                        'maps': f"https://www.google.com/maps?q={lat},{lon}"
                    })
                else:
                    resultados.append({
                        'lat': lat, 'lon': lon, 'direccion': "No encontrada",
                        'ciudad': '', 'codigo_postal': '', 'estado': '', 'pais': '', 'maps': ''
                    })
                time.sleep(1)
            except Exception as e:
                resultados.append({
                    'lat': lat, 'lon': lon, 'direccion': f"Error: {e}",
                    'ciudad': '', 'codigo_postal': '', 'estado': '', 'pais': '', 'maps': ''
                })

    return render_template('index.html', resultados=resultados)

if __name__ == '__main__':
    app.run(debug=True)
