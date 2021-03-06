#! /usr/bin/python2.7
#gcc -shared -pthread -fPIC -fwrapv -O2 -Wall -fno-strict-aliasing -I/usr/include/python2.6 -o speedblob.so speedblob.c

import numpy as nu
cimport numpy as nu
import pylab as pl
import pyfits as fits


def MCMC(nu.ndarray data,int itter,int blobs, int plot=True):
    #mcmc for fitting blobs to 2-d image
    cdef int ii,i,k
    #cdef unsigned j
    cdef dict Naccept={'x':<float> 1,'y':<float> 1,'sigma_x':<float> 1,'sigma_y':<float> 1 ,'flux':<float> 1}
    cdef dict Nreject={'x':<float> 1,'y':<float> 1,'sigma_x':<float> 1,'sigma_y':<float> 1 ,'flux':<float> 1}
    #set up parameters
    cdef list param_list=['x','y','sigma_x','sigma_y','flux']
    cdef dict active_param={'x':<nu.ndarray>nu.zeros(blobs),'y':<nu.ndarray>nu.zeros(blobs)
                  ,'sigma_x':<nu.ndarray>nu.zeros(blobs),'sigma_y':<nu.ndarray>nu.zeros(blobs)
                  ,'flux':<nu.ndarray>nu.zeros(blobs)}
    cdef dict out_param={'x':<list>[],'y':<list>[],'sigma_x':<list>[],'sigma_y':<list>[] ,'flux':<list>[]}
    cdef list chi=[]
    cdef dict limits={'x':<list>[0,data.shape[0]-1],'y':<list>[0,data.shape[1]-1],
            'sigma_x':<list>[0,data.shape[1]-1],'sigma_y':<list>[0,data.shape[1]-1],
            'flux':<list>[0,data.max()]}
    cdef dict step={'x':<float>5.0,'y':<float>5.0,'sigma_x':<float>5.0,'sigma_y':<float>5.0,'flux':<float>12.0}
    #randomly put params
    
    for j in param_list:
        active_param[j]=nu.random.rand(len(active_param[j]))*limits[j][1]
        out_param[j].append(active_param[j])
    #calculate 1st chi val
    cdef nu.ndarray model=nu.zeros([data.shape[0],data.shape[1]])
    cdef nu.ndarray x,y,chi_out
    x,y=nu.meshgrid(range(data.shape[0]),range(data.shape[1]))
    for 0<= i <  blobs:
        model=model+gauss_2d(x,y,active_param['x'][i],active_param['y'][i],
                             active_param['flux'][i],active_param['sigma_x'][i],
                             active_param['sigma_y'][i])
    chi.append(nu.sum((data-model)**2))
    
    #start MCMC
    for 0 <= ii < itter:
    	
        for 0<= i <  blobs:
            #move blob
            for j in param_list:
                active_param[j][i] = change_param(out_param[j][-1][i],
                                                  limits[j],step[j])

            #check chi and MH condition
                model=model*0
                for 0 <= k < blobs:
                    model=model+gauss_2d(x,y,active_param['x'][k],
                                     active_param['y'][k],
                             active_param['flux'][k],active_param['sigma_x'][k],
                             active_param['sigma_y'][k])
                chi.append(nu.sum((data-model)**2))
            #mh critera
                if nu.random.rand()<nu.min([1.0,nu.exp((chi[-2]-chi[-1])/2.0)]):
                    if min(chi)==chi[-1]:
                        print 'Best chi2 is %8.0f acceptance rate %2.1f' %(chi[-1],Naccept[j]/Nreject[j])
                #accept and false accept
                    Naccept[j] = Naccept[j]+ 1
                #for j in param_list:
                    out_param[j].append(nu.copy(
                            active_param[j]))
                else:
                    Nreject[j] = Nreject[j]+1
                    chi[-1]=nu.copy(chi[-2])
                #for j in param_list:
                    out_param[j].append(nu.copy(
                            out_param[j][-1]))

        #aceptance rate stuff
                if Naccept[j]/Nreject[j]<.4 and step[j]<50:
           #for j in param_list:
                    step[j]=step[j]*1.05
                elif Naccept[j]/Nreject[j]>.5 and step[j]>.001:
           #for j in param_list:
                    step[j]=step[j]/1.05

        if plot:
            pl.imshow(model-data,vmin=0,vmax=300)
            pl.title('sim with chi of'+str(chi[-1])+' blobs')
            if ii<10:
                filename = 'gau000'+str(ii)+'.png'
            elif ii<100 and ii>=10:
                filename = 'gau00'+str(ii)+'.png'
            elif ii<1000 and ii>=100:
                filename = 'gau0'+str(ii)+'.png'
            else:
                filename = 'gau'+str(ii)+'.png'
            pl.savefig(filename, dpi=50)
            pl.clf()

    #save as numpy arrays
    chi_out=nu.array(chi)
    for j in out_param.keys():
        out_param[j]=nu.array(out_param[j])
        
    return out_param,chi


cdef inline float change_param(float param,list limits,
     	    	  		     float sigma):
    #moves param with normal dist and checks limits
        new=param+nu.random.randn()*sigma
        while new<limits[0] or new>limits[1]:
            new=param+nu.random.randn()*sigma
        return new
 
cdef inline nu.ndarray gauss_2d(nu.ndarray x,nu.ndarray y
     	    	       ,float mu_x,float mu_y,
		       	float A,float sig_x,float sig_y):
    return A*nu.exp(-(x-mu_x)**2/(2.0*sig_x**2)-(y-mu_y)**2/(2.0*sig_y**2))

def plot_param(active_param,chi):
    #plot best fit blobs on a 128x128 grid takes only numpy arrays
    x,y=nu.float64(nu.meshgrid(range(128),
                               range(128)))
    model=nu.zeros([128,128])
    #find best chi value
    index=nu.nonzero(min(chi)==chi)[0]
    
    for k in xrange(active_param[active_param.keys()[0]].shape[1]):
        model=model+gauss_2d(x,y,active_param['x'][index[0]][k],
                             active_param['y'][index[0]][k],
                             active_param['flux'][index[0]][k],
                             active_param['sigma_x'][index[0]][k],
                             active_param['sigma_y'][index[0]][k])
    #plot
    pl.figure()
    pl.imshow(model,vmin=0,vmax=300)
    pl.title('best fit image, chi='+str(min(chi)))
    pl.show()
    return model

def make_data(blobs=2):
	#makes data for quick testing
    x,y=nu.meshgrid(nu.linspace(-10,10,128),nu.linspace(-10,10,128))
    return gauss_2d( x, y, 0.0,0.0,150,5,5)+gauss_2d( x, y, -4,-5.0,100,3,9)

def make_movie():
    import os
    command = ('mencoder',
           'mf://*.png',
           '-mf',
           'type=png:w=800:h=600:fps=25',
           '-ovc',
           'lavc',
           '-lavcopts',
           'vcodec=mpeg4',
           '-oac',
           'copy',
           '-o',
           'fit_movie.avi')

    os.spawnvp(os.P_WAIT, 'mencoder', command)

if __name__=='__main__':
    #try load data
    import time
    x,y=nu.meshgrid(nu.linspace(-10,10,128),nu.linspace(-10,10,128))
    fluxd= gauss_2d( x, y, 0.0,0.0,150,5,5)+gauss_2d( x, y, -4,-5.0,100,3,9)
    t=time.time()
    param,chi=MCMC(fluxd,1000,2,False)
    print t-time.time()
    #save params
#    import cPickle as pik
#    pik.dump((param,chi),open('blob.pik','w'),2)

