import os
import subprocess
import time
from pathlib import Path

def run_tests():
    # Ensure raw_data dir exists
    raw_dir = Path(__file__).parent.parent / "reports" / "raw_data"
    os.makedirs(raw_dir, exist_ok=True)
    
    locust_dir = Path(__file__).parent.parent / "locustfiles"
    scenarios = [
        ("query", "locustfile_query.py"),
        ("mixed", "locustfile_mixed.py")
    ]
    user_counts = [100, 500, 1000]
    
    # Ramp rate (users per second)
    spawn_rate = 100
    # Hold steady state for short time for immediate data generation
    run_time = "10s"
    
    host = "http://127.0.0.1:8000"
    
    print("Starting automated load testing suite...")
    
    for scenario_name, locust_file in scenarios:
        for users in user_counts:
            print(f"--- Running {scenario_name.upper()} load test with {users} users ---")
            
            csv_prefix = raw_dir / f"{scenario_name}_{users}u"
            file_path = locust_dir / locust_file
            
            cmd = [
                "locust",
                "-f", str(file_path),
                "--headless",
                "-u", str(users),
                "-r", str(spawn_rate),
                "--run-time", run_time,
                "--host", host,
                "--csv", str(csv_prefix)
            ]
            
            try:
                subprocess.run(cmd, check=True)
                print(f"Completed {scenario_name}_{users}u. Waiting 10s for cool-down...\n")
                time.sleep(10) # Let the server breathe and drop connections
            except subprocess.CalledProcessError as e:
                print(f"Error running test {scenario_name}_{users}u: {e}")

if __name__ == "__main__":
    run_tests()
