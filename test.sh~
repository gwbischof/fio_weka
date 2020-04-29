#!/bin/bash

# I've defined 6 diff "det" sizes
# for each client we'll randomly assign one...
sleeptime=120
#sleeptime=2
i=1
for ip in $(cat privateips); do
    jobs=($(sed -nr '/^\[([0-9].*-(detector|hdf5))-prelayout\].*$/{s||\1|p}' fio-jobfiles/026-detector_prelayout.job))
    rnd=$((RANDOM % 6))
    job=${jobs[$rnd]}

    echo "### ($i) starting ${ip}_${job} #############################################"
    date
    ((./fio/fio --client=${ip} fio-jobfiles/025-${job}_read_write.job; echo "### ($i) done ${ip}_${job} #############################################") 2>&1 | tee manual_run/${ip}_${job}.log ) &

    i=$(($i + 1))
    sleep $sleeptime
done
date
