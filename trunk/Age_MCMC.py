#!/usr/bin/env python


from Age_date import *
#import time as Time
a=nu.seterr(all='ignore')

def MCMC_multi(data,itter,bins,cpus=cpu_count()):
    #more effecent version of multi core MCMC
    #uses cominication methods instead of creating and distroying processes

    #shared arrays (chibest, parambest,i)
    chibest=Value('f', nu.inf)

    i=Value('i', 0)

    parambest=Array('d',nu.zeros([3*bins]))

    option=Value('b',True)
    option.burnin=10**3
    option.itter=int(itter+option.burnin)


    #sig_share=Array('d',nu.zeros([3*bins]))
    work=[]
    q=Queue()
    #start multiprocess mcmc
    for ii in range(cpus):
        work.append(Process(target=MCMC_SA,args=(data,bins,i,chibest
                                                     ,parambest,option,q)))
        work[-1].start()
    while i.value<itter:
        print '%2.2f percent done' %(i.value/float(itter)*100)
        sys.stdout.flush()
        #print i.value
        Time.sleep(5)
    option.value=False
    #wait for proceses to finish
    count=0
    temp=[]
    while count<cpus:
        if q.qsize()>0:
           temp.append(q.get())
           count+=1
    #post processing
    count=0
    #outsigma={}
    #outrate,outparam,outchi={},{},{}

    outparam,outchi=nu.zeros([2,3*bins]),nu.array([nu.inf])
    for ii in temp:
        outparam=nu.concatenate((outparam,ii[0][~nu.isinf(ii[1]),:]
                                 ),axis=0)
        outchi=nu.concatenate((outchi,ii[1][~nu.isinf(ii[1])]))
        '''outsigma[str(count)]=ii[2]
        outparam[str(count)]=ii[0][~nu.isinf(ii[1]),:]
        outchi[str(count)]=ii[1][~nu.isinf(ii[1])]
        outsigma[str(count)]=nu.array(ii[2])
        outrate[str(count)]=nu.array(ii[3])'''
        
        count+=1

    return outparam[2:,:],outchi[1:]
    #return outparam,outchi,outsigma,outrate
 
def MCMC_comunicate(data,bins,itter):
    #acts a 1 chain but uses multiple feelers
    #data[:,1]=data[:,1]*1000.  
    fun=MC_func(data,bins)
    fun.Mh_criteria=Mh_criteria
    cpu=float(cpu_count())
    non_N_index=nu.array([range(1,bins*3,3),range(0,bins*3,3)]).ravel()
    #change random seed for random numbers for multiprocessing
    #nu.random.seed(current_process().ident)
    #initalize parmeters and chi squared
    lib_vals=get_fitting_info(lib_path)
    lib_vals[0][:,0]=10**nu.log10(lib_vals[0][:,0]) #to keep roundoff error constistant
    metal_unq=nu.log10(nu.unique(lib_vals[0][:,0]))
    age_unq=nu.unique(lib_vals[0][:,1])

    #param=nu.zeros([itter+1,bins*3])
    param=[]
    active_param=nu.zeros(bins*3)
    
    bin=nu.log10(nu.linspace(10**age_unq.min(),10**age_unq.max(),bins+1))
    bin_index=0
    #start in random place
    for k in xrange(bins*3):
        if any(nu.array(range(0,bins*3,3))==k):#metalicity
            active_param[k]=(nu.random.random()*metal_unq.ptp()+metal_unq[0])
        else:#age and normilization
            if any(nu.array(range(1,bins*3,3))==k): #age
                #active_param[k]=nu.random.random() #random
                #active_param[k]=nu.random.random()*age_unq.ptp()/float(bins)+bin[bin_index] #random in bin
                active_param[k]=nu.mean([bin[bin_index],bin[1+bin_index]]) #mean position in bin
                bin_index+=1
                #active_param[k]=nu.random.random()*age_unq.ptp()+age_unq[0] #random place anywhere
            else: #norm
                active_param[k]=nu.random.random()*1000

    chi=[]
    chiappend=chi.append
    sigma=nu.identity(bins*3)*nu.tile(
                [0.5,age_unq.ptp()*nu.random.rand(),1.],bins)
    #try leastquares fit
    active_param=fun.n_neg_lest(active_param)
    chiappend(0)
    chi[-1],active_param[range(2,bins*3,3)]=fun.func_N_norm(active_param)
    param.append(nu.copy(active_param))
    
