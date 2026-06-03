from __future__ import annotations

import app_automate.cli._accessibility  # noqa: F401
import app_automate.cli._cdp  # noqa: F401
import app_automate.cli._probe  # noqa: F401
import app_automate.cli._profiles  # noqa: F401
import app_automate.cli._run  # noqa: F401
from app_automate.cli._shared import app


def main() -> None:
    app()
