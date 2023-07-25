from setuptools import setup, find_packages

PYTHON_VERSION_REQ = ">3.10.0"
BPOD_CURRENT_VERSION = "0.0.0"

long_description = """bpod is a python module for interaction with the Bpod finite state
state machine from [Sanworks](https://sanworks.io/)."""

with open("requirements.txt") as f:
    require = [x.strip() for x in f.readlines() if not x.startswith("git+")]

setup(
    name="bpod",
    version=BPOD_CURRENT_VERSION,
    python_requires=PYTHON_VERSION_REQ,
    description="python module for interfacing with a Bpod finite state machine",
    license="MIT",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="IBL Staff",
    url="https://github.com/int-brain-lab/bpod/",
    package_dir={"": "src"},
    packages=find_packages(where="src", exclude=["scratch", "test"]),  # same as name
    include_package_data=True,
    install_requires=require,
    scripts=[],
)
