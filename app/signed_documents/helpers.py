import requests


def get_geolocation(ip_address):
    """
       Fetches geolocation data for a given IP address using the ip-api service.

       This function sends a request to the ip-api service with the provided IP address and retrieves
       geolocation information, such as country, region, city, latitude, and longitude.

       Parameters:
       - ip_address (str): The IP address for which to fetch geolocation data.

       Returns:
       - dict or None: A dictionary with geolocation data if the request is successful and the status is "success".
         Returns None if the request fails or if the data is unavailable.

       Geolocation Data Fields:
       - country (str): The country of the IP address.
       - country_code (str): ISO country code.
       - region (str): Region or state code.
       - region_name (str): Full name of the region or state.
       - city (str): City name.
       - zip (str): Postal code.
       - latitude (float): Latitude coordinate.
       - longitude (float): Longitude coordinate.
       - timezone (str): Timezone of the IP location.
       - isp (str): Internet Service Provider.
       - org (str): Organization associated with the IP.
       - as_number (str): Autonomous System number.

       Example:
       - Input: "8.8.8.8"
       - Output: {'country': 'United States', 'country_code': 'US', 'region': 'CA', ... }

       Notes:
       - The function handles `requests.RequestException` errors gracefully and prints an error message if fetching fails.
       - The ip-api service may have usage limits; consider adding error handling for rate limits in production.
       """
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
    """
       Fetches proxy or VPN information for a given IP address using the ProxyCheck service.

       This function sends a request to ProxyCheck with the provided IP address and retrieves information
       about whether the IP address is associated with a proxy or VPN, including its type and provider.

       Parameters:
       - ip_address (str): The IP address for which to fetch proxy or VPN information.

       Returns:
       - dict or None: A dictionary with proxy information if the request is successful and the status is "ok".
         Returns None if the request fails or if the data is unavailable.

       Proxy/VPN Data Fields:
       - is_proxy (bool): True if the IP address is identified as a proxy or VPN, otherwise False.
       - proxy_type (str or None): The type of proxy (e.g., "VPN", "TOR") if available.
       - proxy_provider (str or None): The provider or organization behind the proxy, if available.

       Example:
       - Input: "8.8.8.8"
       - Output: {'is_proxy': False, 'proxy_type': None, 'proxy_provider': None}

       Notes:
       - The function handles `requests.RequestException` errors gracefully and prints an error message if fetching fails.
       - The ProxyCheck service may have usage limits; consider adding error handling for rate limits in production.
       """
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
