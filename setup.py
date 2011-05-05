from distutils.core import setup

setup(
        name="fakemtpd",
        version="0.1.6",
        provides="fakemtpd",
        author="James Brown",
        author_email="jbrown@yelp.com",
        url="http://github.com/Roguelazer/fakemtpd",
        description="Fake SMTP Daemon",
        classifiers = [
            "Programming Language :: Python",
            "Operating System :: POSIX",
            "License :: OSI Approved :: ISC License (ISCL)",
            "Intended Audience :: System Administrators",
            "Topic :: Communications :: Email",
            "Development Status :: 2 - Pre-Alpha"
        ],
        requires = [ "tornado (>=1.0)", "lockfile (>=0.7)", "yaml" ],
        packages = [ "fakemtpd" ],
        scripts = [ "bin/fakemtpd" ],
)
