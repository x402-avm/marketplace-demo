# Master MCP Documentation

This documentation has been consolidated into [README.md](README.md). Please refer to `README.md` for complete, up-to-date documentation on:
- Ecosystem architecture and canonical port topology across all 16 domains
- Server lifecycle management (`tools/domainctl.sh`, `./start_all.sh`, `./stop_all.sh`)
- Unified test suite (`./test_all.sh`) and test matrix probe assertions (`tools/probe.py`)
- Algorand micropayments integration (`x402`), dynamic fee floors, and SQLite replay protection
- Charge-only-on-success settlement and proxy `ToolError` handling
- Safety allow-lists (`common/paths.py` filesystem allow-list, `common/netguard.py` SSRF guard)
- Artifacts and outputs cleanup (`tools/clean_outputs.sh`)
