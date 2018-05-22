import tensorflow as tf
import scipy as sp
import params



class HodgkinHuxley():
    """Full Hodgkin-Huxley Model implemented in Python"""


    DECAY_CA = params.DECAY_CA
    RHO_CA = params.RHO_CA
    REST_CA = params.REST_CA

    def __init__(self, init_p=params.DEFAULT, init_state=params.INIT_STATE, tensors=False, consts=[]):
        self.tensors = tensors
        self.init_state = init_state
        if(self.tensors):
            tf.reset_default_graph()
            self.init_p = init_p
            self.param = {}
            for var, val in self.init_p.items():
                if(var in consts):
                    self.param[var] = tf.constant(val, name=var, dtype=tf.float32)
                else:
                    self.param[var] = tf.get_variable(var, initializer=val, dtype=tf.float32)
        else:
            self.param = init_p



    def inf(self, V, rate):
        mdp = self.param['%s__mdp' % rate]
        scale = self.param['%s__scale' % rate]
        if(self.tensors):
            return tf.sigmoid((V - mdp) / scale)
        else:
            return 1 / (1 + sp.exp((mdp - V)/scale))

    def h(self, cac):
        """Channel gating kinetics. Functions of membrane voltage"""
        q = self.inf(cac, 'h')
        return 1 + (q - 1) * self.param['h__alpha']

    def I_Ca(self, V, e, f, h):
        """
        Membrane current (in uA/cm^2)
        Calcium (Ca = element name)
        """
        return self.param['g_Ca'] * e ** 2 * f * h * (V - self.param['E_Ca'])

    def I_Kf(self, V, p, q):
        """
        Membrane current (in uA/cm^2)
        Potassium (K = element name)
        """
        return self.param['g_Kf'] * p ** 4 * q * (V - self.param['E_K'])

    def I_Ks(self, V, n):
        """
        Membrane current (in uA/cm^2)
        Potassium (K = element name)
        """
        return self.param['g_Ks'] * n * (V - self.param['E_K'])

    #  Leak
    def I_L(self, V):
        """
        Membrane current (in uA/cm^2)
        Leak
        """
        return self.param['g_L'] * (V - self.param['E_L'])

    @staticmethod 
    def integ_comp(X, i_inj, dt, self):
        """
        Integrate
        """
        V = X[0]
        p = X[1]
        q = X[2]
        n = X[3]
        e = X[4]
        f = X[5]
        cac = X[6]
        h = self.h(cac)
        V += ((i_inj - self.I_Ca(V, e, f, h) - self.I_Ks(V, n) - self.I_Kf(V, p, q) - self.I_L(V)) / self.param[
            'C_m']) * dt
        cac += (-self.I_Ca(V, e, f, h) * self.RHO_CA - ((cac - self.REST_CA) / self.DECAY_CA)) * dt
        tau = self.param['p__tau']
        p = ((tau * dt) / (tau + dt)) * ((p / dt) + (self.inf(V, 'p') / tau))
        tau = self.param['q__tau']
        q = ((tau * dt) / (tau + dt)) * ((q / dt) + (self.inf(V, 'q') / tau))
        tau = self.param['e__tau']
        e = ((tau * dt) / (tau + dt)) * ((e / dt) + (self.inf(V, 'e') / tau))
        tau = self.param['f__tau']
        f = ((tau * dt) / (tau + dt)) * ((f / dt) + (self.inf(V, 'f') / tau))
        tau = self.param['n__tau']
        n = ((tau * dt) / (tau + dt)) * ((n / dt) + (self.inf(V, 'n') / tau))

        if(self.tensors):
            cac = tf.maximum(cac, 0.)
            return tf.stack([V, p, q, n, e, f, cac], 0)
        else:
            cac = max(cac, 0.)
            return [V, p, q, n, e, f, cac]

    @staticmethod 
    def no_tau_ca(X, i_inj, dt, self):
        """
        Integrate
        """
        V = X[0]
        p = X[1]
        q = X[2]
        n = X[3]
        e = X[4]
        f = X[5]
        cac = X[6]
        h = self.h(cac)
        V += ((i_inj - self.I_Ca(V, e, f, h) - self.I_Ks(V, n) - self.I_Kf(V, p, q) - self.I_L(
            V)) / self.param['C_m']) * dt
        cac = (self.DECAY_CA / (dt + self.DECAY_CA)) * (
                cac - self.I_Ca(V, e, f, h) * self.RHO_CA * dt + self.REST_CA * self.DECAY_CA / dt)
        tau = self.param['p__tau']
        p = ((tau * dt) / (tau + dt)) * ((p / dt) + (self.inf(V, 'p') / tau))
        tau = self.param['q__tau']
        q = ((tau * dt) / (tau + dt)) * ((q / dt) + (self.inf(V, 'q') / tau))
        tau = self.param['n__tau']
        n = ((tau * dt) / (tau + dt)) * ((n / dt) + (self.inf(V, 'n') / tau))
        e = self.inf(V, 'e')
        f = self.inf(V, 'f')
        if (self.tensors):
            cac = tf.maximum(cac, 0.)
            return tf.stack([V, p, q, n, e, f, cac], 0)
        else:
            cac = max(cac, 0.)
            return [V, p, q, n, e, f, cac]

    @staticmethod 
    def no_tau(X, i_inj, dt, self):
        """
        Integrate
        """
        V = X[0]
        p = X[1]
        q = X[2]
        n = X[3]
        e = X[4]
        f = X[5]
        cac = X[6]
        h = self.h(cac)
        V += ((i_inj - self.I_Ca(V, e, f, h) - self.I_Ks(V, n) - self.I_Kf(V, p, q) - self.I_L(
            V)) / self.param['C_m']) * dt

        cac = (self.DECAY_CA / (dt + self.DECAY_CA)) * (
                cac - self.I_Ca(V, e, f, h) * self.RHO_CA * dt + self.REST_CA * self.DECAY_CA / dt)
        p = self.inf(V, 'p')
        q = self.inf(V, 'q')
        e = self.inf(V, 'e')
        f = self.inf(V, 'f')
        n = self.inf(V, 'n')
        if (self.tensors):
            cac = tf.maximum(cac, 0.)
            return tf.stack([V, p, q, n, e, f, cac], 0)
        else:
            cac = max(cac, 0.)
            return [V, p, q, n, e, f, cac]

    @staticmethod 
    def ica_from_v(X, v_fix, dt, self):
        e = X[1]
        f = X[2]
        cac = X[-1]

        h = self.h(cac)
        tau = self.param['e__tau']
        e = ((tau * dt) / (tau + dt)) * ((e / dt) + (self.inf(v_fix, 'e') / tau))
        tau = self.param['f__tau']
        f = ((tau * dt) / (tau + dt)) * ((f / dt) + (self.inf(v_fix, 'f') / tau))
        ica = self.I_Ca(v_fix, e, f, h)
        cac = (self.DECAY_CA / (dt + self.DECAY_CA)) * (
                cac - ica * self.RHO_CA * dt + self.REST_CA * self.DECAY_CA / dt)

        if (self.tensors):
            cac = tf.maximum(cac, 0.)
            return tf.stack([ica, e, f, h, cac], 0)
        else:
            cac = max(cac, 0.)
            return [ica, e, f, h, cac]


    loop_func = integ_comp

