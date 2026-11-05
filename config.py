# HAL9042 web frontend — configuration
# -------------------------------------
# paco: do NOT commit this with real values again. (it was committed. twice.)

DB_HOST = "127.0.0.1"
DB_NAME = "hal9042"
DB_USER = "hal9042"
DB_PASS = "Moulinette2024!"

SECRET_KEY = "hal9042secret"

# Internal maintenance token. The /api/debug console accepts this token to run
# diagnostic commands. Was supposed to be rotated before launch.
ADMIN_TOKEN = "h4l_d3bug_t0k3n_2024"

# Legacy debug endpoint. "removed" in a later commit (see git log) but the route
# is still wired in app.py.
DEBUG_ENDPOINT = "/api/debug"
ENV = "development"