.. _lcb: https://gbiomed.kuleuven.be/english/research/50000622/lcb
.. _vsc: https://www.vscentrum.be/
.. _Gert: https://gbiomed.kuleuven.be/english/research/50000622/lcb/people/00079808
.. _Mark: https://gbiomed.kuleuven.be/english/research/50000622/lcb/people/00089478
.. _ssh: https://en.wikipedia.org/wiki/Secure_Shell
.. _`terminal multiplexer`: https://en.wikipedia.org/wiki/Terminal_multiplexer
.. _tmux: https://github.com/tmux/tmux/wiki
.. _jupyter: http://jupyter.org/
.. _`installation guide`: installation.html
.. _`known issue`: #known-issues
.. _`github issue`: https://github.com/dask/distributed/issues/1515
.. _`diagnostics dashboard`: http://distributed.readthedocs.io/en/latest/web.html

LCB Notes
=========

This page contains additional documentation relevant for the Stein Aerts Lab of
Computation Biology (LCB_).

VSC access
----------

First you will need access to the VSC_ front nodes. For this, a VSC_ account is
required plus additional ssh_ configuration.

.. tip::

    Kindly ask Gert_ for assistance setting up your ssh_ configuration for the VSC using the
    ``https://git.aertslab.org/connect_to_servers/`` script.


Front nodes
~~~~~~~~~~~

We will work with following machines:

=========   ========    =======================     ======
Alias       HostName    CPU                         Memory
=========   ========    =======================     ======
hpc2-big1   r10n1       10 core (20 threads)        256 GB
hpc2-big2   r10n2       10 core (20 threads)        256 GB
hpc2-big3   r6i0n5      2x 12-core (48 threads)     512 GB
hpc2-big4   r6i0n12     2x 12-core (48 threads)     512 GB
hpc2-big5   r6i0n13     2x 12-core (48 threads)     512 GB
hpc2-big6   r6i1n12     2x 12-core (48 threads)     512 GB
hpc2-big7   r6i1n13     2x 12-core (48 threads)     512 GB
=========   ========    =======================     ======

The aliases are the ones defined by the ``https://git.aertslab.org/connect_to_servers/`` script.

Running Arboretum on the front nodes
------------------------------------

Following section describes the steps requires for inferring a GRN using Arboretum
in distributed mode, using the front nodes.

.. tip::

    Setting up a Dask.distributed cluster requires ssh access to multiple nodes.
    We recommend using a `terminal multiplexer`_ tool like tmux_ for managing
    multiple ssh sessions.

    On the VSC_, tmux_ is available by loading following module:

    .. code-block:: bash

        $ module load tmux/2.5-foss-2014a

Scenario
~~~~~~~~

We will set up a cluster using about half the CPU resources of the 5 larger nodes
(``hpc2-big3`` to ``hpc2-big7``). One of the large nodes will also host the
Dask scheduler. One a smaller node, we run a Jupyter_ notebook server from which we
run the GRN inference using Arboretum.


.. figure:: https://github.com/tmoerman/arboretum/blob/master/img/lcb/distributed.png?raw=true
    :alt: LCB front nodes distributed architecture
    :align: center

    LCB front nodes distributed architecture


Setup
~~~~~

0. Software preparation
+++++++++++++++++++++++

As recommended in the `Installation Guide`_, we will use an Anaconda distribution.
On the front nodes we do this by loading a module:

.. code-block:: bash
    :caption: ``vsc12345@r6i0n5``

    $ module load Anaconda/5-Python-3.6

We obviously need Arboretum (make sure you have the latest version):

.. code-block:: bash
    :caption: ``vsc12345@r6i0n5``

    $ pip install arboretum

    $ pip show arboretum

    Name: arboretum
    Version: 0.1.3
    Summary: Scalable gene regulatory network inference using tree-based ensemble regressors
    Home-page: https://github.com/tmoerman/arboretum
    Author: Thomas Moerman
    Author-email: thomas.moerman@gmail.com
    License: BSD 3-Clause License
    Location: /vsc-hard-mounts/leuven-data/software/biomed/Anaconda/5-Python-3.6/lib/python3.6/site-packages
    Requires: scikit-learn, dask, numpy, scipy, distributed, pandas

We now proceed with launching the Dask scheduler and workers. Make sure that on
the nodes, the Anaconda module was loaded like explained above.

