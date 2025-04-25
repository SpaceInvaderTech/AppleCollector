class AppleAuthCredentialsExpired(Exception):
    """Exception raised when Apple authentication credentials are expired."""
    pass


class NoMoreLocationsToFetch(Exception):
    """Exception raised when there are no more locations to fetch."""
    pass