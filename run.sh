#!/bin/bash
# Istalgan papkadan ishga tushirish mumkin; argumentlar (--area, --full) uzatiladi
cd "$(dirname "$(readlink -f "$0")")" || exit 1
exec ./venv/bin/python3 myshot.py "$@"
