#!/usr/bin/env python
#
# DCore -- Integrated DMFT software for correlated electrons
# Copyright (C) 2017 The University of Tokyo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
from __future__ import print_function
import os
import argparse
import re
from dmft_core import DMFTCoreSolver
from program_options import create_parser
from pytriqs.applications.dft.sumk_dft_tools import *
from pytriqs.applications.dft.converters.wannier90_converter import Wannier90Converter


class DMFTCoreTools:
    def __init__(self, seedname, params, n_k, xk):
        """
        Class of posting tool for DCore.

        Parameters
        ----------
        :param seedname: string
            name for hdf5 file
        :param params:  dictionary
            Input parameters
        :param n_k: integer
            Number of k points
        :param xk:  integer array
            x-position for plotting band
        """

        self._params = copy.deepcopy(params)
        # Construct a SumKDFT object
        self._n_pade = int(params['tool']['n_pade']) # Number of Matsubara frequencies
        self._omega_min = float(params['tool']['omega_min'])
        self._omega_max = float(params['tool']['omega_max'])
        self._Nomega = int(params['tool']['Nomega'])
        self._broadening = float(params['tool']['broadening'])
        self._eta = float(params['tool']['eta'])
        self._seedname = seedname
        self._n_k = n_k
        self._xk = xk
        self._SKT = SumkDFTTools(hdf_file=self._seedname + '.h5', use_dft_blocks=False)
        self._solver = DMFTCoreSolver(seedname, params)

    def post(self):
        """
        Calculate DOS (Density Of State) and energy dispersions.
        For Hubbard-I solver, self-energy is calculated in this function.
        For cthyb (both TRIQS and ALPS), self-energy is read from hdf5 file.
        """
        SKT = self._SKT
        Sol = self._solver
        S = self._solver._S
        nsh = SKT.n_inequiv_shells
        dc_type = int(self._params['system']['dc_type'])  # DC type: -1 None, 0 FLL, 1 Held, 2 AMF
        if dc_type == -1:
            with_dc = False
        else:
            with_dc = True

        if mpi.is_master_node():
            print("\n  @ Compute Green' function at the real frequency")
        #
        # Set necessary quantities
        #
        if mpi.is_master_node():
            SKT.chemical_potential, SKT.dc_imp, SKT.dc_energ = SKT.load(['chemical_potential','dc_imp','dc_energ'])
        SKT.chemical_potential = mpi.bcast(SKT.chemical_potential)
        SKT.dc_imp = mpi.bcast(SKT.dc_imp)
        SKT.dc_energ = mpi.bcast(SKT.dc_energ)

        # compute real-frequency self-energy, sigma_w
        sigma_w =[]
        if Sol._solver_name == 'TRIQS/hubbard-I':
            # set atomic levels:
            eal = SKT.eff_atomic_levels()
            for ish in range(nsh):
                S[ish].set_atomic_levels(eal=eal[ish])
                # Run the solver to get GF and self-energy on the real axis
                S[ish].GF_realomega(ommin=self._omega_min, ommax=self._omega_max, N_om=self._Nomega,
                                    U_int=Sol._U_int, J_hund=Sol._J_hund)
                sigma_w.append(S[ish].Sigma_iw)
        elif Sol._solver_name == "TRIQS/cthyb" or Sol._name == "ALPS/cthyb":
            # Read info from HDF file
            ar = HDFArchive(self._seedname+'.out.h5', 'r')
            iteration_number = ar['dmft_out']['iterations']
            print("    Iteration {0}".format(iteration_number))
            for ish in range(nsh):
                S[ish].Sigma_iw << ar['dmft_out']['Sigma_iw'][str(ish)]
                # set BlockGf sigma_w
                block_names = list(S[ish].Sigma_iw.indices)
                glist = lambda: [GfReFreq(indices=sig.indices, window=(self._omega_min, self._omega_max),
                                          n_points=self._Nomega, name="sig_pade") for bname, sig in S[ish].Sigma_iw]
                sigma_w.append(BlockGf(name_list=block_names, block_list=glist(), make_copies=False))
                # Analytic continuation
                for bname, sig in S[ish].Sigma_iw:
                    sigma_w[ish][bname].set_from_pade(sig, n_points=self._n_pade, freq_offset=self._eta)
        else:
            raise RuntimeError("Unknown solver " + Sol._solver_name)

        #
        SKT.set_Sigma([sigma_w[ish] for ish in range(nsh)])
        if mpi.is_master_node(): print("    Done")
        #
        #  (Partial) DOS
        #
        if mpi.is_master_node(): print("\n  @ Compute (partial) DOS")
        dos, dosproj, dosproj_orb = SKT.dos_wannier_basis(broadening=self._broadening,
                                                          mesh=[self._omega_min, self._omega_max, self._Nomega],
                                                          with_Sigma=True, with_dc=with_dc, save_to_file=False)
        #
        # Print DOS to file
        #
        om_mesh = numpy.linspace(self._omega_min, self._omega_max, self._Nomega)
        if mpi.is_master_node():
            with open(self._seedname + '_dos.dat', 'w') as f:
                print("# Energy DOS Partial-DOS", file=f)
                for iom in range(self._Nomega):
                    if Sol.SO:
                        print("{0} {1}".format(om_mesh[iom], dos['ud'][iom]), file=f, end="")
                    else:
                        print("{0} {1}".format(om_mesh[iom], 2.0*dos['down'][iom]), file=f, end="")
                    for ish in range(SKT.n_inequiv_shells):
                        for i in range(SKT.corr_shells[SKT.inequiv_to_corr[ish]]['dim']):
                            if Sol.SO:
                                print(" {0}".format(dosproj_orb[ish]['ud'][iom,i,i].real), end="", file=f)
                            else:
                                print(" {0}".format(2.0*dosproj_orb[ish]['down'][iom, i, i].real), end="", file=f)
                    print("", file=f)
            print("\n    Output {0}".format(self._seedname + '_dos.dat'))
        #
        # Band structure
        #
        if self._params["model"]["lattice"] == 'bethe': return
        #
        if mpi.is_master_node(): print ("\n  @ Compute band structure\n")
        akw = SKT.spaghettis(broadening=self._broadening,plot_range=None,ishell=None,save_to_file=None)
        #
        # Print band-structure into file
        #
        mesh = [x.real for x in SKT.Sigma_imp_w[0].mesh]
        if mpi.is_master_node():
            with open(self._seedname + '_akw.dat', 'w') as f:
                for ik in range(self._n_k):
                    for iom in range(self._Nomega):
                        if Sol.SO:
                            print("{0} {1} {2}".format(self._xk[ik], mesh[iom],akw['ud'][ik,iom]), file=f)
                        else:
                            print("{0} {1} {2}".format(self._xk[ik], mesh[iom],2.0*akw['down'][ik, iom]), file=f)
                    print("", file=f)
            print("\n    Output {0}".format(self._seedname + '_akw.dat'))


