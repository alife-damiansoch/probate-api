import requests


def get_geolocation(ip_address):
    """Fetch geolocation data for a given IP address using ip-api."""
    try:
        response = requests.get(f"http://ip-api.com/json/{ip_address}")
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return {
                    "country": data.get("country"),
                    "country_code": data.get("countryCode"),  # Fixed naming
                    "region": data.get("region"),
                    "region_name": data.get("regionName"),
                    "city": data.get("city"),
                    "zip": data.get("zip"),  # Corrected from "zip" to "eircode"
                    "latitude": data.get("lat"),
                    "longitude": data.get("lon"),
                    "timezone": data.get("timezone"),
                    "isp": data.get("isp"),
                    "org": data.get("org"),
                    "as_number": data.get("as")  # Fixed field reference
                }
    except requests.RequestException as e:
        print(f"Error fetching geolocation: {e}")
    return None


def get_proxy_info(ip_address):
    """Fetch proxy/VPN info for a given IP address using ProxyCheck."""
    try:
        response = requests.get(f"https://proxycheck.io/v2/{ip_address}?key=free&vpn=1")
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok" and data.get(ip_address):
                return {
                    "is_proxy": data[ip_address].get("proxy") == "yes",
                    "proxy_type": data[ip_address].get("type"),
                    "proxy_provider": data[ip_address].get("provider")
                }
    except requests.RequestException as e:
        print(f"Error fetching proxy info: {e}")
    return None
