import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import random
from collections import deque
import json

class TrafficDQN(nn.Module):
    def __init__(self, state_size=8, action_size=4):
        super(TrafficDQN, self).__init__()
        self.fc1 = nn.Linear(state_size, 128)
        self.relu1 = nn.ReLU()
        self.fc2 = nn.Linear(128, 128)
        self.relu2 = nn.ReLU()
        self.out = nn.Linear(128, action_size)

    def forward(self, x):
        x = self.relu1(self.fc1(x))
        x = self.relu2(self.fc2(x))
        return self.out(x)

def train_agent():
    print("🚦 Training Multi-Agent PyTorch DQN (Green Wave)...")
    state_size = 8
    action_size = 4
    model = TrafficDQN(state_size, action_size)
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    loss_fn = nn.MSELoss()
    
    epochs = 3000
    batch_size = 64
    epsilon = 1.0
    epsilon_min = 0.05
    epsilon_decay = 0.995
    gamma = 0.95
    
    memory = deque(maxlen=5000)
    
    for epoch in range(epochs):
        # State: [N_A, S_A, E_A, W_A, N_B, S_B, E_B, W_B]
        state = np.array([random.randint(0, 50) for _ in range(8)], dtype=np.float32)
        
        state_scaled = state / 50.0 # simple scaling
            
        state_tensor = torch.FloatTensor(state_scaled).unsqueeze(0)
        
        if random.random() < epsilon:
            action = random.randint(0, action_size-1)
        else:
            with torch.no_grad():
                q_vals = model(state_tensor)
                action = torch.argmax(q_vals).item()
                
        # Action mappings
        # 0: NS_A + NS_B
        # 1: NS_A + EW_B
        # 2: EW_A + NS_B
        # 3: EW_A + EW_B
        
        next_state = np.copy(state)
        
        # Intersection A Physics
        cleared_E_A = 0
        if action == 0 or action == 1: # NS_A Green
            next_state[0] = max(0, next_state[0] - 6)
            next_state[1] = max(0, next_state[1] - 6)
        else: # EW_A Green
            cleared_E_A = min(6, next_state[2]) # Cars leaving East A
            next_state[2] = max(0, next_state[2] - 6)
            next_state[3] = max(0, next_state[3] - 6)

        # Intersection B Physics
        if action == 0 or action == 2: # NS_B Green
            next_state[4] = max(0, next_state[4] - 6)
            next_state[5] = max(0, next_state[5] - 6)
        else: # EW_B Green
            next_state[6] = max(0, next_state[6] - 6)
            next_state[7] = max(0, next_state[7] - 6)
            
        # GREEN WAVE LINK: Cars clearing East_A travel down the arterial road and enter West_B!
        next_state[7] += cleared_E_A
            
        # The penalty is the total cars waiting in BOTH intersections!
        reward = -np.sum(next_state)
        
        # Reward Bonus for creating a green wave (cars didn't have to stop at B)
        # If East A is green (action 2 or 3) AND EW_B is green (action 1 or 3)
        if (action == 3) and cleared_E_A > 0:
            reward += cleared_E_A * 2 # Huge bonus for syncing the lights!

        next_state_scaled = next_state / 50.0
            
        memory.append((state_scaled, action, reward, next_state_scaled))
        
        if len(memory) > batch_size:
            minibatch = random.sample(memory, batch_size)
            
            states = torch.FloatTensor(np.vstack([x[0] for x in minibatch]))
            actions = torch.LongTensor([x[1] for x in minibatch]).unsqueeze(1)
            rewards = torch.FloatTensor([x[2] for x in minibatch]).unsqueeze(1)
            next_states = torch.FloatTensor(np.vstack([x[3] for x in minibatch]))
            
            current_q = model(states).gather(1, actions)
            
            with torch.no_grad():
                max_next_q = model(next_states).max(1)[0].unsqueeze(1)
                target_q = rewards + gamma * max_next_q
                
            loss = loss_fn(current_q, target_q)
            
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
        if epsilon > epsilon_min:
            epsilon *= epsilon_decay
            
        if epoch % 500 == 0:
            print(f"Epoch {epoch}/{epochs} | Epsilon: {epsilon:.2f} | Last Reward: {reward}")

    torch.save(model.state_dict(), "traffic_dqn_multi.pth")
    print("✅ PyTorch Multi-Agent Model Saved to traffic_dqn_multi.pth")

if __name__ == "__main__":
    train_agent()
