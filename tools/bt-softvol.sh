#!/bin/bash
for p in $(bluealsactl list-pcms 2>/dev/null); do
  bluealsactl soft-volume "$p" true 2>/dev/null
done
