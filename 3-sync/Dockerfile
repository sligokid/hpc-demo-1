FROM rclone/rclone:latest

# rclone/rclone is Alpine-based; add bash for sync.sh compatibility
RUN apk add --no-cache bash

COPY sync.sh /usr/local/bin/sync.sh
RUN chmod +x /usr/local/bin/sync.sh

# rclone config is injected at runtime via bind mount — never baked in.
# Run as: docker run -v ~/.config/rclone:/root/.config/rclone:ro ...
#
# Workspace directories (sync/input, sync/output, logs) are supplied
# via bind mount at: -v /path/on/host:/workspace

ENTRYPOINT ["/usr/local/bin/sync.sh"]