class MC_func:
    #compact MCMC function, can add new parts by calling in program
    def __init__(self,data,bins,spect=spect):
        #initalize bounds
        data_match_all(data)
        self.data=nu.copy(data)
        self.data[:,1]=self.data[:,1]*1000.
        lib_vals=get_fitting_info(lib_path)
        lib_vals[0][:,0]=10**nu.log10(lib_vals[0][:,0]) #to keep roundoff error constistant
        metal_unq=nu.log10(nu.unique(lib_vals[0][:,0]))
        age_unq=nu.unique(lib_vals[0][:,1])
        self.lib_vals=lib_vals
        self.age_unq= age_unq
        self.metal_unq,self.bins,self.spect=metal_unq,bins,spect
        self.bounds()
        #create random seed
        seed = open("/dev/random")
        rand_int = 0
        for i in seed.read(4):
            rand_int <<= 8
            rand_int += ord(i)
        print rand_int
        self.seed=rand_int
        nu.random.seed(self.seed)
        #accept and reject
        self.Nreject=1
        self.Naccept=1
        self.iteration=1
        #sigma for step
        self.non_N_index=nu.array([range(1,bins*3,3),range(0,bins*3,3)]).ravel()
        self.sigma=nu.identity(bins*3)*nu.tile(
                [0.5,age_unq.ptp()*nu.random.rand(),1.],bins)

    def func(self,param):
        if len(param)!=self.bins*3:
            return nu.nan
        if check(param,self.metal_unq, self.age_unq,self.bins): #make sure params are in correct range
            for i in xrange(len(self.bounds)): #find which is out and fix
                if self.bounds[i][0]>param[i]: #if below bounds
                    param[i]=nu.copy(self.bounds[i][0])
                if self.bounds[i][1]<param[i]: #if above bounds
                    param[i]=nu.copy(self.bounds[i][1])

        model=get_model_fit_opt(param,self.lib_vals,self.age_unq,self.metal_unq,self.bins)  
    #model=data_match_new(data,model,bins)
        index=xrange(2,self.bins*3,3)
        model['wave']= model['wave']*.0
        for ii in model.keys():
            if ii!='wave':
                model['wave']+=model[ii]*param[index[int(ii)]]
        return nu.sum((self.data[:,1]-model['wave'])**2)

    def func_N_norm(self,param):
        #returns chi and N norm best fit params
        if len(param)!=self.bins*3:
            return nu.nan
        model=get_model_fit_opt(param,self.lib_vals,self.age_unq,self.metal_unq,self.bins)  
        N,model,chi=N_normalize(self.data, model,self.bins)
    
        return chi,N

 
    def min_bound(self):
        #outputs an array of minimum values for parameters
        out=nu.zeros(self.bins*3)
        bin=nu.log10(nu.linspace(10**self.age_unq.min(),10**self.age_unq.max(),self.bins+1))
        bin_index=0
        for k in range(self.bins*3):
            if any(nu.array(range(0,self.bins*3,3))==k): #metal
                out[k]=self.metal_unq[0]
            elif any(nu.array(range(1,self.bins*3,3))==k): #age
                out[k]=bin[bin_index]
                bin_index+=1
            elif any(nu.array(range(2,self.bins*3,3))==k): #norm
                out[k]=0.0
        return out

    def max_bound(self):
        #outputs an array of maximum values for parameters
        out=nu.zeros(self.bins*3)
        bin=nu.log10(nu.linspace(10**self.age_unq.min(),10**self.age_unq.max(),self.bins+1))
        bin_index=1
        for k in range(self.bins*3):
            if any(nu.array(range(0,self.bins*3,3))==k): #metal
                out[k]=self.metal_unq[-1]
            elif any(nu.array(range(1,self.bins*3,3))==k): #age
                out[k]=bin[bin_index]
                bin_index+=1
            elif any(nu.array(range(2,self.bins*3,3))==k): #norm
                out[k]=nu.inf
        return out

    def bounds(self):
        #puts bounds into a easy reconizible format
        Min=self.min_bound()
        Max=self.max_bound()
        out=[]
        for i in range(len(Min)):
            out.append((Min[i],Max[i]))
        self.bounds=nu.copy(out)
        return out

    def n_neg_lest(self,param):
        #does bounded non linear fit
        try:
            out=fmin_bound(self.func,param, bounds = self.bounds,approx_grad=True)[0]
        except IndexError:
            out=param
        return out
    
    def Mh_criteria(self,chiold,para,nrand,seeds):
        #does metropolis hastings critera works with PMC class
    #initalize out params
        out_param=[]
        out_param.append(para)
        for i in xrange(nrand):
            chinew,active_param[range(2,self.bins*3,3)]=self.func_N_norm(out_param[-1])
            chiold.append(chinew+0.)
            a=nu.exp((chiold[-2]-chiold[-1])/2)
            if not min([1,a])>nu.random.rand(): #acepted
                out_param[-1]=nu.copy(out_param[-2])
                chiold[-1]=nu.copy(chiold[-2])
                self.Nreject+=1
            else:
                self.Naccept+=1
            out_param.append(chain_gen_all(out_param[-1],self.metal_unq,self.age_unq,self.bins,self.self.sigma))
            self.iteration+=1

        return out_param,chiold

    def Step(self,param,Type='cov'):
        acc_rate=self.Naccept/(self.Naccept+self.Nreject)
        if Type=='adapt': #change sigma with acceptance rate
            if acc_rate>.50 and all(self.sigma.diagonal()>=10**-5): 
               #too few aceptnce decrease sigma
                self.sigma=self.sigma/1.05
            elif acc_rate<.25 and all(self.sigma.diagonal()[self.non_N_index]<10): #not enough
                self.sigma=sigma*1.05
        elif Type=='cov': #use covarnence matrix
            if self.iteration%1000==0: #and (Nacept/Nreject>.50 or Nacept/Nreject<.25):
                self.sigma=Covarence_mat(param,self.iteration)
        elif Type=='scale':
            if acc_rate<0.001:
            # reduce by 90 percent
                self.sigma*= 0.1
            elif acc_rate<0.05:
                # reduce by 50 percent
                self.sigma*= 0.5
            elif acc_rate<0.2:
                # reduce by ten percent
                self.sigma*= 0.9
            elif acc_rate>0.95:
                # increase by factor of ten
                self.sigma*= 10.0
            elif acc_rate>0.75:
                # increase by double
                self.sigma*= 2.0
            elif acc_rate>0.5:
                # increase by ten percent
                self.sigma*= 1.1
            else:
                pass
  
        self.Naccept,self.Nreject=1.,1.


   
