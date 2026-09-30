#!/bin/bash
# Debug helper: instead of printing, save the PostScript that Wine emits for the
# "Brother PT-P700" printer. Install with:  ./install.py --spool "$PWD/spool-capture.sh"
dir="${XDG_STATE_HOME:-$HOME/.local/state}/ptp700/captures"
mkdir -p "$dir"
out="$dir/job-$(date +%Y%m%d-%H%M%S)-$$.ps"
cat > "$out"
echo "$(date -Is) captured $out ($(stat -c %s "$out") bytes)" >> "$dir/capture.log"
