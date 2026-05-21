def register_all_tools():
    """
    This function's purpose is to explicitly import all tool modules.
    The act of importing them runs the @mcp.tool decorators within, which
    registers the tools with the central 'mcp' instance from app.py.
    """
    import logging
    log = logging.getLogger(__name__)

    # Custom tools
    try:
        from tapir_archicad_mcp.tools.custom import functions
        log.info("Registered custom general tools successfully.")
    except Exception as e:
        log.error(f"Failed to register custom functions: {e}")

    try:
        from tapir_archicad_mcp.tools.custom import jjp_extension
        log.info("Registered JJP extension tools and resources successfully.")
    except Exception as e:
        log.error(f"Failed to register JJP extension tools: {e}")

    # Generated official tools
    try:
        from tapir_archicad_mcp.tools.generated import official
        log.info("Registered official generated tools successfully.")
    except Exception as e:
        log.error(f"Failed to register official generated tools: {e}")

    # Generated tapir tools (experimental, wrapped to prevent mismatches crashing the server)
    try:
        from tapir_archicad_mcp.tools.generated import tapir
        log.info("Registered experimental Tapir tools successfully.")
    except ImportError as e:
        log.warning(f"Skipping experimental Tapir tools due to package version mismatch: {e}")
    except Exception as e:
        log.error(f"Failed to register Tapir tools: {e}")
