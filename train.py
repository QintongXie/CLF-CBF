import sys
sys.dont_write_bytecode = True

import os
import h5py
import argparse
import numpy as np
import tensorflow as tf

import core
import config

import matplotlib.pyplot as plt
import matplotlib.animation as animation

np.set_printoptions(4)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--num_agents', type=int, required=True)
    parser.add_argument('--model_path', type=str, default=None)
    parser.add_argument('--gpu', type=str, default='0')
    args = parser.parse_args()
    return args


def build_optimizer(loss):
    optimizer = tf.train.AdamOptimizer(learning_rate=config.LEARNING_RATE)
    trainable_vars = tf.trainable_variables()

    accumulators = [tf.Variable(tf.zeros_like(tv.initialized_value()), trainable=False) for tv in trainable_vars]
    accumulation_counter = tf.Variable(0.0, trainable=False)
    grad_pairs = optimizer.compute_gradients(loss, trainable_vars)

    accumulate_ops = [accumulator.assign_add(grad) for (accumulator, (grad, var)) in zip(accumulators, grad_pairs)]
    accumulate_ops.append(accumulation_counter.assign_add(1.0))

    gradient_vars = [(accumulator / accumulation_counter, var) for (accumulator, (grad, var)) in zip(accumulators, grad_pairs)]
    
    gradient_vars_h = [(accumulate_grad, var) for accumulate_grad, var in gradient_vars if 'cbf' in var.name]
    gradient_vars_a = [(accumulate_grad, var) for accumulate_grad, var in gradient_vars if 'action' in var.name]

    train_step_h = optimizer.apply_gradients(gradient_vars_h)
    train_step_a = optimizer.apply_gradients(gradient_vars_a)

    zero_ops = [accumulator.assign(tf.zeros_like(tv)) for (accumulator, tv) in zip(accumulators, trainable_vars)]
    zero_ops.append(accumulation_counter.assign(0.0))
    
    return zero_ops, accumulate_ops, train_step_h, train_step_a


def build_training_graph(num_agents):
    num_agents = int(num_agents)  # Convert to Python integer before passing
    s = tf.placeholder(tf.float32, [num_agents, 4])
    g = tf.placeholder(tf.float32, [num_agents, 2])
    
    x = tf.expand_dims(s, 1) - tf.expand_dims(s, 0)
    h, mask, indices = core.network_cbf(x=x, r=config.DIST_MIN_THRES, indices=None)
    a = core.network_action(s=s, g=g, obs_radius=config.OBS_RADIUS, indices=indices)

    (loss_dang, loss_safe, acc_dang, acc_safe) = core.loss_barrier(h=h, s=s, r=config.DIST_MIN_THRES, 
                                                                    ttc=config.TIME_TO_COLLISION, indices=indices)
    (loss_dang_deriv, loss_safe_deriv, acc_dang_deriv, acc_safe_deriv) = core.loss_derivatives(
        s=s, a=a, h=h, x=x, r=config.DIST_MIN_THRES, indices=indices, 
        ttc=config.TIME_TO_COLLISION, alpha=config.ALPHA_CBF)

    # Define desired formation (e.g., a circular formation)
    desired_formation = core.define_circular_formation(num_agents, radius=0.5)  # Example formation
    desired_relative_positions = np.expand_dims(desired_formation, 1) - np.expand_dims(desired_formation, 0)

    # Compute loss_action using the loss_actions function
    loss_action = core.loss_actions(s=s, g=g, a=a, desired_formation=desired_formation, 
                                    r=config.DIST_MIN_THRES, ttc=config.TIME_TO_COLLISION)

    # Formation loss: Encourage agents to maintain relative formation
    actual_relative_positions = tf.expand_dims(s[:, :2], 1) - tf.expand_dims(s[:, :2], 0)
    loss_formation = tf.reduce_mean(tf.square(actual_relative_positions - desired_relative_positions))

    # Combine all loss terms
    loss_list = [2 * loss_dang, loss_safe, 2 * loss_dang_deriv, loss_safe_deriv, 0.01 * loss_action, 0.1 * loss_formation]
    acc_list = [acc_dang, acc_safe, acc_dang_deriv, acc_safe_deriv]

    # Add weight decay to the loss
    weight_loss = [config.WEIGHT_DECAY * tf.nn.l2_loss(v) for v in tf.trainable_variables()]
    loss = 10 * tf.math.add_n(loss_list + weight_loss)

    return s, g, a, loss_list, loss, acc_list

