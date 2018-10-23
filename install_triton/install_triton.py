import atexit
import os
import platform
import shutil
import tempfile
from distutils.dir_util import copy_tree
from distutils.version import LooseVersion
from subprocess import check_call, check_output, STDOUT, CalledProcessError


def main():
    if platform.system() != 'Linux':
        raise RuntimeError('Only support Linux.')

    dist = platform.linux_distribution()
    if dist[0] != 'Ubuntu':
        raise RuntimeError('Only support Ubuntu.')

    if platform.machine() == 'i686':
        if dist[1] != '14.04' or platform.release() >= '4':
            raise RuntimeError('In 32bit version, Only support Ubuntu 14.04 with kernel version less than 4 '
                               '(Hint: Install Ubuntu 32bit 14.04.0-14.04.3')
    elif platform.machine() == 'x86_64':
        if LooseVersion(dist[1]) < LooseVersion('14.04'):
            raise RuntimeError('Only support Ubuntu 14.04 or higher.')
    else:
        raise RuntimeError('Only support x64 and x86.')

    if os.getuid() != 0:
        raise RuntimeError('Super user is required.')

    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    temp_dir = tempfile.mkdtemp()
    atexit.register(lambda: os.path.exists(temp_dir) and shutil.rmtree(temp_dir))
    copy_tree(os.curdir, temp_dir)
    os.chdir(temp_dir)
    if dist[1] == '14.04':
        required_packages = ['git', 'build-essential', 'cmake', 'libpython2.7-dev', 'libboost1.55-all-dev', 'unzip']
        check_call(['apt-get', 'install', '-y'] + required_packages)

    elif dist[1] >= '16.04':
        required_packages = ['git', 'build-essential', 'cmake', 'libpython2.7-dev', 'libboost-all-dev', 'unzip']
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
            if z3_version < 'Z3 version 4.8.1':
                install_z3 = True

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

    cmake_args = ['cmake', '..', '-DPINTOOL=on',
                  '-DKERNEL4=on' if platform.release().startswith('4') else '-DKERNEL4=off']
    if install_z3:
        if dist == '14.04':
            if platform.machine() == 'i686':
                z3_file = 'z3-4.8.1.b301a59899ff-x86-ubuntu-14.04'
            else:
                z3_file = 'z3-4.8.1.016872a5e0f6-x64-ubuntu-14.04'
        else:
            z3_file = 'z3-4.8.1.016872a5e0f6-x64-ubuntu-16.04'
        z3_url = 'https://github.com/Z3Prover/z3/releases/download/z3-4.8.1/{}.zip'.format(z3_file)
        check_call(['wget', '-U', 'Mozilla/5.0', '-O', 'z3.zip', z3_url])
        check_call(['unzip', 'z3.zip'])
        os.unlink('z3.zip')
        shutil.move(z3_file, 'z3')

        z3_dir = '/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux/source/tools/Triton/z3'
        cmake_args.append('-DZ3_INCLUDE_DIRS=' + z3_dir + '/include')
        cmake_args.append('-DZ3_LIBRARIES=' + z3_dir + '/bin/libz3.so')

    if install_capstone:
        check_call(['git', 'clone', 'https://github.com/aquynh/capstone.git', 'capstone_git'])
        os.chdir('capstone_git')
        check_call(['git', 'reset', '--hard', '3.0.5'])
        check_call(['./make.sh'])

        capstone_dir = '/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux/source/tools/Triton/capstone'
        check_call(['make', 'install'], env={'PREFIX': capstone_dir})
        os.chdir('..')
        shutil.rmtree('capstone_git')

        cmake_args.append('-DCAPSTONE_INCLUDE_DIRS=' + capstone_dir + '/include')
        cmake_args.append('-DCAPSTONE_LIBRARIES=' + capstone_dir + '/lib/libcapstone.so')

    os.mkdir('build')
    os.chdir('build')
    check_call(cmake_args)
    check_call(['make'])

    check_call(['patch', '/usr/local/bin/pin-2.14-71313-gcc.4.4.7-linux/source/tools/Triton/build/triton', '-i',
                os.path.join(temp_dir, 'patch_triton_executable.diff')])

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
