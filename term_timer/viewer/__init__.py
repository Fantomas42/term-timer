"""
Out of process 3D visualisation of the cube.

The only place in term-timer allowed to import
``cubing_algs.display.gl``: everything here runs in the ``cube-view``
process, which subscribes to the event stream and draws what it hears.
The process timing the solves never loads a GPU driver, so no crash of
one can reach a session.
"""
