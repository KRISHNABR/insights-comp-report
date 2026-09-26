# Generated. Three lines, and none of them are yours to maintain.
# The base image carries the runtime, the SDK, the non-root user and the entrypoint -
# so a platform CVE is one base-image rebuild, not 12 pull requests.
FROM insights-hub/base:0.1
COPY src/ /app/src/
COPY app.yaml /app/app.yaml
