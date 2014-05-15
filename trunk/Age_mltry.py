#!/usr/bin/env python2.7
#
# Name:  Age multiy-try metropolis with RJMCMC
#
# Author: Thuso S Simon
#
# Date: 29th of June, 2012
# TODO:  
#    
#
#    vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv
#    Copyright (C) 2011  Thuso S Simon
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    For the GNU General Public License, see <http://www.gnu.org/licenses/>.
#    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# History (version,date, change author)
# More general version of RJMCMC, allows multiple objects to be fitted 
# independetly or hierarically. Also fits single objects and splits into 
# multiple independent componets via coverance matrix

import numpy as nu
import sys
import os
import time as Time
import cPickle as pik
import MC_utils as MC
import pylab as lab
# import acor
# from memory_profiler import profile
from glob import glob
a = nu.seterr(all='ignore')

def _model(x, p):
    '''makes lower model for fitting'''
    return p[3] * x + p[2]


def multi_main(fun, option, burnin=5*10**3, birth_rate=0.5, max_iter=10**5,
            seed=None, fail_recover=False):
    '''Main multi RJMCMC program. Like gibbs sampler but for RJMCMC'''
    # see if to use specific seed
    if seed is not None:
        nu.random.seed(seed)
    # initalize paramerts/class for use by program
    Param = param(fun, burnin)
    if fail_recover:
        # fail recovery
        Param.fail_recover(fail_recover)
    else:
        # initalize and check if param are in range
        timeInit = Time.time()
        while Param.initalize(fun):
            if Time.time() - timeInit > 60.:
                raise MCMCError('Bad Starting position, check params')
    # Start RJMCMC
    while option.iter_stop:
        bins = Param.bins
        if option.current% 501 == 0:
            show = ('acpt = %.2f,log lik = %e, bins = %s, steps = %i,ESS = %2.0f'
                    %(Param.acept_rate[bins][-1],Param.chi[bins][-1],bins,
                      option.current,Param.eff))
            print show
            #lab.plot(fun.data[0][:,0],fun.data[0][:,1],label='Data')
            #lab.plot(fun.data[0][:,0], _model(fun.data[0][:,0],Param.active_param[bins][0]))
            #lab.savefig('%3d.png'%option.current)
            #lab.close()
            sys.stdout.flush()
        # stay, try or jump
        doStayTryJump =  nu.random.rand()
        stay(Param, fun)
        '''if doStayTryJump <= .3:
            # Stay
            stay(Param, fun)
        elif doStayTryJump > .3 and doStayTryJump < .6:
            # Try
            pass
        else:
            # Jump
            pass
            # jump(Param, fun, birth_rate)'''
        # Change Step size
        Param.step(fun, option.current, 500)
        # Change parameter grouping
        # reconfigure(Param)
        # Change temperature
        # Convergence assement
        if option.current % 5000 == 0 and option.current > 1:
            pass
            #Param.eff = MC.effectiveSampleSize(Param.param[bins])
        # Save currnent Chain state
        option.current += 1
        if option.current >= max_iter:
            option.iter_stop = False
    # Finish and return
    return Param


def stay(Param, fun):
    '''Does stay step for RJMCMC'''
    bins = Param.bins
    # sample from distiburtion
    Param.active_param[bins] = fun.proposal(Param.active_param[bins], Param.sigma[bins])
    # calculate new model and chi
    prior = fun.prior(Param.active_param, bins)
    lik = fun.lik(Param.active_param, bins)
    new_chi = {}
    #calc posterior for each object
    for Prior,index in prior:
        new_chi[index] = Prior
    for Lik,index in lik:
        if nu.isfinite(new_chi[index]):
            new_chi[index] += Lik
    #MH critera
    for key in new_chi.keys():
        if mh_critera(Param.active_chi[bins][key],new_chi[key]):
            #accept
            Param.active_chi[bins][key] = new_chi[key] + 0.
            Param.accept()
        else:
            #reject
            Param.active_param[bins][key] = nu.copy(Param.param[bins][-1][key])
            Param.reject()
    Param.save_chain()
    Param.cal_accept()
        
def jump(Param, fun, birth_rate):
    '''Does cross model jump for RJMCM'''
    bins = Param.bins
    Param.active_param, temp_bins, attempt, critera = fun.birth_death(
        birth_rate, bins, Param.active_param)
    # if attempt:
    # check if accept move
    tchi = fun.prior(Param.active_param, temp_bins)
    if nu.isfinite(tchi):
        tchi += fun.lik(Param.active_param, temp_bins)
        # likelihoods
        rj_a = (tchi - Param.chi[bins][-1])
        # model prior
        rj_a += (fun.model_prior(temp_bins) - fun.model_prior(Param.bins))
        Param.trans_moves += 1
        # simulated aneeling 
        rj_a /= MC.SA(Param.trans_moves, 50, abs(Param.chi[bins][-1]),
                      Param.T_stop)
        # RJ-MH critera
    else:
        rj_a, critera = -nu.inf, 1.  
        
    if nu.exp(rj_a) * critera > nu.random.rand():
        # accept move
        Param.accept(temp_bins)
        bins = Param.bins
        # bins = temp_bins
        Param.chi[bins].append(tchi + 0)
        # allow for quick tuneing of sigma
        if Param.T_cuurent[bins] > Param.burnin + 5000:
            Param.T_cuurent[bins] = Param.burnin + 4800
            Param.Nacept[bins] , Param.Nreject[bins] = 1., 1.
    else:
        # rejected
        Param.reject()

        
