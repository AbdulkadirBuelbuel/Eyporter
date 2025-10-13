#!/usr/bin/env python3
"""
Test Parser with Real Data
"""

import re

def test_parser():
    # Test data from the actual lmstat output
    test_data = """Users of cae_cwstd:  (Total of 2 licenses issued;  Total of 1 license in use)

  "cae_cwstd" v32.0, vendor: SW_D, expiry: 03-dec-2026
  vendor_string: sd=12-03-2024
  floating license

    nih2wee VDI00000000k7sW VDI00000000k7sW (v31.0) (wa2vmp275/25734 35485), start Wed 9/3 10:00

Users of solidworks:  (Total of 339 licenses issued;  Total of 323 licenses in use)

  "solidworks" v32.0, vendor: SW_D, expiry: 03-dec-2026
  vendor_string: sd=12-03-2024
  floating license

    MAT3WA2 PC-CZC909868N PC-PF3073BN (v31.0) (wa2vmp275/25734 22225), start Tue 9/2 14:36
    JGC1HZ2 CR-VDI050 PC-PW08RQDH (v31.0) (wa2vmp275/25734 31738), start Wed 9/3 3:27"""

    print("=== Testing Feature Header Patterns ===")
    
    # Current regex patterns
    feature_hdr_re = re.compile(r'^Users of\s+([A-Za-z0-9_\-\.\+]+):\s+\(Total of\s+(\d+)\s+licenses?\s+issued;.*Total of\s+(\d+)\s+licenses?\s+in use\)', re.IGNORECASE)
    feature_hdr_alt = re.compile(r'^Users of\s+([A-Za-z0-9_\-\.\+]+):\s+\(Total of\s+(\d+)\s+licenses?,\s+(\d+)\s+in use\)', re.IGNORECASE)
    
    lines = test_data.split('\n')
    for i, line in enumerate(lines):
        if 'Users of ' in line:
            print(f"Line {i}: {repr(line)}")
            
            match1 = feature_hdr_re.search(line)
            match2 = feature_hdr_alt.search(line)
            
            if match1:
                print(f"  ✅ Main pattern matched: {match1.groups()}")
            else:
                print(f"  ❌ Main pattern failed")
                
            if match2:
                print(f"  ✅ Alt pattern matched: {match2.groups()}")
            else:
                print(f"  ❌ Alt pattern failed")
                
            # Try simpler pattern
            simple_re = re.compile(r'Users of ([^:]+):\s+\(Total of (\d+) [^;]+; Total of (\d+)', re.IGNORECASE)
            match3 = simple_re.search(line)
            if match3:
                print(f"  ✅ Simple pattern matched: {match3.groups()}")
            else:
                print(f"  ❌ Simple pattern failed")
            print()

    print("=== Testing User Line Patterns ===")
    user_lines = [
        "    nih2wee VDI00000000k7sW VDI00000000k7sW (v31.0) (wa2vmp275/25734 35485), start Wed 9/3 10:00",
        "    MAT3WA2 PC-CZC909868N PC-PF3073BN (v31.0) (wa2vmp275/25734 22225), start Tue 9/2 14:36"
    ]
    
    user_line_re = re.compile(r'^\s*(\S+)\s+(\S+)\s+(\S+)\s+\([^)]+\)\s+\([^)]+\s+\d+\)', re.IGNORECASE)
    user_line_generic = re.compile(r'^\s*(\S+?)(?:@|\s+)([A-Za-z0-9_\-.]+)\s+\(v[0-9\.]+\)\s+\([^)]+\s+\d+\)', re.IGNORECASE)
    
    for line in user_lines:
        print(f"Line: {repr(line)}")
        
        match1 = user_line_re.search(line)
        match2 = user_line_generic.search(line)
        
        if match1:
            print(f"  ✅ Main user pattern: {match1.groups()}")
        else:
            print(f"  ❌ Main user pattern failed")
            
        if match2:
            print(f"  ✅ Generic user pattern: {match2.groups()}")
        else:
            print(f"  ❌ Generic user pattern failed")
        print()

if __name__ == "__main__":
    test_parser()
