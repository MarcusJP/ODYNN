"""
.. module:: neuron
    :synopsis: Module containing classes for neuron models

.. moduleauthor:: Marc Javin
"""


import numpy as np
import tensorflow as tf

from .models import cfg_model
from .models.model import Neuron
from .optim import Optimized

MODEL = cfg_model.NEURON_MODEL
class PyBioNeuron(MODEL):
    """Class representing a neuron, implemented only in Python
    This class allows simulation but not optimization"""

    def __init__(self, init_p=None, dt=0.1):
        MODEL.__init__(self, init_p=init_p, tensors=False, dt=dt)


class NeuronTf(Neuron, Optimized):
    """
    Abstract class whose implementation allow single optimization as well as in a Circuit
    """

    _ions = MODEL.ions
    default_init_state = MODEL.default_init_state
    nb = 0

    def __init__(self, dt=0.1):
        Neuron.__init__(self, dt=dt)
        Optimized.__init__(self, dt=dt)
        self.id = self._give_id()

    @property
    def groups(self):
        """
        list indicating the group of each neuron
        Neurons with the same group share the same parameters
        """
        return None

    def init(self, batch):
        """
        Method to implement whe initialization is needed, will be called before reset

        Args:
            batch(int): number of batches
        """
        pass

    @property
    def trainable(self):
        """boolean stating if the neuron can be optimized"""
        return True

    @classmethod
    def _give_id(cls):
        cls.nb += 1
        return str(cls.nb - 1)

    @property
    def hidden_init_state(self):
        """For behavioral models eg LSTM"""
        return None


