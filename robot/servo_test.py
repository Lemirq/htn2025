import requests
import time

ESP32_IP = "10.37.114.149"  # Change this to your ESP32's IP
URL = f"http://{ESP32_IP}/servos"
HEADERS = {"Content-Type": "application/json"}

def set_all_servos(angles):
    data = {"angles": angles}
    response = requests.post(URL, json=data, headers=HEADERS)
    print(f"Set angles to {angles}: {response.status_code} {response.text}")

if __name__ == "__main__":
    # Test: center all servos
    set_all_servos([90, 90, 90, 90, 90, 90])
    time.sleep(2)
    # Test: move all to 0
    set_all_servos([0, 0, 0, 0, 0, 0])
    time.sleep(2)
    # Test: move all to 180
    set_all_servos([180, 180, 180, 180, 180, 180])
    time.sleep(2)
    # Return to center
    set_all_servos([90, 90, 90, 90, 90, 90])

