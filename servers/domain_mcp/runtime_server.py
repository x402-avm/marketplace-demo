import asyncio
from collections import OrderedDict
import ssl
import socket
import time
import whois
import dns.resolver
from fastapi import FastAPI, HTTPException
import uvicorn

app = FastAPI()

# Cache configuration: (kind, domain.lower()) -> (result, expires_at)
CACHE_TTL = 600.0
CACHE_MAX_ENTRIES = 512
cache: OrderedDict[tuple[str, str], tuple[dict, float]] = OrderedDict()

# Lock to serialize WHOIS queries
whois_lock = asyncio.Lock()


def get_cached(kind: str, domain: str) -> dict | None:
    key = (kind, domain.strip().lower())
    now = time.time()
    if key in cache:
        res, exp = cache[key]
        if now < exp:
            cache.move_to_end(key)
            return res
        else:
            cache.pop(key, None)
    return None


def set_cached(kind: str, domain: str, res: dict) -> None:
    key = (kind, domain.strip().lower())
    now = time.time()
    if len(cache) >= CACHE_MAX_ENTRIES and key not in cache:
        cache.popitem(last=False)
    cache[key] = (res, now + CACHE_TTL)


def is_no_such_domain(exc: Exception) -> bool:
    """Identify domain-not-found / invalid domain errors vs transient network issues."""
    if isinstance(exc, whois.exceptions.WhoisDomainNotFoundError):
        return True
    if isinstance(exc, dns.resolver.NXDOMAIN):
        return True
    if isinstance(exc, socket.gaierror):
        err_msg = str(exc).lower()
        if "not known" in err_msg or "nodename" in err_msg or getattr(exc, "errno", None) in (socket.EAI_NONAME, -2):
            return True
    msg = str(exc).lower()
    if "not known" in msg or "no such" in msg or "does not exist" in msg:
        return True
    return False


async def _execute_with_retry(func, *args, is_async: bool = False) -> dict:
    backoffs = [1.0, 2.0]
    last_exc = None
    for attempt in range(3):
        try:
            if is_async:
                return await func(*args)
            else:
                return await asyncio.to_thread(func, *args)
        except HTTPException:
            raise
        except Exception as e:
            last_exc = e
            if is_no_such_domain(e):
                raise HTTPException(status_code=500, detail=str(e))
            if attempt < len(backoffs):
                await asyncio.sleep(backoffs[attempt])
    raise HTTPException(
        status_code=503,
        detail=f"lookup temporarily unavailable: {last_exc}"
    )


def _do_whois(domain: str) -> dict:
    w = whois.whois(domain)
    return {"result": str(w)}


def _do_dns(domain: str) -> dict:
    records = {}
    had_network_error = None
    for record_type in ['A', 'AAAA', 'MX', 'NS', 'TXT']:
        try:
            answers = dns.resolver.resolve(domain, record_type)
            records[record_type] = [str(rdata) for rdata in answers]
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            pass
        except Exception as e:
            if not is_no_such_domain(e):
                had_network_error = e
    if not records and had_network_error is not None:
        raise had_network_error
    return {"result": records}


def _extract_rdn(rdns) -> dict:
    res = {"CN": None, "O": None}
    for rdn in rdns or ():
        for item in rdn:
            if len(item) == 2:
                k, v = item
                if k == "commonName":
                    res["CN"] = v
                elif k == "organizationName":
                    res["O"] = v
    return res


def _do_ssl(domain: str) -> dict:
    from datetime import datetime, timezone
    context = ssl.create_default_context()
    with socket.create_connection((domain, 443), timeout=10) as sock:
        with context.wrap_socket(sock, server_hostname=domain) as ssock:
            cert = ssock.getpeercert()
            tls_version = ssock.version()
            ts_before = ssl.cert_time_to_seconds(cert['notBefore'])
            not_before_dt = datetime.fromtimestamp(ts_before, tz=timezone.utc)
            not_before_iso = not_before_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

            ts_after = ssl.cert_time_to_seconds(cert['notAfter'])
            not_after_dt = datetime.fromtimestamp(ts_after, tz=timezone.utc)
            not_after_iso = not_after_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

            now_utc = datetime.now(timezone.utc)
            days_left = int((not_after_dt - now_utc).total_seconds() / 86400)
            serial_number = str(cert.get('serialNumber', ''))
            san = [val for typ, val in cert.get('subjectAltName', ()) if typ == 'DNS']

            return {
                "result": {
                    "subject": _extract_rdn(cert.get('subject')),
                    "issuer": _extract_rdn(cert.get('issuer')),
                    "notBefore": not_before_iso,
                    "notAfter": not_after_iso,
                    "not_before": not_before_iso,
                    "not_after": not_after_iso,
                    "raw_notAfter": cert.get('notAfter'),
                    "notAfter_raw": cert.get('notAfter'),
                    "days_left": days_left,
                    "serial_number": serial_number,
                    "serialNumber": serial_number,
                    "subjectAltName": san,
                    "san": san,
                    "tls_version": tls_version,
                    "tlsVersion": tls_version,
                }
            }


def _do_ip(domain: str) -> dict:
    ip = socket.gethostbyname(domain)
    return {"result": ip}


@app.get("/whois/{domain}")
async def get_whois(domain: str):
    cached = get_cached("whois", domain)
    if cached is not None:
        return cached

    async with whois_lock:
        cached = get_cached("whois", domain)
        if cached is not None:
            return cached

        res = await _execute_with_retry(_do_whois, domain)
        set_cached("whois", domain, res)
        return res


@app.get("/dns/{domain}")
async def get_dns(domain: str):
    cached = get_cached("dns", domain)
    if cached is not None:
        return cached

    res = await _execute_with_retry(_do_dns, domain)
    set_cached("dns", domain, res)
    return res


@app.get("/ssl/{domain}")
async def get_ssl(domain: str):
    cached = get_cached("ssl", domain)
    if cached is not None:
        return cached

    res = await _execute_with_retry(_do_ssl, domain)
    set_cached("ssl", domain, res)
    return res


@app.get("/ip/{domain}")
async def get_ip(domain: str):
    cached = get_cached("ip", domain)
    if cached is not None:
        return cached

    res = await _execute_with_retry(_do_ip, domain)
    set_cached("ip", domain, res)
    return res


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8070)
