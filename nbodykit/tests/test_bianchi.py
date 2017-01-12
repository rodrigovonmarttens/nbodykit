from mpi4py_test import MPITest
from nbodykit.lab import *
from nbodykit import setup_logging

from scipy.interpolate import InterpolatedUnivariateSpline
from numpy.testing import assert_allclose

# debug logging
setup_logging("debug")

@MPITest([1, 4])
def test_bianchi(comm):
    
    NDATA = 1000
    NBAR = 1e-4
    
    CurrentMPIComm.set(comm)
    cosmo = cosmology.Planck15
    
    data = Source.RandomParticles(NDATA, seed=42)
    randoms = Source.RandomParticles(NDATA*10, seed=84)
    
    # add the random columns
    for s in [data, randoms]:
        
        # ra, dec, z
        s['z']   = s.rng.normal(loc=0.5, scale=0.1, size=s.size)
        s['ra']  = s.rng.uniform(low=110, high=260, size=s.size)
        s['dec'] = s.rng.uniform(low=-3.6, high=60., size=s.size)
        
        # position
        s['Position'] = transform.SkyToCartesion(s['ra'], s['dec'], s['z'], cosmo=cosmo)
    
        # constant number density
        s['NZ'] = NBAR
                
        # completeness weights
        P0 = 1e4
        s['Weight'] = (1 + P0*s['NZ'])**2
    
    # the FKP source
    fkp = Source.FKPCatalog(data, randoms)
    fkp = fkp.to_mesh(Nmesh=128, dtype='f8', nbar='NZ', fkp_weight='FKPWeight', comp_weight='Weight')

    # compute the multipoles
    r = BianchiFFTPower(fkp, max_ell=4, dk=0.005, use_fkp_weights=True, P0_FKP=P0)

    # normalization
    assert_allclose(r.attrs['data.A'], NDATA*NBAR)
    assert_allclose(r.attrs['randoms.A'], NDATA*NBAR)
    
    # shotnoise
    S_data = r.attrs['data.W']/r.attrs['randoms.A']
    assert_allclose(S_data, r.attrs['data.S'])
    
    S_ran = r.attrs['randoms.W']/r.attrs['randoms.A']*r.attrs['alpha']**2
    assert_allclose(S_ran, r.attrs['randoms.S'])
    
@MPITest([1, 4])
def test_with_zhist(comm):
    
    NDATA = 1000
    NBAR = 1e-4
    FSKY = 0.15
    
    CurrentMPIComm.set(comm)
    cosmo = cosmology.Planck15
    
    data = Source.RandomParticles(NDATA, seed=42, use_cache=True)
    randoms = Source.RandomParticles(NDATA*10, seed=84, use_cache=True)
    
    # add the random columns
    for s in [data, randoms]:
        
        # ra, dec, z
        s['z']   = s.rng.normal(loc=0.5, scale=0.1, size=s.size)
        s['ra']  = s.rng.uniform(low=110, high=260, size=s.size)
        s['dec'] = s.rng.uniform(low=-3.6, high=60., size=s.size)
        
        # position
        s['Position'] = transform.SkyToCartesion(s['ra'], s['dec'], s['z'], cosmo=cosmo)
        
    # initialize the FKP source
    fkp = Source.FKPCatalog(data, randoms)
    
    # compute NZ from randoms
    zhist = RedshiftHistogram(fkp.randoms, FSKY, cosmo, redshift='z')
    
    # add n(z) from randoms to the FKP source
    nofz = InterpolatedUnivariateSpline(zhist.bin_centers, zhist.nbar)
    fkp['randoms.NZ'] = nofz(randoms['z'])
    fkp['data.NZ'] = nofz(data['z'])
    
    # normalize NZ to the total size of the data catalog
    alpha = 1.0 * data.csize / randoms.csize
    fkp['randoms.NZ'] *= alpha
    fkp['data.NZ'] *= alpha
    
    # compute the multipoles
    r = BianchiFFTPower(fkp.to_mesh(Nmesh=128), max_ell=4, dk=0.005)

    assert_allclose(r.attrs['data.A'], 0.000388338522187, rtol=1e-5)
    assert_allclose(r.attrs['randoms.A'], 0.000395808747269, rtol=1e-5) 

    


