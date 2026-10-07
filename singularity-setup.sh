#!/usr/bin/env bash

# When pulling or building from Docker containers using singularity, 
# the conversion can be quite heavy. 
# Speed up the conversion and avoid leaving behind temporary files 
# by using the in-memory filesystem on /tmp as the Singularity cache 
# directory, i.e.

mkdir -p /tmp/$USER
export SINGULARITY_TMPDIR=/tmp/$USER
export SINGULARITY_CACHEDIR=/tmp/$USER