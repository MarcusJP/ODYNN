from unittest import TestCase
from context import odynn
import odynn.circuit as cr
import odynn.datas
from odynn import utils
import numpy as np
from odynn import optim
from odynn.coptim import CircuitOpt
import odynn.csimul as csim
import odynn.neuron as nr
import tensorflow as tf

n_neuron = 2
conns = {(0, 1): odynn.circuit.SYNAPSE_inhib,
         (1, 0): odynn.circuit.SYNAPSE_inhib}
conns_opt = {(0, 1): odynn.circuit.get_syn_rand(False),
             (1, 0): odynn.circuit.get_syn_rand(False)}
conns_opt_parallel = [conns_opt for _ in range(10)]
dir = 'unittest/'
dir = utils.set_dir(dir)

dt = 0.5
t, i = odynn.datas.give_train(dt=dt, max_t=5.)
length = int(5./0.5)
i_1 = np.zeros(i.shape)
i_injs = np.stack([i, i_1], axis=2)
i_injs3 = np.stack([i, i_1, i_1], axis=2)

p = nr.PyBioNeuron.get_random()
pars = [p for _ in range(n_neuron)]
plot = False
evol_var = False

class TestCircuitOpt(TestCase):

    def test_loss(self):
        pars = [p for _ in range(n_neuron)]
        conns_opt = {(0, 1): odynn.circuit.get_syn_rand(False),
                     (1, 0): odynn.circuit.get_syn_rand(False)}
        co = CircuitOpt(cr.CircuitTf(nr.BioNeuronTf(pars, dt=dt), synapses=conns_opt))
        res = tf.zeros((len(t), len(nr.PyBioNeuron.default_init_state), 3, n_neuron))
        ys_ = [tf.placeholder(shape=(len(t), 3, n_neuron), dtype=tf.float32, name="test")] + [tf.placeholder(shape=(len(t), 3, n_neuron), dtype=tf.float32, name="test") for _ in nr.PyBioNeuron.ions.items()]
        w = [1] + [1 for _ in nr.PyBioNeuron.ions.items()]
        co.n_out = list(range(n_neuron))
        co._build_loss(res, ys_, w)

    def test_settings(self):
        pars = [p for _ in range(n_neuron)]
        conns_opt = {(0, 1): odynn.circuit.get_syn_rand(False),
                     (1, 0): odynn.circuit.get_syn_rand(False)}
        co = CircuitOpt(cr.CircuitTf(nr.BioNeuronTf(pars, dt=dt), synapses=conns_opt))
        train = [np.zeros(2), np.zeros(2), [None, None, np.zeros(4)]]
        co.l_rate = (0.1,0.1,0.1)
        co.n_batch = 3
        w = (1.,0)
        co.settings(w, train)

    def test_opt_circuits(self):
        print('one target'.center(40, '#'))
        n_out = [1]
        train = csim.simul(t=t, i_injs=i_injs, pars=pars, synapses=conns, n_out=n_out, show=False)
        co = CircuitOpt(cr.CircuitTf(nr.BioNeuronTf(pars, dt=dt), synapses=conns_opt))
        co.optimize(dir, n_out=n_out, train=train, epochs=1, plot=plot)
        optim.get_best_result(dir)

        self.assertEqual(co._loss.shape, ())

        print('one target parallel'.center(40, '#'))
        co = CircuitOpt(cr.CircuitTf(nr.BioNeuronTf(n_rand=n_neuron, dt=dt), synapses=conns_opt_parallel))
        co.optimize(dir, n_out=n_out, train=train, test=train, epochs=1, plot=plot, evol_var=evol_var)
        self.assertEqual(co._loss.shape, (10,))

        print('several targets'.center(40, '#'))
        n_out = [0, 1]
        train = csim.simul(t=t, i_injs=i_injs, pars=pars, synapses=conns, n_out=n_out, show=False)
        co = CircuitOpt(cr.CircuitTf(nr.BioNeuronTf(pars, dt=dt), synapses=conns_opt))
        co.optimize(dir, n_out=n_out, train=train, epochs=1, w_n=(1,2), plot=plot, evol_var=evol_var)
        self.assertEqual(co._loss.shape, ())

        print('several targets parallel'.center(40, '#'))
        co = CircuitOpt(cr.CircuitTf.create_random(n_neuron=2, syn_keys={k: False for k in conns.keys()}, dt=dt))
        co.optimize(dir, n_out=n_out, train=train, epochs=1, w_n=(1.,0.2), plot=plot, evol_var=evol_var)
        self.assertEqual(co._loss.shape, (10,))


        print('1 LSTM'.center(40, '#'))
        neurons = nr.Neurons(
            [nr.NeuronLSTM(dt=dt), nr.BioNeuronTf(p, fixed='all', dt=dt)])
        c = cr.CircuitTf(neurons=neurons, synapses=conns_opt)
        co = CircuitOpt(circuit=c)
        co.optimize(dir, train=train, n_out=[0, 1], l_rate=(0.01, 9, 0.95), epochs=1, plot=plot, evol_var=evol_var)

        print('2 LSTM'.center(40, '#'))
        neurons = nr.Neurons(
            [nr.NeuronLSTM(dt=dt), nr.NeuronLSTM(dt=dt)])
        c = cr.CircuitTf(neurons=neurons, synapses=conns_opt)
        co = CircuitOpt(circuit=c)
        co.optimize(dir, train=train, n_out=[0, 1], l_rate=(0.01, 9, 0.95), epochs=1, plot=plot, evol_var=evol_var)

        conns_opt[(0, 2)] = odynn.circuit.get_syn_rand()
        with self.assertRaises(AttributeError):
            c = cr.CircuitTf(neurons=neurons, synapses=conns_opt)
            co = CircuitOpt(circuit=c)
            co.optimize(dir, train=train, n_out=[0, 1], l_rate=(0.01, 9, 0.95), epochs=1, plot=plot, evol_var=evol_var)

        print('2 bio + 1 LSTM'.center(40, '#'))
        neurons = nr.Neurons(
            [nr.BioNeuronTf(init_p=[p for _ in range(2)], dt=dt), nr.NeuronLSTM(dt=dt)])
        c = cr.CircuitTf(neurons=neurons, synapses=conns_opt)
        co = CircuitOpt(circuit=c)
        train[1] = i_injs3
        co.optimize(dir, train=train, n_out=[0, 1], l_rate=(0.01, 9, 0.95), epochs=1, plot=plot, evol_var=evol_var)




