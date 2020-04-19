#!/bin/bash

# I've defined 6 diff "det" sizes
# for each client we'll randomly assign one...
date
time cat privateips | parallel 'bash -c "jobs=($(sed -nr '\''/^\[([0-9].*-(detector|hdf5))-prelayout\].*$/{s||\1|p}'\'' fio-jobfiles/026-detector_prelayout.job)); rnd=\$((RANDOM % 6)); ./fio/fio --client={} fio-jobfiles/025-\${jobs[\$rnd]}_read_write.job"'
date
