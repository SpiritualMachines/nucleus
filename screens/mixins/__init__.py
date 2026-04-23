"""Mixin classes for Dashboard behaviour partitioning.

Each mixin owns a coherent slice of Dashboard logic. They are designed to be
composed into the Dashboard class via multiple inheritance. No mixin imports
from dashboard.py -- all required symbols are imported at the top of each file.
"""

from screens.mixins.members_mixin import MembersMixin
from screens.mixins.pos_mixin import POSMixin
from screens.mixins.storage_mixin import StorageMixin

__all__ = ["MembersMixin", "POSMixin", "StorageMixin"]
