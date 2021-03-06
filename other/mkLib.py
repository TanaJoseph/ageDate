#!/usr/bin/env python
#
# Name: Make spectral library
#
# Author: Thuso S Simon
#
# Date: 4th of Aug. 2011
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
"""
funtions to make a spectral library, from raw files, wrong format etc...

Gives standard names to files
"""


import os
import numpy as nu
import csv
import pyfits as fits
try:
    from astLib import astSED as sed_lib
except:
    print 'some moduals may not work since no astLib installed'

def BC03(inpath,outpath):
    #makes exsisting spectra files into stadard using a file with the refeences
    
    if inpath[-1]!='/':
        inpath=inpath+'/'
    if outpath[-1]!='/':
        outpath=outpath+'/'

    #load file names
    files=nu.array(os.listdir(inpath))
    #search for file without *.spec name
    for i in files: 
        if i[-4:]!='spec':
            break
    
    #open and start reading in file
    con_table=open(inpath+i,'r')
    files_match,params=[],[]
    for ii in con_table:
        if ii[0][0]=='#':
            continue
        params.append([float(ii[40:50]),float(ii[56:63])])
        files_match.append(ii[:32])
    params=nu.array(params)
    params[:,0]=age_convrt(params[:,0])
    #check for inf and remove
    index=nu.nonzero(~nu.isinf(params[:,0]))[0]
    params=params[index,:]
    files_match=nu.array(files_match)[index]
    #write files in new format
    for i,j in enumerate( files_match):
        temp_spec=open(inpath+j,'r')
        #make outname
        outname='ssp_%1.4f_%1.6f.spec' %(params[i,1],params[i,0])
        out_file=open(outpath+outname,'w')
        out_file.write(temp_spec.read())

        temp_spec.close()
        out_file.close()

def age_convrt(age):
    #goes from Gyrs to Enrinco format
    return nu.log10(age)
def metal_convrt(Z):
    #goes from Z_solar to Enrico format
    return nu.log10(Z+1.1111)+5
def metal_non_inf_conver(Z):
    #if their are 0's in metalicty so no nan crop up
    return 

def P09_all(inpath,outpath):
    #looks in all dirs of main P09 dir and gets ssps
    if inpath[-1]!='/':
        inpath=inpath+'/'
    if outpath[-1]!='/':
        outpath=outpath+'/'
    #check if a dir
    files=os.listdir(inpath)
    i=0
    while i<len(files):
        if os.path.isfile(inpath+files[i]):
            files.pop(i)
        else:
            i+=1
    #go into each file in files and extract the ssps
    for i in files:
        tochange=os.listdir(inpath+i)
        i+='/'
        try:
            Z=float(i[4])*10**(-float(i[6]))
        except ValueError: #non-standard dir probably not used to hold ssp
            continue
        temp_class=sed_lib.P09Model(inpath+i)
        for j in temp_class.ages:
            outname='ssp_%1.4f_%1.6f.spec' %(Z,nu.log10(j*10**9))
            nu.savetxt(outpath+outname,nu.array(temp_class.getSED(j).asList())) #not normailized



def P05(inpath,outpath):
    #does P05 ssp's
    
    if inpath[-1]!='/':
        inpath=inpath+'/'
    if outpath[-1]!='/':
        outpath=outpath+'/'

    #metalicity is formated as Zedf e.d * 10**-f

def Mar05(inpath,outpath,IMF='ss', option='bhb'):
    '''formats the Mar05 and M11 ssp into standard format
    uses astLib
    IMF can be "ss" for Salpeter, "kr" for kruopa or "cha" for chabrier
    option can be bhb or rhr'''
    if inpath[-1]!='/':
        inpath=inpath+'/'
    if outpath[-1]!='/':
        outpath=outpath+'/'
    option=option.lower()
    #check IMF adn option are correct options
    if not (option=='bhb' or option=='rhb'):
        print 'those branches do not exsist try again: bhb or rhb'
        raise
    assert IMF == 'ss' or IMF == 'kr' or IMF == 'cha'
    #load file names
    files=nu.array(os.listdir(inpath))
    for i in files:
        #if suffix is bhb or rbr
        if i.endswith(option) and i.rfind(IMF)>0:
            temp=sed_lib.M05Model(inpath+i,fileType='ssp')
            i=i[:-4]
        elif i.rfind(IMF)>0:
            temp=sed_lib.M05Model(inpath+i,fileType='ssp') 
        else:
            continue
        #temp=sed_lib.M05Model(inpath+i,fileType='ssp')
        #split
        if i.endswith('z007'): #in solar metalicity
            metal=3.5
        elif i.endswith('z004'):
            metal=2.
        elif i.endswith('z002'):
            metal=1.
        elif i.endswith('z001'):
            metal=.5
        elif i.endswith('z0001'):
            metal=1/50.
        elif i.endswith('z10m4'):
            metal=1/200.
        #loop over ages in class
        print i
        for j in temp.ages:
            outname='ssp_%1.4f_%1.6f.spec' %(metal,nu.log10(j*10**9))
            nu.savetxt(outpath+outname,nu.array(temp.getSED(j).asList())) #not normailized

def speed(inpath,outpath):
    pass

