"""Load the plugin as a package, with small stand-ins for the Hermes modules when Hermes is not installed."""

import abc
import importlib.util
import sys
import types
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]

try:
    import agent.secret_scope  # noqa: F401
    import agent.web_search_provider  # noqa: F401
except ImportError:
    secret_scope = types.ModuleType("agent.secret_scope")
    secret_scope.get_secret = lambda name, default=None: default
    web_search_provider = types.ModuleType("agent.web_search_provider")

    class WebSearchProvider(abc.ABC):
        @abc.abstractmethod
        def is_available(self): ...

    web_search_provider.WebSearchProvider = WebSearchProvider
    agent = types.ModuleType("agent")
    agent.secret_scope = secret_scope
    agent.web_search_provider = web_search_provider
    sys.modules.update(
        {"agent": agent, "agent.secret_scope": secret_scope, "agent.web_search_provider": web_search_provider}
    )

spec = importlib.util.spec_from_file_location(
    "hermes_plugin_cloro", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)]
)
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
