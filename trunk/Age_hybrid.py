#!/usr/bin/env python
#
# Name:  RJMCMC and partical swarm
#
# Author: Thuso S Simon
#
# Date: Sep. 2012
# TODO: 
#
#    vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv
#    Copyright (C) 2012  Thuso S Simon
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
#History (version,date, change author)
#
#
#
''' Does RJMCMC with partical swarm. Trys different topologies of comunication from Mendes et al 2004 and different weighting types for ps'''

from Age_date import MC_func
from Age_RJMCMC import *
try:
    from mpi4py import MPI as mpi
except ImportError('Warrning: Not detecting mpi4py. No mpi will be avalible'):
    mpi = None
import time as Time
import cPickle as pik
import csv
#import pylab as lab
import os

def root_run(fun, topology, func, burnin=5000, itter=10**5, k_max=10):
    '''From MPI start, starts workers doing RJMCMC and coordinates comunication 
    topologies'''
   #start RJMCMC SWARM 
    N = 3 #output number
    if not topology.rank == 0:
        #output is: [param, chi, bayes_fact, acept_rate, out_sigma, rank]
        print 'Starting rank %i on %s.'%(topology.rank_world,mpi.Get_processor_name())    
        temp = rjmcmc_swarm(fun, topology, func, burnin)
        #temp = [param, chi, bayes_fact]
        #print topology.iter_stop
        print 'rank %i on %s is complete'%(topology.rank_world,mpi.Get_processor_name())
        #topology.comm_world.isend(topology.rank_world,dest=0,tag=99)
        #print topology.iter_stop
        #topology.comm_world.barrier()
        for i in range(N):
            topology.comm_world.send(temp[i], dest=0,tag=99)
        return None,None,None
    else:
    #while rjmcmc is  root process is running update curent iterations and gather best fit for swarm
        print 'starting root on %i on %s'%(topology.rank,mpi.Get_processor_name())
        stop_iter = burnin * topology.size_world + itter
        #dummy param for swarm
        time = Time.time()
        i = 1
        while (topology.global_iter <= stop_iter and nu.any(topology.iter_stop)): 
            #get swarm values from other workers depending on topology
            topology.get_best()
            topology.swarm_update(topology.parambest,topology.chibest, (nu.isfinite(topology.parambest).sum() - 6)/3)
            #get total iterations
            Time.sleep(.1)
            if Time.time() - time > 5:
                print '%2.2f percent done at %i' %((float(topology.global_iter) / stop_iter) * 100., 
                                                   topology.global_iter)
                sys.stdout.flush()
                time = Time.time()
                #print topology.current
            #pik.dump((topology.swarm,topology.swarmChi),open('swarm','w'),2)
            i += 1
        #put in convergence diagnosis
        #tell other workers to stop
        print 'Sending stop signal.'
        for i in xrange(1,topology.comm_world.size):
            topology.iter_stop[:,i] = 0
        t= Time.time()
        while True:
            topology.get_best(True)
            #Time.sleep(1)
            if Time.time() -t >15: #or len(done) == topology.size_world:
                break
        
        #get results from other processes
        print 'Root reciving.'
        temp =[]
        i= 1
        time = Time.time() 
        while Time.time() - time < 60:
        #for i in xrange(1,topology.size_world):
            if topology.comm_world.Iprobe(source=i,tag=99):
                print 'getting data from %i '%(i)
                t=[]
                for k in xrange(N):
                    t.append( topology.comm_world.recv(source=i,tag=99))
                temp.append(t)
                print 'done from %i '%(i)
            i+=1
            if i > topology.comm_world.size -1:
                i = 1
        print 'done reciving'
        try:
            param, chi, bayes = dic_data(temp, burnin)
        except IndexError:
            pass
        #save accept rate and sigma for output
        return param, chi, t

 #===========================================
#swarm functions
def vanilla(active_param, active_dust, active_losvd, rank, birth_rate, option,T_cuurent, 
            burnin, fun, accept_rate):
    '''does normal swarm stuff untill burnin is done, that only contribures every 100 iterations'''
    if T_cuurent<burnin or T_cuurent % 100 == 0:
        active_param, active_dust, active_losvd, birth_rate = swarm_vect(active_param, active_dust, 
                                                                         active_losvd, rank, birth_rate, option)
    if birth_rate > .8:
        birth_rate = .8
    elif birth_rate < .2:
        birth_rate = .2
    return active_param, active_dust, active_losvd, birth_rate

def hybrid(active_param, active_dust, active_losvd, rank, birth_rate, option,T_cuurent, 
           burnin, fun, accept_rate):
    '''chooses weather current possiotion or swarm is better and passes it on'''
    Tactive_param, Tactive_dust, Tactive_losvd, Tbirth_rate = swarm_vect(active_param, active_dust, 
                                                                         active_losvd, rank, birth_rate, option)
    if fun.lik(Tactive_param, Tactive_dust, Tactive_losvd)[0] < fun.lik(active_param, active_dust, active_losvd)[0]:
        #if swarm is better than current possition
        if birth_rate > .8:
            Tbirth_rate = .8
        elif birth_rate < .2:
            Tbirth_rate = .2
        return Tactive_param, Tactive_dust, Tactive_losvd, Tbirth_rate
    else:
        return active_param, active_dust, active_losvd, birth_rate

def tuning(active_param, active_dust, active_losvd, rank, birth_rate, option,T_cuurent, burnin,fun, accept_rate):
    '''uses swarm more likely when the acceptance rate is not optimal '''
    if accept_rate < .235 or accept_rate > .5:
        active_param, active_dust, active_losvd, birth_rate = swarm_vect(active_param, active_dust, 
                                                                         active_losvd, rank, birth_rate, option)
    if birth_rate > .8:
        birth_rate = .8
    elif birth_rate < .2:
        birth_rate = .2
    return active_param, active_dust, active_losvd, birth_rate

def none(active_param, active_dust, active_losvd, rank, birth_rate, option,T_cuurent, burnin,fun, accept_rate):
    '''normal RJMCMC'''
    return active_param, active_dust, active_losvd, birth_rate