class BioNeuronTf(MODEL, NeuronTf):
    """
    Class representing a neuron, implemented using Tensorflow.
    This class allows simulation and optimization, alone and in a Circuit.
    It can contain several neurons at the same time. Which in turn can be optimized in parallel, or be used to
    represent the entire neurons in a Circuit.
    """

    def __init__(self, init_p=None, dt=0.1, fixed=(), constraints=None, groups=None, n_rand=None):
        """
        Initializer
        Args:
            init_p(dict or list of dict): initial parameters of the neuron(s). If init_p is a list, then this object
                will model n = len(init_p) neurons
            dt(float): time step
            fixed(set): parameters that are fixed and will stay constant in case of optimization.
                if fixed == 'all', all parameters will be constant
            constraints(dict of ndarray): keys as parameters name, and values as [lower_bound, upper_bound]
        """
        NeuronTf.__init__(self, dt=dt)
        if n_rand is not None:
            init_p = [self.get_random() for _ in range(n_rand)]
        self.n_rand = n_rand
        MODEL.__init__(self, init_p=init_p, tensors=True, dt=dt)
        if fixed == 'all' :
            fixed = set(self.parameter_names)
        self._fixed = fixed
        if constraints is not None :
            self._constraints_dic = constraints
        if groups is None:
            pass
        elif len(np.unique(groups)) > self.num:
            raise ValueError('Too many groups defined')
        elif len(groups) < self.num:
            raise ValueError('Some neurons are not assigned to any group')
        self._groups = groups


    def __getstate__(self):
        state = self.__dict__.copy()
        del state['_param']
        del state['_constraints']
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._param = {}
        self._constraints = {}

    @property
    def groups(self):
        return self._groups

    @property
    def init_params(self):
        """initial model parameters"""
        return self._init_p

    @init_params.setter
    def init_params(self, value):
        self._init_p = {v: value[v] for v in self.parameter_names}
        # TODO : test
        param_ex = self._init_p[self.parameter_names[0]]
        self._num = len(param_ex)
        if len(param_ex) == 1:
            self._init_state = self.default_init_state
        else:
            self._init_state = np.stack([self.default_init_state for _ in range(self._num)], axis=-1)
            if isinstance(param_ex, np.ndarray) and param_ex.ndim == 2:
                n = self._init_p[self.parameter_names[0]].shape[-1]
                self._init_state = np.stack([self._init_state for _ in range(n)], axis=-1)
        for v in self._init_p.values():
            if len(v) != self._num:
                raise ValueError('The shape of the parameters don\'t match the object structure')

    def set_init_param(self, name, value=None):
        if name not in self.parameter_names:
            raise ValueError('The parameter "{}" does not exist'.format(name))
        if value is None:
            value = self.default_params[name]
        shape = self._init_p[name].shape
        val = np.full(shape, value, dtype=np.float32)
        self._init_p[name] = val

    @property
    def trainable(self):
        """True if the object can be optimized"""
        return (self._fixed != set(self._init_p.keys()))

    def reset(self):
        """rebuild tf variable graph"""
        with(tf.variable_scope(self.id)):
            self._param = {}
            self._constraints = []
            for var, val in self._init_p.items():
                if var in self._fixed:
                    if self._groups is None:
                        vals = tf.constant(val, name=var, dtype=tf.float32)
                    else:
                        vals = [tf.constant(val[i], name=var + str(i), dtype=tf.float32) for i in self._groups]
                else:
                    with tf.variable_scope(self.id, reuse=tf.AUTO_REUSE):
                        if self._groups is None:
                            vals = tf.get_variable(var, initializer=val, dtype=tf.float32)
                        else:
                            vals = [tf.get_variable(var + str(i), initializer=val[i], dtype=tf.float32) for i in self._groups]
                    if var in self._constraints_dic:
                        con = self._constraints_dic[var]
                        if self.groups is None:
                            self._constraints.append(
                                tf.assign(vals, tf.clip_by_value(vals, con[0], con[1])))
                        else:
                            self._constraints.extend(
                            [tf.assign(val, tf.clip_by_value(val, con[0], con[1])) for val in vals])
                self._param[var] = tf.stack(vals)
        # print('neuron_params after reset : ', self._param)

    def parallelize(self, n):
        """Add a dimension of size n in the initial parameters and initial state

        Args:
          n(int): size of the new dimension
        """
        if self.n_rand is not None:
            if self._num > 1 and list(self._init_p.values())[0].ndim == 1:
                keys = self._init_p.keys()
                toadd = [[self.get_random() for _ in range(self._num)] for __ in range(n-1)]
                toadd_ = [{var: np.array([par[i][var] for i in range(self._num)], dtype=np.float32) for var in keys} for par in toadd]
                l = [self._init_p] + toadd_
                self._init_p = {var: np.stack([l[i][var] for i in range(n)], axis=-1) for var in keys}
            elif not hasattr(list(self._init_p.values())[0], '__len__'):
                keys = self._init_p.keys()
                l = [self._init_p] + [self.get_random() for _ in range(n - 1)]
                self._init_p = {var: np.array([l[i][var] for i in range(n)], dtype=np.float32) for var in keys}
            self._init_state = np.stack([self._init_state for _ in range(n)], axis=-1)
        else:
            MODEL.parallelize(self, n)

    def build_graph(self, batch=None):
        """
        Build a tensorflow graph for running the neuron(s) on a series of input
        Args:
            batch(int): dimension of the batch

        Returns:
            tf.placeholder, tf.Tensor: input placeholder and results of the run
        """
        tf.reset_default_graph()
        self.reset()
        xshape = [None]
        initializer = self._init_state
        if batch is not None:
            xshape.append(None)
            initializer = np.stack([initializer for _ in range(batch)], axis=1)
        if self._num > 1:
            xshape.append(self._num)
        curs_ = tf.placeholder(shape=xshape, dtype=tf.float32, name='input_current')
        res_ = tf.scan(self.step,
                       curs_,
                       initializer=initializer.astype(np.float32))
        return curs_, res_

    def calculate(self, i):
        """
        Iterate over i (current) and return the state variables obtained after each step

        Args:
          i(ndarray): input current

        Returns:
            ndarray: state vectors concatenated [i.shape[0], len(self.init_state)(, i.shape[1]), self.num]
        """
        if i.ndim > 1:
            input_cur, res_ = self.build_graph(batch=i.shape[1])
        else:
            input_cur, res_ = self.build_graph()
        if i.ndim < 3 and self._num > 1:
            i = np.stack([i for _ in range(self._num)], axis=i.ndim)
        with tf.Session() as sess:
            sess.run(tf.global_variables_initializer())
            results = sess.run(res_, feed_dict={
                input_cur: i
            })
        return results

    def settings(self):
        """

        Returns(str): string describing the object

        """
        return ('Neuron optimization'.center(20, '.') + '\n' +
                'Nb of neurons : {}'.format(self._num) + '\n' +
                'Initial neuron params : {}'.format(self._init_p) + '\n' +
                'Fixed variables : {}'.format([c for c in self._fixed]) + '\n' +
                'Initial state : {}'.format(self.default_init_state) + '\n' +
                'Constraints : {}'.format(self._constraints_dic) + '\n' +
                'dt : {}'.format(self.dt) + '\n')

    def apply_constraints(self, session):
        """
        Apply the constraints to the object variables

        Args:
            session: tensorflow session

        """
        session.run(self._constraints)

    @property
    def variables(self):
        """Current variables of the models"""
        return self._param


