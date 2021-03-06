#Does a Monte-Carlo Markov Chain fit to the data (works with any form of equation). The starting values don't need to be good to use this - you just need to change sigma (in def quick_MCMC) to get better fits. A large sigma may miss the best fit and a small sigma could get stuck or go on forever. Note that this was written by Thuso and comes from papers by Metropolis and Hastings. It gives a Chi squared fit. To get a reduced chi squared, then divide by the number of unknown parameters. This should be close to 1 if the fit is good.

import numpy as nu
import pylab as pl
## quick linear fit
def poly_fit(x,y,order,point=[]):
#uses numpy poly fit x,y should be 1D numpy arrays
#returns a lambda formula of mX+b where poly makes
#m and b
#can plug in a x point also and will return line of that


    #polynomial interpolator
   Y=nu.poly1d(nu.polyfit(x,y,order))
   if point:
       return Y(point)
   else:
       return Y

def quick_MCMC(x,y,y_err,params,func=[],constrants=[],sigma=0.8,itter=10**5,quiet=False):
#fits any function to some data using a simple MCMC rutine
#params should be a array of the length of free parameters from func argument
#if no func argument func is a poly of order of length of params
#constraints is a 2Xlen(params) giving upper and lower bounds of fit like
# constrains=[[parma0_lower,parma0_high],[parma1_lower,parma1_high],...]
#funct should look like func=lambda x,param:x*param[0]+param[1]x*...param[-1]x
##################
#intitalize
    out_param=[]
    out_chi=[]
    param=nu.array([params,params])#set input parameters [0]=old [1]=new
    if not func: #see if inputed a function
        func=''
        for i in range(len(params)):
            func=func+'param['+str(i)+']*x**'+str(i)+'+'
        func=func[:-1]
        func=eval('lambda x,param: '+func)

    if any(constrants):
            #set up constraints checker
       checker=[]
       for i in range(len(params)):
          checker.append('while param[1]['+str(i)+']<=constrants['+str(i)+'][0] or param[1]['+str(i)+']>=constrants['+str(i)+'][1]: param[1]['+str(i)+']=param[0]['+str(i)+']+nu.random.randn()*sigma')


    else:
       checker=False

    #first fit
    y_fit=func(x,param[1])
#start up chi
    chi=[nu.sum((y_fit-y)**2/y_err**2),nu.inf]
    if nu.isnan(chi[0]):
       chi[0]=nu.inf
    chibest=nu.inf
    parambest=param[0]
    j=0
    out_param.append(nu.copy(param[0]))
    out_chi.append(nu.copy(chi[0]))

    #start mcmc
    for i in xrange(itter):
        if i%500==0 and not quiet:
            print 'current accptence rate %2.2f and chi2 is %2.2f' %(j/(i+1.0)*100.0,chi[1])
           # print param[1] 
 #select new param
        
        param[1]=param[0]+nu.random.randn(len(param[0]))*sigma
        #check constraints
        #print checker
        if checker:
            for ii in checker:
                exec(ii)
#sample new distribution
        y_fit=func(x,param[1])
        chi[1]=nu.sum((y_fit-y)**2/y_err**2)
        if nu.isnan(chi[1]):
           chi[1]=nu.inf

        #decide to accept or not
        a=nu.exp((chi[0]-chi[1])/2.0)
        #metropolis hastings
        if a>=1: #acepted
            chi[0]=chi[1]+0.0
            param[0]=param[1]+0.0
            out_param.append(nu.copy(param[0]))
            out_chi.append(nu.copy(chi[0]))
            j=j+1
            if chi[0]<chibest:
                chibest=chi[0]+0.0
                parambest=param[0]+0.0
                #if not quiet:
		print 'best fit value for %3.2f,%3.2f with chi2=%4.2f' %(parambest[0],parambest[1],chibest)

        else:
            if a>nu.random.rand():#false accept
                chi[0]=chi[1]+0.0
                param[0]=param[1]+0.0
                j=j+1
                out_param.append(nu.copy(param[0]))
                out_chi.append(nu.copy(chi[0]))
            else:
               out_param.append(nu.copy(param[0]))
               out_chi.append(nu.copy(chi[0]))

 
       #change sigma with acceptance rate
        if j/(i+1.0)>.24 and sigma>3.: #too many aceptnce increase sigma
           sigma=sigma*5.0
        elif j/(i+1.0)<.34 and sigma<10**-5: #not enough
           sigma=sigma/5.0
               

    return out_chi,out_param,parambest,chibest

def quick_cov_MCMC(x,y,params,func=[],constrants=[],sigma=0.8,itter=10**5,quiet=False):
    '''fits any function to some data using a simple MCMC rutine
    params should be a array of the length of free parameters from func argument
    if no func argument func is a poly of order of length of params
    constraints is a 2Xlen(params) giving upper and lower bounds of fit like
    constrains=[[parma0_lower,parma0_high],[parma1_lower,parma1_high],...]
    funct should look like func=lambda x,param:x*param[0]+param[1]x*...param[-1]x'''
