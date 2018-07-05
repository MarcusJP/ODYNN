"""
.. module:: optimize
    :synopsis: Module containing classes for optimization with Tensorflow

.. moduleauthor:: Marc Javin
"""

import pickle
import time
from abc import ABC, abstractmethod

import numpy as np
import tensorflow as tf
from tqdm import tqdm

from .utils import plots_output_double, OUT_SETTINGS, set_dir, OUT_PARAMS
from . import utils
import pylab as plt

SAVE_PATH = 'tmp/model.ckpt'
FILE_LV = 'tmp/dump_lossratevars'
FILE_CIRC = 'tmp/circuit'

class Optimized(ABC):
    """
    Abstract class for object to be optimized. It could represent on or a set of neurons, or a circuit.
    """

    def __init__(self, dt):
        self.dt = dt
        self.init_p = {}

    @abstractmethod
    def build_graph(self):
        """
        Build the tensorflow graph. Take care of the loop and the initial state.
        Returns
        -------
        tf.placeholder, for input current.
        """
        pass

    @abstractmethod
    def settings(self):
        """
        Return a string describing the parameters of the object
        """
        pass

    @staticmethod
    def plot_vars(var_dic, suffix, show, save):
        """A function to plot the variables of the optimized object"""
        pass

    def apply_constraints(self, session):
        """Return a tensorflow operation applying constraints to the variables"""
        pass

    def get_params(self):
        """Return the variables parameters names of the optimized object"""
        return []


