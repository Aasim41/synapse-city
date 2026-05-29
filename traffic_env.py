"""
traffic_env.py
==============
Custom Gymnasium environment simulating a 4-way traffic intersection.

Lanes:  0 = North, 1 = South, 2 = East, 3 = West
Actions:
    0 → Green for North-South (lanes 0 & 1 clear traffic)
    1 → Green for East-West  (lanes 2 & 3 clear traffic)

Each step:
    1. 0-2 new cars arrive randomly at each lane.
    2. Green lanes clear up to 2 cars each.
    3. Reward = -(total cars still waiting across all lanes).
"""

from __future__ import annotations

import gymnasium as gym
import numpy as np
from gymnasium import spaces


class TrafficIntersectionEnv(gym.Env):
    """A minimal 4-way intersection traffic signal environment."""

    metadata = {"render_modes": ["human"], "render_fps": 1}

    # ---- construction parameters ----
    MAX_CARS_PER_LANE: int = 50        # upper bound for observation space
    MAX_NEW_ARRIVALS: int = 2          # max cars arriving per lane per step
    CARS_CLEARED_PER_GREEN: int = 2    # cars that pass on green per step
    NUM_LANES: int = 4                 # N, S, E, W

    def __init__(self, render_mode: str | None = None):
        super().__init__()

        # --- spaces ---
        # State: number of waiting cars in each of the 4 lanes
        self.observation_space = spaces.Box(
            low=0,
            high=self.MAX_CARS_PER_LANE,
            shape=(self.NUM_LANES,),
            dtype=np.int32,
        )

        # Action: 0 = Green N-S, 1 = Green E-W
        self.action_space = spaces.Discrete(2)

        self.render_mode = render_mode

        # internal state
        self._lanes: np.ndarray | None = None
        self._step_count: int = 0

    # ------------------------------------------------------------------
    # Gymnasium API
    # ------------------------------------------------------------------

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict | None = None,
    ) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        self._lanes = np.zeros(self.NUM_LANES, dtype=np.int32)
        self._step_count = 0
        return self._get_obs(), self._get_info()

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict]:
        assert self.action_space.contains(action), f"Invalid action: {action}"

        # 1. Arrivals — 0-2 new cars per lane
        arrivals = self.np_random.integers(
            0, self.MAX_NEW_ARRIVALS + 1, size=self.NUM_LANES
        )
        self._lanes = self._lanes + arrivals

        # 2. Clearing — green lanes lose up to CARS_CLEARED_PER_GREEN cars
        if action == 0:
            green_lanes = [0, 1]  # North-South
        else:
            green_lanes = [2, 3]  # East-West

        for lane in green_lanes:
            self._lanes[lane] = max(
                0, self._lanes[lane] - self.CARS_CLEARED_PER_GREEN
            )

        # Clamp to MAX
        self._lanes = np.clip(self._lanes, 0, self.MAX_CARS_PER_LANE)

        # 3. Reward = negative total waiting cars
        reward = -float(self._lanes.sum())

        self._step_count += 1
        terminated = False   # episode never ends on its own
        truncated = False

        if self.render_mode == "human":
            self.render()

        return self._get_obs(), reward, terminated, truncated, self._get_info()

    def render(self) -> None:
        if self.render_mode == "human":
            n, s, e, w = self._lanes
            print(
                f"Step {self._step_count:>4d} | "
                f"N={n:>3d}  S={s:>3d}  E={e:>3d}  W={w:>3d}  | "
                f"Total={self._lanes.sum():>4d}"
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_obs(self) -> np.ndarray:
        return self._lanes.copy()

    def _get_info(self) -> dict:
        return {
            "step": self._step_count,
            "total_waiting": int(self._lanes.sum()),
        }
