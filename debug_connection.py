#!/usr/bin/env python3
"""
Debug-Script für FlexLM Connection Issues
"""

import subprocess
import os
import sys

def test_lmutil_direct():
    """Teste lmutil direkt"""
    
    # Verschiedene lmutil Pfade testen
    lmutil_paths = [
        r"C:\Temp\SolidWorks_Exporter\FlexLM_Export\lmutil.exe",
        r"lmutil.exe",  # Falls im PATH
        r".\lmutil.exe",  # Lokale Kopie
    ]
    
    servers = [
        "lic-solidworks-emea.patec.group:25734",
        "lic-solidworks-amas.patec.group:25734"
    ]
    
    for lmutil_path in lmutil_paths:
        print(f"\n=== Testing lmutil: {lmutil_path} ===")
        
        if not os.path.exists(lmutil_path):
            print(f"❌ lmutil not found: {lmutil_path}")
            continue
        
        print(f"✅ lmutil found: {lmutil_path}")
        
        # Test lmutil version
        try:
            result = subprocess.run([lmutil_path], capture_output=True, text=True, timeout=10)
            print(f"lmutil version test - RC: {result.returncode}")
            if result.stdout:
                print(f"STDOUT (first 200 chars): {result.stdout[:200]}")
            if result.stderr:
                print(f"STDERR: {result.stderr}")
        except Exception as e:
            print(f"❌ lmutil version test failed: {e}")
            continue
        
        # Test each server
        for server in servers:
            print(f"\n--- Testing server: {server} ---")
            
            # Test lmstat -c SERVER -a
            cmd = [lmutil_path, "lmstat", "-c", server, "-a"]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                print(f"Command: {' '.join(cmd)}")
                print(f"Return Code: {result.returncode}")
                
                if result.returncode == 0:
                    print("✅ lmstat successful!")
                    stdout = result.stdout
                    print(f"Output length: {len(stdout)} characters")
                    
                    # Check for key indicators
                    if "license server UP" in stdout:
                        print("✅ License server is UP")
                    elif "Cannot connect" in stdout:
                        print("❌ Cannot connect to license server")
                    else:
                        print("⚠️ Unclear server status")
                    
                    # Check for features
                    if "Users of " in stdout:
                        feature_count = stdout.count("Users of ")
                        print(f"✅ Found {feature_count} features")
                        
                        # Show first feature
                        lines = stdout.split('\n')
                        for line in lines:
                            if line.strip().startswith("Users of "):
                                print(f"First feature: {line.strip()}")
                                break
                    else:
                        print("❌ No features found")
                    
                    # Show first 500 chars of output
                    print(f"\nFirst 500 chars of output:\n{stdout[:500]}")
                    
                else:
                    print(f"❌ lmstat failed with RC {result.returncode}")
                    if result.stderr:
                        print(f"STDERR: {result.stderr}")
                    if result.stdout:
                        print(f"STDOUT: {result.stdout[:200]}")
                        
            except subprocess.TimeoutExpired:
                print("❌ lmstat timeout (30s)")
            except Exception as e:
                print(f"❌ lmstat exception: {e}")

if __name__ == "__main__":
    print("FlexLM Connection Debug Tool")
    print("=" * 50)
    
    test_lmutil_direct()
    
    print("\n" + "=" * 50)
    print("Debug completed!")
