import os
import sys
import psutil
import sympy
import subprocess
import marshal

from multiprocessing.connection import Listener
from elftools.elf.elffile import ELFFile

# symbolic registers
zmm12, zmm13, zmm10, zmm11, zmm16, zmm17, zmm14, zmm15, bl, zmm18, zmm19, bh, bp, bx, sil, esp, r8b, r8d, rip, spl, rl, rh, mm7, rax, gs, zmm29, zmm28, zmm27, zmm26, zmm25, zmm24, zmm23, zmm22, zmm21, zmm20, r9, om, r14d, r14b, of, oe, r14w, xmm3, xmm0, xmm1, xmm6, xmm7, xmm4, xmm5, xmm8, r11w, sp, rdx, zmm30, zmm31, cr14, cr15, cr10, cr11, cr12, cr13, xmm2, r14, r15, r12, r13, r10, r11, r11b, rbx, r11d, pf, pe, pm, zm, ze, zf, es, cr2, cr3, cr0, cr1, cr6, cr7, cr4, cr5, ymm1, ymm0, cr8, ymm2, mxcsr, ymm4, ymm7, ymm6, um, zmm9, eflags, ue, zmm1, zmm2, zmm3, zmm4, zmm5, zmm6, zmm7, ip, fs, mm5, mm4, fz, mm6, mm1, mm0, mm3, mm2, xmm10, xmm11, xmm12, xmm9, xmm14, xmm15, r13w, r13d, r13b, ecx, ymm9, ch, ymm8, cf, ah, cx, cs, rdi, ss, r10b, edi, r10d, si, r8w, edx, r10w, sf, dil, eip, dl, cr9, rcx, dh, di, df, r9b, de, bpl, ymm12, dx, ymm3, ds, xmm13, r15d, zmm8, r15b, cl, eax, r15w, tf, ebp, dm, daz, ymm14, af, r8, r9d, al, rbp, zmm0, im, ymm5, r9w, ax, ie, esi, IF, rsi, r12w, ebx, ymm11, ymm10, ymm13, r12b, ymm15, r12d, rsp = sympy.symbols(
    'zmm12 zmm13 zmm10 zmm11 zmm16 zmm17 zmm14 zmm15 bl zmm18 zmm19 bh bp bx sil esp r8b r8d rip spl rl rh mm7 rax gs '
    'zmm29 zmm28 zmm27 zmm26 zmm25 zmm24 zmm23 zmm22 zmm21 zmm20 r9 om r14d r14b of oe r14w xmm3 xmm0 xmm1 xmm6 xmm7 '
    'xmm4 xmm5 xmm8 r11w sp rdx zmm30 zmm31 cr14 cr15 cr10 cr11 cr12 cr13 xmm2 r14 r15 r12 r13 r10 r11 r11b rbx r11d '
    'pf pe pm zm ze zf es cr2 cr3 cr0 cr1 cr6 cr7 cr4 cr5 ymm1 ymm0 cr8 ymm2 mxcsr ymm4 ymm7 ymm6 um zmm9 eflags ue '
    'zmm1 zmm2 zmm3 zmm4 zmm5 zmm6 zmm7 ip fs mm5 mm4 fz mm6 mm1 mm0 mm3 mm2 xmm10 xmm11 xmm12 xmm9 xmm14 xmm15 r13w '
    'r13d r13b ecx ymm9 ch ymm8 cf ah cx cs rdi ss r10b edi r10d si r8w edx r10w sf dil eip dl cr9 rcx dh di df r9b '
    'de bpl ymm12 dx ymm3 ds xmm13 r15d zmm8 r15b cl eax r15w tf ebp dm daz ymm14 af r8 r9d al rbp zmm0 im ymm5 r9w '
    'ax ie esi IF rsi r12w ebx ymm11 ymm10 ymm13 r12b ymm15 r12d rsp')
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
        exit_value = self.process.poll()
        if exit_value is not None:
            raise EOFError('[*] Triton has been terminated with exit code {}.'.format(exit_value))
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
        self.connection.send({'action': 'run_to', 'address': address, 'inclusive': include_this_address,
                              'commit': commit_this_address_to_hw})
        print '[>] Triton is running'

    @method_at_break
    def run_to_next_instruction(self, include_next_instruction=False, commit_next_instruction_to_hw=None):
        exit_value = self.process.poll()
        if exit_value is not None:
            raise EOFError('[*] Triton has been terminated with exit code {}.'.format(exit_value))

        self.running = True
        self.connection.send({'action': 'run_to_next_instruction',
                              'inclusive': include_next_instruction,
                              'commit': commit_next_instruction_to_hw})
        print '[>] Triton is running'

    @method_at_break
    def run_to_condition(self, function, include_this_address=False, commit_next_instruction_to_hw=None):
        exit_value = self.process.poll()
        if exit_value is not None:
            raise EOFError('[*] Triton has been terminated with exit code {}.'.format(exit_value))

        function = marshal.dumps(function.func_code)
        self.running = True
        self.connection.send({'action': 'run_to_condition', 'function': function, 'inclusive': include_this_address,
                              'commit': commit_next_instruction_to_hw})
        print '[>] Triton is running'

    @method_at_break
    def set_register_as_variable(self, register):
        self.connection.send({'action': 'set_register_as_variable', 'register': register})
        result = self.connection.recv()
        self._variables.append(result['variable_id'])

    @method_at_break
    def set_string_as_variable(self, expression, length=None):
        self.connection.send({'action': 'set_string_as_variable', 'string_address': expression, 'length': length})
        result = self.connection.recv()
        variable_ids = tuple(result['variable_ids'])
        self._string_variables[variable_ids] = result['current_value']
        print '[*] String at {:#x} {!r} is set as variable'.format(result['start_address'], result['current_value'])
        return variable_ids

    def set_bytes_as_variable(self, expression, length):
        self.set_string_as_variable(expression, length)

    @method_at_break
    def get_register_se(self, register, dereference=True, simplify=True):
        self.connection.send({'action': 'get_register_se', 'register': register, 'dereference': dereference,
                              'simplify': simplify})
        result = self.connection.recv()
        return result['se']

    @method_at_break
    def get_value(self, expression):
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
        function = marshal.dumps(function.func_code)
        self.connection.send({'action': 'eval', 'function': function})
        result = self.connection.recv()
        return result['return_value']

    @method_at_break
    def solve_equality(self, register_or_address, value, include_path_constraint=True):
        self.connection.send({'action': 'solve_equality',
                              'register_or_address': register_or_address,
                              'value': value,
                              'include_path_constraint': include_path_constraint})
        result = self.connection.recv()
        print '[>] Solving'
        if not result['sat']:
            raise RuntimeError('unsat')
        print '[+] Solving: Done'
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
