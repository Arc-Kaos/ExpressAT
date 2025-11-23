import network
import urequests
import time
import machine
from machine import Pin, SPI
from mfrc522 import MFRC522
import ujson

# --- 1. CONFIGURACIÓN DEL USUARIO ---
WIFI_SSID = "PON_AQUI_TU_WIFI"       # <--- SOLO FALTA ESTO
WIFI_PASSWORD = "PON_AQUI_TU_CLAVE"  # <--- Y ESTO

# Tus credenciales de Ubidots (YA CONFIGURADAS)
UBIDOTS_TOKEN = "BBUS-v3WLO496FQSUch1AOJR5UEbGJ8QEnT" 
DEVICE_LABEL = "expressat-pico"   # Así aparecerá el dispositivo en la web
VARIABLE_LABEL = "registro"       # Así se llamará la variable

# --- 2. BASE DE DATOS LOCAL (SIMULACIÓN) ---
# Cambia estos códigos por los de TUS tarjetas reales
DB_PACIENTES = {
    "E3B2D108": {"nombre": "Juan Perez", "area": "Triaje", "estado": "ESPERA"},
    "A2F5C311": {"nombre": "Maria Gomez", "area": "Lab", "estado": "ATENCION"},
    "11223344": {"nombre": "Carlos Ruiz", "area": "Cama 402", "estado": "HOSPITALIZADO"}
}

# --- 3. CONFIGURACIÓN HARDWARE ---
led_verde = Pin(14, Pin.OUT)
led_rojo = Pin(15, Pin.OUT)
led_verde.value(0)
led_rojo.value(0)

# Configuración RFID (SPI)
spi = SPI(0, baudrate=100000, polarity=0, phase=0, sck=Pin(2), mosi=Pin(3), miso=Pin(4))
reader = MFRC522(spi, 0, 1)

# --- 4. FUNCIONES (Estilo de tu profesor + ExpressAT) ---

def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        print('Conectando a Wi-Fi', end='')
        wlan.connect(ssid, password)
        
        timeout = 15
        while timeout > 0:
            if wlan.status() < 0 or wlan.status() >= 3:
                break
            timeout -= 1
            print('.', end='')
            time.sleep(1)
            
    if wlan.isconnected():
        print(f'\n✅ Conexión exitosa! IP: {wlan.ifconfig()[0]}')
        return wlan
    else:
        print('\n❌ Fallo al conectar Wi-Fi.')
        return None

def send_data_ubidots(device, variable, paciente, token):
    try:
        # Enviamos valor 1 y los datos de texto en el contexto
        payload = {
            variable: {
                "value": 1,
                "context": {
                    "nombre": paciente['nombre'],
                    "area": paciente['area'],
                    "estado": paciente['estado']
                }
            }
        }
        
        url = f"https://industrial.api.ubidots.com/api/v1.6/devices/{device}"
        headers = {"X-Auth-Token": token, "Content-Type": "application/json"}
        
        print(f"   ☁️ Enviando a Ubidots...")
        response = urequests.post(url, json=payload, headers=headers)
        
        if response.status_code == 201:
            print(f"   ✅ Datos subidos correctamente.")
        else:
            print(f"   ⚠️ Error de Ubidots: {response.status_code}")
            
        response.close()
        
    except Exception as e:
        print(f"   ❌ Error de red: {e}")

# --- 5. PROGRAMA PRINCIPAL ---

print("\n=== INICIANDO ExpressAT ===")

# 1. Conectar WiFi
if connect_wifi(WIFI_SSID, WIFI_PASSWORD) is None:
    print("⚠️ Trabajando SIN internet (Modo Local).")
    # Si quieres que se detenga si no hay wifi, pon un while True: pass aquí

print("Esperando tarjetas NFC...")
last_card_time = 0
CARD_DELAY = 5000 # 5 segundos de espera entre lecturas

while True:
    try:
        # Escanear Tarjetas
        (stat, tag_type) = reader.request(reader.REQIDL)
        if stat == reader.OK:
            (stat, uid) = reader.anticoll()
            if stat == reader.OK:
                current_time = time.ticks_ms()
                
                # Evitar lecturas múltiples muy rápidas
                if time.ticks_diff(current_time, last_card_time) > CARD_DELAY:
                    
                    # Convertir UID a Hexadecimal
                    uid_str = "{:02X}{:02X}{:02X}{:02X}".format(uid[0], uid[1], uid[2], uid[3])
                    print(f"\n💳 Tarjeta detectada: {uid_str}")
                    
                    # Buscar en Base de Datos
                    if uid_str in DB_PACIENTES:
                        # -- PACIENTE ENCONTRADO --
                        led_verde.value(1)
                        paciente = DB_PACIENTES[uid_str]
                        print(f"   Paciente: {paciente['nombre']}")
                        print(f"   Area: {paciente['area']}")
                        
                        # Enviar a la nube
                        send_data_ubidots(DEVICE_LABEL, VARIABLE_LABEL, paciente, UBIDOTS_TOKEN)
                        
                        time.sleep(1)
                        led_verde.value(0)
                    else:
                        # -- NO REGISTRADO --
                        print("   ❌ No registrado")
                        for _ in range(3):
                            led_rojo.value(1); time.sleep(0.2)
                            led_rojo.value(0); time.sleep(0.2)
                    
                    last_card_time = current_time
        
        time.sleep_ms(50)

    except KeyboardInterrupt:
        print("Programa detenido.")
        break
    except Exception as e:
        print(f"Error: {e}")
        machine.reset()