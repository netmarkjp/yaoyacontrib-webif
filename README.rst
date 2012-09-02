========================
YAOYA data convertor
========================

Requirement
========================

- python 2.6+
- mongodb


Install
========================

shell::

 pip install -r requirements.txt
 
 # on MacOSX, if pymongo installation failed, exec following line
 env ARCHFLAGS="-arch i386 -arch x86_64" pip install -r requirements.txt

Usage
========================

1. Run yaoyacontrib-webif( `python yaoya-webif/application.py` )
2. access `http://localhost:5000/`
   or `http://localhost:5000/specsheet` (specsheet is recommended)

Development
========================

shell::

 virtualenv --no-site-packages --python=python2.6 venv
 venv/bin/pip -r requirements.txt

