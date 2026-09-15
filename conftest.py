# Root conftest re-exports fixtures from fixtures/conftest.py so pytest
# picks them up regardless of which test subfolder is being run.
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from fixtures.conftest import *  # noqa: F401,F403
