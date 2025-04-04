import numpy as np
import tensorflow as tf

import config

def generate_obstacle_circle(center, radius, num=12):
    theta = np.linspace(0, np.pi*2, num=num, endpoint=False).reshape(-1, 1)
    unit_circle = np.concatenate([np.cos(theta), np.sin(theta)], axis=1)
    circle = np.array(center) + unit_circle * radius
    return circle

def generate_obstacle_rectangle(center, sides, num=12):
    a, b = sides
    n_side_1 = int(num // 2 * a / (a+b))
    n_side_2 = num // 2 - n_side_1
    n_side_3 = n_side_1
    n_side_4 = num - n_side_1 - n_side_2 - n_side_3
    side_1 = np.concatenate([
        np.linspace(-a/2, a/2, n_side_1, endpoint=False).reshape(-1, 1), 
        b/2 * np.ones(n_side_1).reshape(-1, 1)], axis=1)
    side_2 = np.concatenate([
        a/2 * np.ones(n_side_2).reshape(-1, 1),
        np.linspace(b/2, -b/2, n_side_2, endpoint=False).reshape(-1, 1)], axis=1)
    side_3 = np.concatenate([
        np.linspace(a/2, -a/2, n_side_3, endpoint=False).reshape(-1, 1), 
        -b/2 * np.ones(n_side_3).reshape(-1, 1)], axis=1)
    side_4 = np.concatenate([
        -a/2 * np.ones(n_side_4).reshape(-1, 1),
        np.linspace(-b/2, b/2, n_side_4, endpoint=False).reshape(-1, 1)], axis=1)

    rectangle = np.concatenate([side_1, side_2, side_3, side_4], axis=0)
    rectangle = rectangle + np.array(center)
    return rectangle


def generate_data(num_agents, dist_min_thres):
    side_length = np.sqrt(max(1.0, num_agents / 8.0))
    states = np.zeros(shape=(num_agents, 2), dtype=np.float32)
    goals = np.zeros(shape=(num_agents, 2), dtype=np.float32)

    i = 0
    while i < num_agents:
        candidate = np.random.uniform(size=(2,)) * side_length
        dist_min = np.linalg.norm(states - candidate, axis=1).min()
        if dist_min <= dist_min_thres:
            continue
        states[i] = candidate
        i = i + 1

    i = 0
    while i < num_agents:
        candidate = np.random.uniform(-0.5, 0.5, size=(2,)) + states[i]
        dist_min = np.linalg.norm(goals - candidate, axis=1).min()
        if dist_min <= dist_min_thres:
            continue
        goals[i] = candidate
        i = i + 1

    states = np.concatenate(
        [states, np.zeros(shape=(num_agents, 2), dtype=np.float32)], axis=1)
    return states, goals


def formation_data(num_agents, dist_min_thres):
    """Generates initial states and goals for agents with a leader-follower formation."""
    # Check if num_agents is a TensorFlow tensor
    if tf.is_tensor(num_agents):
        # Evaluate the tensor to get a Python integer
        with tf.Session() as sess:
            num_agents = sess.run(num_agents)  # Convert tensor to integer
    else:
        # If num_agents is already an integer, use it directly
        num_agents = int(num_agents)

    leader_position = np.array([0.0, 0.0])
    leader_goal = np.random.uniform(-1.0, 1.0, size=(2,))  # Random goal for leader

    radius = 0.1  # Radius of follower circular formation
    followers_positions = define_circular_formation(num_agents - 1, radius) + leader_position

    assert followers_positions.shape == (num_agents - 1, 2), f"Unexpected shape: {followers_positions.shape}"

    states = np.zeros(shape=(num_agents, 2), dtype=np.float32)
    goals = np.zeros(shape=(num_agents, 2), dtype=np.float32)

    # Assign leader's position and goal
    states[0] = leader_position
    goals[0] = leader_goal

    # Assign followers' positions
    states[1:] = followers_positions
    goals[1:] = followers_positions  # Followers maintain formation

    # Add zero velocity (vx, vy)
    states = np.concatenate([states, np.zeros(shape=(num_agents, 2), dtype=np.float32)], axis=1)

    return states, goals

def define_circular_formation(num_agents, radius):
    # Check if num_agents is a TensorFlow tensor
    if tf.is_tensor(num_agents):
        # Evaluate the tensor to get a Python integer
        with tf.Session() as sess:
            num_agents = sess.run(num_agents)  # Convert tensor to integer
    else:
        # If num_agents is already an integer, use it directly
        num_agents = int(num_agents)

    # Use np.linspace with the evaluated integer
    angles = np.linspace(0.0, 2.0 * np.pi, num_agents)  # Use np.linspace()
    formation = radius * np.column_stack((np.cos(angles), np.sin(angles)))  # Use np.column_stack()
    return formation

def network_action(s, g, obs_radius=1.0, indices=None, leader_idx=0, radius=0.5, desired_formation=None, stop_threshold=0.05):
    """
    Computes actions for agents while maintaining a leader-follower formation.

    stop_threshold: Distance threshold below which the agent stops moving.
    """
    num_agents = tf.shape(s)[0]

    # Compute distance to goals
    distances_to_goal = tf.norm(s[:, :2] - g, axis=1, keepdims=True)

    # Mask: If an agent is within stop_threshold, it should stop moving
    stop_mask = tf.cast(distances_to_goal > stop_threshold, tf.float32)

    # Compute leader velocity
    leader_position = s[leader_idx, :2]
    leader_goal = g[leader_idx]
    leader_velocity = (leader_goal - leader_position)  # Move towards goal

    # Compute desired follower positions
    if desired_formation is None:
        num_followers = num_agents - 1
        follower_desired_positions = define_circular_formation(num_followers, radius) + leader_position
    else:
        follower_desired_positions = desired_formation[1:] + leader_position

    # Compute formation error
    follower_errors = s[1:, :2] - follower_desired_positions
    formation_error = tf.concat([tf.zeros((1, 2)), follower_errors], axis=0)

    # Compute action
    x = tf.expand_dims(s, 1) - tf.expand_dims(s, 0)
    x, _ = remove_distant_agents(x=x, k=config.TOP_K, indices=indices)
    dist = tf.norm(x[:, :, :2], axis=2, keepdims=True)
    mask = tf.cast(tf.less(dist, obs_radius), tf.float32)

    # Action network computation
    x = tf.contrib.layers.conv1d(inputs=x, num_outputs=64, kernel_size=1, reuse=tf.AUTO_REUSE, scope='action/conv_1', activation_fn=tf.nn.relu)
    x = tf.reduce_max(x * mask, axis=1)
    x = tf.concat([x, s[:, :2] - g, s[:, 2:]], axis=1)
    x = tf.contrib.layers.fully_connected(inputs=x, num_outputs=64, reuse=tf.AUTO_REUSE, scope='action/fc_1', activation_fn=tf.nn.relu)
    x = tf.contrib.layers.fully_connected(inputs=x, num_outputs=4, reuse=tf.AUTO_REUSE, scope='action/fc_4', activation_fn=None)
    x = 2.0 * tf.nn.sigmoid(x) + 0.2
    k_1, k_2, k_3, k_4 = tf.split(x, 4, axis=1)

    gain_x = -tf.concat([k_1, tf.zeros_like(k_1), k_2, tf.zeros_like(k_2)], axis=1)
    gain_y = -tf.concat([tf.zeros_like(k_3), k_3, tf.zeros_like(k_4), k_4], axis=1)
    state = tf.concat([s[:, :2] - g, s[:, 2:]], axis=1)

    # Compute acceleration (action) and apply stop mask
    formation_gain = 1.0  # Tune this value
    formation_control = formation_gain * formation_error
    a_x = tf.reduce_sum(state * gain_x, axis=1, keepdims=True) + formation_control[:, 0:1]
    a_y = tf.reduce_sum(state * gain_y, axis=1, keepdims=True) + formation_control[:, 1:2]

    a = tf.concat([a_x, a_y], axis=1) * stop_mask  # Apply stop mask here

    return a

def network_cbf(x, r, indices=None):
    d_norm = tf.sqrt(
        tf.reduce_sum(tf.square(x[:, :, :2]) + 1e-4, axis=2))
    x = tf.concat([x,
        tf.expand_dims(tf.eye(tf.shape(x)[0]), 2),
        tf.expand_dims(d_norm - r, 2)], axis=2)
    x, indices = remove_distant_agents(x=x, k=config.TOP_K, indices=indices)
    dist = tf.sqrt(
        tf.reduce_sum(tf.square(x[:, :, :2]) + 1e-4, axis=2, keepdims=True))
    mask = tf.cast(tf.less_equal(dist, config.OBS_RADIUS), tf.float32)
    x = tf.contrib.layers.conv1d(inputs=x, 
                                 num_outputs=64,
                                 kernel_size=1, 
                                 reuse=tf.AUTO_REUSE,
                                 scope='cbf/conv_1', 
                                 activation_fn=tf.nn.relu)
    x = tf.contrib.layers.conv1d(inputs=x, 
                                 num_outputs=128,
                                 kernel_size=1, 
                                 reuse=tf.AUTO_REUSE,
                                 scope='cbf/conv_2', 
                                 activation_fn=tf.nn.relu)
    x = tf.contrib.layers.conv1d(inputs=x, 
                                 num_outputs=64,
                                 kernel_size=1, 
                                 reuse=tf.AUTO_REUSE,
                                 scope='cbf/conv_3', 
                                 activation_fn=tf.nn.relu)
    x = tf.contrib.layers.conv1d(inputs=x, 
                                 num_outputs=1,
                                 kernel_size=1, 
                                 reuse=tf.AUTO_REUSE,
                                 scope='cbf/conv_4', 
                                 activation_fn=None)
    x = x * mask
    return x, mask, indices


def dynamics(s, a):
    """ The ground robot dynamics.
    
    Args:
        s (N, 4): The current state.
        a (N, 2): The acceleration taken by each agent.
    Returns:
        dsdt (N, 4): The time derivative of s.
    """
    dsdt = tf.concat([s[:, 2:], a], axis=1)
    return dsdt


def loss_barrier(h, s, r, ttc, indices=None, eps=[1e-3, 0]):
    """ Build the loss function for the control barrier functions.

    Args:
        h (N, N, 1): The control barrier function.
        s (N, 4): The current state of N agents.
        r (float): The radius of the safe regions.
        ttc (float): The threshold of time to collision.
    """

    h_reshape = tf.reshape(h, [-1])
    dang_mask = ttc_dangerous_mask(s, r=r, ttc=ttc, indices=indices)
    dang_mask_reshape = tf.reshape(dang_mask, [-1])
    safe_mask_reshape = tf.logical_not(dang_mask_reshape)

    dang_h = tf.boolean_mask(h_reshape, dang_mask_reshape)
    safe_h = tf.boolean_mask(h_reshape, safe_mask_reshape)

    num_dang = tf.cast(tf.shape(dang_h)[0], tf.float32)
    num_safe = tf.cast(tf.shape(safe_h)[0], tf.float32)

    loss_dang = tf.reduce_sum(
        tf.math.maximum(dang_h + eps[0], 0)) / (1e-5 + num_dang)
    loss_safe = tf.reduce_sum(
        tf.math.maximum(-safe_h + eps[1], 0)) / (1e-5 + num_safe)

    acc_dang = tf.reduce_sum(tf.cast(
        tf.less_equal(dang_h, 0), tf.float32)) / (1e-5 + num_dang)
    acc_safe = tf.reduce_sum(tf.cast(
        tf.greater(safe_h, 0), tf.float32)) / (1e-5 + num_safe)

    acc_dang = tf.cond(
        tf.greater(num_dang, 0), lambda: acc_dang, lambda: -tf.constant(1.0))
    acc_safe = tf.cond(
        tf.greater(num_safe, 0), lambda: acc_safe, lambda: -tf.constant(1.0))

    return loss_dang, loss_safe, acc_dang, acc_safe


def loss_derivatives(s, a, h, x, r, ttc, alpha, indices=None, eps=[1e-3, 0]):
    dsdt = dynamics(s, a)
    s_next = s + dsdt * config.TIME_STEP

    x_next = tf.expand_dims(s_next, 1) - tf.expand_dims(s_next, 0)
    h_next, mask_next, _ = network_cbf(x=x_next, r=config.DIST_MIN_THRES, indices=indices)

    deriv = h_next - h + config.TIME_STEP * alpha * h

    deriv_reshape = tf.reshape(deriv, [-1])
    dang_mask = ttc_dangerous_mask(s=s, r=r, ttc=ttc, indices=indices)
    dang_mask_reshape = tf.reshape(dang_mask, [-1])
    safe_mask_reshape = tf.logical_not(dang_mask_reshape)

    dang_deriv = tf.boolean_mask(deriv_reshape, dang_mask_reshape)
    safe_deriv = tf.boolean_mask(deriv_reshape, safe_mask_reshape)

    num_dang = tf.cast(tf.shape(dang_deriv)[0], tf.float32)
    num_safe = tf.cast(tf.shape(safe_deriv)[0], tf.float32)

    loss_dang_deriv = tf.reduce_sum(
        tf.math.maximum(-dang_deriv + eps[0], 0)) / (1e-5 + num_dang)
    loss_safe_deriv = tf.reduce_sum(
        tf.math.maximum(-safe_deriv + eps[1], 0)) / (1e-5 + num_safe)

    acc_dang_deriv = tf.reduce_sum(tf.cast(
        tf.greater_equal(dang_deriv, 0), tf.float32)) / (1e-5 + num_dang)
    acc_safe_deriv = tf.reduce_sum(tf.cast(
        tf.greater_equal(safe_deriv, 0), tf.float32)) / (1e-5 + num_safe)

    acc_dang_deriv = tf.cond(
        tf.greater(num_dang, 0), lambda: acc_dang_deriv, lambda: -tf.constant(1.0))
    acc_safe_deriv = tf.cond(
        tf.greater(num_safe, 0), lambda: acc_safe_deriv, lambda: -tf.constant(1.0))

    return loss_dang_deriv, loss_safe_deriv, acc_dang_deriv, acc_safe_deriv

def loss_actions(s, g, a, desired_formation, r, ttc):
    # Compute formation error
    formation_error = tf.reduce_mean(tf.norm(s[:, :2] - desired_formation, axis=1))
    
    # Reference action (LQR-like controller)
    state_gain = -tf.constant(
        np.eye(2, 4) + np.eye(2, 4, k=2) * np.sqrt(3), dtype=tf.float32)
    s_ref = tf.concat([s[:, :2] - g, s[:, 2:]], axis=1)
    action_ref = tf.linalg.matmul(s_ref, state_gain, False, True)
    
    # Compute the difference between the network's action and the reference action
    action_ref_norm = tf.reduce_sum(tf.square(action_ref), axis=1)
    action_net_norm = tf.reduce_sum(tf.square(a), axis=1)
    norm_diff = tf.abs(action_net_norm - action_ref_norm)
    
    # Total loss: action difference + formation error
    loss = tf.reduce_mean(norm_diff) + formation_error
    return loss


def statics(s, a, h, alpha, indices=None):
    dsdt = dynamics(s, a)
    s_next = s + dsdt * config.TIME_STEP

    x_next = tf.expand_dims(s_next, 1) - tf.expand_dims(s_next, 0)
    h_next, mask_next, _ = network_cbf(x=x_next, r=config.DIST_MIN_THRES, indices=indices)

    deriv = h_next - h + config.TIME_STEP * alpha * h

    mean_deriv = tf.reduce_mean(deriv)
    std_deriv = tf.sqrt(tf.reduce_mean(tf.square(deriv - mean_deriv)))
    prob_neg = tf.reduce_mean(tf.cast(tf.less(deriv, 0), tf.float32))

    return mean_deriv, std_deriv, prob_neg


def ttc_dangerous_mask(s, r, ttc, indices=None):
    s_diff = tf.expand_dims(s, 1) - tf.expand_dims(s, 0)
    s_diff = tf.concat(
        [s_diff, tf.expand_dims(tf.eye(tf.shape(s)[0]), 2)], axis=2)
    s_diff, _ = remove_distant_agents(s_diff, config.TOP_K, indices)
    x, y, vx, vy, eye = tf.split(s_diff, 5, axis=2)
    x = x + eye
    y = y + eye
    alpha = vx ** 2 + vy ** 2
    beta = 2 * (x * vx + y * vy)
    gamma = x ** 2 + y ** 2 - r ** 2
    dist_dangerous = tf.less(gamma, 0)

    has_two_positive_roots = tf.logical_and(
        tf.greater(beta ** 2 - 4 * alpha * gamma, 0),
        tf.logical_and(tf.greater(gamma, 0), tf.less(beta, 0)))
    root_less_than_ttc = tf.logical_or(
        tf.less(-beta - 2 * alpha * ttc, 0),
        tf.less((beta + 2 * alpha * ttc) ** 2, beta ** 2 - 4 * alpha * gamma))
    has_root_less_than_ttc = tf.logical_and(has_two_positive_roots, root_less_than_ttc)
    ttc_dangerous = tf.logical_or(dist_dangerous, has_root_less_than_ttc)

    return ttc_dangerous


def ttc_dangerous_mask_np(s, r, ttc):
    s_diff = np.expand_dims(s, 1) - np.expand_dims(s, 0)
    x, y, vx, vy = np.split(s_diff, 4, axis=2)
    x = x + np.expand_dims(np.eye(np.shape(s)[0]), 2)
    y = y + np.expand_dims(np.eye(np.shape(s)[0]), 2)
    alpha = vx ** 2 + vy ** 2
    beta = 2 * (x * vx + y * vy)
    gamma = x ** 2 + y ** 2 - r ** 2
    dist_dangerous = np.less(gamma, 0)

    has_two_positive_roots = np.logical_and(
        np.greater(beta ** 2 - 4 * alpha * gamma, 0),
        np.logical_and(np.greater(gamma, 0), np.less(beta, 0)))
    root_less_than_ttc = np.logical_or(
        np.less(-beta - 2 * alpha * ttc, 0),
        np.less((beta + 2 * alpha * ttc) ** 2, beta ** 2 - 4 * alpha * gamma))
    has_root_less_than_ttc = np.logical_and(has_two_positive_roots, root_less_than_ttc)
    ttc_dangerous = np.logical_or(dist_dangerous, has_root_less_than_ttc)

    return ttc_dangerous


def remove_distant_agents(x, k, indices=None):
    n, _, c = x.get_shape().as_list()
    if n <= k:
        return x, False
    d_norm = tf.sqrt(tf.reduce_sum(tf.square(x[:, :, :2]) + 1e-6, axis=2))
    if indices is not None:
        x = tf.reshape(tf.gather_nd(x, indices), [n, k, c])
        return x, indices
    _, indices = tf.nn.top_k(-d_norm, k=k)
    row_indices = tf.expand_dims(
        tf.range(tf.shape(indices)[0]), 1) * tf.ones_like(indices)
    row_indices = tf.reshape(row_indices, [-1, 1])
    column_indices = tf.reshape(indices, [-1, 1])
    indices = tf.concat([row_indices, column_indices], axis=1)
    x = tf.reshape(tf.gather_nd(x, indices), [n, k, c])
    return x, indices
