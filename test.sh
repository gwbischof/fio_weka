#!/bin/bash

# horrible hack trying to stop the whole run as soon as the 1st client
# finishes...  and we can use 'runtime=${RUNTIME}' in the jobfile, and
# pass in a much shorter runtime for the 26th job

set -m 

function handle_child() {
    if ! for c in $children; do kill -0 $c; done; then
	echo kill -9 $children
    else
	echo no dead children
    fi
}

trap handle_child CHLD


# I've defined 6 diff "det" sizes
# for each client we'll randomly assign one...
sleeptime=2
s=30
i=1
for ip in $(cat privateips); do
    echo $i
    jobs=($(sed -nr '/^\[([0-9].*-(detector|hdf5))-prelayout\].*$/{s||\1|p}' fio-jobfiles/026-detector_prelayout.job))
    rnd=$((RANDOM % 6))
    job=${jobs[$rnd]}

    if [ "$i" == "26" ]; then
	s=2
    fi
    #(sleep $s; echo "### ($i) starting ${ip}_${job} ###### $(date) ###") &
    bash -c "sleep $s; echo '### ($i) starting ${ip}_${job} ###### $(date) ###'" &
    children="$children $!"
    echo $children
#    ((./fio/fio --client=${ip} fio-jobfiles/025-${job}_read_write.job; echo "### ($i) done ${ip}_${job} #############################################") 2>&1 | tee manual_run/${ip}_${job}.log ) &

    i=$(($i + 1))
    sleep $sleeptime
    echo here
done
date
