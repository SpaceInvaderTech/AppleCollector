"""
Fetch private keys from API
"""

from requests import get


def fetch_devices(url, headers=None):
    """Returns id and private key for devices"""
    response = get(url, headers=headers, timeout=60)
    return response.json()
