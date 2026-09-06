"""
Nexxus Graph Analytics & Risk Scoring Engine (Arnish's Package)
--------------------------------------------------------------
Provides centrality metrics, community detection, financial anomaly detection,
call burst analysis, and multi-factor criminal risk scoring.
"""

import sys
from pathlib import Path

# Alias the internal 'graph' namespace used by Arnish's submodules
# to 'backend.app.analytics' so all internal imports resolve seamlessly.
if "graph" not in sys.modules:
    import backend.app.analytics as _analytics
    sys.modules["graph"] = _analytics
    _analytics.__path__ = [str(Path(__file__).resolve().parent)]
