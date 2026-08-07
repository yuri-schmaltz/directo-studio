"""Directo Studio engine bridge package.

Currently hosts the OpenMontage bridge (`openmontage_bridge.py`),
which exposes 5 cinematic production pipelines to the FastAPI
backend. New engine adapters (ComfyUI workflow bridges, etc.) can
land alongside `openmontage_bridge.py` and be re-exported here.

Without this file the package works as a PEP 420 namespace
package, but explicit `__init__.py` makes:

1. The engine surface discoverable to type checkers (mypy) and
   documentation tools.
2. Imports that use `from directo.engine import openmontage_bridge`
   work without depending on namespace-package resolution rules,
   which can break under namespace package collisions or
   conditional imports inside `openmontage_bridge.py`.
3. `directo.engine` resolvable as a real attribute, not just as a
   path prefix.

Public API:

- :data:`OPENMONTAGE_PIPELINES` — the 5-pipeline catalogue.
- :class:`OpenMontageBridge` — the bridge instance.
- :data:`openmontage_bridge` — the shared singleton used by
  ``directo.platform.api`` and the UI.

The legacy direct import path
``from directo.engine.openmontage_bridge import openmontage_bridge``
keeps working unchanged; this package is additive.
"""

from directo.engine.openmontage_bridge import (
    OPENMONTAGE_PIPELINES,
    OpenMontageBridge,
    openmontage_bridge,
)

__all__ = [
    "OPENMONTAGE_PIPELINES",
    "OpenMontageBridge",
    "openmontage_bridge",
]