class NeuronLSTM(NeuronTf):
    """Behavior model of a neuron using an LSTM network"""

    _max_cur = 60.
    _rest_v = -60.
    _scale_v = 100.
    _scale_ca = 500.

    def __init__(self, nb_layer=1, layer_size=50, extra_ca=0, dt=0.1, vars_init=None):
        self.vars_init = None
        self._hidden_layer_nb = nb_layer
        self._hidden_layer_size = layer_size
        self._extra_ca = extra_ca
        self._volt_net = None
        self._ca_net = None
        NeuronTf.__init__(self, dt=dt)
        self._hidden_init_state = None

    @property
    def hidden_init_state(self):
        """Give the initial state needed for the LSTM network"""
        if self._hidden_init_state is None:
            raise ReferenceError("The LSTM cell has not yet been iniatialized")
        else:
            return self._hidden_init_state

    @property
    def num(self):
        """Number of neurons contained in the object, always 1 here"""
        return 1

    @property
    def init_params(self):
        """Initial model parameters"""
        if self.vars_init is None:
            return {}
        return self.vars_init

    @init_params.setter
    def init_params(self, value):
        self.vars_init = value

    def predump(self, sess):
        self.vars_init = {v.name: sess.run(v) for v in tf.trainable_variables()}

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['_ca_net']
        del state['_volt_net']
        del state['_hidden_init_state']
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._volt_net = None
        self._ca_net = None
        self._hidden_init_state = None

    def reset(self):
        num_units1 = [self._hidden_layer_size for _ in range(self._hidden_layer_nb)]
        num_units1.append(1)
        with tf.variable_scope(self.id+'Volt'):
            cells = [tf.nn.rnn_cell.LSTMCell(n, use_peepholes=True, state_is_tuple=True) for n in num_units1]
            self._volt_net = tf.nn.rnn_cell.MultiRNNCell(cells)

        if self._extra_ca > 0:
            num_units2 = [self._hidden_layer_size for _ in range(self._extra_ca)]
            num_units2.append(1)
            with tf.variable_scope(self.id+'Calc'):
                cells = [tf.nn.rnn_cell.LSTMCell(n, use_peepholes=True, state_is_tuple=True) for n in num_units2]
                self._ca_net = tf.nn.rnn_cell.MultiRNNCell(cells)

    def init(self, batch):
        with tf.variable_scope(self.id+'Volt'):
            init_vstate = self._volt_net.zero_state(batch, dtype=tf.float32)
            self._hidden_init_state = (init_vstate, init_vstate)
        if self._ca_net:
            with tf.variable_scope(self.id+'Calc'):
                init_castate = self._ca_net.zero_state(batch, dtype=tf.float32)
            self._hidden_init_state = (init_vstate, init_castate)

    def build_graph(self, batch=1):
        tf.reset_default_graph()
        self.reset()
        xshape = [None, None]

        curs_ = tf.placeholder(shape=xshape, dtype=tf.float32, name='input_current')
        with tf.variable_scope('prelayer'):
            input = tf.expand_dims(curs_ / self._max_cur, axis=len(xshape))

        with tf.variable_scope(self.id+'Volt'):
            initializer = self._volt_net.zero_state(batch, dtype=tf.float32)
            v_outputs, _ = tf.nn.dynamic_rnn(self._volt_net, inputs=input, initial_state=initializer, time_major=True)

        if self._ca_net:
            with tf.variable_scope(self.id+'Calc'):
                initializer = self._ca_net.zero_state(batch, dtype=tf.float32)
                ca_outputs, _ = tf.nn.dynamic_rnn(self._ca_net, inputs=v_outputs, initial_state=initializer, time_major=True)
        else:
            ca_outputs = v_outputs

        with tf.name_scope('Scale'):
            V = v_outputs[:, :, self.V_pos] * self._scale_v + self._rest_v
            Ca = ca_outputs[:, :, -1] * self._scale_ca
            results = tf.stack([V, Ca], axis=1)

        return curs_, results

    def step(self, X, hprev, i_inj):
        """
        Update function

        Args:
            X(Tensor): not used here, classical state
            hprev(tuple of LSTMStateTuple): previous LSTM state
            i_inj(Tensor): array of input currents, dimension [batch]

        Returns:
            Tensor: Tensor containing the voltages in the first position
        """
        with tf.variable_scope(self.id+'Volt'):
            # apply lstm network (self._volt_net) with i_inj as input, using the previous state
            v, vstate = self._volt_net(i_inj/self._max_cur, hprev[0])
            v = v * self._scale_v + self._rest_v

        if self._ca_net:
            with tf.variable_scope(self.id+'Calc'):
                ca, castate = self._ca_net(v, hprev[1])
                ca = ca * self._scale_ca
        else:
            ca = v
            castate = vstate

        # Fill with void to mimic classical state
        out = [v]
        for i in range(len(self.default_init_state)-2):
            out.append(tf.fill(tf.shape(i_inj), 0.))
        out.append(ca)

        return tf.stack(out), (vstate, castate)

    def calculate(self, i):
        """
        Iterate over i (current) and return the state variables obtained after each step

        Args:
          i(ndarray): input current

        Returns:
            ndarray: state vectors concatenated [i.shape[0], len(self.init_state)(, i.shape[1]), self.num]
        """
        if i.ndim > 1:
            input_cur, res_ = self.build_graph(batch=i.shape[1])
        else:
            input_cur, res_ = self.build_graph()
            i = i[:, None]
        with tf.Session() as sess:
            sess.run(tf.global_variables_initializer())
            self.apply_init(sess)
            results = sess.run(res_, feed_dict={
                input_cur: i
            })
        return results

    def settings(self):
        """

        Returns(str): string describing the object

        """
        return ('Number of hidden layers : {}'.format(self._hidden_layer_nb) + '\n'
                'Units per hidden layer : {}'.format(self._hidden_layer_size) + '\n' +
                'Extra layers for [Ca] : %s' % self._extra_ca + '\n' +
                'dt : {}'.format(self.dt) + '\n' +
                'max current : {}, rest. voltage : {}, scale voltage : {}, scale calcium : {}'
                .format(self._max_cur, self._rest_v, self._scale_v, self._scale_ca)
                )

    def apply_init(self, sess):
        """Initialize the variables if loaded object

        Args:
          sess: tf.Session
        """
        if self.vars_init is not None:
            train_vars = self._volt_net.trainable_variables
            if self._ca_net:
                train_vars += self._ca_net.trainable_variables
            sess.run([tf.assign(v, self.vars_init[v.name]) for v in train_vars])