def miles_fits(inpath,outpath):
    if inpath[-1]!='/':
        inpath=inpath+'/'
    if outpath[-1]!='/':
        outpath=outpath+'/'

    #load file names
    files=nu.array(os.listdir(inpath))
    for i in files:
        #load file
        temp=fits.open(inpath+i)
        wave=nu.arange(temp[0].header['CRVAL1'],temp[0].header['CDELT1']*
                temp[0].header['NAXIS1']+temp[0].header['CRVAL1'],temp[0].header['CDELT1']) #make wavelngth range
        #get metalicty
        for j in temp[0].header.get_comment():
            if j.value.find('Age')>0:
                break
        try:    
            metal=float(j.value[-6:-1])
        except ValueError:
            print i
            raise
        if metal==-2.32:
            Z=0.0001
        elif metal==-1.71:
            Z=0.0004
        elif metal==-1.31:
            Z=0.0010
        elif metal==-0.71:
            Z=0.0040
        elif metal==-0.40:
            Z=0.0080
        elif metal==0.00:
            Z=0.0190
        elif metal==0.22: #an error on the Miles website
            Z=0.0300
        else:
            raise
        
        outname='ssp_%1.4f_%1.6f.spec' %(Z,nu.log10(float(i[-12:-5])*10**9))
        nu.savetxt(outpath+outname,nu.vstack((wave,temp[0].data)).T)

def ESPS(inpath,outpath):
    if inpath[-1] != '/':
        inpath += '/'
    if outpath[-1] != '/':
        outpath += '/'
    
    files = nu.array(os.listdir(inpath))
    for i in files:
        temp = nu.loadtxt(inpath+i)
        temp_file = open(inpath+i)
        j = temp_file.readline()
        Z=i[-3:]
        Z=float('.'+Z)
        while j.split()[1].lower() != 'age':
            j = temp_file.readline()
            try:
                j.split()[1].lower()
            except IndexError:
                j = temp_file.readline()

        age= nu.float32(nu.array(j.split())[3:])
        wave, temp = nu.copy(temp[:,0]), temp[:,range(1,temp.shape[1],3)]
        wave = air_to_vacuum(wave) #convert from air to vacuum wavelengths
        #convert air to vacuum wavelengths
        for j in xrange(temp.shape[1]):
            nu.savetxt(outpath+'ssp_%1.4f_%1.6f.spec' %(Z,nu.log10(age[j])),
                       nu.vstack((wave,temp[:,j])).T)

def ulyss_fits(inpath,outpath):
    import pyfits as fits
    #take ssp lib froma fits file and turns into correct format   
    if outpath[-1]!='/':
        outpath=outpath+'/'

    files=fits.open(inpath)
    for i in files: #extract age and metal combinations
        try:
            if i.header['EXTNAME'].lower()=='age':
                age=i.data
            elif i.header['EXTNAME'].lower()=='metal':
                metal=i.data
        except KeyError:
            pass
    # make wavelength array
    wave=nu.arange(files[0].header['CRVAL1'],
                   files[0].header['CRVAL1']+files[0].header['CDELT1']
                   *(files[0].data.shape[2]-1),files[0].header['CDELT1'])
    #makes 1 to many elements
    #wave=wave[:-1]
    #convert age from Myr to Gyr and take log10
    age=nu.log10(nu.exp(age)*10**6)
    #convert metal from dex to solar 
    metal=10**metal
    
    #save 
    temp=-nu.ones([wave.shape[0],2])
    temp[:,0]=wave
    for i in range(len(age)):
        for j in range(len(metal)):
            outname='ssp_%1.4f_%1.6f.spec' %(metal[j],age[i])
            temp[:,1]=files[0].data[j,i,1:]
            nu.savetxt(outpath+outname,temp)

####from astrophysiscs tools#######
def air_to_vacuum(airwl,nouvconv=True):
    """
    Returns vacuum wavelength of the provided air wavelength array or scalar.
    Good to ~ .0005 angstroms.

    If nouvconv is True, does nothing for air wavelength < 2000 angstroms.
    
    Input must be in angstroms.
    
    Adapted from idlutils airtovac.pro, based on the IAU standard 
    for conversion in Morton (1991 Ap.J. Suppl. 77, 119)
    """
    airwl = nu.array(airwl,copy=False,dtype=float,ndmin=1)
    isscal = airwl.shape == tuple()
    if isscal:
        airwl = airwl.ravel()
    
    #wavenumber squared
    sig2 = (1e4/airwl)**2
    
    convfact = 1. + 6.4328e-5 + 2.94981e-2/(146. - sig2) +  2.5540e-4/( 41. - sig2)
    newwl = airwl.copy() 
    if nouvconv:
        convmask = newwl>=2000
        newwl[convmask] *= convfact[convmask]
    else:
        newwl[:] *= convfact
    return newwl[0] if isscal else newwl

def vacuum_to_air(vacwl,nouvconv=True):
    """
    Returns air wavelength of the provided vacuum wavelength array or scalar.
    Good to ~ .0005 angstroms.
    
    If nouvconv is True, does nothing for air wavelength < 2000 angstroms.
    
    Input must be in angstroms.
    
    Adapted from idlutils vactoair.pro.
    """
    vacwl = nu.array(vacwl,copy=False,dtype=float)
    isscal = vacwl.shape == tuple()
    if isscal:
        vacwl = vacwl.ravel()
    
    #wavenumber squared
    wave2 = vacwl*vacwl
    
    convfact = 1.0 + 2.735182e-4 + 131.4182/wave2 + 2.76249e8/(wave2*wave2)
    newwl = vacwl.copy()/convfact
    
    if nouvconv:    
        #revert back those for which air < 2000
        noconvmask = newwl<2000
        newwl[noconvmask] *= convfact[noconvmask] 
    
    return newwl[0] if isscal else newwl
