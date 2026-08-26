#!/bin/sh
# _fetchg.sh <out> <base-url> [curl -G args...]  -> paced logged GET with encoded params
out="$1"; base="$2"; shift 2
code=$(curl -sS -G -o "$out" -w "%{http_code}" --max-time 60 "$base" "$@")
printf '%s %s %s\n' "$(date +%FT%T%z)" "$code" "$out" >> _fetch-log.txt
sleep 2
