import os
os.environ["CUDA_VISIBLE_DEVICES"]="-1"
from Hodghux import HodgkinHuxley
import tensorflow as tf
import numpy as np
from utils import  plots_output_double, OUT_SETTINGS, OUT_PARAMS, plot_loss_rate, get_data_dump, set_dir, plot_vars

import params
from tqdm import tqdm
import time


NB_SER = 15
BATCH_SIZE = 60

DECAY_STEP = 10
START_RATE = 1.
DECAY_RATE = 0.95
EPOCHS = 200



class HH_opt(HodgkinHuxley):
    """Full Hodgkin-Huxley Model implemented in Python"""


    def __init__(self, init_p=params.PARAMS_RAND, init_state=params.INIT_STATE, consts=[]):
        HodgkinHuxley.__init__(self, init_p, init_state, tensors=True, consts=consts)


    def condition(self, hprev, x, dt, index, mod):
        return tf.less(index * dt, self.DT)


    def step_long(self, hprev, x):
        index = tf.constant(0.)
        h = tf.while_loop(self.condition, self.loop_func, (hprev, x, self.dt, index, self))
        return h

    def step(self, hprev, x):
        return self.loop_func(hprev, x, self.DT, self)

    def step_test(self, X, i):
        return self.loop_func(X, i, self.dt, self)

    def test(self):

        ts_ = tf.placeholder(shape=[None], dtype=tf.float32)
        init_state = tf.placeholder(shape=[len(self.init_state)], dtype=tf.float32)
        res = tf.scan(self.step_test,
                      self.i_inj,
                      initializer=init_state)

        with tf.Session() as sess:
            sess.run(tf.global_variables_initializer())
            start = time.time()
            results = sess.run(res, feed_dict={
                ts_: self.t,
                init_state: np.array(self.init_state)
            })
            print('time spent : %.2f s' % (time.time() - start))


    def Main(self, subdir, w=[1,0], sufix=''):
        DIR = set_dir(subdir+'/')

        with open('%s%s_%s.txt' % (DIR, OUT_SETTINGS, sufix), 'w') as f:
            f.write('Initial params : %s' % self.init_p + '\n'+
                    'Initial state : %s' % self.init_state + '\n' +
                    'Model solver : %s' % self.loop_func + '\n' +
                    'Weights (out, cac) : %s' % w + '\n' +
                    'Start rate : %s, decay_step : %s, decay_rate : %s' % (START_RATE, DECAY_STEP, DECAY_RATE) + '\n')

        self.T, self.X, self.V, self.Ca = get_data_dump()
        self.DT = params.DT
        # inputs
        xs_ = tf.placeholder(shape=[None], dtype=tf.float32)
        ys_ = tf.placeholder(shape=[2, None], dtype=tf.float32)
        init_state = tf.placeholder(shape=[len(self.init_state)], dtype=tf.float32)

        res = tf.scan(self.step,
                      xs_,
                     initializer=init_state)

        cac = res[:, -1]
        out = res[:, 0]
        losses = w[0]*tf.square(tf.subtract(out, ys_[0])) + w[1]*tf.square(tf.subtract(cac, ys_[-1]))
        loss = tf.reduce_mean(losses)

        global_step = tf.Variable(0, trainable=False)
        learning_rate = tf.train.exponential_decay(
            START_RATE,  # Base learning rate.
            global_step,  # Current index into the dataset.
            DECAY_STEP,  # Decay step.
            DECAY_RATE,  # Decay rate.
            staircase=True)
        opt = tf.train.AdamOptimizer(learning_rate=learning_rate)
        grads = opt.compute_gradients(loss)
        grads = [(tf.clip_by_value(grad, -50., 50.), var) for grad, var in grads]
        train_op = opt.apply_gradients(grads, global_step=global_step)

        if('e__tau' not in self.consts):
            c_e = tf.assign(self.param['e__tau'], tf.clip_by_value(self.param['e__tau'], 1e-3, np.infty))
            c_e2 = tf.assign(self.param['e__scale'], tf.clip_by_value(self.param['e__scale'], 1e-3, np.infty))
            c_f = tf.assign(self.param['f__tau'], tf.clip_by_value(self.param['f__tau'], 1e-3, np.infty))
            c_f2 = tf.assign(self.param['f__scale'], tf.clip_by_value(self.param['f__scale'], -np.infty, -1e-3))
            c_h = tf.assign(self.param['h__alpha'], tf.clip_by_value(self.param['h__alpha'], 0., 1.))
            c_h2 = tf.assign(self.param['h__scale'], tf.clip_by_value(self.param['h__scale'], -np.infty, -1e-3))
            c_ca = tf.assign(self.param['g_Ca'], tf.clip_by_value(self.param['g_Ca'], 1e-5, np.infty))
            constraints = tf.stack([c_e, c_e2, c_f, c_f2, c_h, c_h2, c_ca], 0)
        else:
            c_p = tf.assign(self.param['p__tau'], tf.clip_by_value(self.param['p__tau'], 1e-3, np.infty))
            c_p2 = tf.assign(self.param['p__scale'], tf.clip_by_value(self.param['p__scale'], 1e-3, np.infty))
            c_q = tf.assign(self.param['q__tau'], tf.clip_by_value(self.param['q__tau'], 1e-3, np.infty))
            c_q2 = tf.assign(self.param['q__scale'], tf.clip_by_value(self.param['q__scale'], 1e-3, np.infty))
            c_n = tf.assign(self.param['n__tau'], tf.clip_by_value(self.param['n__tau'], 1e-3, np.infty))
            c_n2 = tf.assign(self.param['n__scale'], tf.clip_by_value(self.param['n__scale'], 1e-3, np.infty))
            c_kf = tf.assign(self.param['g_Kf'], tf.clip_by_value(self.param['g_Kf'], 1e-5, np.infty))
            c_ks = tf.assign(self.param['g_Ks'], tf.clip_by_value(self.param['g_Ks'], 1e-5, np.infty))
            c_l = tf.assign(self.param['g_L'], tf.clip_by_value(self.param['g_L'], 1e-5, np.infty))
            constraints = tf.stack([c_p, c_p2, c_q, c_q2, c_n, c_n2, c_kf, c_ks, c_l], 0)



        losses = np.zeros(EPOCHS)
        rates = np.zeros(EPOCHS)

        vars = {}
        for v in self.param.keys():
            vars[v] = np.zeros(EPOCHS)

        with tf.Session() as sess:
            sess.run(tf.global_variables_initializer())

            for i in tqdm(range(EPOCHS)):
                results, _, train_loss = sess.run([res, train_op, loss], feed_dict={
                    xs_: self.X,
                    ys_: np.vstack((self.V, self.Ca)),
                    init_state: self.init_state
                })
                _ = sess.run(constraints)

                with open(DIR + OUT_PARAMS, 'w') as f:

                    for name, v in self.param.items():
                        v_ = sess.run(v)
                        vars[name][i] = v_
                        f.write('%s : %s\n' % (name, v_))

                rates[i] = sess.run(learning_rate)
                losses[i] = train_loss
                print('[{}] loss : {}'.format(i, train_loss))
                train_loss = 0

                plots_output_double(self.T, self.X, results[:,0], self.V, results[:,-1], self.Ca, suffix='%s_%s'%(sufix, i + 1), show=False, save=True)
                if(i%10==0):
                    plot_vars(vars, i, suffix=sufix, show=False, save=True)
                    plot_loss_rate(losses, rates, i, suffix=sufix, show=False, save=True)



if __name__ == '__main__':
    runner = HH_opt()
    runner.loop_func = runner.integ_comp
    runner.Main('test')