class Optimizer(ABC):
    min_loss = 1.

    def __init__(self, optimized, epochs=500, frequency=10):
        self.start_time = time.time()
        self.optimized = optimized
        self.parallel = self.optimized.num
        self._epochs = epochs
        self._frequency = frequency
        self._test_losses = None
        self._test = False

    def _init_l_rate(self):
        self.global_step = tf.Variable(0, trainable=False)
        # progressive learning rate
        self.learning_rate = tf.train.exponential_decay(
            self.start_rate,  # Base learning rate.
            self.global_step,  # Current index to the dataset.
            self.decay_step,  # Decay step.
            self.decay_rate,  # Decay rate.
            staircase=True)

    def _build_train(self):
        """learning rate and optimization"""
        self._init_l_rate()
        # self.learning_rate = 0.1
        tf.summary.scalar("learning rate", self.learning_rate)
        opt = tf.train.AdamOptimizer(learning_rate=self.learning_rate)

        gvs = opt.compute_gradients(self.loss)
        grads, vars = zip(*gvs)

        if self.parallel > 1:
            grads_normed = []
            for i in range(self.parallel):
                # clip by norm for each parallel model (neuron or circuit)
                gi = [g[..., i] for g in grads]
                # if isinstance(self.optimized, Circuit.Circuit):
                #     #[synapse, model]
                #     gi = [g[:,i] for g in grads]
                # else:
                #     gi = [g[i] for g in grads]
                gi_norm, _ = tf.clip_by_global_norm(gi, 5.)
                grads_normed.append(gi_norm)
            grads_normed = tf.stack(grads_normed)
            # resize to tf format
            try:  # for circuits
                grads_normed = tf.transpose(grads_normed, perm=[1, 2, 0])
                grads_normed = tf.unstack(grads_normed, axis=0)
            except:
                grads_normed = tf.unstack(grads_normed, axis=1)
        else:
            grads_normed, _ = tf.clip_by_global_norm(grads, 5.)
        self.train_op = opt.apply_gradients(zip(grads_normed, vars), global_step=self.global_step)

        self.saver = tf.train.Saver()

    def _init(self, subdir, suffix, train, test, l_rate, w, yshape):
        """
        Initialize directory and the object to be optimized, get the dataset, write settings in the directory
        and initialize placeholders for target output and results.
        """
        self.suffix = suffix
        self.dir = set_dir(subdir + "/")
        tf.reset_default_graph()
        self.start_rate, self.decay_step, self.decay_rate = l_rate

        self._T, self._X, self._V, self._Ca = train
        if test is not None:
            self._test = True
            self._test_losses = []
            self._T_test, self._X_test, self._V_test, self._Ca_test = test
            assert (self.optimized.dt == self._T_test[1] - self._T_test[0])
        assert (self.optimized.dt == self._T[1] - self._T[0])

        self.n_batch = self._X.shape[1]
        self.write_settings(w)

        if self.parallel > 1:
            # add dimension for neurons trained in parallel
            # [time, n_batch, neuron]
            self._X = np.stack([self._X for _ in range(self.parallel)], axis=self._X.ndim)
            self._V = np.stack([self._V for _ in range(self.parallel)], axis=self._V.ndim)
            self._Ca = np.stack([self._Ca for _ in range(self.parallel)], axis=self._Ca.ndim)

            if self._test:
                self._X_test = np.stack([self._X_test for _ in range(self.parallel)], axis=self._X_test.ndim)
                self._V_test = np.stack([self._V_test for _ in range(self.parallel)], axis=self._V_test.ndim)
                self._Ca_test = np.stack([self._Ca_test for _ in range(self.parallel)], axis=self._Ca_test.ndim)
            yshape.append(self.parallel)

        self.xs_, self.res = self.optimized.build_graph(batch=self.n_batch)
        self.ys_ = tf.placeholder(shape=yshape, dtype=tf.float32, name="voltage_Ca")

        print("i expected : ", self.xs_.shape)
        print("i : ", self._X.shape, "V : ", self._V.shape)

    def write_settings(self, w):
        """Write the settings of the optimization in a file"""
        with open(self.dir + OUT_SETTINGS, 'w') as f:
            f.write("Weights (out, cac) : {}".format(w) + "\n" +
                    "Start rate : {}, decay_step : {}, decay_rate : {}".format(self.start_rate, self.decay_step,
                                                                               self.decay_rate) + "\n" +
                    "Number of batches : {}".format(self.n_batch) + "\n" +
                    "Number of time steps : {}".format(self._T.shape) + "Input current shape : {}".format(
                self._X.shape) +
                    "Output voltage shape : {}".format(self._V.shape) + "\n" +
                    self.optimized.settings())


    def _train_and_gather(self, sess, i, losses, rates, vars):
        """Train the model and collect loss, learn_rate and variables"""
        summ, results, _, train_loss = sess.run([self.summary, self.res, self.train_op, self.loss], feed_dict={
            self.xs_: self._X,
            self.ys_: np.array([self._V, self._Ca])
        })

        self.tdb.add_summary(summ, i)

        self.optimized.apply_constraints(sess)

        with open("{}{}_{}.txt".format(self.dir, OUT_PARAMS, self.suffix), 'w') as f:
            for name, v in self.optimized.get_params():
                v_ = sess.run(v)
                f.write("{} : {}\n".format(name, v_))
                vars[name][i + 1] = v_

        rates[i] = sess.run(self.learning_rate)
        losses[i] = train_loss
        if self.parallel > 1:
            train_loss = np.nanmean(train_loss)
        print("[{}] loss : {}".format(i, train_loss))
        return results

    def _plots_dump(self, sess, losses, rates, vars, i):
        """Plot the variables evolution, the loss and saves it in a file"""
        results = None
        if self._test:
            test_loss, results = sess.run([self.loss, self.res], feed_dict={
                self.xs_: self._X_test,
                self.ys_: np.array([self._V_test, self._Ca_test])
            })
            self._test_losses.append(test_loss)


        with (open(self.dir + FILE_LV + self.suffix, 'wb')) as f:
            pickle.dump([losses, self._test_losses, rates, vars], f)

        plot_loss_rate(losses[:i + 1], rates[:i + 1], losses_test=self._test_losses, suffix=self.suffix, show=False, save=True)
        self.saver.save(sess, "{}{}{}".format(self.dir, SAVE_PATH, self.suffix))

        self.optimized.plot_vars(dict([(name, val[:i + 2]) for name, val in vars.items()]),
                                 suffix=self.suffix + "evolution", show=False,
                                 save=True)
        return results

    def optimize(self, subdir, train=None, test=None, w=[1, 0], l_rate=[0.1, 9, 0.92], suffix='', step='',
                 reload=False, reload_dir=None):

        print(suffix, step)
        T, X, V, Ca = train
        if test is not None:
            T_test, X_test, V_test, Ca_test = test

        yshape = [2, None, None]
        if reload_dir is None:
            reload_dir = subdir
        self._init(subdir, suffix, train, test, l_rate, w, yshape)

        self._build_loss(w)
        self._build_train()
        self.summary = tf.summary.merge_all()

        with tf.Session() as sess:

            self.tdb = tf.summary.FileWriter(self.dir + '/tensorboard',
                                             sess.graph)

            sess.run(tf.global_variables_initializer())
            losses = np.zeros((self._epochs, self.parallel))
            rates = np.zeros(self._epochs)

            if reload:
                """Get variables and measurements from previous steps"""
                self.saver.restore(sess, '%s/%s' % (utils.RES_DIR + reload_dir, SAVE_PATH))
                with open(utils.RES_DIR + reload_dir + '/' + FILE_LV, 'rb') as f:
                    l, self._test_losses, r, vars = pickle.load(f)
                losses = np.concatenate((l, losses))
                rates = np.concatenate((r, rates))
                sess.run(tf.assign(self.global_step, 200))
                len_prev = len(l)
            else:
                vars = {var : [val] for var, val in self.optimized.init_p.items()}
                len_prev = 0

            vars = dict([(var, np.vstack((val, np.zeros((self._epochs, self.parallel))))) for var, val in vars.items()])

            for i in tqdm(range(self._epochs)):
                results = self._train_and_gather(sess, len_prev + i, losses, rates, vars)

                # if losses[len_prev+i]<self.min_loss:
                #     self.plots_dump(sess, losses, rates, vars, len_prev + i)
                #     return i+len_prev

                # for b in range(self.n_batch):
                #     plots_output_double(self._T, X[:, b], results[:, V_pos, b], V[:, b], results[:, Ca_pos, b],
                #                         Ca[:, b], suffix='%s_train%s_%s_%s' % (suffix, b, step, i + 1), show=False,
                #                         save=True, l=0.7, lt=2)
                #
                # if i % self._frequency == 0 or i == self._epochs - 1:
                #     res_test = self._plots_dump(sess, losses, rates, vars, len_prev + i)
                #     if res_test is not None:
                #         for b in range(self.n_batch):
                #             plots_output_double(self._T, X_test[:, b], res_test[:, V_pos, b], V_test[:, b], res_test[:, Ca_pos, b],
                #                                 Ca_test[:, b], suffix='%s_test%s_%s_%s' % (suffix, b, step, i + 1),
                #                                 show=False,
                #                                 save=True, l=0.7, lt=2)

            with open(self.dir + 'time', 'w') as f:
                f.write(str(time.time() - self.start_time))

        return -1




