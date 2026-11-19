# Domain Intelligence MCP Subsystem

## Overview
The Domain Intelligence MCP provides AI agents with network intelligence tools to investigate domains. It retrieves WHOIS records, DNS matrices (A, AAAA, NS, MX, TXT), SSL Expiration dates, and direct IP addresses.

## Architecture
- **Runtime Server (Port 8073)**: Centralized FastAPI backend executing `python-whois`, `dnspython`, and `socket`/`ssl` commands.
- **MCP Server 1 (Port 8074)**: Proxy node exposing all 4 intelligence tools.
- **MCP Server 2 (Port 8075)**: Proxy node exposing all 4 intelligence tools.

## Tools Exposed
- `domain_whois(domain: str)`: Returns the WHOIS JSON structure (registrar, org, expiry dates).
- `domain_dns(domain: str)`: Returns the DNS records (A, AAAA, MX, NS, TXT).
- `domain_ssl(domain: str)`: Returns the exact SSL certificate expiration timestamp.
- `domain_ip(domain: str)`: Returns the resolved IPv4 address.

## Execution
```bash
source venv/bin/activate
python runtime_server.py &
python mcp_server_1.py &
python mcp_server_2.py &
```
