#!/bin/bash
if ! ping -c 2 -W 3 192.168.1.1 > /dev/null 2>&1; then
    logger -t wifi-watchdog "Passerelle injoignable, relance du Wi-Fi"
    nmcli radio wifi off
    sleep 3
    nmcli radio wifi on
fi
