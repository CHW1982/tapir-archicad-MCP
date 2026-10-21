import logging

from jjp_bim_audit_mcp.app import mcp
from jjp_bim_audit_mcp.logging_config import setup_logging

setup_logging()


def main():
    logging.info("Starting JJP PPT BIM MCP Server...")
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()
