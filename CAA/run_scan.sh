#!/bin/bash

export LD_LIBRARY_PATH=/root/CFM/cpp_core/build/lib:$LD_LIBRARY_PATH
export PYTHONPATH=/root/CAA/CAA:/root/CFM/cpp_core/build:$PYTHONPATH

cd /root/CAA/CAA

echo "=== CAA Scanner ==="
echo "Target: https://videoplayer.mediavi.ru/"
echo ""

python3 run_scan.py