#+===================================
#main function  
def rjmcmc_swarm(fun, option, swarm_function=vanilla, burnin=5*10**3):
    nu.random.seed(random_permute(current_process().pid))
    #file = csv.writer(open('out'+str(rank)+'txt','w'))
    #initalize boundaries
    lib_vals = fun._lib_vals
    metal_unq = fun._metal_unq
    age_unq = fun._age_unq
    global_rank = option.rank_world
    rank = option.comm_world.rank
    #create fun for all number of bins
    #attempt=False
    param,active_param,chi,sigma={},{},{},{}
    Nacept,Nreject,acept_rate,out_sigma={},{},{},{}
    #set up dust if in use
    if fun._dust:
        #[tau_ism, tau_BC ]
        active_dust = nu.random.rand(2)*4.
        sigma_dust = nu.identity(2)*nu.random.rand()*2
    else:
        active_dust = nu.zeros(2)
        sigma_dust = nu.zeros([2,2])
    #set up LOSVD
    if fun._losvd:
        #[sigma, redshift, h3, h4]
        active_losvd = nu.random.rand(4)*2
        active_losvd[1] = 0.
        sigma_losvd = nu.random.rand(4,4)
    else:
        active_losvd = nu.zeros(4)
        sigma_losvd = nu.zeros([4,4])
    bayes_fact={} #to calculate bayes factor
    for i in range(1,option._k_max+1):
        param[str(i)]=[]
        active_param[str(i)],chi[str(i)]=nu.zeros(3*i),[nu.inf]
        sigma[str(i)]=nu.identity(3*i)*nu.tile(
            [0.5,age_unq.ptp()*nu.random.rand(),1.],i)
        #active_dust[str(i)]=nu.random.rand(2)*5.
        #sigma_dust[str(i)]=nu.identity(2)*nu.random.rand()*2
        Nacept[str(i)],Nreject[str(i)]=1.,0.
        acept_rate[str(i)],out_sigma[str(i)]=[.35],[]
        bayes_fact[str(i)]=[]       
    
    #bins to start with
    try:
        bins = nu.random.randint(1,option._k_max)
    except ValueError:
        bins = 1
    while True:
    #create starting active params
        bin=nu.log10(nu.linspace(10**age_unq.min(),10**age_unq.max(),bins+1))
        bin_index=0
    #start in random place
        for k in xrange(3*bins):
            if any(nu.array(range(0,bins*3,3))==k):#metalicity
                active_param[str(bins)][k]=(nu.random.random()*metal_unq.ptp()+metal_unq[0])
            else:#age and normilization
                if any(nu.array(range(1,bins*3,3))==k): #age
                    active_param[str(bins)][k]=nu.random.random()*age_unq.ptp()+age_unq[0] #random place anywhere
                    bin_index+=1
                else: #norm
                    active_param[str(bins)][k]=nu.random.random()*10000
    #try leastquares fit
        if len(chi[str(bins)])==1:
            chi[str(bins)].append(0.)
    #active_param[str(bins)]=fun[str(bins)].n_neg_lest(active_param[str(bins)])
        (chi[str(bins)][-1],active_param[str(bins)][range(2,bins*3,3)]) = fun.lik(
            active_param[str(bins)], active_dust, active_losvd)
    #check if starting off in bad place ie chi=inf or nan
        if not nu.isfinite(chi[str(bins)][-1]):
            continue
        else:
            break
    
    param[str(bins)].append(nu.copy(nu.hstack((
                    active_param[str(bins)], active_dust, active_losvd))))
    #set best chi and param
    if option.chibest > chi[str(bins)][-1]:
        option.chibest[0] = chi[str(bins)][-1]+.0
        for kk in range(len(option.parambest)):
            if kk<bins*3+2+4:
                option.parambest[kk] = nu.hstack((active_param[str(bins)],
                                               active_dust,active_losvd))[kk]
            else:
                    option.parambest[kk] = nu.nan
    #set current swarm value
    for kk in range(len(option.swarm[0])):
        if kk<bins*3+2+4:
            option.swarm[0][kk] = nu.hstack((active_param[str(bins)],
                                                active_dust,active_losvd))[kk]
        else:
            option.swarm[0][kk] = nu.nan
    option.swarmChi[0]= chi[str(bins)][-1]
    #start rjMCMC
    T_cuurent,Nexchange_ratio = 0.0,1.0
    size = 0
    j,T,j_timeleft = 1,9.,nu.random.exponential(100)
    T_start,T_stop = 3*10**5., 1.
    birth_rate = 0.5
    out_dust_sig, out_losvd_sig = [sigma_dust], [sigma_losvd]
    #profiling
    t_pro,t_swarm,t_lik,t_accept,t_step,t_unsitc,t_birth,t_house,t_comm = [],[],[],[],[],[],[],[],[] 
    while option.iter_stop:
        if T_cuurent% 1000 == 0:
            print "hi, I'm at itter %i, chi %f from %s bins and from %i SA %2.2f" %(len(param[str(bins)]),chi[str(bins)][-1],bins, global_rank,SA_polymodal(T_cuurent,burnin,T_start,T_stop))
            sys.stdout.flush()

        #sample from distiburtion
        t_pro.append(Time.time())
        
        active_param[str(bins)] = fun.proposal(active_param[str(bins)],
                                               sigma[str(bins)])
        if fun._dust:
            active_dust = fun.proposal(active_dust,sigma_dust)
        if fun._losvd:
            active_losvd  = fun.proposal(active_losvd, sigma_losvd)
            active_losvd[1] = 0.
        t_pro[-1] -= Time.time()
        #swarm stuff
        t_swarm.append(Time.time())
        #if option.rank == 1:
            #print 'before',active_param[str(bins)] 
        active_param[str(bins)], active_dust, active_losvd, birth_rate = swarm_function(active_param[str(bins)],
                                                                                        active_dust, active_losvd, rank, birth_rate,
                                                                                        option,T_cuurent, burnin, fun, acept_rate[str(bins)][-1] )
        #if option.rank == 1:
            #print 'after',active_param[str(bins)] 

        t_swarm[-1] -= Time.time()
        #calculate new model and chi
        t_lik.append(Time.time())
        chi[str(bins)].append(0.)
        chi[str(bins)][-1],active_param[str(bins)][range(2,bins*3,3)]=fun.lik(
            active_param[str(bins)], active_dust, active_losvd)
        #sort by age
        if not nu.all(active_param[str(bins)][range(1,bins*3,3)]==
                      nu.sort(active_param[str(bins)][range(1,bins*3,3)])):
            index = nu.argsort(active_param[str(bins)][range(1,bins*3,3)])
            temp_index=[] #create sorting indcci
            for k in index:
                for kk in range(3):
                    temp_index.append(3*k + kk)
            active_param[str(bins)] = active_param[str(bins)][temp_index]
        #decide to accept or not
        a = nu.exp((chi[str(bins)][-2] - chi[str(bins)][-1])/
                 SA_polymodal(T_cuurent,burnin,T_start,T_stop))
        t_lik[-1]-=Time.time()
        t_accept.append(Time.time())
        #metropolis hastings
        if a > nu.random.rand(): #acepted
            print 'here'
            param[str(bins)].append(nu.copy(nu.hstack((active_param[str(bins)]
                                                       , active_dust,
                                                       active_losvd))))
            
            Nacept[str(bins)] += 1
            #put temperature on order of chi calue
            if nu.abs(nu.log10(T_start /chi[str(bins)][-1])) > 2 and T_cuurent < burnin:
                T_start = chi[str(bins)][-1]
            #see if global best fit
            if option.chibest > chi[str(bins)][-1]:
                option.chibest[0] = chi[str(bins)][-1]+.0
                for kk in xrange(option._k_max*3):
                    if kk<bins*3+2+4:
                        option.parambest[kk]=nu.hstack((active_param[str(bins)],
                                               active_dust, active_losvd))[kk]
                    else:
                        option.parambest[kk] = nu.nan
        else:
            param[str(bins)].append(nu.copy(param[str(bins)][-1]))
            active_param[str(bins)] = nu.copy(param[str(bins)][-1][range(3*bins)])
            if fun._dust:
                active_dust = nu.copy(param[str(bins)][-1][-6:-4])
            if fun._losvd:
                active_losvd = nu.copy(param[str(bins)][-1][-4:])
                
            chi[str(bins)][-1]=nu.copy(chi[str(bins)][-2])
            Nreject[str(bins)]+=1
        t_accept[-1]-=Time.time()
        ###########################step stuff
        t_step.append(Time.time())
        sigma[str(bins)],sigma_dust,sigma_losvd = Step_func(acept_rate[str(bins)][-1]
                                                            ,param[str(bins)][-2000:]
                                                            ,sigma[str(bins)],
                                                            sigma_dust,
                                                            sigma_losvd,
                                                            bins, j,fun._dust, 
                                                            fun._losvd)
        t_step[-1]-=Time.time()
        ############################determine if chain stuck and shake it out of it
        t_unsitc.append(Time.time())
        sigma[str(bins)],sigma_dust,sigma_losvd = unstick(acept_rate[str(bins)],param[str(bins)][-2000:],
                                                          sigma[str(bins)],sigma_dust, sigma_losvd, j, fun._dust, fun._losvd
                                                          , option.rank,T_cuurent)
        t_unsitc[-1]-=Time.time()
        #############################decide if birth or death
        t_birth.append(Time.time())
        active_param, temp_bins, attempt, critera = swarm_death_birth(fun, birth_rate, bins, j, j_timeleft, active_param)
        #calc chi of new model
        if attempt:
            attempt = False
            tchi, active_param[str(temp_bins)][range(2,temp_bins*3,3)] = fun.lik(
                active_param[str(temp_bins)], active_dust, active_losvd)
            bayes_fact[str(bins)].append(nu.exp((chi[str(bins)][-1]-tchi)/2.)*critera) #save acceptance critera for later
            #rjmcmc acceptance critera ##############
            if bayes_fact[str(bins)][-1]  > nu.random.rand():
                #print '%i has changed from %i to %i' %(rank,bins,temp_bins)
                #accept model change
                bins = temp_bins + 0
                chi[str(bins)].append(nu.copy(tchi))
                #sort by age so active_param[bins*i+1]<active_param[bins*(i+1)+1]
                if not nu.all(active_param[str(bins)][range(1,bins*3,3)] ==
                          nu.sort(active_param[str(bins)][range(1,bins*3,3)])):
                    index = nu.argsort(active_param[str(bins)][range(1,bins*3,3)])
                    temp_index = [] #create sorting indcci
                    for k in index:
                        for kk in range(3):
                            temp_index.append(3*k+kk)
                    active_param[str(bins)] = active_param[str(bins)][temp_index]
                param[str(bins)].append(nu.copy((nu.hstack((active_param[str(bins)],active_dust,active_losvd)))))
                j, j_timeleft = 0, nu.random.exponential(200)
                #continue
            if T_cuurent >= burnin:
                j, j_timeleft = 0, nu.random.exponential(200)
        else: #reset j and time till check for attempt jump
            j, j_timeleft = 0, nu.random.exponential(200)
        t_birth[-1]-=Time.time()
        #########################################change temperature
        '''if nu.min([1,nu.exp((chi[str(bins)][-2]-chi[str(bins)][-1])/(2.*SA(T_cuurent+1,burnin,T_start,T_stop))-(chi[str(bins)][-2]+chi[str(bins)][-1])/(2.*SA(T_cuurent,burnin,T_start,T_stop)))/T])>nu.random.rand():
            if T_cuurent<burnin:
                T_cuurent += 1
                #print T_cuurent,burnin,rank
            if T_cuurent==round(burnin):
                print 'done with cooling'
                T_cuurent += 1
            Nexchange_ratio+=1   
        #make sure the change temp rate is aroudn 20%
        if Nexchange_ratio/(nu.sum(Nacept.values())+nu.sum(Nreject.values()))>.25:
            T=T*1.05
        elif Nexchange_ratio/(nu.sum(Nacept.values())+nu.sum(Nreject.values()))<.20:
            T=T/1.05
        #change current temperature with size of param[bin]
        if len(param[str(bins)])<burnin:
            T_cuurent=len(param[str(bins)])'''
        T_cuurent += 1
        if T_cuurent==round(burnin):
            print 'done with cooling from %i' %global_rank 

    ##############################convergece assment
        
        ##############################house keeping
        t_house.append(Time.time())
        j+=1
        option.current += 1
        acept_rate[str(bins)].append(nu.copy(Nacept[str(bins)]/(Nacept[str(bins)]+Nreject[str(bins)])))
        #out_sigma[str(bins)].append(nu.copy(sigma[str(bins)].diagonal()))
        if fun._dust:
            out_dust_sig.append(nu.copy(sigma_dust))
        if fun._losvd:
            out_losvd_sig.append(nu.copy(sigma_losvd))
        t_house[-1]-=Time.time()
        #swarm update
        t_comm.append(Time.time())
        if T_cuurent<burnin or T_cuurent % 100 == 0:
            option.swarm_update(nu.hstack((active_param[str(bins)],active_dust,active_losvd)),
                                chi[str(bins)][-1],bins)
        
        #get other wokers param
        if  option.current % 200 == 0:
            option.get_best()
        t_comm[-1]-=Time.time()
        #pik.dump((t_pro,t_swarm,t_lik,t_accept,t_step,t_unsitc,t_birth,t_house,t_comm),open('time_%i.pik'%option.rank_world,'w'),2)
    #####################################return once finished 
    for i in param.keys():
        chi[i]=nu.array(chi[i])
        param[i]=nu.array(param[i])
        ###correct metalicity and norm 
        try:
            param[i][:,range(0,3*int(i),3)]=10**param[i][:,range(0,3*int(i),3)] #metalicity conversion
            param[i][:,range(2,3*int(i),3)]=param[i][:,range(2,3*int(i),3)] #*fun.norms #norm conversion
        except ValueError:
            pass
        #acept_rate[i]=nu.array(acept_rate[i])
        #out_sigma[i]=nu.array(out_sigma[i])
        bayes_fact[i] = nu.array(bayes_fact[i])
    pik.dump((t_pro,t_swarm,t_lik,t_accept,t_step,t_unsitc,t_birth,t_house,t_comm,param,chi),open('time_%i.pik'%option.rank_world,'w'),2)
    return param, chi, bayes_fact,acept_rate, out_sigma,rank

