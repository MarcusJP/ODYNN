from Neuron_opt import HH_opt
from Neuron_simul import HH_simul
from Neuron import HodgkinHuxley
import params, data
import utils
import sys
import numpy as np
import scipy as sp


CA_VAR = {'e__tau', 'e__mdp', 'e__scale', 'f__tau', 'f__mdp', 'f__scale', 'h__alpha', 'h__mdp', 'h__scale', 'g_Ca', 'E_Ca', 'rho_ca', 'decay_ca'}
K_VAR = {'p__tau', 'p__mdp', 'p__scale', 'q__tau', 'q__mdp', 'q__scale', 'n_tau', 'n__mdp', 'n__scale', 'g_Kf', 'g_Ks', 'E_K'}

CA_CONST = params.ALL - CA_VAR
K_CONST = params.ALL - K_VAR

pars = [params.give_rand() for i in range(100)]
dt=0.1
t,i_inj = params.give_train(dt)
"""Single optimisation"""
def single_exp(xp, w_v, w_ca, suffix=None):
    name = 'Classic'

    opt = HH_opt(init_p=params.give_rand())
    sim = HH_simul(init_p=params.DEFAULT, t=t, i_inj=i_inj)
    loop_func = HodgkinHuxley.integ_comp

    if (xp == 'ica'):
        name = 'Icafromv'
        opt = HH_opt(init_p=params.give_rand(), fixed=CA_CONST)
        sim = HH_simul(init_p=params.DEFAULT, t=t, i_inj=i_inj)
        loop_func = HodgkinHuxley.ica_from_v

    elif(xp == 'ik'):
        name = 'Ikfromv'
        opt = HH_opt(init_p=params.give_rand(), fixed=K_CONST)
        sim = HH_simul(init_p=params.DEFAULT, t=t, i_inj=i_inj)
        loop_func = HodgkinHuxley.ik_from_v

    elif (xp == 'notauca'):
        name = 'Notauca'
        loop_func = HodgkinHuxley.no_tau_ca

    elif (xp == 'notau'):
        name = 'Notau'
        loop_func = HodgkinHuxley.no_tau

    elif (xp == 'classic'):
        name = 'integcomp'
        loop_func = HodgkinHuxley.integ_comp

    print(name, w_v, w_ca, loop_func)
    dir = '%s_v=%s_ca=%s' % (name, w_v, w_ca)
    if (suffix is not None):
        dir = '%s_%s' % (dir, suffix)
    utils.set_dir(dir)
    opt.loop_func = loop_func
    sim.loop_func = loop_func
    file = sim.simul(show=True, dump=True)
    opt.optimize(dir, w=[w_v, w_ca], file=file)
    return dir


def steps2_exp_ca(w_v1, w_ca1, w_v2, w_ca2):
    name = '_2steps'

    dir = single_exp('ica', w_v1, w_ca1, suffix='%s%s%s' % (name, w_v2, w_ca2))

    param = utils.get_dic_from_var(dir)
    opt = HH_opt(init_p=param, fixed=CA_VAR)
    sim = HH_simul(init_p=params.DEFAULT, t=t, i_inj=i_inj)
    loop_func = HodgkinHuxley.integ_comp
    opt.loop_func = loop_func
    sim.loop_func = loop_func
    file = sim.simul(dump=True, suffix='step2', show=False)
    opt.optimize(dir, w=[w_v2, w_ca2], l_rate=[0.1,9,0.9],suffix='step2', file=file)

    test_xp(dir)

def steps2_exp_k(w_v2, w_ca2):
    name = '_2steps'

    dir = single_exp('ik', 1, 0, suffix='%s%s%s' % (name, w_v2, w_ca2))

    param = utils.get_dic_from_var(dir)
    opt = HH_opt(init_p=param, fixed=K_VAR)
    sim = HH_simul(init_p=params.DEFAULT, t=t, i_inj=i_inj)
    loop_func = HodgkinHuxley.integ_comp
    opt.loop_func = loop_func
    sim.loop_func = loop_func
    file = sim.simul(dump=True, suffix='step2')
    opt.optimize(dir, w=[w_v2, w_ca2], l_rate=[0.1,9,0.9], suffix='step2', file=file)

    test_xp(dir)



