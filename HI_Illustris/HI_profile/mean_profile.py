import numpy as np 
import sys,os,h5py

#################################### INPUT #####################################
Mmin_fin = 1e9 #Msun/h
Mmax_fin = 1e15 #Msun/h
bins     = 50
redshift = 4.01

Mmin = 1e12 #Msun/h
Mmax = 2e12 #Msun/h
################################################################################

# find output file name
fout1 = 'HI_profile_new_sample_%.1e-%.1e_z=%.1f.txt'%(Mmin,Mmax,redshift)
fout2 = 'HI_profile_new_%.1e-%.1e_z=%.1f.txt'%(Mmin,Mmax,redshift)

# read HI profiles file
fin = 'HI_profiles_%.1e-%.1e_%d_z=%.2f.hdf5'%(Mmin_fin,Mmax_fin,bins,redshift)
f      = h5py.File(fin, 'r')
rho_HI = f['rho_HI'][:]
Mass   = f['Mass'][:]
r      = f['r'][:]
f.close()

# select the halos in the mass bin
indexes = np.where((Mass>Mmin) & (Mass<Mmax) & (r[:,-1]!=0.0))[0]
rho_HI  = rho_HI[indexes]
Mass    = Mass[indexes]
r       = r[indexes]
Rv      = r[:,-1]

f = open(fout1,'w')
numbers = np.random.choice(len(Mass), min(len(Mass),60), replace=False)
for i in numbers:
	for j in xrange(len(r[i])):
		f.write(str(r[i][j])+' '+str(rho_HI[i][j])+'\n')
	f.write('\n')
f.close()

Rv_median      = np.median(Rv)
r_mean_profile = np.logspace(-5, np.log10(Rv_median), bins)

print 'Found %d halos'%Mass.shape[0]
print '%.3e < M [Msun/h] < %.3e'%(np.min(Mass), np.max(Mass))
print '%.4f < Rv [Mpc/h] < %.4f'%(np.min(Rv), np.max(Rv))
print 'Median Rv = %.4f Mpc/h'%Rv_median

HI_mean = np.zeros(bins, dtype=np.float64)
HI_std  = np.zeros(bins, dtype=np.float64)
f = open(fout2, 'w')
for i in xrange(bins):

	radius = r_mean_profile[i]

        # select the halos with Rv>radius
	indexes      = np.where(Rv>=radius)[0]
	rho_HI_stack = rho_HI[indexes]
	r_stack      = r[indexes]

	print '%6d halos with Rv>%.5f Mpc/h'%(r_stack.shape[0],radius)

	HI_prof = np.zeros(r_stack.shape[0], dtype=np.float64)
	for j in xrange(rho_HI_stack.shape[0]):
		HI_prof[j] = np.interp(radius, r_stack[j], rho_HI_stack[j])

	HI_mean[i] = np.mean(HI_prof)
	HI_std[i]  = np.std(HI_prof)
	f.write(str(radius)+' '+str(HI_mean[i])+' '+\
		str(np.median(HI_prof))+' '+str(HI_std[i])+'\n')
f.close()

