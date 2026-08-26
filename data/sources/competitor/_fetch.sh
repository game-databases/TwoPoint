#!/bin/sh
# polite paced fetch: one GET -> out file, log line, >=2s gap
url="$1"; out="$2"
code=$(curl -sS -o "$out" -w "%{http_code}" --max-time 40 "$url")
printf '%s %s %s %s\n' "$(date +%FT%T%z)" "$code" "$out" "$url" >> _fetch-log.txt
sleep 2