def test_xp(dir, suffix='', show=False):

    dt = 0.05
    t = np.array(sp.arange(0.0, 4000, dt))
    t3 = np.array(sp.arange(0.0, 6000, dt))
    i1 = (t-1000)*(30./200)*((t>1000)&(t<=1200)) + 30*((t>1200)&(t<=3000)) - (t-2800)*(30./200)*((t>2800)&(t<=3000))
    i2 = (t - 1000) * (50. / 1000) * ((t > 1000) & (t <= 2000)) + (3000 - t) * (50. / 1000) * ((t > 2000) & (t <= 3000))
    i3 = (t3-1000)*(1./2000)*((t3>1000)&(t3<=3000)) + (5000-t3)*(1./2000)*((t3>3000)&(t3<=5000))

    utils.set_dir(dir)
    param = data.get_vars(dir)
    sim = HH_simul(init_p=param, t=t, i_inj=i1)
    sim.simul(show=show, suffix='test1')
    sim.i_inj = i2
    sim.simul(show=show, suffix='test2')
    sim.i_inj=i3
    sim.t = t3
    sim.simul(show=show, suffix='test3')

def alternate(name=''):
    dir = 'Integcomp_alternate_%s' % name
    utils.set_dir(dir)
    loop_func = HodgkinHuxley.integ_comp
    # pars = data.get_vars('Integcomp_alternate_100-YAYY', 0)
    # pars = [dict([(k, v[n]) for k, v in pars.items()]) for n in range(len(pars['C_m']))]
    opt = HH_opt(init_p=pars, loop_func=loop_func, dt=dt)
    sim = HH_simul(init_p=params.DEFAULT, t=t, i_inj=i_inj, loop_func=loop_func)
    file = sim.simul(show=False, suffix='train', dump=True)
    wv = 0.2
    wca = 0.8
    opt.optimize(dir, [wv, wca], epochs=20, step=0, file=file)
    for i in range(24):
        wv = 1 - wv
        wca = 1 - wca
        n = opt.optimize(dir, [wv, wca], reload=True, epochs=20, step=i + 1, file=file)
    comp_pars(dir, n)
    test_xp(dir)

def only_v(name=''):
    dir = 'Integcomp_volt_%s' % name
    utils.set_dir(dir)
    loop_func = HodgkinHuxley.integ_comp
    opt = HH_opt(init_p=pars, loop_func=loop_func, dt=dt)
    sim = HH_simul(init_p=params.DEFAULT, t=t, i_inj=i_inj, loop_func=loop_func)
    sim.simul(show=False, suffix='train', dump=True)
    wv = 1
    wca = 0
    n = opt.optimize(dir, [wv, wca], epochs=500)
    comp_pars(dir, n)
    test_xp(dir)

def only_calc(name=''):
    dir = 'Integcomp_calc_%s' % name
    utils.set_dir(dir)
    loop_func = HodgkinHuxley.integ_comp
    opt = HH_opt(init_p=pars, loop_func=loop_func, dt=dt)
    sim = HH_simul(init_p=params.DEFAULT, t=t, i_inj=i_inj, loop_func=loop_func)
    sim.simul(show=False, suffix='train', dump=True)
    wv = 0
    wca = 1
    n = opt.optimize(dir, [wv, wca], epochs=500)
    comp_pars(dir, n)
    test_xp(dir)

def comp_pars(dir, i=-1):
    p = data.get_vars(dir, i)
    pall = data.get_vars_all(dir, i)
    utils.set_dir(dir)
    utils.plot_vars(pall, func=utils.plot, suffix='evolution', show=False, save=True)
    utils.plot_vars(p, func=utils.bar, suffix='compared', show=False, save=True)
    utils.boxplot_vars(p, suffix='boxes', show=False, save=True)


def add_plots():
    import glob
    import re
    for filename in glob.iglob(utils.RES_DIR+'*'):
        dir = re.sub(utils.RES_DIR, '', filename)
        try:
            comp_pars(dir)
        except:
            print(dir)


if __name__ == '__main__':


    xp = sys.argv[1]
    if(xp == 'alt'):
        name = sys.argv[2]
        alternate(name)
    elif(xp=='cac'):
        name = sys.argv[2]
        only_calc(name)
    elif(xp=='v'):
        name = sys.argv[2]
        only_v(name)
    elif(xp == 'single'):
        xp = sys.argv[2]
        w_v, w_ca = list(map(int, sys.argv[3:5]))
        single_exp(xp, w_v, w_ca)
    elif(xp == '2stepsca'):
        w_v1, w_ca1, w_v2, w_ca2 = list(map(int, sys.argv[2:6]))
        steps2_exp_ca(w_v1, w_ca1, w_v2, w_ca2)
    elif (xp == '2stepsk'):
        w_v2, w_ca2 = list(map(int, sys.argv[2:4]))
        steps2_exp_k(w_v2, w_ca2)



    exit(0)
