"""
Domain-focused service package for Nucleus.

Re-exports every public function from each sub-module so that both
``from core import services; services.get_setting(...)`` and
``from core.services import get_setting`` continue to work unchanged.
"""

from core.services.settings import *  # noqa: F401,F403
from core.services.preferences import *  # noqa: F401,F403
from core.services.users import *  # noqa: F401,F403
from core.services.auth import *  # noqa: F401,F403
from core.services.attendance import *  # noqa: F401,F403
from core.services.membership import *  # noqa: F401,F403
from core.services.transactions import *  # noqa: F401,F403
from core.services.feedback import *  # noqa: F401,F403
from core.services.community import *  # noqa: F401,F403
from core.services.products import *  # noqa: F401,F403
from core.services.admin import *  # noqa: F401,F403
from core.services.reporting import *  # noqa: F401,F403
from core.services.storage import *  # noqa: F401,F403
from core.services.inventory import *  # noqa: F401,F403
from core.services.day_pass import *  # noqa: F401,F403