class Neurons(NeuronTf):
    """
    This class allow to use neurons from different classes inheriting NeuronTf in a same Circuit
    """

    def __init__(self, neurons):
        """
        Args:
            neurons(list): list of NeuronTf objects

        Raises:
            AttributeError: If all neurons don't share the same dt
        """
        if len(set([n.dt for n in neurons])) > 1:
            raise AttributeError('All neurons must have the same time step, got : {}'.format([n.dt for n in neurons]))
        NeuronTf.__init__(self, dt=neurons[0].dt)
        self._neurons = neurons
        self._num = np.sum([n.num for n in neurons])
        self._init_state = np.concatenate([n.init_state if n.init_state.ndim == 2 else n.init_state[:,np.newaxis] for n in neurons], axis=1)

    def predump(self, sess):
        for n in self._neurons:
            n.predump(sess)

    def __getstate__(self):
        state = self.__dict__.copy()
        state['neurons'] = [n.__getstate__().copy() for n in self._neurons]
        for n in state['neurons']:
            pass
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        for i, n in enumerate(self._neurons):
            n.__setstate__(state['neurons'][i])

    def reset(self):
        for n in self._neurons:
            n.reset()

    def init(self, batch):
        """call `init` method for all contained neuron objects"""
        for n in self._neurons:
            n.init(batch)

    @property
    def hidden_init_state(self):
        return [n.hidden_init_state if n.hidden_init_state is not None else 0. for n in self._neurons]

    def build_graph(self):
        raise AttributeError('Nope')

    def step(self, X, hidden, i):
        """
        Share the state and the input current into its embedded neurons

        Args:
            X(tf.Tensor): precedent state vector
            i(tf.Tensor): input current

        Returns:
            ndarray: next state vector

        """
        next_state = []
        idx = 0
        extras = []
        for j, n in enumerate(self._neurons):
            if n.hidden_init_state is None:
                nt = n.step(X[:,:,idx:idx+n.num], i[:,idx:idx+n.num])
                extr = hidden[j]
            else:
                nt, extr = n.step(X[:,:,idx:idx+n.num], hidden[j], i[:, idx:idx + n.num])
            extras.append(extr)
            next_state.append(nt)
            idx += n.num
        # for t in extras[0]:
        #     print(t)
        # print(tf.concat(next_state, axis=-1))
        with tf.variable_scope('1state'):
            return (tf.concat(next_state, axis=-1), extras)

    def calculate(self, i):
        """
        Iterate over i (current) and return the state variables obtained after each step

        Args:
          i(ndarray): input current

        Returns:
            ndarray: state vectors concatenated [i.shape[0], len(self.init_state)(, i.shape[1]), self.num]
        """
        pass

    def settings(self):
        """

        Returns(str): string describing the object

        """
        return 'Ensemble neurons : '.join(['\n' + n.settings() for n in self._neurons])

    def apply_constraints(self, session):
        """
        Apply the constraints to the object variables

        Args:
            session: tensorflow session

        """
        return [n.apply_constraints(session) for n in self._neurons]

    def apply_init(self, session):
        [n.apply_init(session) for n in self._neurons]




