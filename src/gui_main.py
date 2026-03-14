#!/usr/bin/env python3
"""
Entry point for the Autograder4Canvas GUI.
"""
import sys
import os

# Ensure src/ is on the path when launched directly
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from gui.app import main

if __name__ == "__main__":
    main()
