#!/bin/bash
# work only on ubuntu 14.04~14.04.3, 16.04 and 16.04.1 installations and
# theirs updates, not on 14.04.4, 14.04.5 and 16.04.2 original installation.

if ! dpkg -s git 2> /dev/null > /dev/null
then
  sudo apt-get install -y git
fi

if ! dpkg -s g++ 2> /dev/null > /dev/null
then
  sudo apt-get install -y g++
fi

if ! dpkg -s libpython2.7-dev 2> /dev/null > /dev/null
then
  sudo apt-get install -y libpython2.7-dev
fi

git clone --recursive https://github.com/boostorg/boost.git
cd boost/
./bootstrap.sh
sudo ./b2 install
cd ..
rm -rf boost

git clone https://github.com/Z3Prover/z3
cd z3/
python scripts/mk_make.py
cd build
make
sudo make install
cd ../..
rm -rf z3

git clone https://github.com/aquynh/capstone
cd capstone/
./make.sh
sudo make install
cd ..
rm -rf capstone

if ! dpkg -s cmake 2> /dev/null > /dev/null
then
  sudo apt-get install -y cmake
fi

wget 'https://software.intel.com/sites/landingpage/pintool/downloads/pin-2.14-71313-gcc.4.4.7-linux.tar.gz'
tar -xvf pin-2.14-71313-gcc.4.4.7-linux.tar.gz
rm pin-2.14-71313-gcc.4.4.7-linux.tar.gz
cd pin-2.14-71313-gcc.4.4.7-linux/source/tools/
git clone https://github.com/JonathanSalwan/Triton.git
cd Triton
mkdir build
cd build
cmake -DPINTOOL=on -DKERNEL4=on ..
make
cd ../../../../../
sudo cp -r pin-2.14-71313-gcc.4.4.7-linux/ /usr/local/bin/
sudo sh -c 'echo 0 > /proc/sys/kernel/yama/ptrace_scope'
sudo ln -s /usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux/source/tools/Triton/build/triton /usr/local/bin/triton
sudo ln -s /usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux/source/tools/Triton/build/tritonAttach /usr/local/bin/tritonAttach