def RJMC_general(fun, option, swarm_function=vanilla, burnin=5*10**3,seed=None):
    '''does RJMC for a general likelhood class
    fun is MCMC class, option is multiprocessing class and 
    tells program when to stop, swarm_function is swarm class
    ,seed is random seed (optional)'''
    '''if not seed:
        nu.random.seed(random_permute(current_process().pid))
    else:
        nu.random.seed(seed)'''
    #initalize parameters from class
    param,active_param,chi,sigma={},{},{},{}
    Nacept,Nreject,acept_rate,out_sigma={},{},{},{}
    bayes_fact={} #to calculate bayes factor
    T_cuurent = {}
    for i in range(1,fun._max_order):
        #save chains
        param[str(i)] = []
        #current and i-1 chain and step size
        active_param[str(i)],sigma[str(i)] = fun.initalize_param(i)
        #log like holder
        chi[str(i)] = [-nu.inf]
        #mixing information
        Nacept[str(i)],Nreject[str(i)]=1.,0.
        acept_rate[str(i)],out_sigma[str(i)]=[.35],[]
        #RJMC bayes estimation (citiation) (doesn't work)
        bayes_fact[str(i)]=[]       
        T_cuurent[str(i)] = 0
    #choose order
    bins = nu.random.randint(fun._min_order,fun._max_order)
    #first lik calc
    chi[str(bins)][-1] = fun.lik(active_param[str(bins)])
    #check if starting off in bad place ie chi=inf or nan
    '''if not nu.isfinite(chi[str(bins)][-1]):
        continue
    else:
        break'''
    #store inital values
    param[str(bins)].append(active_param[str(bins)].copy())
    #set best chi and param
    if nu.isfinite(chi[str(bins)][-1]):
        option.chibest[0] = chi[str(bins)][-1]+.0
        for kk in range(len(option.parambest)):
            if len(active_param[str(bins)]) > kk:
                option.parambest[kk] = active_param[str(bins)][kk]
            else:
                    option.parambest[kk] = nu.nan
    #set current swarm value
    '''for kk in range(len(option.swarm[0])):
        if kk<bins*3+2+4:
            option.swarm[0][kk] = nu.hstack((active_param[str(bins)],
                                                active_dust,active_losvd))[kk]
        else:
            option.swarm[0][kk] = nu.nan
    option.swarmChi[0]= chi[str(bins)][-1]'''
    #start rjMCMC
    Nexchange_ratio = 1.0
    size,a = 0,0
    j,T,j_timeleft = 1,9.,nu.random.exponential(100)
    T_start,T_stop = 300, 1.
    birth_rate = 0.5
    trans_moves = 0
    #profiling
    t_pro,t_swarm,t_lik,t_accept,t_step,t_unsitc,t_birth,t_house,t_comm = [],[],[],[],[],[],[],[],[] 
    while option.iter_stop:
        if T_cuurent[str(bins)] % 20001 == 0:
            print acept_rate[str(bins)][-1],chi[str(bins)][-1],bins,option.current
            sys.stdout.flush()

        #sample from distiburtion
        t_pro.append(Time.time())
        active_param[str(bins)] = fun.proposal(active_param[str(bins)],
                                               sigma[str(bins)])
            
        t_pro[-1] -= Time.time()
        #swarm stuff
        t_swarm.append(Time.time())
        '''active_param[str(bins)], active_dust, active_losvd, birth_rate = swarm_function(active_param[str(bins)]'''
        #if option.rank == 1:
            #print 'after',active_param[str(bins)] 

        t_swarm[-1] -= Time.time()
        #calculate new model and chi
        t_lik.append(Time.time())
        chi[str(bins)].append(0.)
        chi[str(bins)][-1] = fun.lik(active_param[str(bins)])
        #print chi[str(bins)][-2], chi[str(bins)][-1] ,sigma[str(bins)].diagonal()
        #decide to accept or not change from log lik to like
        #just lik part
        a = (-(chi[str(bins)][-2] - chi[str(bins)][-1])
                 /SA_polymodal(T_cuurent[str(bins)],burnin,abs(T_start),T_stop))
        #priors
        a += (fun.prior(active_param[str(bins)]) - 
                    fun.prior(param[str(bins)][-1]))
        #print bins ,chi[str(bins)][-2], chi[str(bins)][-1], active_param[str(bins)]
        
        t_lik[-1]-=Time.time()
        t_accept.append(Time.time())
        #put temperature on order of chi calue
        '''if nu.abs(nu.log10(T_start /chi[str(bins)][-1])) > 2 and T_cuurent[str(bins)] < burnin:
            T_start = option.chibest[0]'''
        #metropolis hastings
        if nu.exp(a) > nu.random.rand(): #acepted
            param[str(bins)].append(nu.copy(active_param[str(bins)]))
            Nacept[str(bins)] += 1
           #see if global best fit
            if option.chibest < chi[str(bins)][-1] and nu.isfinite(chi[str(bins)][-1]):
                option.chibest[0] = chi[str(bins)][-1]+.0
                for kk in range(len(option.parambest)):
                    if len(active_param[str(bins)]) > kk:
                        option.parambest[kk] = active_param[str(bins)][kk]
                    else:
                        option.parambest[kk] = nu.nan
        else:
            try:
                param[str(bins)].append(nu.copy(param[str(bins)][-1]))
            except IndexError:
                #if first time in new place
                param[str(bins)].append(nu.copy(active_param[str(bins)]))
            active_param[str(bins)] = nu.copy(param[str(bins)][-1]) 
            chi[str(bins)][-1] = nu.copy(chi[str(bins)][-2])
            Nreject[str(bins)]+=1
        t_accept[-1]-=Time.time()
        ###########################step stuff
        t_step.append(Time.time())
        if T_cuurent[str(bins)] < burnin + 5000:
            #only tune step if in burn-in
            sigma[str(bins)] =  fun.step_func(acept_rate[str(bins)][-1] ,param[str(bins)][-2000:],sigma[str(bins)],bins)
        t_step[-1]-=Time.time()
        ############################determine if chain stuck and shake it out of it
        t_unsitc.append(Time.time())
        '''sigma[str(bins)],sigma_dust,sigma_losvd = unstick(acept_rate[str(bins)],param[str(bins)][-2000:],
                                                          sigma[str(bins)],sigma_dust, sigma_losvd, j, fun._dust, fun._losvd
                                                          , option.rank,T_cuurent)'''
        t_unsitc[-1]-=Time.time()
        #############################decide if birth or death
        t_birth.append(Time.time())
        if j >= j_timeleft:
            active_param, temp_bins, attempt, critera, j, j_timeleft = fun.birth_death(birth_rate, bins, j, j_timeleft, active_param)
            if attempt:
                #check if accept move
                tchi = fun.lik(active_param[str(temp_bins)])
                #likelihoods
                rj_a = (-(chi[str(bins)][-1]-tchi)/
                              SA(trans_moves,100,5000.,T_stop))
                #parameter priors
                rj_a += (fun.prior(active_param[str(temp_bins)]) - 
                         fun.prior(active_param[str(bins)]))
                #model priors
                rj_a += 0 #uniform
                trans_moves += 1
                #print rj_a , critera, temp_bins>bins
                if nu.exp(rj_a) * critera > nu.random.rand():
                    #accept move
                    bins = temp_bins +0
                    chi[str(bins)].append(tchi + 0)
                    param[str(bins)].append(nu.copy(active_param[str(bins)]))
                    #print T_cuurent[str(bins)],burnin,T_start,T_stop
                attempt = False
        t_birth[-1]-=Time.time()
        #########################################change temperature
        T_cuurent[str(bins)] += 1
        if T_cuurent[str(bins)]==round(burnin):
            pass#print 'done with cooling from %i' %global_rank 

    ##############################convergece assment
       
        ##############################house keeping
        t_house.append(Time.time())
        j+=1
        option.current += 1
        acept_rate[str(bins)].append(nu.copy(Nacept[str(bins)]/(Nacept[str(bins)]+Nreject[str(bins)])))
        out_sigma[str(bins)].append(nu.copy(sigma[str(bins)].diagonal()))
        t_house[-1]-=Time.time()
        #swarm update
        t_comm.append(Time.time())
        '''if T_cuurent<burnin or T_cuurent % 100 == 0:
            option.swarm_update(nu.hstack((active_param[str(bins)],active_dust,active_losvd)),
                                chi[str(bins)][-1],bins)
        '''
        #get other wokers param
        '''if  option.current % 200 == 0:
            option.get_best()'''
        t_comm[-1]-=Time.time()
        #if mpi isn't on allow exit
        if option.comm_world.size == 1:
            if option.current > 2*10**5:
                option.iter_stop = False
        #pik.dump((t_pro,t_swarm,t_lik,t_accept,t_step,t_unsitc,t_birth,t_house,t_comm),open('time_%i.pik'%option.rank_world,'w'),2)
    #####################################return once finished 
    for i in param.keys():
        chi[i]=nu.array(chi[i])
        param[i]=nu.array(param[i])
        ###correct metalicity and norm 
        bayes_fact[i] = nu.array(bayes_fact[i])
    #pik.dump((t_pro,t_swarm,t_lik,t_accept,t_step,t_unsitc,t_birth,t_house,t_comm,param,chi),open('time_%i.pik'%option.rank_world,'w'),2)
    return param, chi, bayes_fact, acept_rate, out_sigma

