import atexit
import os
import platform
import shutil
import tempfile
from distutils.dir_util import copy_tree
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

    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    temp_dir = tempfile.mkdtemp()
    atexit.register(lambda: os.path.exists(temp_dir) and shutil.rmtree(temp_dir))
    copy_tree(os.curdir, temp_dir)
    os.chdir(temp_dir)
    if dist[1] == '14.04':
        required_packages = ['git', 'build-essential', 'cmake', 'libpython2.7-dev', 'libboost1.55-all-dev']
        check_call(['apt-get', 'install', '-y'] + required_packages)

    elif dist[1] >= '16.04':
        required_packages = ['git', 'build-essential', 'cmake', 'libpython2.7-dev', 'libboost-all-dev']
        check_call(['apt-get', 'install', '-y'] + required_packages)
    else:
        raise RuntimeError('Only Ubuntu 14.04, 16.04 and higher are supported.')

    try:
        check_capstone = check_output(['gcc', '-lcapstone'], stderr=STDOUT)
    except CalledProcessError as e:
        check_capstone = e.output

    install_capstone = False
    if 'cannot find -lcapstone' in check_capstone:
        install_capstone = True
    else:
        try:
            with open(os.devnull, 'w') as devnull:
                check_call(['gcc', '-o', 'check_capstone_version', 'check_capstone_version.c'], stderr=devnull)
        except CalledProcessError:
            install_capstone = True
        else:
            try:
                capstone_version = int(check_output(['./check_capstone_version'], stderr=STDOUT), 10)
            except (CalledProcessError, OSError, ValueError, TypeError):
                install_capstone = True
            else:
                if capstone_version > 3:
                    install_capstone = True
            os.unlink('check_capstone_version')

    try:
        check_z3 = check_output(['gcc', '-lz3'], stderr=STDOUT)
    except CalledProcessError as e:
        check_z3 = e.output

    install_z3 = False
    if 'cannot find -lz3' in check_z3:
        install_z3 = True
    else:
        try:
            z3_version = check_output(['z3', '-version'], stderr=STDOUT)
        except CalledProcessError:
            install_z3 = True
        else:
            if z3_version < 'Z3 version 4.4.1':
                install_z3 = True

    if install_z3:
        check_call(['git', 'clone', 'https://github.com/Z3Prover/z3.git'])
        os.chdir('z3')
        check_call(['python', 'scripts/mk_make.py'])
        os.chdir('build')
        check_call(['make'])
        check_call(['make', 'install'])
        os.chdir('../..')
        shutil.rmtree('z3')

    os.chdir(temp_dir)
    check_call(['wget', '-U', 'Mozilla/5.0',
                'http://software.intel.com/sites/landingpage/pintool/downloads/pin-2.14-71313-gcc.4.4.7-linux.tar.gz'])

    if os.path.exists('/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux'):
        if os.path.isdir('/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux'):
            shutil.rmtree('/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux')
        else:
            os.unlink('pin-2.14-71313-gcc.4.4.7-linux')
    check_call(['tar', '-xvf', 'pin-2.14-71313-gcc.4.4.7-linux.tar.gz', '-C', '/usr/local/bin'])
    os.chmod('/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux/pin.sh', 0o755)
    os.chmod('/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux/source/tools/Utils/testGccVersion', 0o755)
    os.chmod('/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux/ia32/', 0o2751)
    os.chmod('/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux/intel64/', 0o2751)

    os.chdir('/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux/source/tools')
    check_call(['git', 'clone', 'https://github.com/JonathanSalwan/Triton.git'])
    os.chdir('Triton')
    check_call(['git', 'reset', '--hard', 'v0.5'])
    check_call(['git', 'apply', os.path.join(temp_dir, 'patch_triton_issue_679.diff')])
    check_call(['git', 'apply', os.path.join(temp_dir, 'patch_z3_451.diff')])
    os.mkdir('build')
    os.chdir('build')

    if install_capstone:
        check_call(['git', 'clone', 'https://github.com/aquynh/capstone.git', 'capstone_git'])
        os.chdir('capstone_git')
        check_call(['git', 'reset', '--hard', '3.0.5'])
        check_call(['./make.sh'])
        capstone_dir = '/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux/source/tools/Triton/capstone'
        check_call(['make', 'install'], env={'PREFIX': capstone_dir})
        os.chdir('..')
        shutil.rmtree('capstone_git')
        check_call(['cmake', '..', '-DPINTOOL=on', '-DCAPSTONE_INCLUDE_DIRS=' + capstone_dir + '/include',
                    '-DCAPSTONE_LIBRARIES=' + capstone_dir + '/lib/libcapstone.so']
                   + (['-DKERNEL4=on'] if platform.release().startswith('4') else ['-DKERNEL4=off']))
    else:
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
