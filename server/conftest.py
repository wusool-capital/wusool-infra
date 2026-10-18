"""Makes pytest add this directory to `sys.path`, so
`tests/integration/test_merged_command_dispatch.py`'s `import main` resolves.

Also disables the Secrets Manager source before any `Settings` is built, so
tests and CI never call AWS.
"""

import os

# Forced, not defaulted: an exported real secret id must not make tests call AWS.
os.environ["AWS_SECRETS_MANAGER_SECRET_ID"] = ""
