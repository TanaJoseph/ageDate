#!/usr/bin/env python
#
# Name:  Hybrid nnls and MC
#
# Author: Thuso S Simon
#
# Date: Oct. 20 2011
# TODO: 
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
''' Fits spectra with a non-negitive least squares fit and finds uncertaties 
in a multitude of ways, using grid,MCMC and population fitting'''

from Age_date import *

def nn_ls_fit(data,max_bins=16,min_norm=10**-4,spect=spect):
    #uses non-negitive least squares to fit data
    #spect is libaray array
    #match wavelength of spectra to data change in to appropeate format
    model={}
    for i in xrange(spect[0,:].shape[0]):
        if i==0:
            model['wave']=nu.copy(spect[:,i])
        else:
            model[str(i-1)]=nu.copy(spect[:,i])

    model=data_match_new(data,model,spect[0,:].shape[0]-1)
    index=nu.float64(model.keys())
    #nnls fit
    N,chi=nnls(nu.array(model.values()).T,data[:,1])
    N=N[index.argsort()]
    #check if above max number of binns
    if len(N[N>min_norm])>max_bins:
        #remove the lowest normilization
        print 'removing bins is not ready yet'
        raise
    current=info[N>min_norm]
    metal,age=[],[]
    for i in current:
        metal.append(float(i[4:10]))
        age.append(float(i[11:-5]))
    metal,age=nu.array(metal),nu.array(age)
    #check if any left
    if len(current)<2:
        return float(current[4:10]),float(current[11:-5]),N[N>min_norm]

    return metal[nu.argsort(age)],age[nu.argsort(age)],N[N>min_norm][nu.argsort(age)]

def info_convert(info_txt):
    #takes info array from Age_date.create_data and turns in floats for plotting
    metal,age=[],[]
    for i in info_txt:
        metal.append(float(i[4:10]))
        age.append(float(i[11:-5]))
    metal,age=nu.array(metal),nu.array(age)
    return metal[nu.argsort(age)],age[nu.argsort(age)]


def grid_fit(data,spect=spect):
    #does nnls to fit data, then uses a adaptive grid to find uncertanty on params
    lib_vals=get_fitting_info(lib_path)
    lib_vals[0][:,0]=10**nu.log10(lib_vals[0][:,0]) #to keep roundoff error constistant
    metal_unq=nu.log10(nu.unique(lib_vals[0][:,0]))
    age_unq=nu.unique(lib_vals[0][:,1])

    #nnls fits
    best_metal,best_age,best_N=nn_ls_fit(data)
    #make iterations ready
    age_grid=nu.linspace(age_unq.min(),age_unq.max(),1000)
    metal_grid=nu.linspace(metal_unq.min(),metal_unq.max(),1000)
    N_grid=nu.linspace(0,max(best_N)+10.,1000)
    #out lists
    out=[]
    chi=[]
    #inital best fit
    bins=len(best_age)
    param=make_correct_params(best_metal,best_age,best_N)
    model=get_model_fit_opt(param,lib_vals,age_unq,metal_unq,bins) 
    model=data_match_new(data,model,bins)
    index=nu.int64(model.keys())
    chi.append(sum((data[:,1]-nu.sum(nu.array(model.values()).T*best_N[index],1))**2))
    out.append(nu.copy(param))
    sigma=nu.identity(bins*3)*.01
    sigma_counter=0
    for i in xrange(len(param)):
        if any(i==nu.arange(0,bins*3,3)): #metal
            for j in metal_grid:
                #for k in xrange(200):
                    #gen new vectors
                    #new_param=chain_gen_all(out[-1],metal_unq, age_unq,bins,sigma)
                    param[i]=nu.copy(j) #make sure correct place
                    #calc chi
                    model=get_model_fit_opt(param,lib_vals,age_unq,metal_unq,bins) 
                    model=data_match_new(data,model,bins)
                    index=nu.int64(model.keys())
                    chi.append(sum((data[:,1]-nu.sum(nu.array(model.values()).T*best_N[index],1))**2))
                    out.append(nu.copy(param))
                    #make new sigma every 200 itterations
                    sigma_counter+=1
                    if sigma_counter%50==0:
                        print sigma_counter
                        sigma=nu.cov(nu.array(out)[sigma_counter-50:].T)

        elif any(i==nu.arange(1,bins*3,3)): #age
            for j in age_grid:
                #for k in xrange(200):
                    #gen new vectors
                    #new_param=chain_gen_all(out[-1],metal_unq, age_unq,bins,sigma)
                    param[i]=nu.copy(j) #make sure correct place
                    #calc chi
                    model=get_model_fit_opt(param,lib_vals,age_unq,metal_unq,bins) 
                    model=data_match_new(data,model,bins)
                    index=nu.int64(model.keys())
                    chi.append(sum((data[:,1]-nu.sum(nu.array(model.values()).T*best_N[index],1))**2))
                    out.append(nu.copy(param))
                    #make new sigma every 200 itterations
                    sigma_counter+=1
                    if sigma_counter%50==0:
                        print sigma_counter
                        sigma=nu.cov(nu.array(out)[sigma_counter-50:].T)

        elif any(i==nu.arange(2,bins*3,3)): #norm
            for j in N_grid:
                #for k in xrange(200):
                    #gen new vectors
                    #new_param=chain_gen_all(out[-1],metal_unq, age_unq,bins,sigma)
                    param[i]=nu.copy(j) #make sure correct place
                    #calc chi
                    model=get_model_fit_opt(param,lib_vals,age_unq,metal_unq,bins) 
                    model=data_match_new(data,model,bins)
                    index=nu.int64(model.keys())
                    chi.append(sum((data[:,1]-nu.sum(nu.array(model.values()).T*best_N[index],1))**2))
                    out.append(nu.copy(param))
                    #make new sigma every 200 itterations
                    sigma_counter+=1
                    if sigma_counter%50==0:
                        print sigma_counter
                        sigma=nu.cov(nu.array(out)[sigma_counter-50:].T)


def make_correct_params(metal,age,norm):
    #turns seprate lists of age,metal,norm in to the correct format to be used for fitting
    out=nu.zeros(len(age)*3)
    index=0
    for i in range(0,len(age)*3,3):
        out[i:i+3]=[nu.log10(metal[index]),age[index],norm[index]]
        index+=1

    return out