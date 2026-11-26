#!/usr/bin/env bash
# Idempotent: copies the CLI into ~/.local/bin and enables the Friday systemd user timer.
# Copies, not symlinks: plugin managers keep this folder in a per-version cache and delete old versions. Re-run after updating.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
UNITS="$HOME/.config/systemd/user"
mkdir -p "$HOME/.local/bin" "$UNITS"
rm -f "$HOME/.local/bin/factorial-time-tracking" "$UNITS/factorial-time-tracking.service" "$UNITS/factorial-time-tracking.timer"
install -m 755 "$HERE/factorial_time_tracking.py" "$HOME/.local/bin/factorial-time-tracking"
install -m 644 "$HERE/systemd/factorial-time-tracking.service" "$HERE/systemd/factorial-time-tracking.timer" "$UNITS/"
systemctl --user daemon-reload
systemctl --user enable --now factorial-time-tracking.timer