##################
#intitalize
    out_param = nu.zeros([itter, len(params)])
    out_chi = nu.zeros(itter) + nu.inf
    sigma = nu.identity(len(params)) * sigma
    param = nu.array([params,params])#set input parameters [0]=old [1]=new
    if not func: #see if inputed a function
        func = ''
        for i in xrange(len(params)):
            func = func+'param['+str(i)+']*x**'+str(i)+'+'
        func = func[:-1]
        func = eval('lambda x,param: '+func)

    #if any(constrants):
            #set up constraints checker
    '''checker=[]
    for i in range(len(params)):
            checker.append('while param[1]['+str(i)+']<=constrants['+str(i)+'][0] or param[1]['+str(i)+']>=constrants['+str(i)+'][1]: param[1]['+str(i)+']=param[0]['+str(i)+']+nu.random.randn()*sigma['+str(i)+','+str(i)+']')'''


    #else:
     #   checker=[]

    #first fit
    y_fit = func(x, param[1])
#start up chi
    chi = [nu.sum((y_fit - y)**2), nu.inf]
    if nu.isnan(chi[0]):
       chi[0] = nu.inf
    chibest = nu.inf
    parambest = nu.copy(param[0])
    j = 0
    out_param[0] = nu.copy(param[0])
    out_chi[0] = nu.copy(chi[0])

    #start mcmc
    for i in xrange(1,itter):
        if i%1000 == 0 and not quiet:
            print 'current accptence rate %2.2f and chi2 is %2.2f' %(j/(i+1.0)*100.0,chi[1])
           # print param[1] 
 #select new param
        param[1] = nu.random.multivariate_normal(param[0],sigma)
        
        #check constraints      
        '''if checker:
           for ii in checker:
              exec(ii)'''
        for ii in xrange(len(params)):
           i2 = 0
           while (param[1][ii] <= constrants[ii][0]
                  or param[1][ii] >= constrants[ii][1]):
                #if fail make a new param
                param[1][ii] = param[0][ii] + nu.random.randn() * sigma[ii, ii]
                i2 += 1
                #sigma may be too big
                if i2 > 50:
                    sigma[ii,ii]=sigma[ii,ii]/1.05
#sample new distribution
        y_fit=func(x,param[1])
        chi[1]=nu.sum((y_fit-y)**2)
        if nu.isnan(chi[1]):
           chi[1]=nu.inf

        #decide to accept or not
        a=nu.exp((chi[0]-chi[1])/2.0)
        #metropolis hastings
        if a>=1: #acepted
            chi[0]=chi[1]+0.0
            param[0]=param[1]+0.0
            out_param[i,:]=nu.copy(param[0])
            out_chi[i]=nu.copy(chi[0])
            j=j+1
            if chi[0]<chibest:
                chibest=chi[0]+0.0
                parambest=param[0]+0.0
                #if not quiet:
		print 'best fit value for %3.2f,%3.2f with chi2=%4.2f' %(parambest[0],parambest[1],chibest)
                print i

        else:
            if a>nu.random.rand():#false accept
                chi[0]=chi[1]+0.0
                param[0]=param[1]+0.0
                j=j+1
                out_param[i,:]=nu.copy(param[0])
                out_chi[i]=nu.copy(chi[0])
            else:
               out_param[i,:]=nu.copy(param[0])
               out_chi[i]=nu.copy(chi[0])

 
       #change sigma with acceptance rate
        if j/(i+1.0)>.24 and any(sigma.diagonal()<3) and i<30000: #too many aceptnce increase sigma
           sigma=sigma*5.0
        elif j/(i+1.0)<.34 and any(sigma.diagonal()>10**-5) and i<30000: #not enough
           sigma=sigma/5.0
        #change sigma with cov matrix
        if i>1000 and i%500==0 and i<30000:
           tsigma=nu.cov(out_param[i-1000:i,:].T)
           if nu.all(nu.isfinite(tsigma)):
              sigma = tsigma +0.

    return out_chi,out_param,parambest,chibest


#To run this in ipython, simply copy and paste the lines below into it (excluding the first line)
if __name__=='__main__':	
   #import thuso_quick_fits as T
   #import asciidata
   import numpy as nu
   import pylab as lab
   import Gauss_landscape as G
   
   #use quick fits for fit of simple function
   fun = G.Gaussian_Mixture_model(1000,1)
   x,y =fun.data[:,0], fun.data[:,1]*1000
   params = nu.random.randn(2)*9
   params[1] = nu.abs(params[1])
   func = lambda x,p: fun.disp_model(p)[1]*1000
   const = [[-nu.inf,nu.inf],[0,nu.inf]]
   #start program
   chi,param,parambest,chibest = quick_cov_MCMC(x,y,params,func,const)