def __print_paramter(p, param_name):
    """
    Print parameters.

    Parameters
    ----------
    p : dictionary
        Dictionary for parameters
    param_name : string
        key for p
    """
    print(param_name + " = " + str(p[param_name]))


def __generate_wannier90_model(params, l, norb, equiv, n_k, kvec):
    """
    Compute hopping etc. for A(k,w) of Wannier90

    Parameters
    ----------
    params : dictionary
        Input parameters
    l : integer array
        Angular momentum at each correlation shell
    norb : integer array
        Number of orbitals at each correlation shell
    equiv : integer array
        Equivalence of correlation shell
    n_k : integer
        Number of k points
    kvec : float array
        k-points where A(k,w) is computed

    Returns
    -------
    hopping : complex
        k-dependent one-body Hamiltonian
    n_orbitals : integer
        Number of orbitals at each k. It does not depend on k
    proj_mat : complex
        Projection onto each correlated orbitals
    """
    ncor = params["ncor"]
    n_spin = 1

    if mpi.is_master_node():print("               ncor = ", ncor)
    for i in range(ncor):
        if equiv[i] == -1: equiv[i] = i
        if mpi.is_master_node():
            print("     l[{0}], norb[{0}], equiv[{0}] = {1}, {2}, {3}".format(i,l[i],norb[i],equiv[i]))
    #
    # Read hopping in the real space from the Wannier90 output
    #
    w90c = Wannier90Converter(seedname=params["seedname"])
    nr, rvec, rdeg, nwan, hamr = w90c.read_wannier90hr(params["seedname"]+"_hr.dat")
    #
    # Fourier transformation of the one-body Hamiltonian
    #
    n_orbitals = numpy.ones([n_k, n_spin], numpy.int) * nwan
    hopping = numpy.zeros([n_k, n_spin, numpy.max(n_orbitals), numpy.max(n_orbitals)], numpy.complex_)
    for ik in range(n_k):
        for ir in range(nr):
            rdotk = numpy.dot(kvec[ik,:], rvec[ir,:])
            factor = (numpy.cos(rdotk) + 1j * numpy.sin(rdotk)) / float(rdeg[ir])
            hopping[ik,0,:, :] += factor * hamr[ir][:, :]
    #
    # proj_mat is (norb*norb) identities at each correlation shell
    #
    proj_mat = numpy.zeros([n_k, n_spin, ncor, numpy.max(norb), numpy.max(n_orbitals)], numpy.complex_)
    iorb = 0
    for icor in range(ncor):
        proj_mat[:, :, icor, 0:norb[icor], iorb:iorb + norb[icor]] = numpy.identity(norb[icor], numpy.complex_)
        iorb += norb[icor]

    return hopping, n_orbitals, proj_mat


