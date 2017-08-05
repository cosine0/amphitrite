# coding=utf-8
import itertools
import types

import sympy
import marshal

from multiprocessing.connection import Client

from pintool import *
from triton import *

started = False

breaks_before_symproc = set()
breaks_before = set()
breaks_after = set()

step_before_symproc = False
step_before = False
step_after = False

conditional_break_before_symproc = None
conditional_break_before = None
conditional_break_after = None


def resolve_expression(expression):
    if not isinstance(expression, sympy.Expr):
        return expression
    substitution = []
    for sym in expression.free_symbols:
        register = getattr(REG, sym.name.upper())
        value = getCurrentRegisterValue(register)
        substitution.append((sym, value))
    return int(expression.subs(substitution))


def convert_string_to_variable(address, length=None):
    variables = []
    current_value = []
    if length is None:
        for p_byte in itertools.count(address):
            c = getCurrentMemoryValue(p_byte)
            if c == 0:
                break
            current_value.append(chr(c))
            setConcreteMemoryValue(p_byte, c)
            var_id = convertMemoryToSymbolicVariable(MemoryAccess(p_byte, 1)).getId()
            variables.append(var_id)
    else:
        for p_byte in xrange(address, address + length):
            c = getCurrentMemoryValue(p_byte)
            current_value.append(chr(c))
            setConcreteMemoryValue(p_byte, c)
            var_id = convertMemoryToSymbolicVariable(MemoryAccess(p_byte, 1)).getId()
            variables.append(var_id)
    return variables, ''.join(current_value)


def process_commands(instruction=None):
    global started, breaks_before_symproc, breaks_before, breaks_after, step_before_symproc, step_before, step_after,\
        conditional_break_before_symproc, conditional_break_before, conditional_break_after
    while True:
        try:
            command = client.recv()
        except EOFError:
            client.close()
            exit()

        if command['action'] == 'run':
            if not started:
                started = True
                # Run the instrumentation - Never returns
                runProgram()
            else:
                break
        elif command['action'] == 'run_to':
            if command['inclusive']:
                if command['commit']:
                    breaks_after.add(command['address'])
                else:
                    breaks_before.add(command['address'])
            else:
                breaks_before_symproc.add(command['address'])
            if not started:
                started = True
                # Run the instrumentation - Never returns
                runProgram()
            else:
                break
        elif command['action'] == 'run_to_next_instruction':
            if command['inclusive']:
                if command['commit']:
                    step_after = True
                else:
                    step_before = True
            else:
                step_before_symproc = True
            if not started:
                started = True
                # Run the instrumentation - Never returns
                runProgram()
            else:
                break
        elif command['action'] == 'run_to_condition':
            serialized_function = command['function']
            code = marshal.loads(serialized_function)
            condition = types.FunctionType(code, globals(), "condition")
            if command['inclusive']:
                if command['commit']:
                    conditional_break_after = condition
                else:
                    conditional_break_before_symproc = condition
            else:
                conditional_break_before_symproc = condition
            if not started:
                started = True
                # Run the instrumentation - Never returns
                runProgram()
            else:
                break
        elif command['action'] == 'set_register_as_variable':
            register = getattr(REG, command['register'].name.upper())
            variable = convertRegisterToSymbolicVariable(register)
            client.send({'variable_id': variable.getId(), 'bit_size': variable.getBitSize()})
        elif command['action'] == 'set_string_as_variable':
            start_address = resolve_expression(command['string_address'])
            variable_ids, current_value = convert_string_to_variable(start_address, command['length'])
            client.send({'start_address': start_address, 'variable_ids': variable_ids, 'current_value': current_value})
        elif command['action'] == 'get_register_se':
            register = getattr(REG, command['register'].name.upper())
            sym_ast = buildSymbolicRegister(register)
            if command['dereference']:
                sym_ast = getFullAst(sym_ast)
            if command['simplify']:
                sym_ast = simplify(sym_ast)
            ast_string = '{!s} (concrete value: {})'.format(sym_ast, sym_ast.evaluate())
            client.send({'se': ast_string})
        elif command['action'] == 'get_value':
            value = resolve_expression(command['expression'])
            client.send({'value': value})
        elif command['action'] == 'eval':
            serialized_function = command['function']
            code = marshal.loads(serialized_function)
            func = types.FunctionType(code, globals(), "func")
            return_value = func(instruction)
            client.send({'return_value': return_value})
        elif command['action'] == 'solve_equality':
            register = getattr(REG, command['register'].name.upper())
            register_ast = buildSymbolicRegister(register)
            value = command['value']
            if not register_ast.isSymbolized():
                if register_ast.evaluate() == value:
                    client.send({'sat': True, 'model': {}})
                else:
                    client.send({'sat': False})
            else:
                size = register_ast.getBitvectorSize()
                setAstRepresentationMode(AST_REPRESENTATION.SMT)
                equation_ast = ast.equal(register_ast, ast.bv(value, size))
                if command['include_path_constraint']:
                    equation_ast = ast.land(equation_ast, getPathConstraintsAst())
                model = getModel(ast.assert_(equation_ast))
                if model:
                    picklable_model = dict()
                    for variable_id, model_object in model.iteritems():
                        picklable_model[variable_id] = model_object.getValue()
                    client.send({'sat': True, 'model': picklable_model})
                else:
                    client.send({'sat': False})
        elif command['action'] == 'exit':
            client.close()
            exit()


