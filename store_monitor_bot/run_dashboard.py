#!/usr/bin/env python3
"""
Simple script to run the admin dashboard
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
from admin.dashboard import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)