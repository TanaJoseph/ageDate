#!/usr/bin/env python
#
# Name:  Age Dating Spectra Fitting Program
#
# Author: Thuso S Simon
#
# Date: 7th of June, 2011
#TODO:  try using cov matrix for sigma
#     make solutions of N_normalize>0 always
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
#History (version,date, change author)
#
#
#
""" A python version of the age dating spectral fitting code done by Mongwane 2010"""

import numpy as nu
import os,sys
from multiprocessing import *
import time as Time
from interp_func import *
from spectra_func import *
import random

###spectral lib stuff####
global lib_path,spect
lib_path='/home/thuso/Phd/Code/Spectra_lib/'
spect,info= load_spec_lib(lib_path)  
#spect=edit_spec_range(spect,3200,9500)

def find_az_box(param,age_unq,metal_unq):
    #find closest metal
    line=None
    dist=(param[0]-metal_unq)**2
    #test to see if smaller or larger
    metal=[metal_unq[nu.argsort(dist)][0]]*2
    try:
        if metal_unq[nu.argsort(dist)][0]>param[0]:
            for i in xrange(2):
                metal.append(metal_unq[metal_unq<metal[0]][-1])
        elif any(dist==0):
            line='metal'
        else:
            for i in xrange(2):
                metal.append(metal_unq[metal_unq>metal[0]][0])
    except IndexError: #if on a line
        line='metal'
    #find closest age 
        
    try:
        dist=(param[1]-age_unq)**2
        age=[age_unq[nu.argsort(dist)][0]]*2
        if age_unq[nu.argsort(dist)][0]>param[1]:
            for i in xrange(2):
                age.append(age_unq[age_unq<age[0]][-1])
        elif any(dist==0):
            if not line:
                line='age'
            else:
                line='both'
            return metal,age,line
        else:
            for i in xrange(2):
                age.append(age_unq[age_unq>age[0]][0])
    except IndexError:
        if not line:
            line='age'
        else:
            line='both'
            
    return metal,age,line

def binary_search(array,points):
    #does binary search for closest points returns 2 closest points
    #array.sort()
    start=int(len(array)/2.)
    if array[start]>points: #go down
        i=-nu.array(range(start))
        option='greater'
    else:
        i=xrange(start)
        option='less'
    for j in i:
        if option=='greater' and array[start+j]<points:
            out= (array[start+j],array[start+j+1])
            break
        elif option=='less' and array[start+j]>points:
            out= (array[start+j],array[start+j-1])
            break 

    return out

def plot_model(param,bins):
    #takes parameters and returns spectra associated with it
    lib_vals=get_fitting_info(lib_path)
    metal_unq=nu.unique(lib_vals[0][:,0])
    age_unq=nu.unique(lib_vals[0][:,1])
    return get_model_fit(param,lib_vals,age_unq,metal_unq,bins)


def get_model_fit(param,lib_vals,age_unq,metal_unq,bins):
    #does dirty work to make spectra models
    #search age_unq and metal_unq to find closet box spectra and interps
    #does multi componets spectra and uses normilization params
    for ii in range(bins):
        temp_param=param[ii*2:ii*2+2]
        metal,age,line=find_az_box(temp_param,age_unq,metal_unq)
        #check to see if on a lib spectra or on a line
        if line=='age': #run 1 d interp along metal only
            metal=nu.array([metal[0],metal[-1]])
            metal.sort()
            age=age[0]
            #find spectra
            closest=[]
            for i in metal:
                index=nu.nonzero(nu.logical_and(lib_vals[0][:,0]==i,
                                            lib_vals[0][:,1]==age))[0]
                #closest.append(read_spec(lib_vals[1][index][0]))
                closest.append(nu.vstack((spect[:,0],spect[:,index[0]+1])).T)
            if ii==0:
                out=nu.vstack((closest[0][:,0],
                          linear_interpolation(metal,closest,temp_param[0]))).T
                
            else:
                out[:,1]=out[:,1]+param[-ii-1]*linear_interpolation(
                    metal,closest,temp_param[0])
        elif line=='metal': #run 1 d interp along age only
            age=nu.array([age[0],age[-1]])
            age.sort()
            metal=metal[0]
            #find spectra
            closest=[]
            for i in age:
                index=nu.nonzero(nu.logical_and(lib_vals[0][:,1]==i,
                                            lib_vals[0][:,0]==metal))[0]
                #closest.append(read_spec(lib_vals[1][index][0]))
                closest.append(nu.vstack((spect[:,0],spect[:,index[0]+1])).T)
            if ii==0:
                out=nu.vstack((closest[0][:,0],
                             linear_interpolation(age,closest,temp_param[1]))).T
            else:
                out[:,1]=out[:,1]+param[-ii-1]*linear_interpolation(
                        age,closest,temp_param[1])

        elif line=='both': #on a lib spectra
            index=nu.nonzero(nu.logical_and(lib_vals[0][:,0]==temp_param[0],
                                            lib_vals[0][:,1]==temp_param[1]))[0]
            if ii==0:
                out=read_spec(lib_vals[1][index][0])
            else:
                out[:,1]=out[:,1]+param[-ii-1]*read_spec(lib_vals[1][index][0])[:,1]
        #run 2 d interp
        else:
            metal.sort()
            metal=nu.array(metal)[nu.array([0,3,1,2],dtype='int32')]
            age.sort()
            closest=[]
            for i in range(4):
                #print metal[i],age[i]
                index=nu.nonzero(nu.logical_and(lib_vals[0][:,1]==age[i],
                                            lib_vals[0][:,0]==metal[i]))[0]
                #closest.append(read_spec(lib_vals[1][index][0]))
                closest.append(nu.vstack((spect[:,0],spect[:,index[0]+1])).T)

        #interp
            if ii==0:
                out=nu.vstack((closest[0][:,0],bilinear_interpolation(
                            metal,age,closest,temp_param[0],temp_param[1]))).T
            else:
                out[:,1]=out[:,1]+param[-ii-1]*bilinear_interpolation(
                    metal,age,closest,
                    temp_param[0],temp_param[1])
        if ii==0: #add normilization to first out spectra
            out[:,1]=param[-ii-1]*out[:,1]
    
   #exit program
    return out

