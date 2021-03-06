
.. highlight:: bash

.. _installation:

Installation
============

Download
--------

You can download the source files in two ways.

- **[Release version]**

  Go to the `release page <https://github.com/issp-center-dev/DCore/releases>`_ and download the latest tar or zip file.
  You can unpack, for example, the tar file by

  .. code-block:: bash

      $ tar zxvf v2.x.x.tar.gz

- **[Develop version]**

  Newly implemented features are available in the source code in GitHub repository. You can clone the repository by

  .. code-block:: bash

      $ git clone https://github.com/issp-center-dev/DCore.git dcore.src

  The master branch basically corresponds to the latest released package, and the develop branch includes new features.
  Note that develop branches may not be well tested and contains some bugs.

Prerequisites
-------------

#. `TRIQS <https://triqs.github.io/triqs/>`_ and `DFTTools/TRIQS <https://triqs.github.io/dft_tools/>`_.
    They must be installed prior to installing all other programs.
    If not, please install them following our instruction for :doc:`TRIQS 1.4.x <install_triqs14x>` or :doc:`TRIQS 2.1.x <install_triqs21x>`.

    In the following, we suppose that ``TRIQS`` is installed in directory *path_to_triqs*.

#. You will also need at least one impurity solver.

   For example, the following programs are supported at present:

   * :doc:`ALPS/CT-HYB<impuritysolvers/alpscore_cthyb/cthyb>`
   * :doc:`ALPS/CT-HYB-SEGMENT<impuritysolvers/alpscore_ctseg/ctseg>`
   * :doc:`TRIQS/cthyb<impuritysolvers/triqs_cthyb/cthyb>`
   * :doc:`Hubbard-I solver<impuritysolvers/triqs_hubbard_one/hubbard_one>` (not available for TRIQS 2.1.x)

   See :doc:`impuritysolvers` for a complete list of supported impurity solvers and their user manuals.

..
   * `Hubbard-I solver <https://triqs.ipht.cnrs.fr/1.x/applications/hubbardI/>`_
   * `ALPS/CT-HYB <https://github.com/ALPSCore/CT-HYB>`_
   * `ALPS/CT-HYB-SEGMENT <https://github.com/ALPSCore/CT-HYB-SEGMENT>`_
   * `TRIQS/cthyb <https://triqs.ipht.cnrs.fr/applications/cthyb/index.html>`_

..
   .. note::

      One must build TRIQS, TRIQS/DFTTools, and TRIQS solvers using the same C++ compiler with the same C++ standard (C++14).
      One does not necessarily have to build ALPS/CT-HYB and/or ALPS/CT-HYB-SEGMENT with the same C++ compiler as that used for TRIQS.

Installation steps
------------------

#. Create an empty directory where you will compile the code

   ::

     $ mkdir dcore.build && cd dcore.build

#. In the build directory, call cmake command with an option to specify the path to TRIQS library

   ::

     $ cmake -DTRIQS_PATH=path_to_triqs path_to_dcore_src -DCMAKE_INSTALL_PREFIX=path_to_dcore_install_directory

   Here, *path_to_triqs* refers to your ``TRIQS`` install directory, and *path_to_dcore_src* refers to the ``DCore`` source directory.
   Please set CMAKE_INSTALL_PREFIX to the directory where DCore will be installed.
   If the cmake command succeeded, you will see the following message.

   ::

     -- Build files have been written to: /.../dcore.build

#. Build DCore by

   ::

     $ make

#. We recommend to run the tests to check if DCore is built correctly. Type

   ::

     $ make test

   If your system MPI wrapper is not "mpirun", please provide the name of the correct one to DCore through cmake by using the flag "-DMPIEXEC".
   The default value is "mpirun -np #" (# is replaced by the number of processors).
   For instance, if your wrapper is "mpijob" and you do not need to specify the number of processors explicitly, please use -DMPIEXEC=mpijob.
   Note that it is not allowed to run MPI programs interactively on some system.
   In this case, please run tests as a job.

   The test results look like

   ::

     Running tests...
     /usr/local/Cellar/cmake/3.13.4/bin/ctest --force-new-ctest-process
     Test project /Users/hiroshi/build/dcore
           Start  1: typed_parser
      1/12 Test  #1: typed_parser .....................   Passed    1.38 sec
           Start  2: tools
      2/12 Test  #2: tools ............................   Passed    0.75 sec
           Start  3: openmx
      3/12 Test  #3: openmx ...........................   Passed    0.70 sec
           Start  4: respack
      4/12 Test  #4: respack ..........................   Passed    0.81 sec
           Start  5: pre_preset
      5/12 Test  #5: pre_preset .......................   Passed    1.69 sec
           Start  6: pre_wannier
      6/12 Test  #6: pre_wannier ......................   Passed    3.02 sec
           Start  7: pre_wannier_so
      7/12 Test  #7: pre_wannier_so ...................   Passed    0.95 sec
           Start  8: pre_respack
      8/12 Test  #8: pre_respack ......................   Passed    0.94 sec
           Start  9: pre_respack_so
      9/12 Test  #9: pre_respack_so ...................   Passed    1.03 sec
           Start 10: alps_cthyb
     10/12 Test #10: alps_cthyb .......................   Passed    3.02 sec
           Start 11: chain_hubbardI_so
     11/12 Test #11: chain_hubbardI_so ................   Passed   28.28 sec
           Start 12: chain_hubbardI
     12/12 Test #12: chain_hubbardI ...................   Passed   23.49 sec
     
     100% tests passed, 0 tests failed out of 12
   
     Total Test time (real) =  66.11 sec
  
   In the above example, all tests have passed in 66 sec.

#. Finally, install by

   ::

     $ make install

   ``DCore`` is installed in the directory *path_to_dcore_install_directory*.

.. Version compatibility
.. ---------------------
..
.. The current version of DCore supports TRIQS 1.4, and ALPSCore 2.1 or later.
.. Be careful that the version of the TRIQS library and of the dft tools must be
.. compatible (more information on the :ref:`TRIQS website <triqslibs:welcome>`).
.. If you want to use a version of the dft tools that is not the latest one, go
.. into the directory with the sources and look at all available versions::
..
..      $ cd src && git tag
..
.. Checkout the version of the code that you want, for instance::
..
..      $ git co 1.4
..
.. Then follow the steps 2 to 5 described above to compile the code.