#mpi run
def mpi_general(fun, topology, swarm_func=vanilla, burnin=5000, itter=10**5):
    '''From MPI start, starts workers doing RJMCMC and coordinates comunication 
    topologies'''
   #start RJMCMC SWARM 
    N = 3 #output number
    if not topology.rank == 0:
        #output is: [param, chi, bayes_fact, acept_rate, out_sigma, rank]
        print 'Starting rank %i on %s.'%(topology.rank_world,mpi.Get_processor_name())    
        temp = RJMC_general(fun, topology, swarm_func, burnin=burnin)
        #temp = [param, chi, bayes_fact]
        #print topology.iter_stop
        print 'rank %i on %s is complete'%(topology.rank_world,mpi.Get_processor_name())
        #topology.comm_world.isend(topology.rank_world,dest=0,tag=99)
        #print topology.iter_stop
        #topology.comm_world.barrier()
        for i in range(N):
            topology.comm_world.send(temp[i], dest=0,tag=99)
        return None,None,None
    else:
    #while rjmcmc is  root process is running update curent iterations and gather best fit for swarm
        print 'starting root on %i on %s'%(topology.rank,mpi.Get_processor_name())
        stop_iter = burnin * topology.size_world + itter
        #dummy param for swarm
        time = Time.time()
        i = 1
        while (topology.global_iter <= stop_iter and nu.any(topology.iter_stop)): 
            #get swarm values from other workers depending on topology
            topology.get_best()
            topology.swarm_update(topology.parambest,topology.chibest, (nu.isfinite(topology.parambest).sum() - 6)/3)
            #get total iterations
            Time.sleep(.1)
            if Time.time() - time > 5:
                print '%2.2f percent done at %i' %((float(topology.global_iter) / stop_iter) * 100., 
                                                   topology.global_iter)
                sys.stdout.flush()
                time = Time.time()
                #print topology.current
            #pik.dump((topology.swarm,topology.swarmChi),open('swarm','w'),2)
            i += 1
        #put in convergence diagnosis
        #tell other workers to stop
        print 'Sending stop signal.'
        for i in xrange(1,topology.comm_world.size):
            topology.iter_stop[:,i] = 0
        t= Time.time()
        while True:
            topology.get_best(True)
            #Time.sleep(1)
            if Time.time() -t >15: #or len(done) == topology.size_world:
                break
        
        #get results from other processes
        print 'Root reciving.'
        temp =[]
        i= 1
        time = Time.time() 
        while Time.time() - time < 60:
        #for i in xrange(1,topology.size_world):
            if topology.comm_world.Iprobe(source=i,tag=99):
                print 'getting data from %i '%(i)
                t=[]
                for k in xrange(N):
                    t.append( topology.comm_world.recv(source=i,tag=99))
                temp.append(t)
                print 'done from %i '%(i)
            i+=1
            if i > topology.comm_world.size -1:
                i = 1
        print 'done reciving'
        try:
            param, chi, bayes = dic_data(temp, burnin)
        except IndexError:
            pass
        #save accept rate and sigma for output
        return param, chi, t



