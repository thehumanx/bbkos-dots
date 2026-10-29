#!/bin/sh
# Stand-in for a command the test shell must not run for real (tests/shell/harness.py): it records the call in
# $HOME/calls.log (the test home) as the command name and its arguments, and succeeds.
printf '%s' "$(basename "$0")" >> "$HOME/calls.log"
for a in "$@"; do printf ' %s' "$a" >> "$HOME/calls.log"; done
printf '\n' >> "$HOME/calls.log"
exit 0
