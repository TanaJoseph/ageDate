#!/usr/bin/env python
#
# Name:  likelihood_class
#
# Author: Thuso S Simon
#
# Date: 25 of April, 2013
#TODO: 
#
#    vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv
#    Copyright (C) 2013 Thuso S Simon
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
""" Likelihood classes for running of MCMC, RJMCMC and other fitting methods. 
First class is and example and has all required methods needed to run MCMC or
RJMCMC. Also has specific classes for use of spectral fitting"""

import numpy as nu
from glob import glob
import spectra_utils as ag
import ezgal as gal
import scipy.stats as stats_dist
from scipy.special import erfinv
import multiprocessing as multi
from itertools import izip
from scipy.cluster.hierarchy import fcluster,linkage
import os, sys, subprocess
from time import time
import MC_utils as MC
import pdb
#hdf5 handling stuff
import database_utils  as  utils
try:
    import tables as tab
except ImportError:
    pass
#meqtrees stuff
try:
    import pyrap.tables
    import scipy.constants as sc
    from Timba import dmi
    from Timba.Meq import meq
    from Timba.Apps import meqserver
    from Timba.TDL import Compile
    from Timba.TDL import TDLOptions
except ImportError:
    pass

np=nu

class Example_lik_class(object):

    '''exmaple class for use with RJCMCM or MCMC program, all methods are
    required and inputs are required till the comma, and outputs are also
    not mutable. The body of the class can be filled in to users delight'''

    def __init__(self,):
        '''(Example_lik_class,#user defined) -> NoneType or userdefined

        initalize class, can do whatever you want. User to define functions'''
        #return #whatever you want or optional
        #needs to have the following as the right types
        
        #self.models = {'name of model':[param names or other junk],'name2':nu.asarray([junk])} #initalizes models
        #self._multi_block = False
        raise NotImplementedError


    def proposal(self,mu,sigma):
        '''(Example_lik_class, ndarray,ndarray) -> ndarray
        Proposal distribution, draws steps for chain. Should use a symetric
        distribution'''
        
        #return up_dated_param 
        raise NotImplementedError

    def lik(self,param,bins):
        '''(Example_lik_class, ndarray) -> float
        Calculates likelihood for input parameters. Outuputs log-likelyhood'''
        
        #return loglik
        raise NotImplementedError

    def prior(self,param,bins):
        '''(Example_lik_class, ndarray) -> float
        Calculates log-probablity for prior'''
        #return logprior
        raise NotImplementedError


    def model_prior(self,model):
        '''(Example_lik_class, any type) -> float
        Calculates log-probablity prior for models. Not used in MCMC and
        is optional in RJMCMC.'''
        #return log_model
        raise NotImplementedError

    def initalize_param(self,model):
        '''(Example_lik_class, any type) -> ndarray, ndarray

        Used to initalize all starting points for run of RJMCMC and MCMC.
        outputs starting point and starting step size'''
        #return init_param, init_step
        raise NotImplementedError

        
    def step_func(self,step_crit,param,step_size,model):
        '''(Example_lik_class, float, ndarray or list, ndarray, any type) ->
        ndarray

        Evaluates step_criteria, with help of param and model and 
        changes step size during burn-in perior. Outputs new step size
        '''
        #return new_step
        raise NotImplementedError

    def birth_death(self,birth_rate, model, param):
        '''(Example_lik_class, float, any type, dict(ndarray)) -> 
           dict(ndarray), any type, bool, float

        For RJMCMC only. Does between model move. Birth rate is probablity to
        move from one model to another, models is current model and param is 
        dict of all localtions in param space. 
        Returns new param array with move updated, key for new model moving to,
        whether of not to attempt model jump (False to make run as MCMC) and the
        Jocobian for move.
        '''
        #for RJCMC
        #return new_param, try_model, attemp_jump, Jocobian
        #for MCMC
        raise NotImplementedError
        return param, None, False, None
        #pass

