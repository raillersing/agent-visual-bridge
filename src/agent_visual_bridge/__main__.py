"""Allow python -m agent_visual_bridge as well as installed CLI entry points."""
from .cli import main

raise SystemExit(main())
