"""Travel-planning Agent Service.

Implements Contract A (`agent-service/openapi.yaml`) — the backend drives runs and receives SSE
events; the agent proposes a draft plan. Business data is pulled from the backend's Contract B
(`internal-tools-openapi.yaml`, Variant B). The reasoning core is the Final agent from
`agent/baselines/final_agent.py`.
"""

__version__ = "0.1.0"