#===========================================    
#catacysmic varible fitting
class CV_Fit(Example_lik_class):

    '''Fits cv spectrum using fortran codes or spectral libray to generate model spectra.
    Runs with only MCMC'''

    def __init__(self,data,model_name='thuso',spec_path='/home/thuso/Phd/other_codes/Valerio',convolution_path='/home/thuso/Phd/other_codes/Valerio/thuso.dat',lib_path='/home/thuso/Phd/other_codes/Valerio/CV_lib.h5',
                gen_spec_lib=False,user_abn=False):
        '''If pool is activated, needs to be run in mpi. Head worker
        will do RJMCMC and working will make likelihoods.'''
        self.data = data
        #make hdf5 thread safe
        self.lock = multi.RLock()
        try:
            self.lock.acquire()
            self.lib = tab.open_file(lib_path,'r+')
            self.tab = self.lib.root.param
            #make index if not aready done
            if len(self.tab.indexedcolpathnames) != len(self.tab.colnames):
                for i in self.tab.colnames:
                    try:
                        if i not in self.tab.indexedcolpathnames and i !='spec':
                            print('indexing col %s'%i)
                            exec('self.tab.cols.%s.create_index()'%i)
                            self.lib.flush()
                    except ValueError:
                        #already been indexed
                        pass
                    
        except IOError:
            #no cv lib
            if not gen_spec_lib:
                raise("No hdf5 library and Not making new spectra. Program can't run!")
        #release hdf5 lock
        self.lock.release()
        if gen_spec_lib:
            self.gen_spec_only = False
            #use created library, but creat new spectra when none avalible
            #move to working dir
            os.chdir(spec_path)
            #load in conf files and store
            pid = os.getpid()
            self.conf_file_name = '%i.5'%pid
            temp = open(model_name + '.5')
            #make temp dir
            if not os.path.exists('temp/'):
                os.mkdir('temp/')
            #make dir so no io errors
            if not os.path.exists('temp/%i'%pid):
                os.mkdir('temp/%i'%pid)
            #make error dir
            if not os.path.exists('temp/%i/TlError'%pid):
                 os.mkdir('temp/%i/TlError'%pid)
            if not os.path.exists('temp/%i/SynError'%pid):
                 os.mkdir('temp/%i/SynError'%pid)
            #set error counter
            self._count = 0
            #change name of output in first line
            os.popen('cp '+convolution_path + ' temp/%i/%i.dat'%(pid,pid))
            dat = open('temp/%i/%i.dat'%(pid,pid),'rw+')
            dat_txt = []
            for i in dat:
                dat_txt.append(i)
            #change first line to pid.spec
            dat.seek(0)
            j = " 'fort.7'   'fort.17'    '%i.spec' \n"%pid
            dat.write(j)
            for i in dat_txt[1:]:
                dat.write(i)
            dat.close()
            #copy other config files to path
            os.popen('cp fort* temp/%i/'%pid)
            batch_file = open('temp/'+str(pid)+'/'+self.conf_file_name,'wr+')
            self.org_file = []
            for i in temp:
                batch_file.write(i)
                self.org_file.append(i)
            batch_file.flush()
            batch_file.seek(0)
            self.temp_model = 'temp/'+str(pid)+'/'+self.conf_file_name
            #find number of abn are used
            while batch_file.next() != '* mode abn modpf\n':
                pass
            self._no_abn,self._abn_lst = 0,[]
            for i in batch_file :
                if i.lstrip().split(' ' )[0] == '2':
                    #count
                    self._no_abn += 1
                    #past element
                    self._abn_lst.append(i.lstrip().split('!')[-1][:-1])
                elif i.startswith('*'):
                    #if finished with section
                    break
            batch_file.close()
            self.models = {'1':[2+self._no_abn]}
        else:
            #interpolate for missing values
            #find list of elements
            all_col = self.tab.colnames
            use_col = []
            for i in all_col:
                #don't try non params
                if i == 'spec':
                    continue
                if i == 'tried':
                    continue
                if i == 'Temp':
                    continue
                if i == 'logg':
                    continue
                #check if used
                query = self.tab.where('%s != %s'%(i,str(self.tab.coldflts[i])))
                if len([x[i] for x in query]) > 0:
                    use_col.append(i)
            #put in order acording to atomic weight ((1,H),(2,He)....)
            atoms = ['H','He','Li','Be','B','C','N','O','F','Ne','Na','Mg','Al','Si','P','S','Cl','Ar','K','Ca','Sc','Ti','V','Cr','Mn','Fe','Co','Ni','Cu','Zn']
            atoms = nu.asarray(atoms)
            index = []
            for i in use_col:
                index.append(nu.where(atoms == i)[0][0])
            self._no_abn,self._abn_lst = len(use_col),nu.asarray(use_col)[nu.argsort(index)]
        #get all param avalible
        self.all_param = []
        #T,logg
        self.all_param.append(self.tab.cols.Temp[:])
        self.all_param.append(self.tab.cols.logg[:])
        for i in self._abn_lst:
            self.all_param.append(eval('self.tab.cols.%s[:]'%i))
        self.all_param = nu.vstack(self.all_param).T
        #generates spectra
        self.gen_spec_lib = gen_spec_lib
                
    def lik(self, param, bins,return_spec=False):
        '''(Example_lik_class, ndarray) -> float
        This calculates the likelihood for a pool of workers.
        If rank == 0, send curent state to workers and wait for liks to be sent
        If rank != 0, recive current state, do trial move and start lik calc. This guy will never leave this function till the end of program
        '''
        
        #search for spectra and interpolate
        spec = utils.get_param_from_hdf5(self.tab,param[bins],
                nu.hstack(('Temp','logg',self._abn_lst)),self.all_param)
        
        #if spectra not there,
        if  type(spec) is list or not nu.all(nu.isfinite(spec)):
            if self.gen_spec_lib:
                #calculate it from.
                loglik,spec = self.lik_calc(param,bins,True,self.gen_spec_only)
                #check spectra
                #print spec
                if not type(spec) is list:
                    #save spec
                    utils.put_in_lib(self.tab,param[bins],self._abn_lst, spec,self.lock)
            else:
               #out of bounds or not going to interp
               loglik = -nu.inf
        else:
            #calculate liklihood
            if self.data is None and self.gen_spec_only:
                #not calculating liklihood so return
                return spec
            loglik = stats_dist.norm.logpdf(spec[:,1],self.data[:,1]).sum()
        if not return_spec:
            return loglik
        else:
            return loglik, spec
       
    def lik_calc(self,param, bins, return_spec=False,gen_spec_only=False):
        '''(Example_lik_class, ndarray) -> float
        Calculates likelihood for input parameters. Outuputs log-likelyhood'''
        #param = [T,g,abn...]
        #overwrite new param to temp file
        batch_file = open(self.temp_model,'wr+')
        #set temp, g
        batch_file.write(' %2.1f   %2.1f\n' %(param[bins][0],param[bins][1]))
        #write to abn
        i = 1
        while self.org_file[i] != '* mode abn modpf\n':
            batch_file.write(self.org_file[i])
            i += 1
        batch_file.write(self.org_file[i])
        #set abn if mode == 2
        j = 2
        i += 1
        for ii,k in enumerate(self.org_file[i:]):
            #print i.split(' ' )
            if k.lstrip().split(' ' )[0] == '2':
                #find what to add at end
                adn = k.rstrip().split(' ')[-1]
                if not adn.isalpha():
                    #make sure it's just a letter
                    adn = adn.split()[-1]
                    if not adn.isalpha():
                        #still not a letter?
                        adn = adn.split()[-1].replace('!','')
                #write
                batch_file.write('2 %1.1f 0\t! %s\n'%(param[bins][j],adn))
                j += 1
            elif k.startswith('*'):
                #if finished with section
                break
            else:
                #write non param
                batch_file.write(k)
        #write remaining file
        for k in range(i+ii,len(self.org_file)):
            batch_file.write(self.org_file[k])
        batch_file.close()
        #call Tl for temp file
        pid = os.getpid()
        out = subprocess.call(['./Tl temp/%i/'%pid+ self.conf_file_name[:-2]],shell=True)
       
        #check if ran successfully
        if out != 0:
            #copy error
            subprocess.call(['cp temp/%i/%i.{5,6} temp/%i/TlError/%i.{5,6}'%(pid,pid,pid,self._count)],shell=True)
            self._count += 1
           
            if return_spec:
                return -nu.inf,[]
            else:
                return -nu.inf
        #call synspecn
        out = subprocess.call(['./Syn temp/%i/'%pid+ self.conf_file_name[:-2]],shell=True)
        
        if out != 0:
            #copy error
            subprocess.call(['cp temp/%i/%i.{5,6} temp/%i/SynError/%i.{5,6}'%(pid,pid,pid,self._count)],shell=True)
            self._count += 1
            if return_spec:
                return -nu.inf,[]
            else:
                return -nu.inf
        #make spectrum
        out = subprocess.call(['./Rot temp/%i/'%pid+self.conf_file_name[:-2]],shell=True)
        if out != 0:
            if return_spec:
                return -nu.inf,[]
            else:
                return -nu.inf
        #load new spect and calculate likelyhood
        try:
            model = nu.loadtxt('%i.spec'%os.getpid())
            #clean up model
            subprocess.call(['rm %i.spec'%os.getpid()],shell=True)
            if gen_spec_only:
                return -nu.inf, model
        except IOError:
            if return_spec:
                return -nu.inf,[]
            else:
                return -nu.inf
        #calc likelyhood
        if model.shape[0] != self.data.shape[0]:
            if return_spec:
                return -nu.inf,[]
            else:
                return -nu.inf
        #fix amplitude
        model[:,1] *= nu.sum(model[:,1]*self.data[:,1])/nu.sum(model[:,1]**2)
        loglik = stats_dist.norm.logpdf(model[:,1],self.data[:,1]).sum()
        if not return_spec:
            return loglik
        else:
            return loglik,model
        
    def proposal(self,mu,sigma):
        '''(Example_lik_class, ndarray,ndarray) -> ndarray
        Proposal distribution, draws steps for chain. Should use a symetric
        distribution'''
        
        #return up_dated_param
        out = nu.random.multivariate_normal(mu,sigma)
        #round to nearest 1000 or tenth assume order
        #Temp to the 1000th
        out[0] = nu.round(out[0],-3)
        #all other to the thenth
        out[1:] = nu.round(out[1:],1)
        return out
    
    def prior(self,param,bins):
        '''(Example_lik_class, ndarray) -> float
        Calculates log-probablity for prior'''
        #return logprior
        out = 0.
        #param = [T,g,abn...]
        #uniform priors
        #T prior
        out += stats_dist.uniform.logpdf(param[bins][0],2*10**4,4*10**4)
        #g
        out += stats_dist.uniform.logpdf(param[bins][1],4,8)
        #abns
        out += stats_dist.uniform.logpdf(param[bins][2:],-1,2).sum()
        
        return out.sum()

    def model_prior(self,model):
        '''(Example_lik_class, any type) -> float
        Calculates log-probablity prior for models. Not used in MCMC and
        is optional in RJMCMC.'''
        #return log_model
        return 0.

    def initalize_param(self,model):
        '''(Example_lik_class, any type) -> ndarray, ndarray

        Used to initalize all starting points for run of RJMCMC and MCMC.
        outputs starting point and starting step size

        model parameter isn't used for now'''

        param = [0,0]
        param[0] = nu.random.rand()*2*10**4 +2*10**4
        param[1] = nu.random.rand()*4+4
        #ABN
        param = nu.hstack((param,nu.random.rand(self._no_abn)*2 - 1))
        #round ABN
        param[0] = nu.round(param[0],-3)
        param[1:] = nu.round(param[1:],1)
        sigma = nu.identity(len(param))
        return param,sigma
        
    def step_func(self,step_crit,param,step_size,model):
        '''(Example_lik_class, float, ndarray or list, ndarray, any type) ->
        ndarray

        Evaluates step_criteria, with help of param and model and 
        changes step size during burn-in perior. Outputs new step size
        '''
        if step_crit > .60:
            step_size[model] *= 1.05
        elif step_crit < .2 and nu.any(step_size[model].diagonal() > 10**-6):
            step_size[model] /= 1.05
        #cov matrix
        if len(param) % 200 == 0 and len(param) > 0.:
            temp = nu.cov(self.list_dict_to(param[-2000:]).T)
            #make sure not stuck
            if nu.any(temp.diagonal() > 10**-6):
                step_size[model] = temp
        
        return step_size[model]

    def birth_death(self,birth_rate, model, param):
        '''(Example_lik_class, float, any type, dict(ndarray)) -> 
           dict(ndarray), any type, bool, float

        For RJMCMC only. Does between model move. Birth rate is probablity to
        move from one model to another, models is current model and param is 
        dict of all localtions in param space. 
        Returns new param array with move updated, key for new model moving to,
        whether of not to attempt model jump (False to make run as MCMC) and the
        Jocobian for move.
        '''
        #for RJCMC
        #return new_param, try_model, attemp_jump, Jocobian
        #for MCMC
        return None, param, False, None
        #pass
    