def MCMC_SA(data,bins,i,chibest,parambest,option,q=None):
    #does MCMC and reduices the false acceptance rate over a threshold
    #itter needs to be a array of normaly distrbuted numbers
    #so there are no problems with multiprocessing
    print "Starting processor %i" %current_process().ident
    #part on every modual wanting to fit the spectra
    #controls input and expot of files for fitt
    data[:,1]=data[:,1]*1000.  
    fun=PMC_func(data,bins)
    cpu=float(cpu_count())
    non_N_index=nu.array([range(1,bins*3,3),range(0,bins*3,3)]).ravel()
    #change random seed for random numbers for multiprocessing
    nu.random.seed(current_process().ident)
    #initalize parmeters and chi squared
    lib_vals=get_fitting_info(lib_path)
    lib_vals[0][:,0]=10**nu.log10(lib_vals[0][:,0]) #to keep roundoff error constistant
    metal_unq=nu.log10(nu.unique(lib_vals[0][:,0]))
    age_unq=nu.unique(lib_vals[0][:,1])

    param=nu.zeros([option.itter+1,len(parambest)])
    active_param=nu.zeros(len(parambest))
    
    bin=nu.log10(nu.linspace(10**age_unq.min(),10**age_unq.max(),bins+1))
    bin_index=0
    #start in random place
    for k in xrange(len(parambest)):
        if any(nu.array(range(0,len(parambest),3))==k):#metalicity
            active_param[k]=(nu.random.random()*metal_unq.ptp()+metal_unq[0])
        else:#age and normilization
            if any(nu.array(range(1,len(parambest),3))==k): #age
                #active_param[k]=nu.random.random() #random
                #active_param[k]=nu.random.random()*age_unq.ptp()/float(bins)+bin[bin_index] #random in bin
                active_param[k]=nu.mean([bin[bin_index],bin[1+bin_index]]) #mean position in bin
                bin_index+=1
                #active_param[k]=nu.random.random()*age_unq.ptp()+age_unq[0] #random place anywhere
            else: #norm
                active_param[k]=nu.random.random()*10000

    chi=nu.zeros(option.itter+1)+nu.inf
    sigma=nu.identity(len(active_param))*nu.tile(
                [0.5,age_unq.ptp()*nu.random.rand(),1.],bins)
    #try leastquares fit
    active_param=fun.n_neg_lest(active_param)
    chi[0],active_param[range(2,bins*3,3)]=fun.func_N_norm(active_param)
    param[0,:]=nu.copy(active_param)
    #parambest=nu.copy(active_param)

    mybest=nu.copy(chi[0])
    for k in range(len(active_param)):
        parambest[k]=nu.copy(active_param[k])
    #stuff just for age_date
    #start MCMC
    #Nacept,Nreject=nu.ones(len(active_param)),nu.ones(len(active_param))
    Nacept,Nreject,Nexchange_ratio,T_cuurent=1.0,1.0,1.0,0.
    acept_rate,out_sigma=[],[]
    j,T=1,279029.333013
    T_start,T_stop=0.34,-1.0
    while option.value and i.value<option.itter:
        if j%100==0:
            #print "hi, I'm %i at itter %i and chi %f" %(current_process().ident,j,chi[j-1])
            #print sigma.diagonal()
            print Nacept/(Nacept+Nreject)*100.,active_param
            sys.stdout.flush()
        active_param= chain_gen_all(active_param,metal_unq, age_unq,bins,sigma)
        #bin_index=0
      #calculate new model and chi
        chi[j],active_param[range(2,bins*3,3)]=fun.func_N_norm(active_param)
        #decide to accept or not
        a=nu.exp((chi[j-1]-chi[j])/2)
        #metropolis hastings
        if a>=1: #acepted
            param[j,:]=nu.copy(active_param)
            Nacept+=1
            if chi[j]< mybest:
                mybest=nu.copy(chi[j])
            if chi[j]<chibest.value:
                print 'best fit value %f in iteration %i, from processor %i' %(chi[j],j,
                                                                               current_process().ident)
                sys.stdout.flush()
                
                chibest.value=nu.copy(chi[j])
                for k in range(len(active_param)):
                    parambest[k]=nu.copy(active_param[k])
                
        else:
            if nu.exp(nu.log(a)/SA(T_cuurent,option.itter/(cpu),T_start,T_stop))>nu.random.rand():#false accept
                param[j,:]=nu.copy(active_param)
                Nacept+=1
            else:
                param[j,:]=nu.copy( param[j-1,:])
                active_param=nu.copy( param[j-1,:])
                chi[j]=nu.copy(chi[j-1])
                Nreject+=1
 
        if j<1000: #change sigma with acceptance rate
            #k=random.randint(0,len(sigma)-1)
            if Nacept/(Nacept+Nreject)>.50 and all(sigma.diagonal()>=10**-5): 
               #too few aceptnce decrease sigma
                sigma=sigma/1.05
            elif Nacept/(Nacept+Nreject)<.25 and all(sigma.diagonal()[non_N_index]<10): #not enough
                sigma=sigma*1.05
        else: #use covarnence matrix
            if j%1000==0: #and (Nacept/Nreject>.50 or Nacept/Nreject<.25):
                sigma=Covarence_mat(param,j)
                active_param=fun.n_neg_lest(active_param)
        #change temperature
        if nu.min([1,nu.exp(-(chi[j-1]-chi[j])/(2.*SA(T_cuurent+1,option.itter/(cpu),T_start,T_stop))-(chi[j-1]+chi[j])/(2.*SA(T_cuurent,option.itter/(cpu),T_start,T_stop)))/T])>nu.random.rand():
            T_cuurent+=1
            Nexchange_ratio+=1   
        #make sure the change temp rate is aroudn 2%
        if Nexchange_ratio/(Nacept+Nreject)>.02:
            T=T*1.05
        elif Nexchange_ratio/(Nacept+Nreject)<.005:
            T=T/1.05
        #change temperature schedual
        if j%50==0:
            if Nacept/(Nacept+Nreject)>.50:
                T_start+=.1
                T_stop+=.1
            elif Nacept/(Nacept+Nreject)<.25:
                T_start-=.1
                T_stop-=.1
                
        
        #if .001>nu.random.rand() and j>500: #every hundred itterations
        #    a=nu.exp((mybest-chibest.value)/2.0)
        #    if a>1: #accept change in param
        #        #print j
        #        chi[j]=nu.copy(chibest.value)
        #        mybest=nu.copy(chibest.value)
        #        print "swiched places. I'm %i" %current_process().ident
        #        for k in range(len(active_param)): 
        #            param[j,k]=nu.copy(parambest[k])
        #            active_param[k]=nu.copy(parambest[k])
                    
                       
        j+=1
        i.value=i.value+1
        acept_rate.append(nu.copy(Nacept/(Nacept+Nreject)))
        out_sigma.append(nu.copy(sigma))
    #return once finished 
    param=outprep(param)
    #for k in range(2,len(parambest),3):
    #    param[:,k]=param[:,k]/1000.
    data[:,1]=data[:,1]/1000.
    q.put((param[option.burnin:,:],chi[option.burnin:]))
   # q.put((param,chi))
    #q.put((param,chi,out_sigma,acept_rate))
    #return param,chi,out_sigma,acept_rate

