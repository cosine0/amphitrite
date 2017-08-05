from amphitrite import *


def condition(instruction):
    if 'xor' in instruction.getDisassembly().lower():
        if instruction.getFirstOperand().getName() == REG.RAX.getName():
            return True

c = Concrete('./validation', 0x40065a)
c.process.stdin.write('asdf\n')
c.process.stdin.write('123\n')
key = ''
while True:
    try:
        c.run_to_condition(condition, True)
        value = c.get_value(al)
        key += chr(value)
    except EOFError:
        break
print repr(key)