def data_match(model,data):
    #makes sure data and model have same wavelength range and points
    #####interpolate if wavelength points aren't the same#####
    if model.shape[0]==data.shape[0]: #if same number of points
        if all(model[:,0]==data[:,0]):#if they have the same x-axis
            return model[:,1]
    else: #not same shape, interp and or cut
        index=nu.nonzero(nu.logical_and(model[:,0]>=min(data[:,0]),
                                        model[:,0]<=max(data[:,0])))[0]
        if index.shape[0]==data.shape[0]: #see if need to cut only
            if sum(model[index,0]==data[:,0])==index.shape[0]:
                return model[index,1]
            else: #need to interpolate but keep same size
                return spectra_lin_interp(model[:,0],model[:,1],data[:,0])
        else:
            return spectra_lin_interp(model[:,0],model[:,1],data[:,0])
 

def check(vals,param,bins): #checks if params are in bounds
    for j in xrange(0,len(param)-bins,2):#check age and metalicity
        if any(vals.max(0)<param[j:j+2]) or any(vals.min(0)>param[j:j+2]):
            return True
    if any(param[-bins:]<0): #check normalizations
        return True
    return False

def continum_normalize(data,order):
    #does a polynomial fit to the continum to flatten it out
    #Y=nu.poly1d(nu.polyfit(data[:,0],data[:,1],order)) 
    pass

def normalize(data,model):
    #normalizes the model spectra so it is closest to the data
    return sum(data[:,1]*model)/sum(model**2)

def N_normalize(data, model,bins):
    #normalizes N different models to the data, may return negitive values
    #A*x=b where A square matrix with the summed flux of each model
    #b is the normised value of the flux from the normalized flux fuction
    #x is the population vector so chi=sum_lam(F-sum_bins(n_i*f))**2 solve for
    #n_i. the last equation is N=sum_bins(n_i)
    A=nu.zeros([2,bins])
    b=nu.ones(bins)
    for i in range(bins):
        A[0,i]=sum(model[i])
        A[1,i]=1.
        if i<bins-1:
            b[i]=normalize(data,nu.sum(model,0))*sum(nu.sum(model,0))
        else:
            b[i]=normalize(data,nu.sum(model,0))
    x=nu.dot(nu.linalg.pinv(A),b.T)
    #check to see if negitive values exsist
    if any(x<0):
        print 'Warning values less than zero detected'
    return x

def chain_gen_all(means,metal_unq, age_unq,bins,sigma):
    #creates new chain for MCMC, does log spacing for metalicity
    #lin spacing for everything else, runs check on values also
    rand=sigma*.0
    #make bins
    bin=nu.linspace(age_unq.min(),age_unq.max(),bins+1)
    bin_index=0
    #create for age and weights
    for k in xrange(rand.shape[0]):
        if k %2==0 and rand.shape[0]-bins-1>k:#metalicity
            rand[k]=10**random.normalvariate(nu.log10(means[k]),sigma[k])
            while rand[k]<metal_unq.min() or rand[k]>metal_unq.max():
                rand[k]=10**random.normalvariate(nu.log10(means[k]),sigma[k])
        else:#age and normilization
            rand[k]=random.normalvariate(means[k],sigma[k])
            if rand.shape[0]-bins-1<k: #normilization
                while rand[k]<0:
                    rand[k]=random.normalvariate(means[k],sigma[k])
            else: #age
                while rand[k]<bin[bin_index] or rand[k]>bin[bin_index+1]:
                    rand[k]=random.normalvariate(means[k],sigma[k])
                bin_index+=1
    return rand

