"""Exit 0 if this interpreter is new enough for the dashboard, else 1.

Invoked directly (not via `python -c "..."`) by start-dashboard.bat: cmd.exe
treats `>`/`<` as redirection operators even inside double-quoted strings, so
a `sys.version_info >= (3, 11)` comparison passed as a `-c` one-liner was
silently corrupted there - a real bug found only by actually running the
launcher on Windows CI with an old Python already on PATH, not by reading
the code. A real file sidesteps cmd.exe's quoting rules entirely.
"""

import sys

sys.exit(0 if sys.version_info >= (3, 11) else 1)
