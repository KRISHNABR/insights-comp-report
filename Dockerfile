# YOUR Dockerfile. Generated once by `insights new-app`; yours to edit from here.
#   app:  comp-report
#   base: python-data
#
# The platform does not rewrite this file and `insights upgrade-scaffold` does not
# touch it - unlike .github/workflows/, which we do own. You can add build stages,
# system packages, whatever your app needs.
#
# FOUR THINGS CI CHECKS, and why (ADR-004):
#
#   1. FROM is a published insights-hub base    we patch these; a base from Docker Hub
#                                               is one nobody is patching for you
#   2. no :latest                               an image you cannot name is one you
#                                               cannot roll back to
#   3. the final USER is not root               a container breakout should land on a
#                                               user that owns nothing
#   4. the base version is current              `insights doctor` warns, CI fails on
#                                               prod deploys. THIS IS THE ONE THAT
#                                               MATTERS: because this file is yours,
#                                               a CVE fix in the base reaches you only
#                                               when you bump the line below. We tell
#                                               you loudly; we cannot do it for you.
FROM insights-hub/python-data:0.1

# Your dependencies, from YOUR pyproject.toml, installed from the COMMITTED lockfile.
# --frozen means the lock must already be current: the image resolves exactly what your
# laptop resolved, or the build fails. "Works on my machine" is not debuggable by a
# platform team of three.
#
# Copied before your source so a code change does not reinstall the world.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ /app/src/
COPY app.yaml /app/app.yaml
