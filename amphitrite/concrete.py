import os
import sys
import psutil
import sympy
import subprocess
import marshal

from multiprocessing.connection import Listener
from elftools.elf.elffile import ELFFile

rax, eax, al, rbp, rsi, esi, rdi, rip = sympy.symbols('rax eax al rbp rsi esi rdi rip')
started_child = []

original_excepthook = sys.excepthook


def terminate_child(exc_type, exc_value, exc_traceback):
    global started_child, original_excepthook
    for child in started_child:
        print '[*] Terminating'
        ps_root = psutil.Process(child.pid)
        for ps in ps_root.children(recursive=True):
            ps.kill()
        ps_root.kill()
    original_excepthook(exc_type, exc_value, exc_traceback)


sys.excepthook = terminate_child


class Solution(object):
    def __init__(self, parent, model):
        self.parent = parent
        self.model = model

    def __getitem__(self, item):
        if isinstance(item, (tuple, list)):
            return self.get_string(item)
        if isinstance(item, (long, int)):
            return self.get_value

    def get_string(self, variable_ids):
        solution_bytes = bytearray()
        for var_id, original in zip(variable_ids, self.parent._string_variables[variable_ids]):
            try:
                solution_bytes.append(self.model[var_id])
            except KeyError:
                solution_bytes.append(original)
        return str(solution_bytes)

    def get_value(self, variable_id):
        try:
            return self.model[variable_id]
        except KeyError:
            return None


# decorator
def method_at_break(method):
    def after_break(self, *args, **kwargs):
        if self.running:
            try:
                break_message = self.connection.recv()
            except IOError as e:
                if e.errno == 104:  # connection reset by peer
                    raise EOFError
            if break_message == 'at break.':
                print '[*] Triton is at break'
                self.running = False
                return method(self, *args, **kwargs)
            else:
                raise RuntimeError('unexpected response from triton {}'.format(break_message))
        else:
            return method(self, *args, **kwargs)

    return after_break


class Concrete(object):
    def __init__(self, arguments, start_address=None, skip_library=True):
        self.closed = True
        self.running = False
        self._string_variables = dict()
        self._variables = []
        if not isinstance(arguments, (list, tuple)):
            arguments = [arguments]
        self.args = arguments
        self.path = self.args[0]
        self.binary = os.path.split(self.path)[-1]
        with open(self.path, 'rb') as f:
            self.arch = ELFFile(f).get_machine_arch()
        if self.arch not in ('x86', 'x64'):
            raise RuntimeError('Architecture is not x86 or x64.')

        print '[*] Starting Triton process'
        listener = Listener(('localhost', 31313))
        child = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'child.py')
        self.process = subprocess.Popen(['triton', child] + arguments,
                                        stdin=subprocess.PIPE,
                                        )

        global started_child
        started_child.append(self.process)
        self.connection = listener.accept()

        self.connection.send({'path': self.path,
                              'binary': self.binary,
                              'skip_library': skip_library,
                              'start_address': start_address,
                              'arch': self.arch})

        if self.connection.recv() == 'triton ready.':
            print '\r[+] Starting Triton process: Done'
            self.closed = True
        else:
            self.connection.close()
            raise RuntimeError('Failed to start Triton')

    def __del__(self):
        self.close()

    @method_at_break
    def run(self):
        exit_value = self.process.poll()
        if exit_value is not None:
            raise EOFError('[*] Triton has been terminated with exit code {}.'.format(exit_value))

        self.running = True
        self.connection.send({'action': 'run'})
        print '[>] Triton is running'

    @method_at_break
    def run_to(self, address, include_this_address=False, commit_this_address_to_hw=None):
        exit_value = self.process.poll()
        if exit_value is not None:
            raise EOFError('[*] Triton has been terminated with exit code {}.'.format(exit_value))

        self.running = True
        self.connection.send({'action': 'run_to', 'address': address, 'inclusive': include_this_address,'commit': commit_this_address_to_hw})
        print '[>] Triton is running'

    @method_at_break
    def run_to_condition(self, function, include_this_address=False):
        exit_value = self.process.poll()
        if exit_value is not None:
            raise EOFError('[*] Triton has been terminated with exit code {}.'.format(exit_value))

        function = marshal.dumps(function.func_code)
        self.running = True
        self.connection.send({'action': 'run_to_condition', 'function': function, 'inclusive': include_this_address})
        print '[>] Triton is running'

    @method_at_break
    def set_register_as_variable(self, register):
        exit_value = self.process.poll()
        if exit_value is not None:
            raise EOFError('[*] Triton has been terminated with exit code {}.'.format(exit_value))

        self.connection.send({'action': 'set_register_as_variable', 'register': register})
        result = self.connection.recv()
        self._variables.append(result['variable_id'])

    @method_at_break
    def set_string_as_variable(self, expression):
        exit_value = self.process.poll()
        if exit_value is not None:
            raise EOFError('[*] Triton has been terminated with exit code {}.'.format(exit_value))

        self.connection.send({'action': 'set_string_as_variable', 'string_address': expression})
        result = self.connection.recv()
        variable_ids = tuple(result['variable_ids'])
        self._string_variables[variable_ids] = result['current_value']
        print '[*] String at {:#x} {!r} is set as variable'.format(result['start_address'], result['current_value'])
        return variable_ids

    @method_at_break
    def get_register_se(self, register, dereference=True, simplify=True):
        exit_value = self.process.poll()
        if exit_value is not None:
            raise EOFError('[*] Triton has been terminated with exit code {}.'.format(exit_value))

        self.connection.send({'action': 'get_register_se', 'register': register, 'dereference': dereference,
                              'simplify': simplify})
        result = self.connection.recv()
        return result['se']

    @method_at_break
    def get_value(self, expression):
        exit_value = self.process.poll()
        if exit_value is not None:
            raise EOFError('[*] Triton has been terminated.')

        self.connection.send({'action': 'get_value', 'expression': expression})
        try:
            result = self.connection.recv()
        except IOError as e:
            if e.errno == 104:
                raise EOFError
        else:
            return result['value']

    @method_at_break
    def eval(self, function):
        exit_value = self.process.poll()
        if exit_value is not None:
            raise EOFError('[*] Triton has been terminated with exit code {}.'.format(exit_value))

        function = marshal.dumps(function.func_code)
        self.connection.send({'action': 'eval', 'function': function})
        result = self.connection.recv()
        return result['return_value']

    @method_at_break
    def solve_equality(self, register, value):
        self.connection.send({'action': 'solve_equality', 'register': register, 'value': value})
        result = self.connection.recv()
        if not result['sat']:
            raise RuntimeError('unsat')
        return Solution(self, result['model'])

    def close(self):
        if not self.closed:
            try:
                self.connection.send({'action': 'exit'})
                self.connection.close()
                self.process.kill()
                started_child.remove(self.process)
            except:
                pass
            self.closed = True
            print '[*] Stopped Triton'
