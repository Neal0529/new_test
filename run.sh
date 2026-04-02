#!/bin/bash
# ETF Trading Analysis System - Run Script
# This script runs the daily analysis

# Navigate to project directory
cd "$(dirname "$0")"

# Run daily analysis
python main.py --once

# Exit with the exit code of the last command
exit $?