1. Starting the Dask scheduler
++++++++++++++++++++++++++++++

On node ``r6i0n5``, we launch the Dask scheduler.

.. code-block:: bash
    :emphasize-lines: 4, 5
    :caption: ``vsc12345@r6i0n5``

    $ dask-scheduler

    distributed.scheduler - INFO - -----------------------------------------------                                                                                                                      │distributed.worker - INFO -         Registered to:  tcp://10.118.224.134:8786
    distributed.scheduler - INFO -   Scheduler at: tcp://10.118.224.134:8786                                                                                                                            │distributed.worker - INFO - -------------------------------------------------
    distributed.scheduler - INFO -       bokeh at:                    :35874                                                                                                                            │distributed.worker - INFO -         Registered to:  tcp://10.118.224.134:8786
    distributed.scheduler - INFO - Local Directory:    /tmp/scheduler-wu5odlrh                                                                                                                          │distributed.worker - INFO - -------------------------------------------------
    distributed.scheduler - INFO - -----------------------------------------------

The command launches 2 services:

* The Dask scheduler on address: ``tcp://10.118.224.134:8786``
* The Dask `diagnostics dashboard`_ on address: ``tcp://10.118.224.134:35874``

.. tip::

    The Dask `diagnostics dashboard`_ is useful for monitoring the progress of
    long-running Dask jobs. In order to view the dashboard, which runs on the VSC
    front node ``r6i0n5``, use ssh port forwarding as follows:

    .. code-block:: bash

        ssh -L 8787:localhost:35874 hpc2-big3

    You can now view the Dask dashboard on url: ``http://localhost:8787``.

2. Adding workers to the scheduler
++++++++++++++++++++++++++++++++++

.. _nice: https://en.wikipedia.org/wiki/Nice_%28Unix%29

We will need the scheduler address: ``tcp://10.118.224.134:8786`` (highlighted
above) when launching worker processes connected to the scheduler.

First, we launch 24 worker processes on the same machine where the scheduler is
running:

.. code-block:: bash
    :caption: ``vsc12345@r6i0n5``

    $ nice -n 10 dask-worker tcp://10.118.224.134:8786 --nprocs 24 --nthreads 1

The command above consists of several parts, let's briefly discuss them:

* ``nice -n 10``

    Setting a nice_ value of higher than 0 gives the process a lower priority,
    which is sometimes desirable to not highjack the resources on compute nodes
    used by multiple users.

    Setting a nice_ value is **entirely optional** and up to the person setting up
    the distributed network. You can safely omit this.

* ``dask-worker tcp://10.118.224.134:8786 --nprocs 24 --nthreads 1``

    Spins up 24 worker processes with 1 thread per process. For Arboretum, it is
    recommended to always set ``--nthreads 1``.

    In this case we have chosen 24 processes because we planned to use only half
    the CPU capacity of the front nodes.

In the terminal where the scheduler was launched, you should see messages indicating
workers have been connected to the scheduler:

.. code-block:: bash

    distributed.scheduler - INFO - Register tcp://10.118.224.134:43342
    distributed.scheduler - INFO - Starting worker compute stream, tcp://10.118.224.134:43342

We now repeat the same command on the other compute nodes that will run Dask worker processes:

.. code-block:: bash
    :caption: ``vsc12345@r6i0n12``

    $ nice -n 10 dask-worker tcp://10.118.224.134:8786 --nprocs 24 --nthreads 1

.. code-block:: bash
    :caption: ``vsc12345@r6i0n13``

    $ nice -n 10 dask-worker tcp://10.118.224.134:8786 --nprocs 24 --nthreads 1

.. code-block:: bash
    :caption: ``vsc12345@r6i1n12``

    $ nice -n 10 dask-worker tcp://10.118.224.134:8786 --nprocs 24 --nthreads 1

.. code-block:: bash
    :caption: ``vsc12345@r6i1n13``

    $ nice -n 10 dask-worker tcp://10.118.224.134:8786 --nprocs 24 --nthreads 1

3. Running Arboretum from a Jupyter notebook
++++++++++++++++++++++++++++++++++++++++++++

So far, we have a scheduler running with 5*24 worker processes connected to it and
a diagnostics dashboard. We can now proceed with launching an Arboretum job on
the Dask cluster.
