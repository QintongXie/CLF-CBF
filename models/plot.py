'''
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Define the environment size
env_size = (20, 20)

# Generate 10 obstacles as a list of (x, y) positions
np.random.seed(33)  # For reproducibility
obstacles = [(np.random.randint(0, env_size[0]), np.random.randint(0, env_size[1])) for _ in range(15)]

# Define the goal position
goal = (15, 15)

# Define initial positions of 8 agents in a relative middle position
agents = [(5, 5), (5, 6), (5, 7), (6, 5), (6, 7), (7, 5), (7, 6), (7, 7)]

# Function to check if a point is in an obstacle
def is_obstacle(point, obstacles):
    return point in obstacles

# Function to check if a point is within the environment bounds
def is_within_bounds(point, env_size):
    return 0 <= point[0] < env_size[0] and 0 <= point[1] < env_size[1]

# Function to move agents towards the goal while avoiding obstacles and staying within bounds
def move_agents(agents, goal, obstacles, env_size):
    new_agents = []
    for agent in agents:
        x, y = agent
        dx, dy = goal[0] - x, goal[1] - y
        if dx != 0:
            x += np.sign(dx)
        if dy != 0:
            y += np.sign(dy)
        new_pos = (x, y)
        if is_within_bounds(new_pos, env_size) and not is_obstacle(new_pos, obstacles):
            new_agents.append(new_pos)
        else:
            new_agents.append(agent)  # Stay in place if moving into an obstacle or out of bounds
    return new_agents

# Function to form a circular formation around the goal
def form_circle(agents, goal, radius):
    angles = np.linspace(0, 2 * np.pi, len(agents), endpoint=False)
    circle_positions = [(int(goal[0] + radius * np.cos(angle)), int(goal[1] + radius * np.sin(angle))) for angle in angles]
    return circle_positions

# Simulate the movement of agents
radius = 3  # Radius of the circular formation
for step in range(50):
    agents = move_agents(agents, goal, obstacles, env_size)
    if all(agent == goal for agent in agents):
        break

# Form a circular formation around the goal
agents = form_circle(agents, goal, radius)

# Visualization
plt.figure(figsize=(8, 8))
plt.xlim(0, env_size[0])
plt.ylim(0, env_size[1])

# Add a thick border around the maze
border = patches.Rectangle((0, 0), env_size[0], env_size[1], linewidth=10, edgecolor='slategray', facecolor='none')
plt.gca().add_patch(border)

# Plot obstacles
for obs in obstacles:
    plt.plot(obs[0], obs[1], 's', color='palevioletred', markersize=12, label='Obstacle' if obs == obstacles[0] else "")

# Plot goal
plt.plot(goal[0], goal[1], 'P', color='mediumpurple', markersize=20, label='Goal')

# Plot agents
for agent in agents:
    plt.plot(agent[0], agent[1], 'o', color='skyblue', markersize=12, label='Agent' if agent == agents[0] else "")

# Plot paths (optional)
for agent in agents:
    plt.plot([agent[0], goal[0]], [agent[1], goal[1]], '--', color='lightblue', alpha=0.4)

# Add labels and title
plt.legend(loc='upper right')
# plt.title("8 Agents Forming a Circular Formation While Avoiding Obstacles", fontsize=14, pad=20)

# Remove axes for a maze-like appearance
plt.axis('off')

# Show the plot
plt.show()

'''
import matplotlib.pyplot as plt
import numpy as np

# Data 8 agents
evaluation_steps = np.arange(1, 11)
formation_errors = {
    'Agent 1': [0.3756, 0.1072, 0.2702, 0.5216, 0.5100, 0.4912, 0.2577, 0.3887, 0.3601, 0.1318],
    'Agent 2': [0.8750, 0.2865, 0.5589, 1.1762, 1.1914, 1.1457, 0.6231, 0.8444, 0.8111, 0.2578],
    'Agent 3': [0.9053, 0.2269, 0.5958, 1.1620, 1.1987, 1.0917, 0.5685, 0.8173, 0.8635, 0.2041],
    'Agent 4': [0.8802, 0.1888, 0.6535, 1.2068, 1.1538, 1.0472, 0.5239, 0.8516, 0.8695, 0.2574],
    'Agent 5': [0.8221, 0.2246, 0.6755, 1.2632, 1.0990, 1.0595, 0.5392, 0.9096, 0.8240, 0.2679],
    'Agent 6': [0.7885, 0.2847, 0.6432, 1.2763, 1.0910, 1.1151, 0.5965, 0.9340, 0.7689, 0.2272],
    'Agent 7': [0.8164, 0.3112, 0.5846, 1.2341, 1.1384, 1.1570, 0.6361, 0.9029, 0.7620, 0.2706],
    'Agent 8': [0.8750, 0.2865, 0.5589, 1.1762, 1.1914, 1.1457, 0.6231, 0.8444, 0.8111, 0.2578]
}

safety_rates_ours = [0.9988, 0.9988, 0.9967, 0.9953, 0.9955, 0.9960, 0.9955, 0.9959, 0.9962, 0.9965]
safety_rates_lqr = [0.9028, 0.8902, 0.8896, 0.8924, 0.8983, 0.8954, 0.8938, 0.8962, 0.8965, 0.8985]

accuracy = [0.9333287, 0.49911913, 0.93677694, 0.9603538]

# Plot Formation Agent Errors Over Time
plt.figure(figsize=(12, 6))
for agent, errors in formation_errors.items():
    plt.plot(evaluation_steps, errors, label=agent)
plt.xlabel('Evaluation Step')
plt.ylabel('Formation Error')
# plt.title('Formation Errors Over Time')
plt.legend()
plt.grid(True)
plt.show()

# Plot Safety Rates Over Time
plt.figure(figsize=(12, 6))
plt.plot(evaluation_steps, safety_rates_ours, label='Safety Rate (Ours)', marker='o')
plt.plot(evaluation_steps, safety_rates_lqr, label='Safety Rate (LQR)', marker='x')
plt.xlabel('Evaluation Step')
plt.ylabel('Safety Rate')
plt.title('Safety Rates Over Time')
plt.legend()
plt.grid(True)
plt.show()

# Plot Accuracy
plt.figure(figsize=(8, 5))
plt.bar(range(len(accuracy)), accuracy, color=['blue', 'orange', 'green', 'red'])
plt.xticks(range(len(accuracy)), ['Accuracy 1', 'Accuracy 2', 'Accuracy 3', 'Accuracy 4'])
plt.ylabel('Accuracy')
plt.title('Accuracy Values')
plt.grid(True)
plt.show()
