from distutils.core import setup, Extension
setup(name='CyMesh',version='1.0', \
        ext_modules=[Extension('CyMesh',['CyMesh.cpp'])])
setup(name='CyOffset',version='1.0', \
        ext_modules=[Extension('CyOffset',['CyOffset.cpp'])])