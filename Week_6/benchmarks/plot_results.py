import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

def plot_metrics():
    out_dir = Path(__file__).parent
    
    with open(out_dir / "retrieval_metrics.json", "r", encoding="utf-8") as f:
        metrics = json.load(f)
        
    models = list(metrics.keys())
    
    # --- Plot 1: Recall@3 and Precision@3 ---
    recall3 = [metrics[m]["recall@3"] for m in models]
    mrr = [metrics[m]["mrr"] for m in models]
    
    x = np.arange(len(models))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(10, 6))
    rects1 = ax.bar(x - width/2, recall3, width, label='Recall@3', color='#6366f1')
    rects2 = ax.bar(x + width/2, mrr, width, label='MRR', color='#10b981')
    
    ax.set_ylabel('Score')
    ax.set_title('Search Quality Comparison (Recall@3 vs MRR)')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend()
    ax.set_ylim(0, 1.1)
    
    # Add values on top of bars
    for rect in rects1 + rects2:
        height = rect.get_height()
        ax.annotate(f'{height:.2f}',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom')
                    
    fig.tight_layout()
    plt.savefig(out_dir / "search_quality.png", dpi=300)
    plt.close()
    
    # --- Plot 2: Latency ---
    latency = [metrics[m]["avg_latency_ms"] for m in models]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(models, latency, color=['#f59e0b', '#3b82f6', '#8b5cf6', '#ef4444'])
    
    ax.set_ylabel('Latency (ms)')
    ax.set_title('Search Latency Comparison')
    
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.1f}ms',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom')
                    
    fig.tight_layout()
    plt.savefig(out_dir / "search_latency.png", dpi=300)
    plt.close()
    
    print("Plots generated successfully in benchmarks folder.")

if __name__ == "__main__":
    plot_metrics()
