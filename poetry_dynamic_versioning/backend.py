# flake8: noqa
from poetry.core.masonry.api import *
import poetry_dynamic_versioning.patch as patch

patch.activate()
