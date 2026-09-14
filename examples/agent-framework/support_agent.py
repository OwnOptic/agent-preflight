"""A small Agent Framework agent, here so the collector has something real to read.

Nothing imports this at scan time. Preflight parses it; it never runs it.
"""
from agent_framework import ChatAgent, ai_function


@ai_function
def lookup_order(order_id: str) -> dict:
    """Look up an order by id. Read-only."""
    return {"id": order_id, "status": "shipped"}


@ai_function
def refund_order(order_id: str, amount: float) -> dict:
    """Refund an order. Money leaves the account and does not come back."""
    return {"id": order_id, "refunded": amount}


agent = ChatAgent(
    name="Support agent",
    instructions="Answer customer questions about orders. Refund when the customer asks.",
    model="gpt-5-mini",
    tools=[lookup_order, refund_order],
)
