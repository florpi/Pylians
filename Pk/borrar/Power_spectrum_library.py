#This file contains the routines used to compute the P(k) of a given point set
#within an N-body simulation

#from mpi4py import MPI
import CIC_library as CIC
import numpy as np
import scipy.fftpack
import scipy.weave as wv
import sys
import time

#pos: an array containing the positions of the particles/galaxies/halos
#dims: the number of points per dimension in the grid
#BoxSize: Size of the simulation. Units must be equal to those of pos
def power_spectrum(pos,dims,BoxSize,shoot_noise_correction=True):

    dims2=dims**2; dims3=dims**3
    bins_r=int(np.sqrt(3*int(0.5*(dims+1))**2))+1
    start_time=time.clock()

    #compute the delta (rho/mean_rho-1) in the grid points by cic interp
    delta=np.zeros(dims3,dtype=np.float32)
    CIC.CIC_serial(pos,dims,BoxSize,delta)
    print 'numbers should be equal:',np.sum(delta,dtype=np.float64),dims3
    delta-=1.0
    print 'min delta in the grid=',np.min(delta)
    print 'max delta in the grid=',np.max(delta)
    
    #FFT of the delta field (scipy.fftpack seems superior to numpy.fft)
    delta=np.reshape(delta,(dims,dims,dims))
    print 'Computing the FFT of the field...'
    start_fft=time.clock()
    #delta_k=np.fft.ifftn(delta)
    delta_k=scipy.fftpack.ifftn(delta,overwrite_x=True)
    end_fft=time.clock()
    print 'done'
    print 'time taken for computing the FFT=',end_fft-start_fft
    del delta
    delta_k=np.ravel(delta_k)

    #apply the cic correction to the modes
    print 'Applying the CIC correction to the modes...'
    #because we are using complex numbers: 1) compute the correction over a
    #np.ones(dims3) array  2) multiply the results
    array=CIC_correction(dims)
    delta_k*=array
    del array
    print 'done'

    #compute delta(k)^2, delete delta(k) and delta(k)*
    delta_k_conj=np.conj(delta_k)
    delta_k2=np.real(delta_k*delta_k_conj)
    del delta_k,delta_k_conj

    #compute the modulus of k at each grid point and count modes
    k=k_module(dims)
    count=lin_histogram(bins_r,0.0,bins_r*1.0,k,weights=None)

    #compute the P(k)
    Pk=lin_histogram(bins_r,0.0,bins_r*1.0,k,delta_k2)
    print Pk
    Pk=Pk/count

    #final processing
    bins_k=np.linspace(0.0,bins_r,bins_r+1)
    #compute k bins and give them physical units (h/Mpc), (h/kpc)
    k=0.5*(bins_k[:-1]+bins_k[1:])
    k=2.0*np.pi*k/BoxSize 

    #given the physical units to P(k) (Mpc/h)^3, (kpc/h)^3 ...
    Pk=Pk*BoxSize**3 

    n=len(pos)*1.0/BoxSize**3 #mean density
    if shoot_noise_correction:
        Pk=Pk-1.0/n #correct for the shot noise

    #compute the error on P(k)
    delta_Pk=np.sqrt(2.0/count)*(1.0+1.0/(Pk*n))*Pk

    print 'time used to perform calculation=',time.clock()-start_time,' s'

    #ignore the first bin
    k=k[1:]; Pk=Pk[1:]; delta_Pk=delta_Pk[1:]
    Pk=np.array([k,Pk,delta_Pk])
    return Pk
##############################################################################


#this function implements the CIC correction to the modes
def CIC_correction(dims):
    array=np.empty(dims**3,dtype=np.float32)
    length=array.shape[0]

    support = "#include <math.h>"
    code = """
       int dims2=dims*dims;
       int middle=dims/2;
       int i,j,k;
       float value_i,value_j,value_k;

       for (long l=0;l<length;l++){
           i=l/dims2;
           j=(l%dims2)/dims;
           k=(l%dims2)%dims;

           i = (i>middle) ? i-dims : i;
           j = (j>middle) ? j-dims : j;
           k = (k>middle) ? k-dims : k;

           value_i = (i==0) ? 1.0 : pow((i*M_PI/dims)/sin(i*M_PI/dims),2);
           value_j = (j==0) ? 1.0 : pow((j*M_PI/dims)/sin(j*M_PI/dims),2);
           value_k = (k==0) ? 1.0 : pow((k*M_PI/dims)/sin(k*M_PI/dims),2);

           array(l)=value_i*value_j*value_k;
       } 
    """
    wv.inline(code,['dims','array','length'],
              type_converters = wv.converters.blitz,
              support_code = support,libraries = ['m'],
              extra_compile_args =['-O3'])
    return array



#this function computes the module of k for a given point in the fourier grid
def k_module(dims):

    mod_k=np.empty(dims**3,np.float32)

    support = "#include <math.h>"
    code = """
       int dims2=dims*dims;
       long dims3=dims2*dims;
       int middle=dims/2;
       int i,j,k;

       for (long l=0;l<dims3;l++){
           i=l/dims2;
           j=(l%dims2)/dims;
           k=(l%dims2)%dims;

           i = (i>middle) ? i-dims : i;
           j = (j>middle) ? j-dims : j;
           k = (k>middle) ? k-dims : k;

           mod_k(l)=sqrt(i*i+j*j+k*k);
       } 
    """
    wv.inline(code,['dims','mod_k'],
              type_converters = wv.converters.blitz,
              support_code = support,libraries = ['m'],
              extra_compile_args =['-O3'])
    return mod_k


def lin_histogram(bins,minimum,maximum,array,weights):
    #the elements which are equal to the maximum may not lie in the bins
    #we create an extra bin to place those elements there
    #at the end we put those elements in the last bin of the histogram

    histo=np.zeros(bins+1,np.float32)
    length=array.shape[0]

    support = "#include <math.h>"

    code1 = """
    int index;

    for (int k=0;k<length;k++){
        index=(int)array(k)*bins/(maximum-minimum);
        histo(index)+=1.0;
    }
    histo(bins-1)+=histo(bins); 
    """

    code2 = """
    int index;

    for (int k=0;k<length;k++){
        index=(int)array(k)*bins/(maximum-minimum);
        histo(index)+=weights(k);
    }
    histo(bins-1)+=histo(bins); 
    """
    
    if weights==None:
        wv.inline(code1,['length','minimum','maximum','bins','histo','array']
                  ,type_converters = wv.converters.blitz,
                  support_code = support,libraries = ['m'],
                  extra_compile_args =['-O3'])
    else:
        if length!=weights.shape[0]:
            print 'the lengths of the array and its weights must be the same'
            sys.exit()
        wv.inline(code2,
                  ['length','minimum','maximum','bins','histo','array','weights'],
                  type_converters = wv.converters.blitz,
                  support_code = support,libraries = ['m'],
                  extra_compile_args =['-O3'])

    return histo[:-1]






########################### EXAMPLE OF USAGE ###########################

BoxSize=500.0 #Mpc/h
dims=1024 #number of points in the grid in each direction
n=1024**3 #number of particles in the catalogue

pos=(np.random.random((n,3))*BoxSize).astype(np.float32) #positions in Mpc/h

Pk=power_spectrum(pos,dims,BoxSize)

print Pk

f=open('borrar.dat','w')
for i in range(len(Pk[0])):
    f.write(str(Pk[0][i])+' '+str(Pk[1][i])+' '+str(Pk[2][i])+'\n')
f.close()