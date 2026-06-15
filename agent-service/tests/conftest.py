"""Pytest bootstrap for the agent-service test suite.

Puts the service package (`agent_service`) and the agent baselines (`travel_catalog`,
which ships the destination catalogue used by the Final graph) on the path, and provides
the service token default so importing settings never fails. The heavyweight LLM runtime
is never built here — tests inject a fake runtime / planner instead.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent-service" / "src"))
sys.path.insert(0, str(ROOT / "agent" / "baselines"))
os.environ.setdefault("AGENT_SERVICE_TOKEN", "test-token")
os.environ.setdefault("BACKEND_TOOL_TOKEN", "test-backend-token")
