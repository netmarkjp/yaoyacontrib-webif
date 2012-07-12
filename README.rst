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


Development
========================

shell::

 virtualenv --no-site-packages --python=python2.6 venv
 venv/bin/pip -r requirements.txt