#########swarm functions only in this program######
def swarm_vect(pam, active_dust, active_losvd, rank, birth_rate, option):
    '''does swarm vector calculations and returns swarm*c+active.
    if not in same bin number, just chnages dust,losvd and birthrate to pull it towards
    other memebers'''
    tot_chi = 0.
    #prob to birth a new ssp
    up_chance = 0.
    #random weight for each swarm array
    u = nu.random.rand() *.1
    swarm_param,swarm_dust,swarm_losvd = [],[],[]
    bins = pam.shape[0]/3
    for i in xrange(len(option.swarmChi)):
        tot_chi += 1/option.swarmChi[:,i]
        temp_array = nu.array(option.swarm[:,i])
        temp_array = temp_array[nu.isfinite(temp_array)]
        if len(temp_array) == 0:
            continue
        temp_pam = temp_array[:-6]
        temp_dust,temp_losvd = temp_array[-6:-4], temp_array[-4:]
        temp_bins = temp_pam.shape[0]/3
        #get direction to other in swarm
        if temp_pam.shape[0] == pam.shape[0]:
            swarm_param.append(pam - temp_pam)
        elif temp_pam.shape[0] > pam.shape[0]:
            #if not in same number of param take closest one or one with most weight
            index = temp_pam[range(2,temp_bins*3,3)].argsort()[-bins:]
            t =[]
            for j in index:
                t.append(temp_pam[j*3:j*3+3])
            swarm_param.append(pam - nu.ravel(t))
            '''elif temp_pam.shape[0] < pam.shape[0] :
            #if not in same number of param take closest one or one with most weight
            index = pam[range(2,bins*3,3)].argsort()[-temp_bins:]
            t = pam.copy()
            for j in xrange(len(index)):
                t[index[j]*3:index[j]*3+3] = t[index[j]*3:index[j]*3+3] - temp_pam[j*3:j*3+3]
            swarm_param.append(t)'''
        else:
            swarm_param.append(False)
        if nu.any(swarm_param[-1]):
            swarm_dust.append(active_dust - temp_dust)
            swarm_losvd.append(active_losvd - temp_losvd)
        else:
            swarm_dust.append(False)
            swarm_losvd.append(False)
        #except ValueError:
            
        if len(temp_array) > len(pam):
            up_chance += 1/option.swarmChi[:,i]
    up_chance /= tot_chi
    #make out array
    out_param, out_dust, out_losvd = pam, active_dust, active_losvd
    for i in xrange(len(swarm_param)):
        try:
            weight = 1/option.swarmChi[:,i]/ tot_chi
            if nu.any(swarm_param[i]):
                out_param = out_param - weight * swarm_param[i] * u
                out_dust = out_dust - weight * swarm_dust[i] * u
                out_losvd = out_losvd - weight * swarm_losvd[i] * u
            if option.swarmChi[:,0]/option.swarmChi.min() > 100:
                #print out_param, rank 
                pass
        except ValueError:
            pass
    return out_param, out_dust, out_losvd, up_chance