def SA(i,i_fin,T_start,T_stop):
    #temperature parameter for Simulated anneling (SA). 
    #reduices false acceptance rate if a<60% as a function on acceptance rate
    m=(T_start-T_stop)/(0.98*i_fin)
    b=T_start-m
    return m*i+b



def Covarence_mat(param,j):
    #creates a covarence matrix for the step size 
    #only takes cov of last 1000 itterations
    if j-2000<0:
        return nu.cov(param[:j,:].T)
    else:
        return nu.cov(param[j-2000:j,:].T)

def outprep(param):
    #changes metals from log to normal
    for i in range(0,param.shape[1],3):
        param[:,i]=10**param[:,i]
        param[:,i+2]=param[:,i+2]/1000.
        
    return param

def MCMC_vanila(data,bins,i,chibest,parambest,option,q=None):
    #does MCMC parameter estimation with a floating step size till 10k iterations
    #itter needs to be a array of normaly distrbuted numbers
    #so there are no problems with multiprocessing

    #part on every modual wanting to fit the spectra
    #controls input and expot of files for fitt
      
    data[:,1]=data[:,1]*1000.  
    cpu=float(cpu_count())
    #change random seed for random numbers for multiprocessing
    nu.random.seed(current_process().ident)
    #initalize parmeters and chi squared
    lib_vals=get_fitting_info(lib_path)
    lib_vals[0][:,0]=10**nu.log10(lib_vals[0][:,0]) #to keep roundoff error constistant
    metal_unq=nu.log10(nu.unique(lib_vals[0][:,0]))
    age_unq=nu.unique(lib_vals[0][:,1])

    param=nu.zeros([option.itter+1,len(parambest)])
    active_param=nu.zeros(len(parambest))
    
    bin=nu.linspace(age_unq.min(),age_unq.max(),bins+1)
    bin_index=0
    #start in random place
    for k in xrange(len(parambest)):
        if any(nu.array(range(0,len(parambest),3))==k):#metalicity
            active_param[k]=(nu.random.random()*metal_unq.ptp()+metal_unq[0])
        else:#age and normilization
            if any(nu.array(range(1,len(parambest),3))==k): #age
                #active_param[k]=nu.random.random() #random
                #active_param[k]=nu.random.random()*age_unq.ptp()/float(bins)+bin[bin_index] #random in bin
                #active_param[k]=nu.mean([bin[bin_index],bin[1+bin_index]]) #mean position in bin
                #bin_index+=1
                active_param[k]=nu.random.random()*age_unq.ptp()+age_unq[0] #random place anywhere
            else: #norm
                active_param[k]=nu.random.random()*10000
    #N=sum(active_param.take(range(2,bins*3,3)))
    #for j in range(2,bins*3,3):            
    #    active_param[j]=active_param[j]/N
    param[0,:]=nu.copy(active_param)
    parambest=nu.copy(active_param)
    chi=nu.zeros(option.itter+1)+nu.inf
    sigma=nu.identity(len(active_param))*nu.concatenate((nu.tile(
                [metal_unq.ptp()*nu.random.rand(),age_unq.ptp()/bins*nu.random.rand()],bins),
                          nu.array([nu.sqrt(bins)]*bins)))

    model=get_model_fit_opt(active_param,lib_vals,age_unq,metal_unq,bins)  
    model=data_match_new(data,model,bins)
    model=nu.sum(nu.array(model.values()).T*active_param.take(range(2,bins*3,3)),1)
    #make weight paramer start closer to where ave data value
    #chi[0]=sum((data[:,1]-normalize(data,model)*model)**2)
    chi[0]=sum((data[:,1]-model)**2)
    chibest.value=chi[0]
    for k in range(len(active_param)):
        parambest[k]=nu.copy(active_param[k])
    #stuff just for age_date
    #start MCMC
    #Nacept,Nreject=nu.ones(len(active_param)),nu.ones(len(active_param))
    Nacept,Nreject,Nexchange_ratio,T_cuurent=1.0,1.0,1.0,0.
    acept_rate,out_sigma=[],[]
    j=1
    while option.value and i.value<option.itter:
        active_param= chain_gen_all(active_param,metal_unq, age_unq,bins,sigma)
        bin_index=0
        '''for k in range(1,len(parambest),3):
            active_param[k]=nu.mean([bin[bin_index],bin[1+bin_index]])
            bin_index+=1'''
        #for k in range(0,len(parambest),3):
        #    active_param[k]=nu.log10(0.0080)
       #calculate new model and chi
        model=get_model_fit_opt(active_param,lib_vals,age_unq,metal_unq,bins)  
        '''N,model=N_normalize(data,model,bins)
        ii=0
        for k in range(2,len(parambest),3):
            active_param[k]=nu.log10(N[ii])
            ii+=1'''
        model=data_match_new(data,model,bins)
        model=nu.sum(nu.array(model.values()).T*active_param.take(range(2,bins*3,3)),1)
        chi[j]=sum((data[:,1]-normalize(data,model)*model)**2)
        #decide to accept or not
        a=nu.exp((chi[j-1]-chi[j])/2)
        #metropolis hastings
        if nu.min([1,a])>nu.random.rand(): #acepted
            param[j,:]=nu.copy(active_param)
            Nacept+=1
            if chi[j]< chibest.value:
                print 'best fit value %f in iteration %i' %(chi[j],j)
                sys.stdout.flush()
                chibest.value=nu.copy(chi[j])
                for k in range(len(active_param)):
                    parambest[k]=nu.copy(active_param[k])
                
        else:
            param[j,:]=nu.copy( param[j-1,:])
            active_param=nu.copy( param[j-1,:])
            chi[j]=nu.copy(chi[j-1])
            Nreject+=1
 
        if j<1000: #change sigma with acceptance rate
            #k=random.randint(0,len(sigma)-1)
            if Nacept/Nreject<.50 and all(sigma.diagonal()[:2]>=10**-6): 
               #too few aceptnce decrease sigma
                sigma=sigma/1.05
            elif Nacept/Nreject>.25 and all(sigma.diagonal()[:2]<10): #not enough
                sigma=sigma*1.05
        else: #use covarnence matrix
            if j%500==0:
                sigma=Covarence_mat(param,j)

        if .01>nu.random.rand(): #every hundred itterations
            a=nu.exp((chi[j]-chibest.value)/2.0)
            if a>1: #accept change in param
                #print j
                chi[j]=nu.copy(chibest.value)
                for k in range(len(active_param)): 
                    param[j,k]=nu.copy(parambest[k])
                    active_param[k]=nu.copy(parambest[k])
                
        j+=1
        i.value=i.value+1
        acept_rate.append(nu.copy(Nacept/(Nacept+Nreject)))
        out_sigma.append(nu.copy(sigma))
    #return once finished 
    param=outprep(param)
    #for k in range(2,len(parambest),3):
    #    param[:,k]=param[:,k]/1000.
    data[:,1]=data[:,1]/1000.
    q.put((param[option.burnin:,:],chi[option.burnin:]))
        



if __name__=='__main__':
    import cProfile as pro
    data,info,weight=create_spectra(2)
    bins=2
    chibest_global=Value('f', nu.inf)
    i=Value('i', 0)
    parambest=Array('d',nu.zeros([3*bins]))
    option=Value('b',True)
    option.itter=5000
    pro.runctx('MCMC_SA(data,bins,i,chibest,parambest,option)'
               , globals(),{'data':data,'bins':bins,'i':i,
                            'chibest':chibest_global,'parambest':parambest
                            ,'option':option}
               ,filename='agedata.Profile')
