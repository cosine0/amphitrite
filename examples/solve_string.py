from amphitrite import *


c = Concrete('./rot7')
c.run_to(0x0804857b)
c.process.stdin.write('aaaabaaacaaadaaaeaaafaaagaaahaaaiaaajaaakaaal\n')
string_variable = c.set_string_as_variable(esp + 0x1c)

c.run_to(0x080485cf)
solution = c.solve_equality(esp + 0x1c, 'wulbtvuvbsayhtpjyvzjvwpjzpspjvcvsjhuvjvupvzpz')
string_instance = solution[string_variable]

print 'one solution: {!r}'.format(string_instance)
