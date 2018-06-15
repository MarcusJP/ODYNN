import tensorflow as tf
from utils import OUT_SETTINGS, set_dir, OUT_PARAMS, plot_loss_rate
from data import FILE_LV, SAVE_PATH
import pickle
import numpy as np

class Optimizer():

    min_loss = 1.

    def __init__(self):
        self.loss_scal = True

    """learning rate and optimization"""
    def build_train(self):
        self.global_step = tf.Variable(0, trainable=False)
        # progressive learning rate
        self.learning_rate = tf.train.exponential_decay(
            self.start_rate,  # Base learning rate.
            self.global_step,  # Current index to the dataset.
            self.decay_step,  # Decay step.
            self.decay_rate,  # Decay rate.
            staircase=True)
        # self.learning_rate = 0.1
        tf.summary.scalar('learning rate', self.learning_rate)
        opt = tf.train.AdamOptimizer(learning_rate=self.learning_rate)

        if(not self.loss_scal):
            loss = self.loss / (self.neuron.num**0.5)
        gvs = opt.compute_gradients(loss)
        grads, vars = zip(*gvs)

        if(self.neuron is not None):
            grads_normed = []
            for i in range(self.neuron.num):
                #clip by norm for each neuron
                gi = [g[i] for g in grads]
                gi_norm, _ = tf.clip_by_global_norm(gi, 5.)
                grads_normed.append(gi_norm)
            grads_normed = np.array(grads_normed)
            #resize to tf format
            grads_normed = [tf.stack([grads_normed[neur, var] for neur in range(grads_normed.shape[0])]) for var in range(grads_normed.shape[1])]
        else:
            grads_normed, _ = tf.clip_by_global_norm(grads, 5.)
        self.train_op = opt.apply_gradients(zip(grads_normed, vars), global_step=self.global_step)

        self.saver = tf.train.Saver()

    """initialize objects to be optimized and write setting in the directory"""
    def init(self, subdir, suffix, l_rate, w, neur=None, circuit=None):
        self.suffix = suffix
        self.dir = set_dir(subdir + '/')
        tf.reset_default_graph()
        assert(neur is not None or circuit is not None)
        if(circuit is not None):
            circuit.reset()
            circuit.neurons.reset()
        else:
            neur.reset()
        self.start_rate, self.decay_step, self.decay_rate = l_rate
        if(circuit is not None):
            self.write_settings(subdir, circuit.neurons, w, circuit)
        else:
            self.write_settings(subdir, neur, w)


    def write_settings(self, dir, neur, w, circuit=None):
        with open('%s%s_%s.txt' % (self.dir, OUT_SETTINGS, self.suffix), 'w') as f:
            if(circuit is not None):
                f.write('Circuit optimization'.center(20, '.') + '\n')
                f.write('Connections : \n %s \n %s' % (circuit.pres, circuit.posts) + '\n' +
                        'Initial synaptic params : %s' % circuit.connections + '\n')
            f.write('Neuron optimization'.center(20, '.') + '\n')
            f.write('Nb of neurons : %s' % neur.num + '\n' +
                    'Initial neuron params : %s' % neur.init_p + '\n'+
                    'Fixed variables : %s' % [c for c in neur.fixed] + '\n'+
                    'Initial state : %s' % neur.init_state + '\n' +
                    'Constraints : %s' % neur.constraints_dic + '\n' +
                    'Model solver : %s' % neur.loop_func + '\n' +
                    'dt : %s' % neur.dt + '\n' +
                    'Weights (out, cac) : %s' % w + '\n' +
                    'Start rate : %s, decay_step : %s, decay_rate : %s' % (self.start_rate, self.decay_step, self.decay_rate) + '\n')

    """train the model and collect loss, learn_rate and variables"""
    def train_and_gather(self, sess, i, losses, rates, vars):
        results, _, train_loss = sess.run([self.res, self.train_op, self.loss], feed_dict={
            self.xs_: self.X,
            self.ys_: np.array([self.V, self.Ca]),
            self.init_state_: self.init_state
        })
        _ = sess.run(self.optimized.constraints)

        with open('%s%s_%s.txt' % (self.dir, OUT_PARAMS, self.suffix), 'w') as f:
            for name, v in self.optimized.param.items():
                v_ = sess.run(v)
                f.write('%s : %s\n' % (name, v_))
                vars[name][i + 1] = v_

        rates[i] = sess.run(self.learning_rate)
        losses[i] = train_loss
        if(not self.loss_scal):
            train_loss = np.mean(train_loss)
        print('[{}] loss : {}'.format(i, train_loss))
        return results

    def plots_dump(self, sess, losses, rates, vars, i):
        with (open(self.dir + FILE_LV, 'wb')) as f:
            pickle.dump([losses, rates, vars], f)
        plot_loss_rate(losses[:i + 1], rates[:i + 1], suffix=self.suffix, show=False, save=True)
        self.saver.save(sess, '%s%s' % (self.dir, SAVE_PATH))
        self.plot_vars(dict([(name, val[:i + 2]) for name, val in vars.items()]), suffix=self.suffix+'evolution', show=False,
                  save=True)