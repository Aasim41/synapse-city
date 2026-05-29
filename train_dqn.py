"""
train_dqn.py
============
Trains a DQN agent on the TrafficIntersectionEnv for 500 episodes,
then evaluates it against a fixed-timer baseline.

Outputs:
    • trained_model.pth        — saved policy-network weights
    • training_metrics.json    — per-episode reward / queue / epsilon
    • evaluation_metrics.json  — step-by-step data from the trained agent
    • Console summary comparing Agent vs Baseline
"""

from __future__ import annotations

import json
import time

import numpy as np

from traffic_env import TrafficIntersectionEnv
from dqn_agent import DQNAgent


# ══════════════════════════════════════════════════════════════════════
# Config
# ══════════════════════════════════════════════════════════════════════
NUM_EPISODES = 500
STEPS_PER_EPISODE = 300
EVAL_STEPS = 300
BASELINE_SWITCH_INTERVAL = 10


def train() -> dict:
    """Train the DQN agent and return training metrics."""
    env = TrafficIntersectionEnv()
    agent = DQNAgent(
        state_dim=4,
        action_dim=2,
        lr=1e-3,
        gamma=0.99,
        tau=0.005,
        eps_start=1.0,
        eps_end=0.01,
        eps_decay_steps=NUM_EPISODES * STEPS_PER_EPISODE // 2,
        buffer_capacity=10_000,
        batch_size=64,
    )

    history = {
        "episode_rewards": [],
        "episode_avg_queues": [],
        "episode_epsilons": [],
        "episode_losses": [],
    }

    print("=" * 70)
    print("  🚦  DQN Training  —  Smart City Traffic Optimizer")
    print("=" * 70)
    t0 = time.time()

    for ep in range(1, NUM_EPISODES + 1):
        obs, _ = env.reset(seed=ep)
        total_reward = 0.0
        total_queue = 0
        ep_losses = []

        for step in range(STEPS_PER_EPISODE):
            action = agent.select_action(obs)
            next_obs, reward, terminated, truncated, info = env.step(action)

            agent.store(obs, action, reward, next_obs, float(terminated))
            loss = agent.learn()
            if loss is not None:
                ep_losses.append(loss)

            obs = next_obs
            total_reward += reward
            total_queue += info["total_waiting"]

            if terminated or truncated:
                break

        avg_queue = total_queue / STEPS_PER_EPISODE
        avg_loss = np.mean(ep_losses) if ep_losses else 0.0

        history["episode_rewards"].append(total_reward)
        history["episode_avg_queues"].append(avg_queue)
        history["episode_epsilons"].append(agent.eps)
        history["episode_losses"].append(avg_loss)

        if ep % 50 == 0 or ep == 1:
            print(
                f"  Episode {ep:>4d}/{NUM_EPISODES} | "
                f"Reward: {total_reward:>8.1f} | "
                f"Avg Queue: {avg_queue:>5.1f} | "
                f"ε: {agent.eps:.3f} | "
                f"Loss: {avg_loss:.4f}"
            )

    elapsed = time.time() - t0
    print(f"\n  Training complete in {elapsed:.1f}s")

    # Save model
    agent.save("trained_model.pth")
    print("  ✅ Model saved → trained_model.pth")

    # Save training metrics
    with open("training_metrics.json", "w") as f:
        json.dump(history, f, indent=2)
    print("  ✅ Metrics saved → training_metrics.json")

    return {"agent": agent, "history": history}


# ══════════════════════════════════════════════════════════════════════
# Evaluation helpers
# ══════════════════════════════════════════════════════════════════════
def evaluate_agent(agent: DQNAgent, steps: int = EVAL_STEPS, seed: int = 999) -> dict:
    """Run the trained agent greedily and collect step-by-step metrics."""
    env = TrafficIntersectionEnv()
    obs, _ = env.reset(seed=seed)

    data = {
        "steps": [],
        "north": [], "south": [], "east": [], "west": [],
        "total_queue": [],
        "actions": [],
        "rewards": [],
    }

    cumulative_wait = 0
    for step in range(1, steps + 1):
        action = agent.select_action_greedy(obs)
        obs, reward, _, _, info = env.step(action)

        cumulative_wait += info["total_waiting"]
        data["steps"].append(step)
        data["north"].append(int(obs[0]))
        data["south"].append(int(obs[1]))
        data["east"].append(int(obs[2]))
        data["west"].append(int(obs[3]))
        data["total_queue"].append(info["total_waiting"])
        data["actions"].append(action)
        data["rewards"].append(reward)

    data["cumulative_wait"] = cumulative_wait
    data["avg_queue"] = cumulative_wait / steps
    return data


