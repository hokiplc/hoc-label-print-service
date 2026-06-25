"""API key auth and LAN/CIDR restriction. Applied as FastAPI dependencies on every
route except /health."""
from __future__ import annotations

import ipaddress

from fastapi import Header, HTTPException, Request, status

from app.config import Settings, get_settings


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce_lan_and_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> str:
    settings: Settings = get_settings()
    client_ip = _client_ip(request)

    if settings.allowed_cidrs:
        try:
            addr = ipaddress.ip_address(client_ip)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid client address")
        allowed = any(
            addr in ipaddress.ip_network(cidr, strict=False) for cidr in settings.allowed_cidrs
        )
        if not allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client IP not permitted")

    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")

    return client_ip
