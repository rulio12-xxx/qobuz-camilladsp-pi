#!/bin/bash
# Reveille la chaine (DAC + CamillaDSP) en jouant le son de test, attend qu elle soit prete.
s() { curl -s http://127.0.0.1:8080/status; }
if s | grep -q "\"camilladsp\": \"active\"" && s | grep -q "\"dac\": true"; then echo "deja reveillee"; exit 0; fi
mpc -q clear; mpc -q add kick2_test.wav; mpc -q play
for i in $(seq 1 40); do sleep 1
  if s | grep -q "\"camilladsp\": \"active\"" && s | grep -q "\"dac\": true"; then
    sleep 3; mpc -q stop; sleep 1; echo "reveillee en ${i}s"; exit 0; fi
done
mpc -q stop; echo "ECHEC du reveil"; exit 1
