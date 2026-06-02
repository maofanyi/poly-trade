"""Simple launcher to debug and start copy_trader."""
import sys, traceback
sys.path.insert(0, '.')

print("Starting monitor...", flush=True)
try:
    from copy_trader import *
    print("Import OK", flush=True)
except Exception as e:
    print(f"Import FAILED: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

if __name__ == '__main__':
    # This triggers copy_trader's __main__ block
    pass
