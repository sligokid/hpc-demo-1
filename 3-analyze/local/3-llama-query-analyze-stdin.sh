#!/bin/bash

cat ../../results/infer-on-gpu.sh.txt | python ../analyze.py --transcript -  --model llama3.1:8b