def mh_critera(chi_old, chi_new, sa=1.):
    '''Does Metropolis-Hastings criera, with simulated anneling'''
    sa = 1. 
    a = (chi_new - chi_old)/(2.*sa)
    if not nu.isfinite(a):
        return False
    if nu.exp(a) > nu.random.rand():
        # acepted
        return True
    else:
        # rejected
        return False
    
class param(object):
    def __doc__(self):
        '''stores params for use in multi_main'''

    def __init__(self, lik_class, burnin):
        self.eff = -9999999.
        self.burnin = burnin
        self.on_dict, self.on = {}, {}
        self.active_param, self.sigma = {}, {}
        self.active_chi = {}
        self.param, self.chi = {}, {}
        self.Nacept, self.Nreject = {},{}
        self.acept_rate, self.out_sigma = {},{}
        # to calculate bayes factor
        self.bayes_fact = {}
        # simulated anneling param
        self.T_cuurent = {}
        self.Nexchange_ratio = 1.0
        self.size, self.a = 0,0
        self.time, self.timeleft = 1, nu.random.exponential(100)
        self.T_stop =  1.
        self.trans_moves = 0
        # bayes_fact[bins] = #something
        # set storage functions

    def initalize(self, lik_fun):
        '''Initalize certan parms'''
        self.bins = nu.random.choice(lik_fun.models.keys())
        self.Nacept[self.bins] , self.Nreject[self.bins] = 1.,1.
        self.T_cuurent[self.bins] = 0
        for i in lik_fun.models.keys():
            self.active_param[i], self.sigma[i] = lik_fun.initalize_param(i)
            self.active_chi[i] = {}
            #self.reconfigure(i)
        self.acept_rate[self.bins] = [1.]
        self.out_sigma[self.bins]  =  [self.sigma[self.bins][0][:]]
        # check if params are in range
        lik,prior = (lik_fun.lik(self.active_param, self.bins),
                               lik_fun.prior(self.active_param, self.bins))
        self.chi[self.bins] = [0.]
        #get intal params lik and priors
        for Prior in prior:
            if not nu.isfinite(Prior[0]):
                return True
            self.chi[self.bins][-1] += Prior[0]
            self.active_chi[self.bins][Prior[1]] = Prior[0]
        for Lik in lik:
            if not nu.isfinite(Lik[0]):
                return True
            self.chi[self.bins][-1] += Lik[0]
            self.active_chi[self.bins][Lik[1]] = Lik[0]
        self.param[self.bins] = [self.active_param[self.bins].copy()]
        self.T_start = self.chi[self.bins][-1] + 0
        return not nu.isfinite(self.chi[self.bins][-1])

    def fail_recover(self, path):
        '''Loads params from old run'''
        raise NotImplementedError

    def save_chain(self):
        '''Records current chain state'''
        self.param[self.bins].append(self.active_param[self.bins].copy())
        self.chi[self.bins].append(nu.sum(self.active_chi[self.bins].values()))

    def save_state(self, path=None):
        '''Saves current state of chain incase run crashes'''
        raise NotImplementedError
        
    def singleObjSplit(self):
        '''Checks correlation between params to see if should split'''
        raise NotImplementedError
        
    def accept(self,bins=None):
        '''Accepts current state of chain, active_param get saved in param
        if bin is different then model is changed'''
        if bins is None:
            # no trans dimensional change
            # need to add scalling
            #self.param[self.bins].append(self.active_param[self.bins].copy())
            self.Nacept[self.bins] += 1
        else:
            # see if model has be created before
            if not bins in self.chi:
                self.chi[bins], self.param[bins] = [] ,[] 
                self.T_cuurent[bins] = 0
                self.acept_rate[bins] = [.5]
                self.Nacept[bins], self.Nreject[bins] = 1., 1.
                self.out_sigma[bins] = []
            
            self.param[bins].append(self.active_param[bins].copy())
            self.bins = bins

    def reject(self):
        '''Rejects current state and gets data from memory'''
        #self.param[self.bins].append(self.param[self.bins][-1].copy())
        #self.active_param[self.bins] = self.param[self.bins][-1].copy()
        #self.chi[self.bins][-1] = nu.copy(self.chi[self.bins][-2])
        self.Nreject[self.bins] += 1
        #self.cal_accept()
        
    def step(self, fun, num_iter,step_freq=500.):
        '''check if time to change step size'''
        bins = self.bins
        if num_iter % step_freq == 0:
            self.sigma[bins] = fun.step_func(self.acept_rate[bins][-1],
                                            self.param[bins],
                                            self.sigma,
                                            bins)
        
    def cal_accept(self):
        '''Calculates accepance rate'''
        bins = self.bins
        self.acept_rate[bins].append(nu.copy(self.Nacept[bins] /
                                             (self.Nacept[bins] +
                                              self.Nreject[bins])))

    def reconfigure(self, param_max):
        '''Changes grouping or something'''
        # each param is different
        self.on[self.bins] = self.active_param[self.bins].keys()[0]
        self.on_dict[self.bins] = range(self.bins)
        # make new step size
        self.sigma[self.bins] = {}
        for i in self.on_dict[self.bins]:
            self.sigma[self.bins][i] = nu.eye(len(self.active_param[self.bins][
                self.on[self.bins]]))
        # group on correlation


    def plot_param(self):
        '''Plots chains'''
        import pylab as lab
        data = {}
        for i in self.param.keys():
            # M, E, b, m_i
            out = []
            for j in self.param[i]:
                t = []
                for k in j:
                    t.append(j[k][-2:])
                out.append(nu.ravel(t))
            lab.plot(nu.asarray(out))
            lab.show()
    
            
class MCMCError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)
