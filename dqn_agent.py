"""
dqn_agent.py
============
Deep Q-Network agent for the Traffic Intersection environment.
Rewritten in pure NumPy to avoid PyTorch dependencies and hang issues.

Components:
    - NumPy MLP:       3-layer MLP  (4 -> 64 -> 64 -> 2)
    - ReplayBuffer:    Circular experience buffer
    - DQNAgent:        epsilon-greedy action selection, target-network updates
"""

import numpy as np
import random
from collections import deque, namedtuple

Transition = namedtuple("Transition", ("state", "action", "reward", "next_state", "done"))

class NumpyMLP:
    def __init__(self, layer_sizes):
        self.layer_sizes = layer_sizes
        self.weights = []
        self.biases = []
        for i in range(len(layer_sizes) - 1):
            w = np.random.randn(layer_sizes[i], layer_sizes[i+1]) * np.sqrt(2. / layer_sizes[i])
            b = np.zeros(layer_sizes[i+1])
            self.weights.append(w)
            self.biases.append(b)
            
    def copy_from(self, other_mlp):
        self.weights = [w.copy() for w in other_mlp.weights]
        self.biases = [b.copy() for b in other_mlp.biases]
        
    def soft_update_from(self, other_mlp, tau):
        for i in range(len(self.weights)):
            self.weights[i] = tau * other_mlp.weights[i] + (1 - tau) * self.weights[i]
            self.biases[i] = tau * other_mlp.biases[i] + (1 - tau) * self.biases[i]

    def forward(self, x):
        activations = [x]
        zs = []
        a = x
        for i in range(len(self.weights) - 1):
            z = np.dot(a, self.weights[i]) + self.biases[i]
            zs.append(z)
            a = np.maximum(0, z)  # ReLU
            activations.append(a)
        
        # Last layer (linear)
        z = np.dot(a, self.weights[-1]) + self.biases[-1]
        zs.append(z)
        activations.append(z)
        return activations, zs
        
    def predict(self, x):
        return self.forward(x)[0][-1]
        
    def backprop(self, activations, zs, dL_dy, lr=1e-3):
        m = dL_dy.shape[0]
        delta = dL_dy
        
        for i in reversed(range(len(self.weights))):
            dW = np.dot(activations[i].T, delta) / m
            db = np.sum(delta, axis=0) / m
            
            if i > 0:
                dz = delta.dot(self.weights[i].T)
                delta = dz * (zs[i-1] > 0) # ReLU derivative
            
            self.weights[i] -= lr * dW
            self.biases[i] -= lr * db

class ReplayBuffer:
    def __init__(self, capacity: int = 10_000):
        self.buffer = deque(maxlen=capacity)

    def push(self, *args):
        self.buffer.append(Transition(*args))

    def sample(self, batch_size: int):
        return random.sample(self.buffer, batch_size)

    def __len__(self) -> int:
        return len(self.buffer)

class DQNAgent:
    def __init__(
        self, state_dim=4, action_dim=2, lr=5e-3, gamma=0.99, tau=0.05,
        eps_start=1.0, eps_end=0.01, eps_decay_steps=3000,
        buffer_capacity=10_000, batch_size=64, device=None
    ):
        self.action_dim = action_dim
        self.gamma = gamma
        self.tau = tau
        self.batch_size = batch_size
        self.lr = lr

        self.eps = eps_start
        self.eps_end = eps_end
        self.eps_step = (eps_start - eps_end) / eps_decay_steps

        # smaller 2-layer MLP for numpy speed
        self.policy_net = NumpyMLP([state_dim, 64, 64, action_dim])
        self.target_net = NumpyMLP([state_dim, 64, 64, action_dim])
        self.target_net.copy_from(self.policy_net)

        self.memory = ReplayBuffer(buffer_capacity)
        self.steps_done = 0

    def select_action(self, state: np.ndarray) -> int:
        self.steps_done += 1
        self.eps = max(self.eps_end, self.eps - self.eps_step)
        if random.random() < self.eps:
            return random.randrange(self.action_dim)
        
        q_values = self.policy_net.predict(state.reshape(1, -1))
        return int(np.argmax(q_values[0]))

    def select_action_greedy(self, state: np.ndarray) -> int:
        q_values = self.policy_net.predict(state.reshape(1, -1))
        return int(np.argmax(q_values[0]))

    def store(self, state, action, reward, next_state, done):
        self.memory.push(state, action, reward, next_state, done)

    def learn(self):
        if len(self.memory) < self.batch_size:
            return None

        batch = self.memory.sample(self.batch_size)
        states = np.array([t.state for t in batch])
        actions = np.array([t.action for t in batch])
        rewards = np.array([t.reward for t in batch])
        next_states = np.array([t.next_state for t in batch])
        dones = np.array([t.done for t in batch])

        activations, zs = self.policy_net.forward(states)
        q_values = activations[-1]

        next_q = self.target_net.predict(next_states)
        target = rewards + self.gamma * np.max(next_q, axis=1) * (1 - dones)

        dL_dy = np.zeros_like(q_values)
        for i in range(self.batch_size):
            error = q_values[i, actions[i]] - target[i]
            # Huber-like clipping for stability
            error = np.clip(error, -1.0, 1.0)
            dL_dy[i, actions[i]] = error
            
        loss = np.mean(np.square(dL_dy))

        self.policy_net.backprop(activations, zs, dL_dy, lr=self.lr)
        self.target_net.soft_update_from(self.policy_net, self.tau)

        return float(loss)

    def save(self, path="trained_model.npy"):
        np.save(path, {'weights': self.policy_net.weights, 'biases': self.policy_net.biases})

    def load(self, path="trained_model.npy"):
        try:
            data = np.load(path, allow_pickle=True).item()
            self.policy_net.weights = data['weights']
            self.policy_net.biases = data['biases']
            self.target_net.copy_from(self.policy_net)
        except Exception:
            pass
