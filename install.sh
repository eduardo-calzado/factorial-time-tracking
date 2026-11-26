#!/usr/bin/env bash
# Manual install: clones (or updates) the repo into ~/projects/factorial-time-tracking and runs the skill's installer.
set -euo pipefail
DIR="$HOME/projects/factorial-time-tracking"
if [[ -d $DIR/.git ]]; then
  git -C "$DIR" pull -q --ff-only
else
  git clone -q https://github.com/eduardo-calzado/factorial-time-tracking.git "$DIR"
fi
exec "$DIR/skills/factorial-time-tracking/scripts/install.sh"