#=============================================
#spectral fitting with RJCMC Class

class VESPA_fit(object):
    '''Finds the age, metalicity, star formation history, 
    dust obsorption and line of sight velocity distribution
    to fit a Spectrum.

    Uses vespa methodology splitting const sfh into multiple componets
    '''
    
    def __init__(self,data,weights=None, resol=180.,min_sfh=1,max_sfh=16,lin_space=False,use_dust=True, 
		use_losvd=True, spec_lib='p2',imf='salp',
			spec_lib_path='/home/thuso/Phd/stellar_models/ezgal/'):
        '''(VESPA_fitclass, ndarray,int,int) -> NoneType
        data - spectrum to fit
        weights/mask for data
        *_sfh - range number of burst to allow
        lin_space - make age bins linearly space or log spaced
        use_* allow useage of dust and line of sigt velocity dispersion
        spec_lib - spectral lib to use
        imf - inital mass function to use
        spec_lib_path - path to ssps
        sets up vespa like fits
        '''
        #set externel functions
        self._check_len = MC._check_len
        self.issorted = MC.issorted
        self._birth = MC._birth
        self._merge = MC._merge
        self._death = MC._death
        self._split = MC._split
        self.data = nu.copy(data)
		#make mean value of data= 100
        self._norm = 1./(self.data[:,1].mean()/100.)
        self.data[:,1] *= self._norm
        #resoluion of data
        self.resol = resol
        if weights is None:
            self.weights = nu.ones_like(data[:,0])
        else:
            self.weights = weights
            self.data[:,1] *= weights
        #load models
        cur_lib = ['basti', 'bc03', 'cb07','m05','c09','p2']
        assert spec_lib.lower() in cur_lib, ('%s is not in ' %spec_lib.lower() + str(cur_lib))
        if not spec_lib_path.endswith('/') :
            spec_lib_path += '/'
        models = glob(spec_lib_path+spec_lib+'*'+imf+'*')
        if len(models) == 0:
            models = glob(spec_lib_path+spec_lib.lower()+'*'+imf+'*')
        assert len(models) > 0, "Did not find any models"
        #crate ezgal class of models
        SSP = gal.wrapper(models)
        #make sure is matched for interpolatioin
        SSP.is_matched = True
        #extract seds from ezgal wrapper
        self._lib_val, self._spect = ag.ez_to_rj(SSP)
        #extra models to use
        self._has_dust = use_dust
        self._has_losvd = use_losvd
        #key order
        self._key_order = ['gal']
        if use_dust:
            self._key_order.append('dust')
        if use_losvd:
            self._key_order.append('losvd')
		#set hidden varibles
        #self._lib_vals = info
        self._age_unq = nu.unique(self._lib_val[0][:,1])
        self._metal_unq = nu.unique(self._lib_val[0][:,0])
        #self._lib_vals[0][:,0] = 10**self._lib_vals[0][:,0]
        self._min_sfh, self._max_sfh = min_sfh,max_sfh +1
		#params
        self.curent_param = nu.empty(2)
        self.models = {}
        for i in xrange(min_sfh,max_sfh+1):
            self.models[str(i)]= ['burst_length','mean_age', 'metal','norm'] * i
        #multiple_block for bad performance
        self._multi_block = True
        self._multi_block_param = {}
        self._multi_block_index = {}
        self._multi_block_i = 0
        #max total length of bins constraints
        self._max_age = self._age_unq.ptp()

    def _seed(self,Seed):
        '''Changes the random seed'''
        nu.random = nu.random.RandomState(Seed)
        nu.random.seed(Seed)
            
    def proposal(self,Mu,sigma):
        '''(Example_lik_class, ndarray,ndarray) -> ndarray
		Proposal distribution, draws steps for chain. Should use a symetric
		distribution
        '''
		#save length and mean age they don't change  self._multi_block
        #self._sigma = nu.copy(sigma)
        #self._mu = Mu.copy()
        #extract out of dict
        
        mu = nu.hstack([i for j in self._key_order for i in Mu[j] ])
        try:
            t_out = nu.random.multivariate_normal(mu,sigma)
        except nu.linalg.LinAlgError:
            print sigma
            return Mu
        bins = Mu['gal'].shape[0]
        #save params for multi-block
        '''if str(bins) not in self._multi_block_param.keys():
            self._multi_block_param[str(bins)] = []
        #limit to length to 1000
        while len( self._multi_block_param[str(bins)]) > 1000:
             self._multi_block_param[str(bins)].pop(0)
        self._multi_block_param[str(bins)].append(nu.copy(mu))
        #if rjmcmc see that performance is bad will turn multi block on
        #finds correlated parameters and changes them together
        bins = str(bins)
        if self._multi_block:
            #see if need initalization
            if bins not in self._multi_block_index.keys():
                self._multi_block_index[bins] = self.cov_sort(
                    self._multi_block_param[bins], int(bins))
                #self._hist[bins] = []
            #update params to change correlated params
            if len(self._multi_block_param[bins]) % 200 == 0:
                
                if int(bins) > 3:
                    self._multi_block_index[bins] = self.cov_sort(
                        self._multi_block_param[bins], int(bins))
                else:
                    self._multi_block_index[bins] = self.cov_sort(
                        self._multi_block_param[bins], 3)
                #if multiblock not working make random block
                if nu.unique(self._multi_block_index[bins]).size == 1:
                    self._multi_block_index[bins] = nu.random.choice(range(3),self._multi_block_index[bins].size)
            #set all non-changing params to original
            if self._multi_block_i > self._multi_block_index[bins].max():
                self._multi_block_i = 1
            index = self._multi_block_index[bins] == self._multi_block_i
            mu[index] = t_out[index]
            t_out = nu.copy(mu)
            #check iteratior
            self._multi_block_i += 1
        '''
        #extract out of mu into correct dict shape
        out = {}
        i,bins = 0,int(bins)
        for j in self._key_order:
            #gal
            if j == 'gal':
                out[j] = nu.reshape(t_out[i:i+bins*4], (bins, 4))
                i+= bins*4
            #dust
            if j == 'dust':
                out[j] = t_out[i:i+2]
                i += 2
            #losvd
            if j == 'losvd':
                out[j] = t_out[i:i+4]
                out[j][1:] = 0
                i+=4
        #gal lengths must be positve
        out['gal'][:,0] = nu.abs(out['gal'][:,0])
        #chech if only 1 metalicity
        if len(self._metal_unq) == 1:
            #set all metalicites to only value
            out['gal'][:,2] = nu.copy(self._metal_unq)

        return out
        
    def multi_try_all(self,param,bins,N=15):
        '''(VESPA_class,ndarray,str,int)-> float
        Does all things for multi try (proposal,lik, and selects best param'''
        temp_param = map(self.proposal,[param]*N, [self._sigma]*N)
    
    #@profile
    def lik(self,param, bins,return_all=False):
        '''(Example_lik_class, ndarray) -> float
        Calculates likelihood for input parameters. Outuputs log-likelyhood'''
        if not self._check_len(param[bins]['gal'],bins,self._age_unq):
            return -nu.inf
        #with profile.timestamp("Get_SSP"):
        burst_model = {}
        for i in param[bins]['gal']:
            burst_model[str(i[1])] =  10**i[3]*ag.make_burst(i[0],i[1],i[2],
            self._lib_val, self._spect)
        burst_model['wave'] = nu.copy(self._spect[:,0])
        '''if not self.issorted(burst_model['wave']):
            for i in burst_model.keys():
                burst_model[i] = burst_model[i][::-1]'''
        #return None
        #return None
		#do dust
        if self._has_dust:
            #dust requires wavelengths
            burst_model = ag.dust(param[bins]['dust'],burst_model)
        #add all spectra for speed
        model = {}
        model['wave'] = burst_model['wave'].copy()
        burst_model.pop('wave')
        model['0'] = nu.add.reduce(burst_model.values())
		#do losvd
        if self._has_losvd:
            #make buffer for edge effects
            wave_range = [self.data[:,0].min(),self.data[:,0].max()]
            model = ag.LOSVD(model, param[bins]['losvd'],
                                   wave_range,self.resol)
        #need to match data wavelength ranges and wavelengths
		#get loglik
        
        model = ag.data_match(self.data,model)
        #model = nu.sum(burst_model.values(),0)
        #weight or mask model
        model['0'] *= self.weights
		#return loglik
        if self.data.shape[1] == 3:
            #uncertanty calc
            prob = stats_dist.norm.logpdf(model['0'],self.data[:,1],self.data[:,2]).sum()
        else:
            prob = stats_dist.norm.logpdf(model['0'],self.data[:,1]).sum()
            #prob = -nu.sum((model -	self.data[:,1])**2)
        #return
        if 	return_all:
            return prob, model['0']
        else:
            return prob
   
    def prior(self,param,bins):
        '''(Example_lik_class, ndarray) -> float
        Calculates log-probablity for prior'''
        #return logprior
        out = 0.
        #make sure shape is ok
        if not self._check_len(param[bins]['gal'],bins,self._age_unq):
            return -nu.inf
        #uniform priors
        #gal priors
        gal = param[bins]['gal']
        #length
        out += stats_dist.uniform.logpdf(gal[:,0],0.,self._age_unq.ptp()).sum()
        #age
        #weight for older
        out += stats_dist.uniform.logpdf(gal[:,1],self._age_unq.min(),self._age_unq.max()).sum()
        #out += stats_dist.norm.logpdf(gal[:,1],9.5,0.2).sum()
        if nu.any(gal[:,1] > self._age_unq.max()):
            return -nu.inf
        #metals
        if len(self._metal_unq) > 1:
                #if has metal range
                out += stats_dist.uniform.logpdf(gal[:,2],self._metal_unq.min(),self._metal_unq.ptp()).sum()
            #weight
        out += stats_dist.uniform.logpdf(gal[:,3], -300, 500).sum()
        #dust
        if self._has_dust:
            #uniform priors
            out += stats_dist.uniform.logpdf(param[bins]['dust'],0,4).sum()
        #losvd
        if self._has_losvd:
            #sigma
            out += stats_dist.uniform.logpdf(param[bins]['losvd'][0],0,3.)
            #z
            out += stats_dist.uniform.logpdf(param[bins]['losvd'][1],0,.05)
            #h3 and h4
            out += stats_dist.uniform.logpdf(param[bins]['losvd'][2:],-.5,.5).sum()
        return out


    def model_prior(self,model):
        '''(Example_lik_class, any type) -> float
        Calculates log-probablity prior for models. Not used in MCMC and
        is optional in RJMCMC.'''
        #peak around 5 bins with heavy tail
        #can't allow for -inf
        '''out = stats_dist.maxwell.logpdf(int(model),2,3)+1
        if nu.isfinite(out):
            return out
        else:
            return -7.78061839'''
        return 0.
        #return stats_dist.maxwell.logpdf(int(model),2,3)+1

    def initalize_param(self,model):
        '''(Example_lik_class, any type) -> ndarray, ndarray

		Used to initalize all starting points for run of RJMCMC and MCMC.
		outputs starting point and starting step size
        '''
        #any amount of splitting
        out = {'gal':[], 'losvd':[],'dust':[]}
        #gal param
        age, metal, norm =  self._age_unq,self._metal_unq, self._norm
        lengths = self._age_unq.ptp()/float(model)
        for i in range(int(model)):
            out['gal'].append([lengths*nu.random.rand(), (i+.5)*lengths + age.min(),0,nu.log10(self._norm*nu.random.rand())])
            #metals
            out['gal'][-1][2] = nu.random.rand()*metal.ptp()+metal.min()
        out['gal'] = nu.asarray(out['gal'])
        #losvd param
        if self._has_dust:
            out['dust'] = nu.random.rand(2)*4
        #dust param
        if self._has_losvd:
            #[log10(sigma), v (redshift), h3, h4]
            out['losvd'] = nu.asarray([nu.random.rand()*4,0.,0.,0.])
        #make step size
        sigma = nu.identity(len([j for i in out.values() for j in nu.ravel(i)]))

        #make coorrect shape
        out['gal'] = MC.make_square({model:out['gal']},model,self._age_unq)
        #check if only 1 metalicity
        if len(self._metal_unq) == 1:
            #set all metalicites to only value
            out['gal'][:,2] = nu.copy(self._metal_unq)
            
        return out, sigma

        
    def step_func(self,step_crit,param,step_size,model):
        '''(Example_lik_class, float, ndarray or list, ndarray, any type) ->
        ndarray

        Evaluates step_criteria, with help of param and model and 
        changes step size during burn-in perior. Outputs new step size
        '''
        if step_crit > .60 and nu.all(step_size[model].diagonal() < 10.):
            step_size[model] *= 1.05
        elif step_crit < .2 and nu.any(step_size[model].diagonal() > 10**-6):
            step_size[model] /= 1.05
        #cov matrix
        if len(param) % 200 == 0 and len(param) > 0.:
            temp = nu.cov(MC.list_dict_to(param[-2000:],self._key_order).T)
            #make sure not stuck
            if nu.any(temp.diagonal() > 10**-6):
                step_size[model] = temp
        
        return step_size[model]


    def birth_death(self,birth_rate, model, Param):
        '''(Example_lik_class, float, any type, dict(ndarray)) -> 
        dict(ndarray), any type, bool, float
        
        For RJMCMC only. Does between model move. Birth rate is probablity to
        move from one model to another, models is current model and param is 
        dict of all localtions in param space.
        
        Returns new param array with move updated, key for new model moving to,
        whether of not to attempt model jump (False to make run as MCMC) and the
        Jocobian for move.

        Brith_rate is ['birth','split','merge','death']
        '''
        new_param = None
        while True:
            #choose step randomly
            step = nu.random.choice(['birth','split','merge','death'],p=birth_rate)
            param = {model:Param[model]['gal'].copy()}
            if step == 'birth' and int(model) + 1 < self._max_sfh:
                new_param, jacob, temp_model = self._birth(param,model,self)
            elif step == 'death' and int(model) - 1 >= self._min_sfh :
                new_param, jacob, temp_model = self._death(param,model,self)
            elif step == 'merge' and int(model) - 1 >= self._min_sfh:
                new_param, jacob, temp_model = self._merge(param,model,self)
            elif step == 'split' and int(model) + 1 < self._max_sfh:
                new_param, jacob, temp_model = self._split(param,model,self)
            elif step == 'len_chng' and int(model) > 1 :
                new_param, jacob, temp_model = self._len_chng(param,model,self)
            #if able to change break and return
            if new_param is not None:
                break
        if not Param.has_key(temp_model):
            Param[temp_model] = {}
        Param[temp_model]['gal'] = new_param[nu.argsort(new_param[:,1])]
        #add dust and losvd to output
        if self._has_dust:
            Param[temp_model]['dust'] = Param[model]['dust'].copy()
        if self._has_losvd:
            Param[temp_model]['losvd'] = Param[model]['losvd'].copy()
        #param[temp_model] = self._make_square(param,temp_model)
        return Param, temp_model, True, abs(jacob) 

        
