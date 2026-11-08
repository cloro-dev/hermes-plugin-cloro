"""cloro web search backend for Hermes Agent."""


def register(ctx):
    from .provider import CloroWebSearchProvider

    ctx.register_web_search_provider(CloroWebSearchProvider(ctx))
