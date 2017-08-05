from amphitrite import *


c = Concrete('./ascii_sum')
c.run_to(0x000000000040067b)
c.process.stdin.write('12345\n')
c.process.stdin.flush()
c.set_string_as_variable(rbp-0x30)

c.run_to(0x00000000004006be)
print c.get_register_se(rsi, dereference=False)