def swarm_death_birth(fun, birth_rate, bins, j,j_timeleft, active_param):
    #does birth or death moved
        attempt = False
        if ((birth_rate > nu.random.rand() and bins < len(active_param.keys()) and 
             j > j_timeleft ) or (j > j_timeleft and bins == 1 and bins < len(active_param.keys()))):
            #birth
            attempt = True #so program knows to attempt a new model
            rand_step = nu.random.rand(3)*[fun._metal_unq.ptp(), fun._age_unq.ptp(),1.]
            rand_index = nu.random.randint(bins)
            temp_bins = 1 + bins
            #criteria for this step
            critera = 1/4.**3 * birth_rate #(1/3.)**temp_bins
            #new param step
            for k in range(len(active_param[str(bins)])):
                active_param[str(temp_bins)][k]=active_param[str(bins)][k]
            #set last 3 and rand_index 3 to new
            if .5 > nu.random.rand(): #x'=x+-u
                active_param[str(temp_bins)][-3:] = (active_param[str(bins)][rand_index*3:rand_index*3+3] + 
                                                     rand_step)
                active_param[str(temp_bins)][rand_index*3:rand_index*3+3] = (
                    active_param[str(bins)][rand_index*3:rand_index*3+3] - rand_step)
                k = 0
                #check to see if in bounds
                while fun.prior(nu.hstack((active_param[str(temp_bins)],
                                           nu.zeros(2)))): 
                    k += 1
                    if k < 100:
                        rand_step = nu.random.rand(3) * [fun._metal_unq.ptp(), fun._age_unq.ptp(),1.]
                    else:
                        rand_step /= 2.
                    active_param[str(temp_bins)][-3:] = (
                        active_param[str(bins)][rand_index*3:rand_index*3+3] + rand_step)
                    active_param[str(temp_bins)][rand_index*3:rand_index*3+3]=(
                        active_param[str(bins)][rand_index*3:rand_index*3+3]-rand_step)
            else: #draw new values randomly from param space
                active_param[str(temp_bins)][-3:] = (nu.random.rand(3) * 
                                                     nu.array([fun._metal_unq.ptp(), fun._age_unq.ptp(),5.]) + 
                                                     nu.array([fun._metal_unq.min(), fun._age_unq.min(), 0]))
        elif j > j_timeleft and bins > 1 and  0.01 < nu.random.rand():
            #death
            attempt = True #so program knows to attempt a new model
            Num_zeros = active_param[str(bins)][range(2,bins*3,3)] == 0
            if Num_zeros.sum() > 1:
                #remove all parts with zeros
                temp_bins = bins - Num_zeros.sum()
                #criteria for this step
                critera = 4.**(3*temp_bins) * (1 - birth_rate) 
                k = 0
                for ii in range(bins):
                    if not active_param[str(bins)][ii*3+2] == 0:
                        active_param[str(temp_bins)][k*3:k*3+3] = active_param[str(bins)][ii*3:ii*3+3].copy()
                        k += 1
            else:
                #choose randomly
                critera = 4.**3 * (1 - birth_rate)
                temp_bins = bins - 1
                Ntot = nu.sum(active_param[str(bins)][range(2,bins*3,3)])
                rand_index = (rand_choice(active_param[str(bins)][range(2,bins*3,3)],
                                      active_param[str(bins)][range(2,bins*3,3)]/Ntot))
                k = 0
                for ii in xrange(bins): #copy to lower dimestion
                    if not ii == rand_index:
                        active_param[str(temp_bins)][3*k:3*k+3] = nu.copy(active_param[str(bins)]
                                                                          [3*ii:3*ii+3])
                        k += 1
        if attempt:
            if temp_bins == 0:
                temp_bins += 1
            return active_param, temp_bins, attempt, critera
        else:
            return active_param, None, attempt, None

def SA_polymodal(i,length,T_start,T_stop, modes=1):
    ''' Does anneling with few nodes using a cos**2 function'''
    if modes % 2. == 0 and modes != 1:
        modes += 1
    elif modes == 1:
        pass
    else:
        modes += 2
    if i < length:
        out = (T_start - T_stop)*nu.cos(i/float(length)*modes*nu.pi/2.)**2 + T_stop
        if out > 1.:
            return out
        else:
            return 1.
    else:
        return 1.

def  unstick(acept_rate, param, sigma, sigma_dust, sigma_losvd, iteration, is_dust, is_losvd,rank,
             T_current):
    '''checks to see if worker is stick and injects a temperature into worker to get it out'''
    if not iteration % 50 == 0:
        #only check every once in a while
        return sigma ,sigma_dust, sigma_losvd
    rate = nu.array(acept_rate)
    Param = nu.array(param)[:,1]
    if nu.median(rate[-2000:]) < .1 and len(nu.unique(Param)) < 200 and len(Param) > 999:
        print 'worker %i is stuck' %rank
        if nu.any(sigma.diagonal() < 10**-10):
            sigma = nu.zeros_like(sigma) + .1
            sigma_dust = nu.ones((2,2))/1.
            sigma_losvd=nu.ones((4,4))/1.
            return sigma ,sigma_dust, sigma_losvd
        else:
            return sigma*10 ,sigma_dust*10, sigma_losvd*10
    else:
        return sigma ,sigma_dust, sigma_losvd

def Convergence_tests(param,keys,n=1000):
    #uses Levene's test to see if var between chains are the same if that is True
    #uses f_oneway (ANOVA) to see if means are from same distrubution 
    #if both are true then tells program to exit
    #uses last n chains only
    for i in param:
        for j in keys:
            i[j]=nu.array(i[j])
    ad_k
    D_result={}
    for i in keys:
        for k in range(param[0][i].shape[1]):
            samples='' 
            for j in range(len(param)):
                samples+='param['+str(j)+']["'+i+'"][-'+str(int(n))+':,'+str(k)+'],'
        D_result[i]=eval('ad_k('+samples[:-1]+')')[-1]>.05
    if any(D_result.values()):
        print 'A-D test says they are the same'
        return True
    #try kustkal test
    A_result={}
    out=False
    for i in keys:
        A_result[i]=nu.zeros(param[0][i].shape[1])
        for k in range(param[0][i].shape[1]):
            samples='' 
            for j in range(len(param)):
                samples+='param['+str(j)+']["'+i+'"][-'+str(int(n))+':,'+str(k)+'],'
            A_result[i][k]=eval('kruskal('+samples[:-1]+')')[1]
        if nu.all(A_result[i]>.05): #if kruskal test is true
            out=True
            print "ANOVA says chains have converged. Ending program"
            return True            
        else:
            print '%i out of %i parameters have same means' %(sum( A_result[i]>.05),
                                                              param[0][i].shape[1])
    #do ANOVA to see if means are same
    if out:
        L_result={}
        out=False
        #turn into an array
        for i in keys:
            param[0][i]=nu.array(param[0][i])
            L_result[i]=nu.zeros(param[0][i].shape[1])
            for k in range(param[0][i].shape[1]):
                samples='' 
                for j in range(len(param)):
                    samples+='param['+str(j)+']["'+i+'"][-'+str(int(n))+':,'+str(k)+'],'
                L_result[i][k]=eval('levene('+samples[:-1]+')')[1]
            if nu.all(L_result[i]>.05): #if leven test is true
                print "Levene's test is true for %s bins" %i
                return True
            else:
                print '%i out of %i parameters have same varance' %(sum( L_result[i]>.05),
                                                                param[0][i].shape[1])
    return False

def get_crash(path):
    '''recovers data from crash run'''
    pass

