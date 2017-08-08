import atexit
import os
import platform
import shutil
import tempfile
from subprocess import check_call, check_output, STDOUT, CalledProcessError


def main():
    if platform.system() != 'Linux':
        raise RuntimeError('Only support Linux.')

    dist = platform.linux_distribution()
    if dist[0] != 'Ubuntu':
        raise RuntimeError('Only support Ubuntu.')

    if os.getuid() != 0:
        raise RuntimeError('Super user is required.')

    if platform.machine() == 'i686' and (dist[1] != '14.04' or platform.release() >= '4'):
        raise RuntimeError('In 32bit version, Only support Ubuntu 14.04 with kernel version less than 4'
                           '(Hint: Install Ubuntu 32bit 14.04.0-14.04.3')

    temp_dir = tempfile.mkdtemp()
    atexit.register(lambda: os.path.exists(temp_dir) and shutil.rmtree(temp_dir))
    os.chdir(temp_dir)
    if dist[1] == '14.04':
        required_packages = ['git', 'build-essential', 'cmake', 'libpython2.7-dev', 'libboost1.55-all-dev']
        check_call(['apt-get', 'install', '-y'] + required_packages)

        try:
            check_capstone = check_output(['gcc', '-lcapstone'], stderr=STDOUT)
        except CalledProcessError as e:
            check_capstone = e.output
        if 'cannot find -lcapstone' in check_capstone:
            check_call(['git', 'clone', 'https://github.com/aquynh/capstone.git'])
            os.chdir('capstone')
            check_call(['./make.sh'])
            check_call(['./make.sh', 'install'])
            os.chdir('..')
            shutil.rmtree('capstone')

        try:
            check_z3 = check_output(['gcc', '-lz3'], stderr=STDOUT)
        except CalledProcessError as e:
            check_z3 = e.output
        if 'cannot find -lz3' in check_z3:
            check_call(['git', 'clone', 'https://github.com/Z3Prover/z3.git'])
            os.chdir('z3')
            check_call(['python', 'scripts/mk_make.py'])
            os.chdir('build')
            check_call(['make'])
            check_call(['make', 'install'])

    elif dist[1] >= '16.04':
        required_packages = ['git', 'build-essential', 'cmake', 'libpython2.7-dev', 'libboost-all-dev',
                             'libcapstone-dev', 'libz3-dev']
        check_call(['apt-get', 'install', '-y'] + required_packages)
    else:
        raise RuntimeError('Only Ubuntu 14.04, 16.04 and higher are supported.')

    os.chdir(temp_dir)
    print 'cur dir:', os.curdir
    check_call(['wget', '-U', 'Mozilla/5.0',
                'http://software.intel.com/sites/landingpage/pintool/downloads/pin-2.14-71313-gcc.4.4.7-linux.tar.gz'])

    if os.path.exists('/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux'):
        if os.path.isdir('/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux'):
            shutil.rmtree('/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux')
        else:
            os.unlink('pin-2.14-71313-gcc.4.4.7-linux')
    check_call(['tar', '-xvf', 'pin-2.14-71313-gcc.4.4.7-linux.tar.gz', '-C', '/usr/local/bin'])
    shutil.rmtree(temp_dir)
    os.chmod('/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux/pin.sh', 0o755)
    os.chmod('/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux/source/tools/Utils/testGccVersion', 0o755)
    os.chmod('/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux/ia32/', 0o2751)
    os.chmod('/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux/intel64/', 0o2751)

    os.chdir('/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux/source/tools')
    check_call(['git', 'clone', 'https://github.com/JonathanSalwan/Triton.git'])
    os.chdir('Triton')
    os.mkdir('build')
    os.chdir('build')
    check_call(['cmake', '..', '-DPINTOOL=on']
               + (['-DKERNEL4=on'] if platform.release().startswith('4') else ['-DKERNEL4=off']))
    check_call(['make'])

    if os.path.exists('/usr/local/bin/triton'):
        os.unlink('/usr/local/bin/triton')
    if os.path.exists('/usr/local/bin/tritonAttach'):
        os.unlink('/usr/local/bin/tritonAttach')
    os.symlink('/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux/source/tools/Triton/build/triton',
               '/usr/local/bin/triton')
    os.symlink('/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux/source/tools/Triton/build/tritonAttach',
               '/usr/local/bin/tritonAttach')


if __name__ == '__main__':
    main()
