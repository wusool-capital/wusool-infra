"""Vendor-specific shared code that can't stay in `domain/` (needs a
third-party SDK import) but is still genuinely identical across the modules
that use it — currently just `bedrock/`. Not part of this module's root
`__all__`; reached directly, same convention as `api/handlers.py` (see
`utilities/__init__.py`'s own docstring for why).
"""