class SSP_fit(object):
    '''Uses all ssp grid and finds mass fractions that best represent all
    of the galaxy. Also includes LOSVD and dust
    '''

    def __init__(self,data, use_dust=True, use_losvd=True, spec_lib='bc03',imf='salp',spec_lib_path='/home/thuso/Phd/stellar_models/ezgal/'):
        '''(Example_lik_class,#user defined) -> NoneType or userdefined

        initalize class, initalize spectal func, put nx2 or nx3 specta
        ndarray (wave,flux,uncert (optional)).

        use_ tells if you want to fit for dust and/or line of sight
        velocity dispersion.
        
        spec_lib is the spectral lib to use. models avalible for use:
        BaSTI - Percival et al. 2009 (ApJ, 690, 472)
        BC03 - Bruzual and Charlot 2003 (MNRAS, 344, 1000)
        CB07 - Currently unpublished. Please reference as an updated BC03 model.
        M05 - Maraston et al. 2005 (MNRAS, 362, 799)
        C09 - Conroy, Gunn, and White 2009 (ApJ, 699, 486C) and Conroy and Gunn 2010 (ApJ, 712, 833C (Please cite both)
        PEGASE2 (p2) - Fioc and Rocca-Volmerange 1997 (A&A, 326, 950)
        More to come!'''
        
        #initalize data and make ezgal class for uses
        self.data = nu.copy(data)
        #check data, reduice wavelenght range, match wavelengths to lib
        self._norm = 1./(self.data[:,1].mean()/100.)
        self.data[:,1] *= self._norm
        #load models
        cur_lib = ['basti', 'bc03', 'cb07','m05','c09','p2']
        assert spec_lib.lower() in cur_lib, ('%s is not in ' %spec_lib.lower() + str(cur_lib))
        if not spec_lib_path.endswith('/') :
            spec_lib_path += '/'
        models = glob(spec_lib_path+spec_lib+'*'+imf+'*')
        if len(models) == 0:
            models = glob(spec_lib_path+spec_lib.lower()+'*'+imf+'*')
        assert len(models) > 0, "Did not find any models"
        #crate ezgal class of models
        SSP = gal.wrapper(models)
        self.SSP = SSP
        
        #extra models to use
        self._has_dust = use_dust
        self._has_losvd = use_losvd
        #key order
        self._key_order = ['gal']
        if use_dust:
            self._key_order.append('dust')
        if use_losvd:
            self._key_order.append('losvd')
		#set hidden varibles
        #self._lib_vals = info
        self._age_unq = nu.unique(nu.log10(SSP[0].ages))[1:]
        self._metal_unq = nu.log10(nu.float64(SSP.meta_data['met']))
        #self._lib_vals[0][:,0] = 10**self._lib_vals[0][:,0]
        self._min_sfh, self._max_sfh = min_sfh,max_sfh +1
		#params
        self.curent_param = nu.empty(2)
        self.models = {}
        for i in xrange(min_sfh,max_sfh+1):
            self.models[str(i)]= ['burst_length','mean_age', 'metal','norm'] * i
        #multiple_block for bad performance
        self._multi_block = False
        self._multi_block_param = {}
        self._multi_block_index = {}
        self._multi_block_i = 0
        #max total length of bins constraints
        self._max_age = self._age_unq.ptp()
		
    def proposal(self,mu,sigma):
        '''(Example_lik_class, ndarray,ndarray) -> ndarray
        Proposal distribution, draws steps for chain. Should use a symetric
        distribution'''
        out = []
        for i in xrange(len(mu)):
            out.append(nu.random.multivariate_normal(mu[i],sigma[i]))

        return out

    def lik(self,param,model):
        '''(Example_lik_class, ndarray, str) -> float
        Calculates likelihood for input parameters. Outuputs log-likelyhood'''
        #get model
        imodel = []
		#get additive models
        for i,j in enumerate(model.split(',')):
            if j.endswith('+'):
                try:
                    imodel.append(self.models[j][1](param[model][i]))
                except ValueError:
                    return -nu.inf

		#combine data with
		imodel = nu.sum(imodel,0)
        #apply multipliticave or convolution models
        for i,j in enumerate(model.split(',')):
            if j.endswith('*'):
				imodel = self.models[j][1](imodel,param[model][i])

        #make model and data have same wavelength
        
        #get likelyhood
        out = stats_dist.norm.logpdf(self.data[:,1],nu.sum(imodel,0))
        #return loglik
        return out.sum()

    def prior(self,param, model):
        '''(Example_lik_class, ndarray, str) -> float
        Calculates log-probablity for prior'''
        #return logprior
        #uniform
        out = 0
        for i,j in enumerate(model.split(',')):
            if j == 'SSP':
            #'age':
                loc = self._age_unq.min()
                scale = self._age_unq.ptp()
                out += stats_dist.uniform.logpdf(param[model][i][0],loc,scale).sum()
            #'metal':
                loc = self._metal_unq.min()
                scale = self._metal_unq.ptp()
                out += stats_dist.uniform.logpdf(param[model][i][1], loc, scale).sum()
            #'norm':
                out += stats_dist.uniform.logpdf(param[model][i][2],0,10**4).sum()
        return out
        #conj of uniform
        #stats_dist.pareto.logpdf
        #normal
        #stats_dist.norm.logpdf
        #multinormal conjuigates
        #stats_dist.gamma.logpdf
        #stats_dist.invgamma.logpdf
        #exponetal
        #stats_dist.expon
        #half normal (never negitive)
        #stats_dist.halfnorm
        


    def model_prior(self,model):
        '''(Example_lik_class, any type) -> float
        Calculates log-probablity prior for models. Not used in MCMC and
        is optional in RJMCMC.'''
        #return log_model
        return 0.

    def initalize_param(self,model):
        '''(Example_lik_class, any type) -> ndarray, ndarray

        Used to initalize all starting points for run of RJMCMC and MCMC.
        outputs starting point and starting step size'''
        if model == 'SSP':
            out_ar, outsig = nu.zeros(3), nu.identity(3)
            loc = self._age_unq.min()
            scale = self._age_unq.ptp()
            out_ar[0] =  stats_dist.uniform.rvs(loc,scale)
            #metal
            loc = self._metal_unq.min()
            scale = self._metal_unq.ptp()
            out_ar[1] = stats_dist.uniform.rvs(loc, scale)
            #normalization
            out_ar[2] =  stats_dist.uniform.rvs(0,10**4)
            return out_ar, outsig
        elif model == 'dust':
            pass
        else:
            raise KeyError("Key dosen't exsist")

        
    def step_func(self, step_crit, param, step_size, model):
        '''(Example_lik_class, float, ndarray or list, ndarray, any type) ->
        ndarray

        Evaluates step_criteria, with help of param and model and 
        changes step size during burn-in perior. Outputs new step size
        '''
        #return new_step
        if step_crit > .60:
            for i in range(len(model.split(','))):
                step_size[model][i] *= 1.05
        elif step_crit < .2:
            for i in range(len(model.split(','))):
                step_size[model][i] /= 1.05
        #cov matrix
        if len(param) % 2000 == 0:
            step_size[model] = [nu.cov(nu.asarray(param[-2000:])[:,0,:].T)]
        return step_size[model]


    def birth_death(self,birth_rate, model, param):
        '''(Example_lik_class, float, any type, rj_dict(ndarray)) -> 
           dict(ndarray), any type, bool, float

        For RJMCMC only. Does between model move. Birth rate is probablity to
        move from one model to another, models is current model and param is 
        dict of all localtions in param space. 
        Returns new param array with move updated, key for new model moving to,
        whether of not to attempt model jump (False to make run as MCMC) and the
        Jocobian for move.
        '''
        #for RJCMC
        if birth_rate > nu.random.rand():
            #birth
            #choose random model to add
            new_model = self.models.keys()[1]
            out_param = param + {new_model:[self.initalize_param(new_model)[0]]}
            new_model = out_param.keys()[0]
            
        else:
            #death
            if len(param[param.keys()[0]]) > 1:
                out_param = param - 'SSP'
                new_model = out_param.keys()[0]
            else:
                return param, model, False, 1.

        return out_param, new_model, True, 1.
        #return new_param, try_model, attemp_jump, Jocobian
        #for MCMC
        #return None, None, False, None