def evaluate_baseline(steps: int = EVAL_STEPS, seed: int = 999) -> dict:
    """Run the fixed-timer baseline and collect step-by-step metrics."""
    env = TrafficIntersectionEnv()
    obs, _ = env.reset(seed=seed)

    data = {
        "steps": [],
        "north": [], "south": [], "east": [], "west": [],
        "total_queue": [],
        "actions": [],
        "rewards": [],
    }

    cumulative_wait = 0
    action = 0

    for step in range(1, steps + 1):
        if step % BASELINE_SWITCH_INTERVAL == 1 and step > 1:
            action = 1 - action

        obs, reward, _, _, info = env.step(action)

        cumulative_wait += info["total_waiting"]
        data["steps"].append(step)
        data["north"].append(int(obs[0]))
        data["south"].append(int(obs[1]))
        data["east"].append(int(obs[2]))
        data["west"].append(int(obs[3]))
        data["total_queue"].append(info["total_waiting"])
        data["actions"].append(action)
        data["rewards"].append(reward)

    data["cumulative_wait"] = cumulative_wait
    data["avg_queue"] = cumulative_wait / steps
    return data


# ══════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════
def main():
    # 1. Train
    result = train()
    agent = result["agent"]

    # 2. Evaluate both strategies on the SAME seed
    print("\n" + "=" * 70)
    print("  📊  Evaluation  —  Same scenario, seed=999, 300 steps")
    print("=" * 70)

    agent_data = evaluate_agent(agent, EVAL_STEPS)
    baseline_data = evaluate_baseline(EVAL_STEPS)

    # 3. Print comparison
    improvement = (
        (baseline_data["avg_queue"] - agent_data["avg_queue"])
        / baseline_data["avg_queue"]
        * 100
    )

    print(f"\n  {'Metric':<30s} {'Fixed Timer':>14s} {'DQN Agent':>14s}")
    print("  " + "─" * 60)
    print(
        f"  {'Cumulative Wait':<30s} "
        f"{baseline_data['cumulative_wait']:>14,d} "
        f"{agent_data['cumulative_wait']:>14,d}"
    )
    print(
        f"  {'Avg Queue Length':<30s} "
        f"{baseline_data['avg_queue']:>14.2f} "
        f"{agent_data['avg_queue']:>14.2f}"
    )
    print(
        f"  {'Total Reward':<30s} "
        f"{sum(baseline_data['rewards']):>14.1f} "
        f"{sum(agent_data['rewards']):>14.1f}"
    )
    print(f"\n  🏆  DQN Agent improvement: {improvement:+.1f}%")
    print("=" * 70)

    # 4. Export evaluation data for the dashboard
    dashboard_data = {
        "training": result["history"],
        "agent_eval": agent_data,
        "baseline_eval": baseline_data,
        "summary": {
            "agent_avg_queue": agent_data["avg_queue"],
            "baseline_avg_queue": baseline_data["avg_queue"],
            "improvement_pct": round(improvement, 2),
            "agent_cumulative_wait": agent_data["cumulative_wait"],
            "baseline_cumulative_wait": baseline_data["cumulative_wait"],
            "agent_total_reward": sum(agent_data["rewards"]),
            "baseline_total_reward": sum(baseline_data["rewards"]),
            "episodes_trained": NUM_EPISODES,
            "steps_per_episode": STEPS_PER_EPISODE,
        },
    }

    with open("dashboard_data.json", "w") as f:
        json.dump(dashboard_data, f, indent=2)
    print("  ✅ Dashboard data saved → dashboard_data.json\n")


if __name__ == "__main__":
    main()
