#!/usr/bin/env bash

set -e
set -x

# Ensure that the CWD is set to script's location
cd "${0%/*}"
CWD=$(pwd)

ORAMS=$1
OPTIMIZATION=$2

for threads in {1..16}
do
	# if [ "$threads" -ge "4" ]; then
	# 	gamma="true"
	# else
	# 	gamma="false"
	# fi
	echo "Running for $threads threads"
	cd ../../dp-oram/dp-oram
	./bin/main -g true -r true -p true -s inmemory -n $threads -b 4096 -u $ORAMS --beta 20 --epsilon 1 --useGamma true --useOramOptimization $OPTIMIZATION --levels 0 -v trace
done

echo "Done!"