#=======UV source finder
class UV_SOURCE(object):

    '''exmaple class for use with RJCMCM or MCMC program, all methods are
    required and inputs are required till the comma, and outputs are also
    not mutable. The body of the class can be filled in to users delight'''
    def __init__(self,script):
        '''(Example_lik_class,#user defined) -> NoneType or userdefined

        initalize class, can do whatever you want. User to define functions'''
        
        #initalize
        # first time we're invoked, do startup and get data
        # This starts a meqserver. Note how we pass the "-mt 2" option to run two threads.
        # A proper pipeline script may want to get the value of "-mt" from its own arguments (sys.argv).
        print "Starting meqserver"
        self._mqs = meqserver.default_mqs(wait_init=10,extra=["-mt","16"]);
        print "Loading config";
        TDLOptions.config.read("tdlconf.profiles");
        print "Compiling TDL script";
        #script = "mcmcsim.py";
        mod,ns,msg = Compile.compile_file(self._mqs,script);

        self._mqs.execute('VisDataMux',mod.mssel.create_io_request(),wait=True)
        self._request = self._mqs.getnodestate("DT").request
        self._data = self._mqs.execute("DT",self._request,wait=True);
        #models avalible
        self.models = {'3':['flux']}
        #multiblock for poor performance
        self._multi_block = False
        self._store = []

    def call_meqtrees(self, params, hypothesis):
        #global request,ndomain,data,mqs;

        B = None;
        lmn = None;
        shape = None;
        hypothesis = int(hypothesis)
      
        # Specify l,m,n values in radians
        # l = np.cos(dec) * np.sin(ra-ra0);
        # m = np.sin(dec) * np.cos(dec0) - np.cos(dec) * np.sin(dec0) * np.cos(ra-ra0);

        # Harcoded values for the phase centre - bad practice!!!
        deg2rad = sc.pi / 180.0;
        ra0 = 0.0; dec0 = 60.0 * deg2rad;

        if hypothesis == 0:
            B = np.array([[0.+0j,0],[0,0.]]);
            lmn = np.array([0.,0,0]);
            shape = np.array([0.,0,0]);

        elif hypothesis == 1:
            B = np.array([[[params[0],0.+0j],[0.+0j,params[0]]],[[params[3],0.+0j],[0.+0j,params[3]]]]);

            l1 = np.cos(dec0+params[2]) * np.sin(params[1]);
            m1 = np.sin(dec0+params[2]) * np.cos(dec0) - np.cos(dec0+params[2]) * np.sin(dec0) * np.cos(params[1]);
            n1 = 0.0;
            l2 = np.cos(dec0+params[5]) * np.sin(params[4]);
            m2 = np.sin(dec0+params[5]) * np.cos(dec0) - np.cos(dec0+params[5]) * np.sin(dec0) * np.cos(params[4]);
            n2 = 0.0;

            lmn = np.array([[l1,m1,n1],[l2,m2,n2]]);

            shape = np.array([[0.,0,0],[0.,0,0]]);
    
        elif hypothesis == 2:
            B = np.array([[[params[0],0.+0j],[0.+0j,params[0]]]]);

            l1 = np.cos(dec0+params[2]) * np.sin(params[1]);
            m1 = np.sin(dec0+params[2]) * np.cos(dec0) - np.cos(dec0+params[2]) * np.sin(dec0) * np.cos(params[1]);
            n1 = 0.0;
            lmn = np.array([[l1,m1,n1]]);
            shape = np.array([[params[4]*np.sin(params[3]),params[4]*np.cos(params[3]),float(params[5])/params[4]]]);

        elif hypothesis == 3:
            B = np.array([[[params[0],0.+0j],[0.+0j,params[0]]]]);

            #l1 = np.cos(dec0+params[2]) * np.sin(params[1]);
            #m1 = np.sin(dec0+params[2]) * np.cos(dec0) - np.cos(dec0+params[2]) * np.sin(dec0) * np.cos(params[1]);
            #l1=m1=n1 = 0.0;
            #lmn = np.array([[l1,m1,n1]]);

            shape = np.array([[0.,0,0]]);

        """print "B:\n",B
        print "lmn:\n",lmn
        print "shape:\n",shape
        print "B:\n",type(B),len(B)
        print "lmn:\n",type(lmn),len(lmn)
        print "shape:\n",type(lmn),len(shape)"""
          
        self._mqs.setnodestate("BT0",dmi.record(value=B),sync=True);
        #self._mqs.setnodestate("lmnT0",dmi.record(value=lmn),sync=True);
        #self._mqs.setnodestate("shapeT0",dmi.record(value=shape),sync=True);

        #t0 = time.time();
        self._mqs.clearcache("MT");
        model = self._mqs.execute("MT",self._request,wait=True);
        
        return model

    def proposal(self,mu,sigma):
        '''(Example_lik_class, ndarray,ndarray) -> ndarray
        Proposal distribution, draws steps for chain. Should use a symetric
        distribution'''
        self._store.append(mu)
        #return up_dated_param 
        out = nu.random.multivariate_normal(mu,sigma)
        return out

    def lik(self,cube, hypothesis):
        '''(Example_lik_class, ndarray) -> float
        Calculates likelihood for input parameters. Outuputs log-likelyhood'''
        
        #return loglik
        #def myloglike(cube, ndim, nparams):
        """
        Simple chisq likelihood for straight-line fit (m=1,c=1)
        
        cube is the unit hypercube containing the current values of parameters
        ndim is the number of dimensions of cube
        nparams (>= ndim) allows extra derived parameters to be carried along
        """
        
        model = self.call_meqtrees(cube[hypothesis], hypothesis)
        
        sigma = 0.01
        #chi2 = 0.
        ndata = 0

        # loop over arrays in data and model to form up chisq
        for vd,vm in zip(self._data.result.vellsets,model.result.vellsets):
            delta = vd.value - vm.value
        
        chi2 = (delta.real**2/sigma**2).sum() + (delta.imag**2/sigma**2).sum()
                
         
        return -chi2

    def prior(self,cube1, hypothesis):
        '''(Example_lik_class, ndarray) -> float
        Calculates log-probablity for prior'''
        #return logprior
        """
        This function just transforms parameters to the unit hypercube

        cube is the unit hypercube containing the current values of parameters
        ndim is the number of dimensions of cube
        nparams (>= ndim) allows extra derived parameters to be carried along

        You can use Priors from priors.py for convenience functions:

        from priors import Priors
        pri=Priors()
        cube[0]=pri.UniformPrior(cube[0],x1,x2)
        cube[1]=pri.GaussianPrior(cube[1],mu,sigma)
        cube[2]=pri.DeltaFunctionPrior(cube[2],x1,anything_ignored)
        """
        
        logprior = 0.
        hypothesis = int(hypothesis);
        deg2rad = sc.pi / 180.0;
        arcsec2rad = sc.pi / 180.0 / 3600.0;
        
        dxmin=-4.0; dxmax=+4.0; dymin=-4.0; dymax=+4.0 # arcsec
        dxmin *= arcsec2rad;
        dxmax *= arcsec2rad;
        dymin *= arcsec2rad;
        dymax *= arcsec2rad;

        Smin=0.0; Smax=2.0 # Jy
        cube = cube1[str(hypothesis)]
        # Need to convert RA, Dec to dra, ddec
        #ra0 = 0.0; dec0 = 60.0; # user-specified (in degrees)
        #ra0 = ra0 * deg2rad;
        #dec0 = dec0 * deg2rad;
        #ra = ra0 - cube[1]; dec = dec0 + cube[2];
        
        # Model 0 (noise only) -- 3 params (all = 0.0)
        if hypothesis == 0:
            #not correct need to test if just noise
            cube[0] = cube[0] * 0.0  # S0
            cube[1] = cube[1] * 0.0  # dx0
            cube[2] = cube[2] * 0.0  # dy0

        # Model 1 (noise + source 1 + source 2) -- distinct position priors
        elif hypothesis == 1:
            #S
            logprior += stats_dist.uniform.pdf([cube[0],cube[3]],Smin,(Smax-Smin)).sum()
            #dx
            logprior += stats_dist.uniform.pdf([cube[1],cube[4]],dxmin,(dxmax-dxmin)).sum()
            #dy
            logprior += stats_dist.uniform.pdf([cube[2],cube[5]],0,dymax).sum()
       

        # Model 2 (noise + source 3 [gaussian]) - Flux in Jy; Pos in ra/dec; PA
        elif hypothesis == 2:
            thetamin = 0.0 * deg2rad; thetamax = 180.0 * deg2rad;
            e1min = 0.0; e1max = 10.0 * arcsec2rad;
            e2min = 0.0; e2max = 10.0 * arcsec2rad;
            """Smin = Smax = 0.993808;
            thetamin = thetamax = 92.0 * deg2rad;
            e1min = e1max = 7.0 * arcsec2rad;
            e2min = e2max = 4.0 * arcsec2rad;"""

            # Flux in Jy, angles in rad.
            #S
            logprior += stats_dist.uniform.pdf(cube[0],Smin,(Smax-Smin)).sum()
            #dx
            logprior += stats_dist.uniform.pdf(cube[1],dxmin,(dxmax-dxmin)).sum()
            #dy
            logprior += stats_dist.uniform.pdf(cube[2],dymin,(dymax-dymin)).sum()
            #posn angle
            logprior += stats_dist.uniform.pdf(cube[3],thetamin,(thetamax-thetamin)).sum()
            #emaj
            logprior += stats_dist.uniform.pdf(cube[4],e1min,(e1max-e1min)).sum()
            #emin
            logprior += stats_dist.uniform.pdf(cube[5],e2min,(e2max-e2min)).sum()
          

        # Model 3 (noise + source 1 [single atom] )
        elif hypothesis == 3:
            #Smax=Smin=5.0
            dxmin=dxmax=dymin=dymax=0.0
            #S
            logprior += stats_dist.uniform.pdf(cube[0],Smin,(Smax-Smin)).sum()
            #dx
            logprior += stats_dist.uniform.pdf( cube[1],dxmin,(dxmax-dxmin)).sum()
            #dy
            logprior += stats_dist.uniform.pdf(cube[2],dymin,(dymax-dymin)).sum()
                 
            
        else:
            #print '*** WARNING: Illegal hypothesis'
            return -nu.inf

        return nu.sum(logprior)


    def model_prior(self,model):
        '''(Example_lik_class, any type) -> float
        Calculates log-probablity prior for models. Not used in MCMC and
        is optional in RJMCMC.'''
        #return log_model
        return 0.

    def initalize_param(self, hypothesis):
        '''(Example_lik_class, any type) -> ndarray, ndarray

        Used to initalize all starting points for run of RJMCMC and MCMC.
        outputs starting point and starting step size'''

        hypothesis = int(hypothesis);
        sigma=0.01 #error on each visibility
        deg2rad = sc.pi / 180.0;
        arcsec2rad = sc.pi / 180.0 / 3600.0;

        dxmin=-4.0; dxmax=+4.0; dymin=-4.0; dymax=+4.0 # arcsec
        dxmin *= arcsec2rad;
        dxmax *= arcsec2rad;
        dymin *= arcsec2rad;
        dymax *= arcsec2rad;

        Smin=0.0; Smax=2.0 # Jy

        #return init_param, init_step
        if hypothesis == 1:
            cube = nu.zeros(6)
            step = nu.identity(6)
            #S
            cube[0],cube[3] = stats_dist.uniform.rvs(Smin,(Smax-Smin),2)
            #dx
            cube[1],cube[4] = stats_dist.uniform.rvs(dxmin,(dxmax-dxmin),2)
            #dy
            cube[2],cube[5] = stats_dist.uniform.rvs(0,dymax,2)
            

        # Model 2 (noise + source 3 [gaussian]) - Flux in Jy; Pos in ra/dec; PA
        elif hypothesis == 2:
            thetamin = 0.0 * deg2rad; thetamax = 180.0 * deg2rad;
            e1min = 0.0; e1max = 10.0 * arcsec2rad;
            e2min = 0.0; e2max = 10.0 * arcsec2rad;
            """Smin = Smax = 0.993808;
            thetamin = thetamax = 92.0 * deg2rad;
            e1min = e1max = 7.0 * arcsec2rad;
            e2min = e2max = 4.0 * arcsec2rad;"""
            #make arrays
            cube = nu.zeros(6)
            step = nu.identity(6)
            # Flux in Jy, angles in rad.
            #S
            cube[0] = stats_dist.uniform.rvs(Smin,(Smax-Smin))
            #dx
            cube[1] = stats_dist.uniform.rvs(dxmin,(dxmax-dxmin))
            #dy
            cube[2] = stats_dist.uniform.rvs(dymin,(dymax-dymin))
            #posn angle
            cube[3] = stats_dist.uniform.rvs(thetamin,(thetamax-thetamin))
            #emaj
            cube[4] = stats_dist.uniform.rvs(e1min,(e1max-e1min))
            #emin
            cube[5] = stats_dist.uniform.rvs(e2min,(e2max-e2min))

        # Model 3 (noise + source 1 [single atom] )
        elif hypothesis == 3:
            #Smax=Smin=5.0
            cube = nu.zeros(3)
            step = nu.identity(3)
            dxmin=dxmax=dymin=dymax=0.0
            #S
            cube[0] = stats_dist.uniform.rvs(Smin,(Smax-Smin))
            #dx
            cube[1] = stats_dist.uniform.rvs(dxmin,(dxmax-dxmin))
            #dy
            cube[2] = stats_dist.uniform.rvs(dymin,(dymax-dymin))

        return cube,step
        
    def step_func(self,step_crit,param,step_size,model):
        '''(Example_lik_class, float, ndarray or list, ndarray, any type) ->
        ndarray

        Evaluates step_criteria, with help of param and model and 
        changes step size during burn-in perior. Outputs new step size
        '''
        #return new_step
        if step_crit > .60:
            step_size[model] *= 1.05
        elif step_crit < .2 and nu.any(step_size[model].diagonal() > 10**-6):
            step_size[model] /= 1.05
        #cov matrix
        '''if len(param) % 200 == 0 and len(param) > 0.:
            temp = nu.cov(self.list_dict_to(param[-2000:]).T)
            #make sure not stuck
            if nu.any(temp.diagonal() > 10**-6):
                step_size[model] = temp'''
        
        return step_size[model]


    def birth_death(self,birth_rate, model, param):
        '''(Example_lik_class, float, any type, dict(ndarray)) -> 
           dict(ndarray), any type, bool, float

        For RJMCMC only. Does between model move. Birth rate is probablity to
        move from one model to another, models is current model and param is 
        dict of all localtions in param space. 
        Returns new param array with move updated, key for new model moving to,
        whether of not to attempt model jump (False to make run as MCMC) and the
        Jocobian for move.
        '''
        #for RJCMC
        #return new_param, try_model, attemp_jump, Jocobian
        #for MCMC
        return param, None, False, None