def __generate_lattice_model(params, n_k, kvec):
    """
    Compute hopping etc. for A(k,w) of preset models

    Parameters
    ----------
    params : dictionary
        Input parameters
    n_k : integer
        Number of k points
    kvec : float array
        k-points where A(k,w) is computed

    Returns
    -------
    hopping : complex
        k-dependent one-body Hamiltonian
    n_orbitals : integer
        Number of orbitals at each k. It does not depend on k
    proj_mat : complex
        Projection onto each correlated orbitals
    """
    #
    # Construct model
    #
    if params["orbital_model"] == 'single':
        norb = 1
    elif params["orbital_model"] == 'eg':
        #FIXME: l=2 does not make sense. l=2 assumes norb=5 (full d-shell) in generating Coulomb tensor.
        #What is the proper way to generate Coulomb tensor for eg?
        norb = 2
    elif params["orbital_model"] == 't2g':
        norb = 3
    elif params["orbital_model"] == 'full-d':
        norb = 5
    else:
        print("Error ! Invalid lattice : ", params["orbital_model"])
        sys.exit(-1)

    t = params["t"]
    tp = params["t'"]
    n_spin = 1
    #
    # Energy band
    #
    n_orbitals = numpy.ones([n_k, n_spin], numpy.int) * norb
    hopping = numpy.zeros([n_k, n_spin, norb, norb], numpy.complex_)
    if params["lattice"] == 'bethe':
        #
        # For Bhete lattice, k-point has no meanings.
        #
        print("Skip")
    else:

        for ik in range(n_k):
            if params["lattice"] == 'chain':
                ek = 2.0*t*numpy.cos(kvec[ik,0]) + 2*tp*numpy.cos(2.0*kvec[ik,0])
            elif params["lattice"] == 'square':
                ek = 2.0 * t * (numpy.cos(kvec[ik,0]) + numpy.cos(kvec[ik,1])) \
                   + 2.0 * tp * (numpy.cos(kvec[ik,0] + kvec[ik,1]) + numpy.cos(kvec[ik,0] - kvec[ik,1]))
            elif params["lattice"] == 'cubic':
                ek = 2 * t * (numpy.cos(kvec[ik,0]) + numpy.cos(kvec[ik,1]) + numpy.cos(kvec[ik,2])) \
                    + 2 * tp * (numpy.cos(kvec[ik,0] + kvec[ik,1]) + numpy.cos(kvec[ik,0] - kvec[ik,1]) \
                              + numpy.cos(kvec[ik,1] + kvec[ik,2]) + numpy.cos(kvec[ik,1] - kvec[ik,2]) \
                              + numpy.cos(kvec[ik,2] + kvec[ik,0]) + numpy.cos(kvec[ik,2] - kvec[ik,0]))

            for iorb in range(norb): hopping[ik, 0, iorb, iorb] = ek
    #
    # proj_mat is (norb*norb) identities at each correlation shell
    #
    proj_mat = numpy.zeros([n_k, n_spin, 1, norb, norb], numpy.complex_)
    proj_mat[:, :, 0, 0:norb, 0:norb] = numpy.identity(norb, numpy.complex_)

    return hopping, n_orbitals, proj_mat


