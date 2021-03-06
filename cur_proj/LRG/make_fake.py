import emcee_lik
import emcee
import numpy as nu
import LRG_lik as lik
import mpi_top
import cPickle as pik
from os import path
from glob import glob
import mpi4py.MPI as mpi
import pylab as lab

'''Makes fake SSPs and CSP for fitting with different noise'''


def make_SSP_grid(db_path, save_path, num_gal=25):
    '''Burst model has tau=0 as SSP so uses tau=0 for all models'''
    #make fake data but correct wavelegth
    wave = make_wavelenght(3500, 9000)
    fake_data = {'fake':nu.vstack((wave, nu.ones_like(wave))).T}
    fun = lik.LRG_Tempering(fake_data, db_path, have_dust=True, have_losvd=True)
    # make 125 gal
    for gal in xrange(num_gal):
        param = fun.initalize_param(1)[0]
        param['tau'] = 0.
        param['redshift'] = 0.
        #param['age'] = gal
        #param[['metalicity', 'normalization', '$T_{bc}$', '$T_{ism}$','$\sigma$', '$V$']] = -3.9019, 33.501257 ,0, 0, 0, 0
        temp = fun.lik({'burst':{'fake':param}},'burst', True)
        for Lik, index, spec in temp:
            pass
        #lab.figure()
        #lab.title(str(gal))
        #lab.plot(spec[0])
        # put noise and save
        snr = nu.random.randint(30,90)
        noise = nu.random.randn(len(spec[0]))*spec[0].mean()/float(snr)
        out = nu.vstack((wave, spec[0] + noise, nu.abs(noise))).T
        pik.dump((param, snr, out), open(path.join(save_path,'%i_ssp.pik'%gal),
                                          'w'), 2)
    
def make_CSP_grid(db_path, save_path, num_gal=25):
    '''Any tau >0'''
    #make fake data but correct wavelegth
    wave = make_wavelenght(3500, 9000)
    fake_data = {'fake':nu.vstack((wave, nu.ones_like(wave))).T}
    fun = lik.LRG_Tempering(fake_data, db_path, have_dust=True, have_losvd=True)
    # make 125 gal
    for gal in xrange(num_gal):
        param = fun.initalize_param(1)[0]
        #param['tau'] = 0.
        param['redshift'] = 0.
        #param['age'] = gal
        #param[['metalicity', 'normalization', '$T_{bc}$', '$T_{ism}$','$\sigma$', '$V$']] = -3.9019, 33.501257 ,0, 0, 0, 0
        temp = fun.lik({'burst':{'fake':param}},'burst', True)
        for Lik, index, spec in temp:
            pass
        #lab.figure()
        #lab.title(str(gal))
        #lab.plot(spec[0])
        # put noise and save
        snr = nu.random.randint(30,90)
        noise = nu.random.randn(len(spec[0]))*spec[0].mean()/float(snr)
        out = nu.vstack((wave, spec[0] + noise, nu.abs(noise))).T
        pik.dump((param, snr, out), open(path.join(save_path,'%i_csp.pik'%gal),
                                          'w'), 2)

def make_wavelenght(lam_min, lam_max):
    '''makes random wavelenth coverage using inputs'''
    return nu.arange(lam_min, lam_max)

def do_fit_ensemble(fit_dir, db_path):
    '''Fits data using emcee'''
    comm = mpi.COMM_WORLD
    pool = emcee_lik.MPIPool_stay_alive(loadbalance=True)
    files = glob(path.join(fit_dir, '*.pik'))
    # start fits
    for gal in files:
        comm.barrier()
        data = {}
        temp = pik.load(open(gal))
        data[gal] = temp[-1]
        data = comm.bcast(data, root=0)
        posterior = emcee_lik.LRG_emcee(data, db_path, have_dust=True,
                                            have_losvd=True)
        posterior.init()
        nwalkers = 4 *  posterior.ndim()
        if pool.is_master():
            pos0 = posterior.inital_pos(nwalkers)
            sampler = emcee.EnsembleSampler(nwalkers, posterior.ndim() ,
                                            posterior, pool=pool)
            iterations = 10 * 10**3
            pos, prob = [], []
            i = 0
            for tpos, tprob, _ in sampler.sample(pos0, iterations=iterations):
                acept = sampler.acceptance_fraction.mean()
                print '%i out of %i, accept=%2.1f'%(i, iterations, acept)
                pos.append(tpos)
                prob.append(tprob)
                i+=1
            pik.dump((temp,(pos, prob)), open(gal + '.ens', 'w'), 2)
            pool.close()
        else:
            pool.wait(posterior)
            
def dummy_prior(param):
    #ipdb.set_trace()
    return 0.
        
def do_fit_PT(fit_dir, db_path):
    '''Fits data using emcee.PTtempering'''
    comm = mpi.COMM_WORLD
    pool = emcee_lik.MPIPool_stay_alive(loadbalance=True)
    files = glob(path.join(fit_dir, '*.pik'))
    # start fits
    for gal in files:
        comm.barrier()
        data = {}
        temp = pik.load(open(gal))
        data[gal] = temp[-1]
        data = comm.bcast(data, root=0)
        posterior = emcee_lik.LRG_emcee_PT(data, db_path, have_dust=False,
                                            have_losvd=False)
        posterior.init()
        nwalkers = 2 *  posterior.ndim()
        #ntemps = 20
        Tmax = 1.7*10**12
        if pool.is_master():
            # need to make pos0 (ntemps, nwalkers, dim)
            pos0 = posterior.inital_pos(nwalkers, ntemps)
            sampler = emcee.PTSampler(None, nwalkers, posterior.ndim() ,
                                            posterior, dummy_prior,Tmax=Tmax,
                                            pool=pool)
            burnin = 2000
            iterations = 10 * 10**3
            #pos, prob = [], []
            i = 0
            #burn in
            pos, prob, state = sampler.run_mcmc(pos0, burnin)
            sampler.reset()
            #mcmc
            for tpos, tprob, _ in sampler.sample(pos, iterations=iterations
                                                 , rstate0=state):
                acept = sampler.acceptance_fraction.mean()
                print '%i out of %i, accept=%2.1f'%(i, iterations, acept)
                if i % 100:
                     pik.dump((temp,sampler), open(gal + '.pt.incomplte', 'w'), 2)
                i+=1
            pik.dump((temp,sampler), open(gal + '.pt', 'w'), 2)
            pool.close()
        else:
            pool.wait(posterior)
            
if __name__ == "__main__":
    '''makes fake spectra'''
    #get database
    if mpi.Get_processor_name() in ['mightee.ast.uct.ac.za','workhorse',
                                    'darkstar'] :
        db_path = '/home/thuso/Phd/experements/hierarical/LRG_Stack/burst_dtau_10.db'
    else:
        db_path = '/mnt/burst_dtau_10.db'
    #path to spectra
    if not path.exists('/home/thuso/Phd/experements/hierarical/LRG_Stack/stacked_real/Fake_SSP'):
        make_SSP_grid(db_path, '/home/thuso/Phd/experements/hierarical/LRG_Stack/stacked_real/Fake_SSP')
        make_CSP_grid(db_path, '/home/thuso/Phd/experements/hierarical/LRG_Stack/stacked_real/Fake_CSP')
    else:
        # fit ssps
        fit_dir = '/home/thuso/Phd/experements/hierarical/LRG_Stack/stacked_real/Fake_SSP'
        do_fit_PT(fit_dir, db_path)
        fit_dir = '/home/thuso/Phd/experements/hierarical/LRG_Stack/stacked_real/Fake_CSP'
        #fit csps
        do_fit_PT(fit_dir, db_path)