class Multinest_fit(object):
    '''Finds the age, metalicity, star formation history, 
    dust obsorption and line of sight velocity distribution
    to fit a Spectrum.

    Uses vespa methodology splitting const sfh into multiple componets
    '''
    
    def __init__(self,data,nbins, use_dust=True, use_losvd=True,
                 spec_lib='p2',imf='salp',
			spec_lib_path='/home/thuso/Phd/stellar_models/ezgal/'):
        '''(VESPA_fitclass, ndarray,int,int) -> NoneType
        data - spectrum to fit
        *_sfh - range number of burst to allow
        lin_space - make age bins linearly space or log spaced
        use_* allow useage of dust and line of sigt velocity dispersion
        spec_lib - spectral lib to use
        imf - inital mass function to use
        spec_lib_path - path to ssps
        sets up vespa like fits
        '''
        self.data = nu.copy(data)
		#make mean value of data= 100
        self._norm = 1./(self.data[:,1].mean()/100.)
        self.data[:,1] *= self._norm
        #load models
        cur_lib = ['basti', 'bc03', 'cb07','m05','c09','p2']
        assert spec_lib.lower() in cur_lib, ('%s is not in ' %spec_lib.lower() + str(cur_lib))
        if not spec_lib_path.endswith('/') :
            spec_lib_path += '/'
        models = glob(spec_lib_path+spec_lib+'*'+imf+'*')
        if len(models) == 0:
			models = glob(spec_lib_path+spec_lib.lower()+'*'+imf+'*')
        assert len(models) > 0, "Did not find any models"
        #crate ezgal class of models
        SSP = gal.wrapper(models)
        self.SSP = SSP
        #extract seds from ezgal wrapper
        spect, info = [SSP.sed_ls], []
        for i in SSP:
			metal = float(i.meta_data['met'])
			ages = nu.float64(i.ages)
			for j in ages:
				if j == 0:
					continue
				spect.append(i.get_sed(j,age_units='yrs'))
				info.append([metal+0,j])
        info,self._spect = [nu.log10(info),None],nu.asarray(spect).T
        #test if sorted
        self._spect = self._spect[::-1,:]
        #make spect match wavelengths of data
        #self._spect = ag.data_match_all(data,self._spect)[0]
        #extra models to use
        self._has_dust = use_dust
        self._has_losvd = use_losvd
        #key order
        self._key_order = ['gal']
        if use_dust:
            self._key_order.append('dust')
        if use_losvd:
            self._key_order.append('losvd')
		#set hidden varibles
        self._lib_vals = info
        self._age_unq = nu.unique(info[0][:,1])
        self._metal_unq = nu.unique(info[0][:,0])
        self._lib_vals[0][:,0] = 10**self._lib_vals[0][:,0]
        #calculate number of parameters and number of bins
        self.nbins = nbins
        nparams = 0
        nparams += nbins*4
        if use_dust:
            nparams += 2
        if use_losvd:
            nparams += 4
        self.nparams = nparams

    
    def lik(self,p, bins,nbins,return_spec=False):
        '''(Example_lik_class, ndarray) -> float
        Calculates likelihood for input parameters. Outuputs log-likelyhood'''
        #change to correct format
        param = self.set_param(p)
        #check if should run or end quickly
        if not self._check_len(param['gal'],'1'):
            return -nu.inf
        burst_model = {}
        for i in param['gal']:
            burst_model[str(i[1])] =  10**i[3]*ag.make_burst(i[0],i[1],i[2],
            self.SSP)
        burst_model['wave'] = nu.copy(self._spect[:,0])
		#do dust
        if self._has_dust:
            #dust requires wavelengths
            burst_model = ag.dust(param['dust'],burst_model)
		#do losvd
        if self._has_losvd:
            #check if wavelength exsist
            if 'wave' not in burst_model.keys():
                burst_model['wave'] = nu.copy(self._spect[:,0])
            #make buffer for edge effects
            wave_range = [self.data[:,0].min(),self.data[:,0].max()]
            burst_model = ag.LOSVD(burst_model, param['losvd'], wave_range)
        #need to match data wavelength ranges and wavelengths
		#get loglik
        
        burst_model = ag.data_match(self.data,burst_model,bins)
        #check if wavelength is still here
        if  burst_model.has_key('wave'):
            #remove
            burst_model.pop('wave')
        model = nu.sum(burst_model.values(),0)
        
		#return loglik
        if self.data.shape[1] == 3:
            #uncertanty calc
            pass
        else:
            prob = stats_dist.norm.logpdf(model,self.data[:,1]).sum()
            #prob = -nu.sum((model -	self.data[:,1])**2)
        #return
        if nu.isnan(prob):
            return -nu.inf
        #print prob
        if return_spec:
            return prob, model
        else:
            return prob        

    def prior(self,p, bins, nbins):
        '''(Example_lik_class, ndarray) -> float
        Calculates log-probablity for prior'''
        #[len,age,metals,weight,tbc,tism,sigma,z,h3,h4]
        param = self.set_param(p)
        count = 0
        for i in param['gal']:
            #gaussian with mean mu and std sigma
            mu = 9.5
            sigma = 0.5
            #p[count+1] = erfinv(i[1] * 2. - 1.)*sigma + mu
            #uniform
            p[count+1] = i[1] * self._age_unq.ptp() + self._age_unq.min()
            #length bin is conditional on age
            min_range = min(abs(i[1] - self._age_unq.min()),
                            abs(self._age_unq.max()-i[1]))
            
            p[count] = i[0] * min_range
            count += 2
            p[count] = i[2] * self._metal_unq.ptp() + self._metal_unq.min()
            count += 1
            p[count] = i[3] * 150 - 50
            count += 1
        #make sure no overlap in age

        if self._has_dust:
            #dust
            p[count] *= 4.
            count += 1
            p[count] *= 4.
            count += 1
        if self._has_losvd:
            #losvd
            p[count] *= 2.7
            count += 1
            p[count] *= 0.
            count += 1
            p[count] *= 0
            count += 1
            p[count] *= 0
        
        #self.param_prior.append(param)

    def set_param(self,p):
        '''takes param from nested sampling and puts it into correct dictorany
        for use in lik and prior'''
        param = {'gal':nu.asarray(p[:self.nbins*4]).reshape(self.nbins,4)}
        if self._has_dust:
            srt_dst = self.nbins*4
            param['dust'] = nu.asarray(p[srt_dst:srt_dst+2])
        else:
            srt_dst = None
        if self._has_losvd:
            if srt_dst is None:
                srt_los = self.nbins*4
            else:
                srt_los = srt_dst + 2
            param['losvd'] = nu.asarray(p[srt_los:srt_los+4])
        return param

    def _check_len(self, tparam, key):
        '''(VESPA_class, dict(ndarray) or ndarray,str)-> ndarray
        Make sure parameters ahere to criterion listed below:
        1. bins cannot overlap
        2. total length of bins must be less than length of age_unq
        3. ages must be in increseing order
        4. make sure bins are with in age range
        5. No bin is larger than the age range
        '''
        
        #check input type
        if type(tparam) == dict:
            param = tparam.copy()
        elif  type(tparam) == nu.ndarray:
            param = {key:tparam}
        else:
            raise TypeError('input must be dict or ndarray')
        #make sure age is sorted
        if not issorted(param[key][:,1]):
            return False
        #make sure bins do not overlap fix if they are
        for i in xrange(param[key].shape[0]-1):
            #assume orderd by age
            max_age = param[key][i,0]/2. + param[key][i,1]
            min_age_i = param[key][i+1,1] - param[key][i+1,0]/2.
            if max_age > min_age_i:
                #overlap
                #make sure overlap is significant
                if not nu.allclose(max_age, min_age_i):
                    return False
            #check if in age bounds
            if i == 0:
                if self._age_unq.min() > param[key][i,1] - param[key][i,0]/2.:
                    return False
        else:
            if self._age_unq.max() < param[key][-1,1] + param[key][-1,0]/2.:
                if not nu.allclose(param[key][-1,1] + param[key][-1,0]/2,self._age_unq.max()):
                    return False
        #check if length is less than age_unq.ptp()
        if param[key][:,0].sum() > self._age_unq.ptp():
            if not nu.allclose( param[key][:,0].sum(),self._age_unq.ptp()):
                return False
        #make sure age is in bounds
        
        #passed all tests
        return True