#====================================================
class Topologies(object):
    """Topologies( cpus='max'. top='cliques', k_max=16)
    Defines different topologies used in communication. Will probably affect
    performance if using a highly communicative topology.
    Topologies include :
    all, ring, cliques and square.
    all - every worker is allowed to communicate with each other, no buffer
    ring -  the workers are only in direct contact with 2 other workers
    cliques - has 1 worked connected to other head workers, which talks to all the other sub workers
    square - every worker is connect to 4 other workers
    cpus is number of cpus (max or number) to run chains on, k_max is max number of ssps to combine"""

    def Single(self):
        #Using mpi but want to run chains independantly
        #if mpi is avalible
        if not mpi is None:
            self.comm = mpi.COMM_SELF
            self.size = self.comm.Get_size()
            self.rank = self.comm.Get_rank()
            self.comm_world = mpi.COMM_SELF
            self.rank_world = self.comm_world.Get_rank()
            self.size_world = self.comm_world.Get_size()
        else:
            self.comm = None
            self.size = 1
            self.rank = 0
            self.comm_world = None
            self.rank_world = 0
            self.size_world = 1



    def All(self):
        #all workers talk to eachother
        self.comm = mpi.COMM_WORLD
        self.size = self.comm.Get_size()
        self.rank = self.comm.Get_rank()
        self.comm_world = mpi.COMM_WORLD
        self.rank_world = self.comm_world.Get_rank()
        self.size_world = self.comm_world.Get_size()

    def Ring(self):
        '''makes ring topology'''
        self.comm_world = mpi.COMM_WORLD
        self.rank_world = self.comm_world.Get_rank()
        self.size_world = self.comm_world.Get_size()
        r_index = range(2,2 * self.size_world+2,2)
        index = range(self.size_world)
        edges = []
        for i in index:
            if i - 1 < 0:
                edges.append(max(index))
            else:
                edges.append( i-1)
            if i + 1 > max(index):
                edges.append(min(index))
            else:
                edges.append( i + 1)
        self.comm = self.comm_world.Create_graph(r_index, edges, True)
        self.rank = self.comm.Get_rank()
        self.size = self.comm.Get_size()

    def Cliques(self, N=10):
        #N = 3
        self.comm_world = mpi.COMM_WORLD
        self.rank_world = self.comm_world.Get_rank()
        self.size_world = self.comm_world.Get_size()
        #setup comunication arrays to other workers + 1 from world
        head_nodes = nu.arange(N)
        workers = []
        for i in xrange(N):
            workers.append([i])
        j = 0
        for i in xrange(max(head_nodes) + 1, self.size_world):
            workers[j].append(i)
            j+=1
            if j == N:
                j=0
        #make index and edges
        index,edges = [],[]
        #workers
        j = 0
        #print 'world',self.size_world 
        for i in range(self.size_world - len(head_nodes)):
            if len(index) == 0:
                index.append(len(workers[j]))
            else:
                index.append(index[-1] + len(workers[j]))
            edges.append(workers[j])
            if (i + 1) % (len(workers[j]) - 1) == 0:
                j += 1
            if j >= len(workers):
                break
        #head nodes
        for i in head_nodes:
            temp = nu.unique(nu.hstack((workers[i],head_nodes)))
            edges.append(list(temp[temp != i]))
            index.append(index[-1] + len(edges[-1]))
        n_edge =[]
        for i in edges:
            for j in i:
                n_edge.append(j)
        self.comm = self.comm_world.Create_graph(index, n_edge, True)
        self.rank = self.comm.Get_rank()
        self.size = self.comm.Get_size()

    def Square(self):
        #Each worker communicates with max of 4 other workers
        Nrow = 3
        #make grid cartiesian grid
        self.comm_world = mpi.COMM_WORLD
        self.rank_world = self.comm_world.Get_rank()
        self.size_world = self.comm_world.Get_size()
        #make grid
        Ncoulms = self.size_world/Nrow
        if self.size_world % Nrow != 0:
            print 'Warrning: Not cylindrical, workers may not work correctly'
        tot = 0
        grid = []
        for i in xrange(Ncoulms):
            for j in range(Nrow):
                grid.append(nu.array([j,i]))
                tot += 1
        #fill in grid if points left over
        i = 0
        while tot < self.size_world:
            grid.append((j,i))
            i += 1
        grid = nu.array(grid)   
        edges,ind=[],[]
        #make comunication indicies
        for i in range(self.size_world):
            #find 4 closest workers
            min_dist = nu.zeros((4,2)) +9999999
            for k in range(min_dist.shape[0]):
                for j in range(self.size_world):
                    if (min_dist[k][0] > nu.sqrt((grid[i][0] - grid[j][0])**2 + (grid[i][1] - grid[j][1])**2) 
                        and i != j):
                        if not nu.any(min_dist[:,1] == j):
                            min_dist[k][0] = nu.sqrt((grid[i][0] - grid[j][0])**2 + (grid[i][1] - grid[j][1])**2)
                            min_dist[k][1] = nu.copy(j)
            #if on edged of grid, wrap around
            if nu.any(grid[i] == 0): #top or left side
                if grid[i][0] == 0: #top
                    #find one on bottom
                    index = min_dist[:,0].argmax()
                    Index = nu.nonzero(nu.logical_and(grid[:,0] == Nrow - 1,grid[:,1] == grid[i,1]))[0]
                    min_dist[index] = [0,Index[0].copy()]
                if grid[i][1] == 0: #left
                    index = min_dist[:,0].argmax()
                    Index = nu.nonzero(nu.logical_and(grid[:,0] == grid[i,0],grid[:,1] == Ncoulms-1))[0]
                    min_dist[index]= [0,Index[0].copy()]
            if nu.any(grid[i]  == Ncoulms - 1): #right side and maybe bottom
                if grid[i][1] == Ncoulms - 1: #right
                    index = min_dist[:,0].argmax()
                    Index = nu.nonzero(nu.logical_and(grid[:,1] == 0,grid[:,0] == grid[i,0]))[0]
                    min_dist[index] = [0,Index[0].copy()]
                if grid[i][0] == Nrow - 1: #bottom
                    index = min_dist[:,0].argmax()
                    Index = nu.nonzero(nu.logical_and(grid[:,1] == grid[i,1],grid[:,0] == 0))[0]
                    min_dist[index] = [0,Index[0].copy()]
            '''if grid[i][0]  == Nrow - 1: #def bottom
                index = min_dist[:,0].argmax()
                Index = nu.nonzero(nu.logical_and(grid[:,1] == grid[i,1],grid[:,0] == 0))[0]
                min_dist[index] = [0,Index[0].copy()]'''
            if nu.any(grid[i]  == Ncoulms): #extra grid on right side
                print 'bad'
            t =[]
            for k in range(min_dist.shape[0]):
                t.append(int(min_dist[k,1]))
            edges.append(t)
            if len(ind) == 0:
                ind.append(min_dist.shape[0])
            else:
                ind.append(ind[-1] + min_dist.shape[0])
        n_edge =[] 
        for i in edges:
            for j in i:
                n_edge.append(j)
        self.comm = self.comm_world.Create_graph(ind, n_edge, True)
        self.rank = self.comm.Get_rank()
        self.size = self.comm.Get_size()
    
    def get_neighbors(self,rank):
        '''for All, since doesn't use make cartisian grid'''
        return range(self.size)

    #====Update stuff====
    def thuso_min(self, x, y):
            if x[0] >y[0]:
                return y
            else:
                return x

    def init_sync_var(self):
        '''initates send and recive varibles'''
        #print self.send_to,self.reciv_from,self.swarmChi
        if self.rank_world == 0:
            #does stop signal to all
            self.iter_stop = nu.ones((1,self.comm_world.size),dtype=int)
            for i in xrange(1,self.comm_world.size):
                self._stop_buffer.append(self.comm_world.Send_init((
                            self.iter_stop[:,i],mpi.INT),dest=i,tag=1))
                #recive best chi,param and current iteration from others
            #make chibest,parambest and current temp arrays
            self._chibest = {}
            self._parambest = {}
            self._current = {}
            for i in xrange(1,self.size_world):
                self._chibest[str(i)] = nu.zeros((1,1)) + nu.inf
                self._parambest[str(i)] = nu.zeros_like(self.parambest) + nu.nan
                self._current[str(i)] = nu.zeros((1,1),dtype=int)
                #make buffer for recv and send best param 
                self._update_buffer.append(self.comm_world.Recv_init((
                            self._chibest[str(i)],mpi.DOUBLE),source=i,tag=2))
                self._update_buffer.append(self.comm_world.Recv_init((
                            self._parambest[str(i)],mpi.DOUBLE),source=i,tag=3))
                self._update_buffer.append(self.comm_world.Recv_init((
                            self._current[str(i)],mpi.INT),source=i,tag=4))
                #self._update_buffer = []      
        else:
            self._stop_buffer.append(self.comm_world.Recv_init((self.iter_stop,mpi.INT), source=0,tag=1))
          #send best chi to root and recive best chi from root
            self._update_buffer.append(self.comm_world.Send_init((self.chibest,mpi.DOUBLE),dest=0,tag=2))
            self._update_buffer.append(self.comm_world.Send_init((self.parambest,mpi.DOUBLE),dest=0,tag=3))
            self._update_buffer.append(self.comm_world.Send_init((self.current,mpi.INT),dest=0,tag=4))
        #send best param as part of swarm and recive swarm
        for i in xrange(len(self.send_to)):
                #send my stuff
            self.buffer.append(self.comm.Send_init((self.swarm[:,0],mpi.DOUBLE),dest=self.send_to[i],tag=5))
            self.buffer.append(self.comm.Send_init((self.swarmChi[:,0],mpi.DOUBLE),dest=self.send_to[i],tag=6))
        for i in xrange(len(self.reciv_from)):
            #recive other stuff
            self.buffer.append(self.comm.Recv_init((self.swarmChi[:,i+1],mpi.DOUBLE),source=self.reciv_from[i],tag=6))
            self.buffer.append(self.comm.Recv_init((self.swarm[:,i+1],mpi.DOUBLE),source=self.reciv_from[i],tag=5))
  
    def get_best(self, op=False):
       #updates chain info
       #checks to see if should stop
        mpi.Prequest.Startall(self._update_buffer)
        if self.rank_world == 0:
            mpi.Prequest.Waitany(self._update_buffer)
            if op:
                mpi.Prequest.Startall(self._stop_buffer)
                mpi.Prequest.Waitall(self._stop_buffer)
              #find best fit
            for i in self._current.keys():
                #print self._parambest[i],i
                if self._current[i] > 199:
                    self.global_iter += self._current[i]
                    self._current[i][0] = 0
                
                if self._chibest[i] < self.chibest:
                    self.chibest = self._chibest[i] + 0
                    self.parambest = self._parambest[i].copy()
                    num = (nu.isfinite(self.parambest).sum() - 6)/3
                    print '%i has best fit with a chi of %2.2f and %i' %(int(i),self.chibest,num)                    
                    sys.stdout.flush()
        else:
            mpi.Prequest.Testall(self._update_buffer)
            if self.comm_world.Iprobe(source=0, tag=1):
                Time.sleep(5)
                mpi.Prequest.Startall(self._stop_buffer)
                mpi.Prequest.Waitall(self._stop_buffer)
            if self.current > 199:
                self.current = nu.array([[0]])
                #print self.iter_stop

    def swarm_update(self,param, chi,bins):
        '''Updates positions of swarm using topology'''
        for kk in xrange(len(self.swarm[:,0])):
            if kk<bins*3+2+4:
                self.swarm[:,0][kk] = param[kk]
            else:
                self.swarm[:,0][kk] = nu.nan
        self.swarmChi[:,0] = chi
        mpi.Prequest.Startall(self.buffer)
        mpi.Prequest.Testany(self.buffer)
        
    def make_swarm(self):
        #who to send to and who to recieve from
        try:
            self.send_to = nu.array(self.comm.Get_neighbors(self.rank))
        except AttributeError:
            #if all no get_neighbors will be found
            self.send_to = nu.array(self.get_neighbors(self.rank))
        self.send_to = nu.unique(self.send_to[self.send_to != self.rank])
        self.reciv_from = []
        try:
            for i in xrange(self.size):
                if nu.any(nu.array(self.comm.Get_neighbors(i)) == self.rank) and i != self.rank:
                    self.reciv_from.append(i)
            self.reciv_from = nu.array(self.reciv_from)
        except AttributeError:
            self.reciv_from = self.send_to.copy()
        #makes large array for sending and reciving
        self.swarm = nu.zeros([len(self.reciv_from)+1, self._k_max * 3 + 2 + 4],order='Fortran') + nu.nan
        self.swarmChi = nu.zeros((1,len(self.reciv_from)+1),order='Fortran') + nu.inf

    def __init__(self, top = 'cliques', k_max=10):
        self._k_max = k_max
        #number of iterations done
        self.current = nu.array([[0]])
        self.global_iter = 0
        #number of workers to create
        #local_cpu = cpu_count()
        if not mpi is None:
            comm = mpi.COMM_WORLD
            size = comm.Get_size()
            rank = comm.Get_rank()
        else:
            comm = None
            size = 1
            rank = 0
        #commuication buffers
        #[(param,source),(chi,source)]
        self.buffer = []
        self._stop_buffer = []
        self._update_buffer = []
        #simple manager just devides total processes up
        self.iter_stop = nu.array([[True]],dtype=int)
        self.chibest = nu.array([[nu.inf]],dtype=float)
        self.parambest = nu.ones(k_max * 3 + 2 + 4) + nu.nan
        #check if topology is in list
        if not top in ['all', 'ring', 'cliques', 'square','single']:
            raise ValueError('Topology is not in list.')
        if top.lower() == 'all':
            self.All()
        elif top.lower() == 'ring':
            self.Ring()
        elif top.lower() == 'cliques':
            self.Cliques()
        elif top.lower() == 'square':
            self.Square()
        elif top.lower() == 'single':
            self.Single()
        #print self.iter_stop
        try:
            self.make_swarm()
            self.init_sync_var()
        except:
            pass
                

if __name__ == '__main__':
    import Age_date as ag
    comm = mpi.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
    if rank == 0:
        data,info,weight,dust = ag.iterp_spec(3,'sinc',lam_min=4000, lam_max=8000)
        data_len = nu.array(data.shape)
        comm.bcast(data_len,0)
    else:
        data_len = nu.zeros(2,dtype=int)
        comm.bcast(data_len,0)
        data = nu.zeros(data_len)
    data = comm.bcast(data, 0)
    fun = MC_func(data)
    fun.autosetup()
    if rank == 0:
        print info,size
    #print size,rank
    for i in ['ring','square','cliques', 'all']:
        Top = Topologies(i)
        #print i, Top.iter_stop
        Top.comm_world.barrier()
        param, chi, bayes = root_run(fun.send_class, Top, itter=10**4, burnin=500 , k_max=10, func=vanilla)
        if rank == 0:
            pik.dump((param,chi,data),open(i+info[0]+'.pik','w'),2)
            #copy times into dir
            os.popen('mkdir %s' %i)
            os.popen('mv *.pik %s/' %i)
            print info
            Top.comm_world.barrier()
        else:
            Top.comm_world.barrier()
