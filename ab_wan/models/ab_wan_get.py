import requests


def wan_get_ip():
    try:
        response = requests.get("https://checkip.amazonaws.com")
        return response.text.strip()
    except requests.RequestException as e:
        return f"Error retrieving WAN IP: {e}"
