"""Optional Application Insights request traces.

setup() does nothing at all unless APPLICATIONINSIGHTS_CONNECTION_STRING is set: no import of the
telemetry package, no exporter, no network. When it is set, the Microsoft OpenTelemetry distro sends
request traces to Azure Monitor; logging and metrics are turned off, so no application log text leaves the
container. The connection string comes from the environment (a Container Apps secret), never from code.
https://learn.microsoft.com/azure/azure-monitor/app/opentelemetry-enable?tabs=python
"""

from __future__ import annotations

import os
import sys

CONNECTION_STRING_ENV = "APPLICATIONINSIGHTS_CONNECTION_STRING"


def setup() -> bool:
    """Enable request tracing if configured. Returns whether telemetry is on. Call before the app is imported."""
    if not os.environ.get(CONNECTION_STRING_ENV):
        return False
    try:
        from microsoft.opentelemetry import use_microsoft_opentelemetry
    except ImportError:
        print(f"{CONNECTION_STRING_ENV} is set but microsoft-opentelemetry is not installed "
              "(pip install -e '.[monitor]'); telemetry stays off", file=sys.stderr)
        return False
    use_microsoft_opentelemetry(enable_azure_monitor=True, disable_logging=True, disable_metrics=True)
    return True