def dcore_post(filename):
    """
    Main routine for the post-processing tool

    Parameters
    ----------
    filename : string
        Input-file name
    """
    if mpi.is_master_node(): print("\n  @ Reading {0} ...".format(filename))
    #
    # Construct a parser with default values
    #
    parser = create_parser()
    #
    # Parse keywords and store
    #
    parser.read(filename)
    p = parser.as_dict()
    seedname = p["model"]["seedname"]
    #
    # Information of correlation shells. It is used only in conjunction to Wannier90.
    # cshell=(l, norb, equiv) or (l, norb)
    #
    cshell_list=re.findall(r'\(\s*\d+\s*,\s*\d+\s*,*\s*\S*\s*\)', p["model"]["cshell"])
    l = [0]*p["model"]['ncor']
    norb = [1]*p["model"]['ncor']
    equiv = [-1]*p["model"]['ncor']
    try:
        equiv_str_list = []
        equiv_index = 0
        for  i, _list  in enumerate(cshell_list):
            _cshell = filter(lambda w: len(w) > 0, re.split(r'[\(\s*\,\s*,*\s*\)]', _list))
            l[i] = int(_cshell[0])
            norb[i] = int(_cshell[1])
            if len(_cshell) == 3:
                if _cshell[2] in equiv_str_list:
                    # Defined before
                    equiv[i] = equiv_str_list.index(_cshell[2])
                else:
                    # New one
                    equiv_str_list.append(_cshell[2])
                    equiv[i] = equiv_index
                    equiv_index+=1
            else:
                equiv[i] = equiv_index
                equiv_index+=1
    except:
        raise RuntimeError("Error ! Format of cshell is wrong.")

    #
    # Nodes for k-point path
    # knode=(label,k0, k1, k2) in the fractional coordinate
    #
    knode_list = re.findall(r'\(\w\d?,\s*-?\s*\d+\.?\d*,\s*-?\s*\d+\.?\d*,\s*-?\s*\d+\.?\d*\)', p["tool"]["knode"])
    knode = numpy.zeros((p["tool"]['nnode'], 3), numpy.float_)
    klabel =['G'] * p["tool"]['nnode']
    try:
        for i, _list in enumerate(knode_list):
            _knode = filter(lambda w: len(w) > 0, re.split(r'[\(\s*\,\s*\,\s*,\s*\)]', _list))
            klabel[i] = _knode[0]
            for j in range(3): knode[i,j] = float(_knode[j+1])
    except:
        raise RuntimeError("Error ! Format of knode is wrong.")
    #
    # Reciprocal lattice vectors
    # bvec=[(b0x, b0y, k0z),(b1x, b1y, k1z),(b2x, b2y, k2z)]
    #
    bvec_list = re.findall(r'\(\s*-?\s*\d+\.?\d*,\s*-?\s*\d+\.?\d*,\s*-?\s*\d+\.?\d*\)', p["model"]["bvec"])
    bvec = numpy.zeros((3, 3), numpy.float_)
    try:
        for i, _list in enumerate(bvec_list):
            _bvec = filter(lambda w: len(w) > 0, re.split(r'[\(\s*\,\s*,\s*\)]', _list))
            for j in range(3): bvec[i,j] = float(_bvec[j])
    except:
        raise RuntimeError("Error ! Format of bvec is wrong.")
    #
    # Summary of input parameters
    #
    if mpi.is_master_node():
        print("\n  @ Parameter summary")
        print("\n    [model] block")
        for k,v in p["model"].items():
            print("      {0} = {1}".format(k,v))
        print("\n    [tool] block")
        for k,v in p["tool"].items():
            print("      {0} = {1}".format(k,v))
    #
    # Construct parameters for the A(k,w)
    #
    if mpi.is_master_node(): print("\n  @ Constructing k-path")
    nnode = p["tool"]["nnode"]
    nk_line = p["tool"]["nk_line"]
    n_k = (nnode - 1)*nk_line + 1
    if mpi.is_master_node(): print("\n   Total number of k =", str(n_k))
    kvec = numpy.zeros((n_k, 3), numpy.float_)
    ikk = 0
    for inode in range(nnode - 1):
        for ik in range(nk_line + 1):
            if inode != 0 and ik == 0: continue
            for i in range(3):
                kvec[ikk,i] = float((nk_line - ik)) * knode[inode,i] + float(ik) * knode[inode + 1,i]
                kvec[ikk,i] = 2.0 * numpy.pi * kvec[ikk,i] / float(nk_line)
            ikk += 1
    #
    # Compute x-position for plotting band
    #
    dk = numpy.zeros(3, numpy.float_)
    dk_cart = numpy.zeros(3, numpy.float_)
    xk = numpy.zeros(n_k, numpy.float_)
    xk_label = numpy.zeros(nnode, numpy.float_)
    xk[0] = 0.0
    ikk = 0
    for inode in range(nnode - 1):
        dk[:] = knode[inode+1,:]- knode[inode,:]
        dk_cart[:] = numpy.dot(dk[:], bvec[:,:])
        klength = numpy.sqrt(numpy.dot(dk_cart[:],dk_cart[:])) / nk_line
        xk_label[inode] = xk[ikk]
        for ik in range(nk_line):
            xk[ikk+1] = xk[ikk] + klength
            ikk += 1
    xk_label[nnode-1] = xk[n_k-1]
    #
    # HDF5 file for band
    #
    if mpi.is_master_node():
        #
        # Compute k-dependent Hamiltonian
        #
        if mpi.is_master_node(): print("\n  @ Compute k-dependent Hamiltonian")
        if p["model"]["lattice"] == 'wannier90':
            hopping, n_orbitals, proj_mat = __generate_wannier90_model(p["model"], l, norb, equiv, n_k, kvec)
        else:
            hopping, n_orbitals, proj_mat = __generate_lattice_model(p["model"], n_k, kvec)
        #
        # Output them into seedname.h5
        #
        f = HDFArchive(seedname+'.h5','a')
        if not ("dft_bands_input" in f):
            f.create_group("dft_bands_input")
        f["dft_bands_input"]["hopping"] = hopping
        f["dft_bands_input"]["n_k"] = n_k
        f["dft_bands_input"]["n_orbitals"] = n_orbitals
        f["dft_bands_input"]["proj_mat"] = proj_mat
        del  f
        print("\n    Done")
    #
    # Plot
    #
    mpi.barrier()
    dct=DMFTCoreTools(seedname, p, n_k, xk)
    dct.post()
    #
    # Output gnuplot script
    #
    if mpi.is_master_node():
        print("\n  @ Generate GnuPlot script")
        with open(seedname + '_akw.gp', 'w') as f:
            print("set xtics (\\", file=f)
            for inode in range(nnode-1):
                print("  \"{0}\"  {1}, \\".format(klabel[inode], xk_label[inode]), file=f)
            print("  \"{0}\"  {1} \\".format(klabel[nnode-1], xk_label[nnode-1]), file=f)
            print("  )", file=f)
            print("set pm3d map", file=f)
            print("#set pm3d interpolate 5, 5", file=f)
            print("unset key", file=f)
            print("set ylabel \"Energy\"", file=f)
            print("set cblabel \"A(k,w)\"", file=f)
            if p["model"]["lattice"] == 'wannier90':
                print("splot \"{0}_akw.dat\", \"{0}_band.dat\" u 1:($2-{1}):(0) every 10 w p lc 5".format(
                    seedname, dct._SKT.chemical_potential), file=f)
            else:
                print("splot \"{0}_akw.dat\"".format(seedname), file=f)
            print("pause -1", file=f)
        print("\n    Usage:")
        print("\n      $ gnuplot {0}".format(seedname + '_akw.gp'))
    #
    # Finish
    #
    if mpi.is_master_node(): print("\n  Done\n")


if __name__ == '__main__':

    parser = argparse.ArgumentParser(\
        prog='dcore_post.py',\
        description='pre script for dcore.',\
        epilog='end',\
        usage = '$ dcore_post input',\
        add_help= True)
    parser.add_argument('path_input_file', \
                        action = 'store',\
                        default= None,    \
                        type=str, \
                        help = "input file name."
    )

    args=parser.parse_args()
    if(os.path.isfile(args.path_input_file) is False):
        print("Input file is not exist.")
        sys.exit(-1)
    dcore_post(args.path_input_file)
