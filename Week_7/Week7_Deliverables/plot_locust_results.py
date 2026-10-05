import os
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

def plot_results():
    raw_dir = Path(__file__).parent.parent / "reports" / "raw_data"
    out_dir = Path(__file__).parent.parent / "reports" / "charts"
    os.makedirs(out_dir, exist_ok=True)
    
    scenarios = ["query", "mixed"]
    user_counts = [100, 500, 1000]
    
    # Store aggregated metrics
    summary = []
    
    for scenario in scenarios:
        throughputs = []
        p95_latencies = []
        error_rates = []
        
        for users in user_counts:
            stats_file = raw_dir / f"{scenario}_{users}u_stats.csv"
            
            if not stats_file.exists():
                print(f"Skipping {stats_file} - not found.")
                throughputs.append(0)
                p95_latencies.append(0)
                error_rates.append(0)
                continue
                
            df = pd.read_csv(stats_file)
            
            # Locust aggregate row is named "Aggregated" in the Name column
            agg_row = df[df["Name"] == "Aggregated"]
            if not agg_row.empty:
                reqs_per_sec = float(agg_row["Requests/s"].values[0])
                p95 = float(agg_row["95%"].values[0])
                total_reqs = float(agg_row["Request Count"].values[0])
                failures = float(agg_row["Failure Count"].values[0])
                err_rate = (failures / total_reqs * 100) if total_reqs > 0 else 0
                
                throughputs.append(reqs_per_sec)
                p95_latencies.append(p95)
                error_rates.append(err_rate)
                
                summary.append({
                    "Scenario": scenario,
                    "Users": users,
                    "Throughput (req/s)": reqs_per_sec,
                    "p50 Latency (ms)": float(agg_row["50%"].values[0]),
                    "p95 Latency (ms)": p95,
                    "p99 Latency (ms)": float(agg_row["99%"].values[0]),
                    "Max Latency (ms)": float(agg_row["Max Response Time"].values[0]),
                    "Error Rate (%)": err_rate
                })
        
        # Plot Throughput vs Users
        plt.figure(figsize=(8, 5))
        plt.plot(user_counts, throughputs, marker='o', color='blue' if scenario == 'query' else 'orange')
        plt.title(f'{scenario.capitalize()} Workload: Throughput vs Concurrent Users')
        plt.xlabel('Concurrent Users')
        plt.ylabel('Requests / sec')
        plt.grid(True)
        plt.savefig(out_dir / f"{scenario}_throughput.png")
        plt.close()
        
        # Plot p95 Latency vs Users
        plt.figure(figsize=(8, 5))
        plt.plot(user_counts, p95_latencies, marker='x', color='red')
        plt.title(f'{scenario.capitalize()} Workload: p95 Latency vs Concurrent Users')
        plt.xlabel('Concurrent Users')
        plt.ylabel('p95 Latency (ms)')
        plt.grid(True)
        plt.savefig(out_dir / f"{scenario}_p95_latency.png")
        plt.close()

    # Save summary table
    if summary:
        df_sum = pd.DataFrame(summary)
        df_sum.to_csv(out_dir / "benchmark_summary.csv", index=False)
        print("Summary charts and CSV saved successfully.")

if __name__ == "__main__":
    plot_results()
