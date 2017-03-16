#!/bin/bash
# work only on ubuntu 16.04 and 16.04.1 installations
# and theirs updates, not on 16.04.2 image installation.
# because pintool in triton only supports kernel version <=4.4
if ! dpkg -s libpython2.7-dev 2> /dev/null > /dev/null
then
  sudo apt-get install -y libpython2.7-dev
fi

if ! dpkg -s libboost-all-dev 2> /dev/null > /dev/null
then
  sudo apt-get install -y libboost-all-dev
fi

if ! dpkg -s libz3-dev 2> /dev/null > /dev/null
then
  sudo apt-get install -y libz3-dev
fi

if ! dpkg -s libcapstone-dev 2> /dev/null > /dev/null
then
  sudo apt-get install -y libcapstone-dev
fi

if ! dpkg -s git 2> /dev/null > /dev/null
then
  sudo apt-get install -y git
fi

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
cmake -DPINTOOL=on -DPINTOOL=on ..
make
cd ..
sudo sh -c 'echo 0 > /proc/sys/kernel/yama/ptrace_scope'
sudo ln -s $PWD/triton /usr/bin/triton