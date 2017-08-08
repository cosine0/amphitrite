from amphitrite import *


c = Concrete('./ascii_sum')
c.run_to(0x000000000040067b)
c.process.stdin.write('12345\n')
c.process.stdin.flush()
string_variable = c.set_string_as_variable(rbp-0x30)

c.run_to(0x00000000004006be)
solution = c.solve_equality(esi, int(sys.argv[1], 0))
string_instance = solution[string_variable]

print 'one solution: {!r}'.format(string_instance)