def before_symproc(instruction):
    global breaks_before_symproc, step_before_symproc, conditional_break_before_symproc
    address = instruction.getAddress()
    if step_before_symproc:
        step_before_symproc = False
        client.send('at break.')
        process_commands(instruction)
    if address in breaks_before_symproc:
        breaks_before_symproc.remove(address)
        client.send('at break.')
        process_commands(instruction)
    elif conditional_break_before_symproc is not None:
        if conditional_break_before_symproc(instruction):
            conditional_break_before_symproc = None
            client.send('at break.')
            process_commands(instruction)


def before(instruction):
    global breaks_before, step_before, conditional_break_before
    address = instruction.getAddress()
    if step_before:
        step_before = False
        client.send('at break.')
        process_commands(instruction)
    if address in breaks_before:
        breaks_before.remove(address)
        client.send('at break.')
        process_commands(instruction)
    elif conditional_break_before is not None:
        if conditional_break_before(instruction):
            conditional_break_before = None
            client.send('at break.')
            process_commands(instruction)


def after(instruction):
    global breaks_after, step_after, conditional_break_after
    address = instruction.getAddress()
    if step_after:
        step_after = False
        client.send('at break.')
        process_commands(instruction)
    if address in breaks_after:
        breaks_after.remove(address)
        client.send('at break.')
        process_commands(instruction)
    elif conditional_break_after is not None:
        if conditional_break_after(instruction):
            conditional_break_after = None
            client.send('at break.')
            process_commands(instruction)


def need_memory_value(memory_access):
    setConcreteMemoryValue(memory_access, getCurrentMemoryValue(memory_access))


if __name__ == '__main__':
    # Set architecture
    setArchitecture(ARCH.X86_64)
    setAstRepresentationMode(AST_REPRESENTATION.PYTHON)

    # quick fix of triton bug
    addCallback(need_memory_value, CALLBACK.GET_CONCRETE_MEMORY_VALUE)

    # Add a callback.
    insertCall(before_symproc, INSERT_POINT.BEFORE_SYMPROC)
    insertCall(before, INSERT_POINT.BEFORE)
    insertCall(after, INSERT_POINT.AFTER)

    enableMode(MODE.ONLY_ON_SYMBOLIZED, True)
    enableMode(MODE.AST_DICTIONARIES, True)

    client = Client(('0', 31313))
    initial_info = client.recv()
    if initial_info['arch'] == 'x86':
        setArchitecture(ARCH.X86)
    elif initial_info['arch'] == 'x64':
        setArchitecture(ARCH.X86_64)
    else:
        raise RuntimeError('Architecture is not x86 or x64.')

    if initial_info['skip_library']:
        setupImageWhitelist([initial_info['binary']])
    if initial_info['start_address'] is None:
        # Start the symbolic analysis from the entry point
        startAnalysisFromEntry()
    else:
        startAnalysisFromAddress(initial_info['start_address'])

    client.send('triton ready.')

    process_commands()
