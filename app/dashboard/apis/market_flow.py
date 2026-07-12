"""Deprecated market-wide capital-flow payload."""


def fetch_market_flow() -> dict[str, None]:
    """Return unavailable values so the dashboard hides this retired widget."""
    return {"total_inflow_yi": None, "total_outflow_yi": None, "net_flow_yi": None}