def count_accuracy(accuracy_lists):
    acc = np.array(accuracy_lists)
    acc_list = [np.mean(acc[acc[:, i] >= 0, i]) for i in range(acc.shape[1])]
    return acc_list


def main():
    args = parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu

    # Build the training graph
    s_train, g_train, a_train, loss_list_train, loss_train, acc_list_train = build_training_graph(args.num_agents)
    zero_ops, accumulate_ops, train_step_h, train_step_a = build_optimizer(loss_train)
    accumulate_ops.append(loss_list_train)
    accumulate_ops.append(acc_list_train)

    accumulation_steps = config.INNER_LOOPS

    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        saver = tf.train.Saver()

        if args.model_path:
            saver.restore(sess, args.model_path)

        state_gain = np.eye(2, 4) + np.eye(2, 4, k=2) * np.sqrt(3)

        loss_lists_np, acc_lists_np, dist_errors_np, init_dist_errors_np = [], [], [], []
        safety_ratios_epoch, safety_ratios_epoch_lqr = [], []
        
        for istep in range(config.TRAIN_STEPS):
            s_np, g_np = core.generate_data(args.num_agents, config.DIST_MIN_THRES)
            s_np_lqr, g_np_lqr = np.copy(s_np), np.copy(g_np)
            init_dist_errors_np.append(np.mean(np.linalg.norm(s_np[:, :2] - g_np, axis=1)))
            sess.run(zero_ops)

            for i in range(accumulation_steps):
                a_np, out = sess.run([a_train, accumulate_ops], feed_dict={s_train: s_np, g_train: g_np})
                if np.random.uniform() < config.ADD_NOISE_PROB:
                    noise = np.random.normal(size=np.shape(a_np)) * config.NOISE_SCALE
                    a_np += noise
                
                s_np += np.concatenate([s_np[:, 2:], a_np], axis=1) * config.TIME_STEP
                safety_ratio = 1 - np.mean(core.ttc_dangerous_mask_np(s_np, config.DIST_MIN_CHECK, config.TIME_TO_COLLISION_CHECK), axis=1)
                safety_ratios_epoch.append(np.mean(safety_ratio == 1))

                loss_list_np, acc_list_np = out[-2], out[-1]
                loss_lists_np.append(loss_list_np)
                acc_lists_np.append(acc_list_np)
                
                if np.mean(np.linalg.norm(s_np[:, :2] - g_np, axis=1)) < config.DIST_MIN_CHECK:
                    break

            for i in range(accumulation_steps):
                s_ref_lqr = np.concatenate([s_np_lqr[:, :2] - g_np_lqr, s_np_lqr[:, 2:]], axis=1)
                a_lqr = -s_ref_lqr.dot(state_gain.T)
                s_np_lqr += np.concatenate([s_np_lqr[:, 2:], a_lqr], axis=1) * config.TIME_STEP
                s_np_lqr[:, :2] = np.clip(s_np_lqr[:, :2], 0, 1)

                safety_ratio_lqr = 1 - np.mean(core.ttc_dangerous_mask_np(s_np_lqr, config.DIST_MIN_CHECK, config.TIME_TO_COLLISION_CHECK), axis=1)
                safety_ratios_epoch_lqr.append(np.mean(safety_ratio_lqr == 1))

                if np.mean(np.linalg.norm(s_np_lqr[:, :2] - g_np_lqr, axis=1)) < config.DIST_MIN_CHECK:
                    break

            dist_errors_np.append(np.mean(np.linalg.norm(s_np[:, :2] - g_np, axis=1)))

            if istep // 10 % 2 == 0:
                sess.run(train_step_h)
            else:
                sess.run(train_step_a)
            
            if istep % config.DISPLAY_STEPS == 0:
                print(f'Step: {istep}, Loss: {np.mean(loss_lists_np, axis=0)}, Accuracy: {count_accuracy(acc_lists_np)}')
                loss_lists_np, acc_lists_np, dist_errors_np, safety_ratios_epoch, safety_ratios_epoch_lqr = [], [], [], [], []

            if istep % config.SAVE_STEPS == 0 or istep + 1 == config.TRAIN_STEPS:
                saver.save(sess, f'models/model_iter_{istep}')

if __name__ == '__main__':
    main()