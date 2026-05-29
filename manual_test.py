"""
manual_test.py
==============
Baseline test: runs the TrafficIntersectionEnv for 100 steps using a
**Fixed Timer** strategy that switches the signal every 10 steps.

Outputs per-step state, final Total Cumulative Wait Time,
and exports baseline metrics to baseline_metrics.json.
"""

import json

from traffic_env import TrafficIntersectionEnv


def main() -> None:
    env = TrafficIntersectionEnv(render_mode="human")
    obs, info = env.reset(seed=42)

    total_steps = 100
    switch_interval = 10        # switch signal every 10 steps
    cumulative_wait = 0         # sum of all waiting cars across all steps

    current_action = 0          # start with Green N-S

    step_data = []              # collect per-step data for JSON export

    print("=" * 60)
    print("  Fixed Timer Baseline  —  switch every 10 steps")
    print("=" * 60)

    for step in range(1, total_steps + 1):
        # Switch action every `switch_interval` steps
        if step % switch_interval == 1 and step > 1:
            current_action = 1 - current_action   # toggle 0 ↔ 1

        obs, reward, terminated, truncated, info = env.step(current_action)

        # Accumulate total waiting cars
        cumulative_wait += info["total_waiting"]

        step_data.append({
            "step": step,
            "north": int(obs[0]),
            "south": int(obs[1]),
            "east": int(obs[2]),
            "west": int(obs[3]),
            "total_queue": info["total_waiting"],
            "action": current_action,
            "reward": reward,
        })

        if terminated or truncated:
            break

    print("=" * 60)
    print(f"  Total Cumulative Wait Time (100 steps): {cumulative_wait}")
    print("=" * 60)

    # Export baseline metrics
    metrics = {
        "strategy": "fixed_timer",
        "switch_interval": switch_interval,
        "total_steps": total_steps,
        "cumulative_wait": cumulative_wait,
        "avg_queue": cumulative_wait / total_steps,
        "steps": step_data,
    }

    with open("baseline_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"  ✅ Baseline metrics saved → baseline_metrics.json\n")


if __name__ == "__main__":
    main()
