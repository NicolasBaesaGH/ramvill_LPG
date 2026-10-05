"""Database settings, read from environment variables (works locally and on a host)."""
import os

DB_NAME = os.getenv("DB_NAME", "ramvill_lpg")


def conn_kwargs():
    kw = dict(host=os.getenv("DB_HOST", "localhost"), port=int(os.getenv("DB_PORT", "3306")),
              user=os.getenv("DB_USER", "root"), password=os.getenv("DB_PASSWORD", ""), charset="utf8mb4")
    ca = os.getenv("DB_SSL_CA")  # path to the host's CA certificate (e.g. ca.pem)
    if ca:
        kw["ssl_ca"] = ca
    elif os.getenv("DB_SSL") == "1":  # encrypted, certificate not verified
        kw["ssl"] = {"ca": None}
    return kw
