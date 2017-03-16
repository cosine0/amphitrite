from amphitrite import *


c = Concrete('./ascii_sum')
c.run_to(0x000000000040067b)
c.process.stdin.write('12345\n')
c.process.stdin.flush()
c.set_string_as_variable(rbp-0x30)
raw_input()

for _ in xrange(5):
    # movzx
    c.run_to(0x0000000000400689)
    print '[#] brefore ' + c.eval(lambda inst: inst.getDisassembly())
    print c.eval(lambda inst: inst.getSecondOperand().getAddress())
    print c.eval(lambda inst: inst.getSecondOperand().getConcreteValue())
    # movsx
    c.run_to(0x000000000040068e)
    print c.eval(lambda inst: inst.getDisassembly())
    print c.get_register_se(al, False, False)
    print c.get_register_se(al)
    c.run_to(0x0000000000400691)
    print c.eval(lambda inst: inst.getDisassembly())
    print c.get_register_se(rax, False, False)
    print c.get_register_se(rax)
    # c.set_register_as_variable(rax)
    raw_input()

c.run_to(0x00000000004006be)
print c.get_register_se(rsi)