def get_vars(dir, i=-1):
    """get dic of vars from dumped file"""
    file = utils.RES_DIR + dir + '/' + FILE_LV
    with open(file, 'rb') as f:
        l,r,dic = pickle.load(f)
        dic = dict([(var, np.array(val[i], dtype=np.float32)) for var, val in dic.items()])
    return dic


def get_vars_all(dir, i=-1):
    """get dic of vars from dumped file"""
    file = utils.RES_DIR + dir + '/' + FILE_LV
    with open(file, 'rb') as f:
        l,r,dic = pickle.load(f)
        dic = dict([(var, val[:i]) for var, val in dic.items()])
    return dic


def get_best_result(dir, i=-1):
    """Return parameters of the best optimized model"""
    file = utils.RES_DIR + dir + '/' + FILE_LV
    with open(file, 'rb') as f:
        l, r, dic = pickle.load(f)
        idx = np.nanargmin(l[-1])
        dic = dict([(var, val[i,idx]) for var, val in dic.items()])
    return dic


def plot_loss_rate(losses, rates, losses_test=None, parallel=1, suffix="", show=True, save=False):
    """plot loss (log10) and learning rate"""
    plt.figure()

    n_p = 2

    plt.ylabel('Test Loss')
    plt.yscale('log')

    plt.subplot(n_p,1,1)
    if parallel == 1:
        plt.plot(losses, 'r', linewidth=0.6, label='Train')
    else:
        plt.plot(losses, linewidth=0.6, label='Train')
    if losses_test is not None:
        losses_test = np.array(losses_test)
        pts = np.linspace(0, losses.shape[0]-1, num=losses_test.shape[0], endpoint=True)
        if parallel == 1:
            plt.plot(pts, losses_test, 'Navy', linewidth=0.6, label='Test')
        else:
            # add another subplot for readability
            n_p = 3
            plt.ylabel('Loss')
            plt.yscale('log')
            plt.legend()
            plt.subplot(n_p,1,2)
            plt.plot(pts, losses_test, linewidth=0.6, label='Test')
    plt.ylabel('Loss')
    plt.yscale('log')
    plt.legend()

    plt.subplot(n_p,1,n_p)
    plt.plot(rates)
    plt.ylabel('Learning rate')

    if save:
        plt.savefig('{}losses_{}.png'.format(utils.current_dir, suffix), dpi=300)
    if show:
        plt.show()
    plt.close()