def chain_gen_one(means,metal_unq, age_unq,bins,sigma,k):
    #changes the value of 1 paramer, does everything else of chain_gen_all
    rand=sigma*.0
    #make bins if needed for age
    if not (k %2==0 and rand.shape[0]-bins-1>k):
        bin=nu.linspace(age_unq.min(),age_unq.max(),bins+1)
    #set correct age bin range
        bin_index=-1
        for kk in xrange(rand.shape[0]):
            if not (kk %2==0 and rand.shape[0]-bins-1>kk):
                if not rand.shape[0]-bins-1<kk:
                    bin_index+=1
                    if kk==k:
                        break

    if k %2==0 and rand.shape[0]-bins-1>k:#metalicity
        rand[k]=10**random.normalvariate(nu.log10(means[k]),sigma[k])
        while rand[k]<metal_unq.min() or rand[k]>metal_unq.max():
            rand[k]=10**random.normalvariate(nu.log10(means[k]),sigma[k])
    else:#age and normilization
        rand[k]=random.normalvariate(means[k],sigma[k])
        if rand.shape[0]-bins-1<k: #normilization
            while rand[k]<0:
                rand[k]=random.normalvariate(means[k],sigma[k])
        else: #age
            while rand[k]<bin[bin_index] or rand[k]>bin[bin_index+1]:
                rand[k]=random.normalvariate(means[k],sigma[k])
    means[k]=rand[k]
    return means



####tests######
def make_chi_grid(data,points=500):
    #makes a 3d pic of metal,age,chi with input spectra 2-D only
    lib_vals=get_fitting_info()
    #create grid
    metal,age=nu.meshgrid(nu.linspace(lib_vals[0][:,0].min(),
                                      lib_vals[0][:,0].max(),points),
                          nu.linspace(lib_vals[0][:,1].min(),
                                      lib_vals[0][:,1].max(),points))
    age,N=nu.meshgrid(nu.linspace(lib_vals[0][:,1].min(),
                                      lib_vals[0][:,1].max(),points),
                  nu.linspace(0,700,points))    
    out=age*0
    metal_unq=nu.unique(lib_vals[0][:,0])
    age_unq=nu.unique(lib_vals[0][:,1])
    #start making calculations for chi squared value
    #queue=Queue()
    #work=[]
    for i in range(points):
         print '%i out of %i' %(i,points)
         sys.stdout.flush()
         for j in range(points):
            model=get_model_fit([.02,age[i,j],N[i,j]],lib_vals,age_unq,metal_unq,1)
            model=data_match(model,data)
            out[i,j]=sum((data[:,1] - model)**2)
 
    return metal,age,N,out

def make_marg_chi_grid(data,points,bins,axis=0):
    #makes a marginalized chi grid for the axis specified just for bins=2 right now
    lib_vals=get_fitting_info()
    metal_unq=nu.unique(lib_vals[0][:,0])
    age_unq=nu.unique(lib_vals[0][:,1])
    bin=nu.linspace(age_unq.min(),age_unq.max(),bins+1)
    
    poss_age={} #all possible vals for age and metal with point fineness
    for i in range(bins):
        poss_age[str(i)]=nu.linspace(bin[i],bin[i+1],num=points)
    poss_metal=nu.logspace(nu.log10(metal_unq[0]),nu.log10(metal_unq.max()),num=points)

    #multiprocess splitting of work
    splits=nu.int32(nu.linspace(0,points,num=cpu_count()+1))
    work=[]
    itter=Value('i', 0)
    q=Queue()
    for i in range(cpu_count()):
        work.append(Process(target=make_grid_multi,args=(data,poss_metal,
                                                         poss_age['0'],
                                                         poss_age['1'],
                                                         range(splits[i],splits[i+1]),itter,q)))
        work[-1].start()
    count=1
    temp=[]
    while count<=cpu_count():
        print '%i out of %i iterations done' %(itter.value,points**4)
        if q.qsize()>0:
            temp.append(q.get())
            count+=1
        else:
            Time.sleep(3)
    #collect data
    for i,j in enumerate(temp):
        if i==0:
            out,index=j
        else:
            out=j[0]+out
    return poss_metal,poss_age['0'],out

def make_grid_multi(data,metal,age,other_age,iss,itter,q):
    #makes chi grid for multiprocess
    out=nu.zeros([len(metal),len(other_age)])
    lib_vals=get_fitting_info()
    metal_unq=nu.unique(lib_vals[0][:,0])
    age_unq=nu.unique(lib_vals[0][:,1])
    for i in iss:#x axis plot age
        for j in xrange(len(metal)):#plot metal
            for k in xrange(len(other_age)): #marginal age
                for l in xrange(len(metal)): #marginal metal
                    param=nu.array([metal[j],age[i],metal[k],other_age[l],1,1])
                    model=get_model_fit(param,lib_vals,age_unq,metal_unq,2)
                    model=data_match(model,data)
                    out[i,j]=out[i,j]+sum((
                            data[:,1]-normalize(data,model)*model))**2
                    itter.value=itter.value+1

    q.put((out,iss))

if __name__=='__main__':
    import cProfile as pro
    data,info,weight=create_spectra(2)
    bins=2
    chibest_global=Value('f', nu.inf)
    i=Value('i', 0)
    parambest=Array('d',nu.zeros([3*bins]))
    option=Value('b',True)
    pro.runctx('MCMC_vanila(data,bins,i,chibest,parambest,option)'
               , globals(),{'data':data,'bins':bins,'i':i,
                            'chibest':chibest_global,'parambest':parambest
                            ,'option':option}
               ,filename='agedata.Profile')
