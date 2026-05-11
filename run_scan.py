import sys
import urllib3
urllib3.disable_warnings()
sys.path.append('.')

print("=== Bot Starting ===")
print(f"Python version: {sys.version}")

try:
    print("Importing scheduler...")
    from scheduler import scan_dan_alert, auto_trade_loop, monitor_posisi
    print("Import OK, running scan...")
    scan_dan_alert()
    auto_trade_loop()
    monitor_posisi()
    print("=== All Done ===")
except Exception as e:
    import traceback
    print(f"ERROR: {e}")
    traceback.print_exc()
    sys.exit(1)